// main.go with file cleanup implementation and worker pool
package main

import (
	"context"
	"fmt"
	"net/http"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"

	"github.com/firechair/odds-receiver/internal/api"
	"github.com/firechair/odds-receiver/internal/config"
	"github.com/firechair/odds-receiver/internal/filemanager"
	"github.com/firechair/odds-receiver/internal/logging"
	"github.com/firechair/odds-receiver/internal/metrics"
	"github.com/firechair/odds-receiver/internal/processor"
	"github.com/firechair/odds-receiver/internal/queue"
	"github.com/firechair/odds-receiver/internal/storage"
)

func main() {
	// Initialize logger
	logger := logging.NewStandardLogger()
	logger.Info("Starting odds receiver service...")

	// Load configuration
	cfg, err := config.Load()
	if err != nil {
		logger.Error("Failed to load configuration: %v", err)
		os.Exit(1)
	}
	logger.Info("Configuration loaded successfully")

	// Log the filtering configuration
	logger.Info("Filtering enabled for %d bookmakers: %v", len(cfg.TargetBookmakerIDs), cfg.TargetBookmakerIDs)

	// Initialize metrics
	metricsCollector := metrics.NewMetrics(logger)

	// Initialize file manager
	fileManager, err := filemanager.NewFileManager(cfg.FilesDir, logger)
	if err != nil {
		logger.Error("Failed to initialize file manager: %v", err)
		os.Exit(1)
	}
	logger.Info("File manager initialized successfully")

	// Initialize DynamoDB storage
	store, err := storage.NewDynamoDB(cfg.DynamoDBRegion, cfg.DynamoDBTable, logger)
	if err != nil {
		logger.Error("Failed to initialize DynamoDB: %v", err)
		os.Exit(1)
	}
	logger.Info("DynamoDB storage initialized successfully")

	// Initialize outcome store
	outcomeStore, err := storage.NewOutcomeStore(cfg.DataDir, logger)
	if err != nil {
		logger.Error("Failed to initialize outcome store: %v", err)
		os.Exit(1)
	}
	logger.Info("Outcome store initialized successfully with %d outcomes", outcomeStore.GetOutcomeCount())

	// Initialize queue
	oddsQueue, err := queue.NewQueue(cfg.QueueDir, logger)
	if err != nil {
		logger.Error("Failed to initialize queue: %v", err)
		os.Exit(1)
	}
	logger.Info("Queue initialized successfully")

	// Start the queue processor
	oddsQueue.Start(func(op *queue.QueuedOperation) error {
		switch op.Type {
		case queue.StoreOperation:
			return store.StoreOddsUpdate(op.Data)
		default:
			return fmt.Errorf("unknown operation type: %s", op.Type)
		}
	})
	logger.Info("Queue processor started")

	// Create odds processor with filtering options
	oddsProcessor := processor.NewOddsProcessor(
		store,
		logger,
		cfg.TargetBookmakerIDs,
	)
	oddsProcessor.SetQueue(oddsQueue)
	oddsProcessor.SetOutcomeStore(outcomeStore)

	// Create API handlers
	handler := api.NewHandler(store, logger, fileManager)
	handler.SetQueue(oddsQueue)
	// Set the configured processor
	handler.SetProcessor(oddsProcessor)

	// Define a type for file processing jobs
	type fileJob struct {
		path      string
		isGzipped bool
	}

	// Create a worker pool with a limited number of workers
	maxWorkers := 5
	fileQueue := make(chan fileJob, 100)
	var workerWg sync.WaitGroup

	// Start worker pool
	for i := 0; i < maxWorkers; i++ {
		workerWg.Add(1)
		go func() {
			defer workerWg.Done()
			for job := range fileQueue {
				handler.ProcessPendingFile(job.path, job.isGzipped)
			}
		}()
	}
	logger.Info("Started worker pool with %d workers", maxWorkers)

	// Create HTTP server for the API
	server := &http.Server{
		Addr:    ":" + cfg.Port,
		Handler: handler.Routes(),
	}

	// Create HTTP server for metrics
	metricsServer := &http.Server{
		Addr:    ":" + cfg.MetricsPort,
		Handler: metricsCollector,
	}

	// Start the metrics server in a goroutine
	go func() {
		logger.Info("Metrics server starting on port %s", cfg.MetricsPort)
		if err := metricsServer.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			logger.Error("Metrics server failed to start: %v", err)
		}
	}()

	// Start the API server in a goroutine
	go func() {
		logger.Info("API server starting on port %s", cfg.Port)
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			logger.Error("API server failed to start: %v", err)
			os.Exit(1)
		}
	}()

	// Set up a periodic task to process any pending files
	processTicker := time.NewTicker(1 * time.Minute)

	// NEW: Set up a periodic task to clean up old parsed files
	cleanupTicker := time.NewTicker(1 * time.Hour) // Run cleanup every 4 hours

	// Create a channel to signal all goroutines to stop
	stop := make(chan struct{})

	// Process pending files using worker pool
	go func() {
		for {
			select {
			case <-processTicker.C:
				logger.Info("Running scheduled check for pending files")
				pendingFiles, err := fileManager.ListPendingFiles()
				if err != nil {
					logger.Error("Failed to list pending files: %v", err)
					continue
				}

				if len(pendingFiles) > 0 {
					logger.Info("Found %d pending files to process", len(pendingFiles))

					// Update metrics
					metricsCollector.SetCustomMetric("pending_files", len(pendingFiles))

					// Limit the number of files to process at once
					batchSize := 100
					if len(pendingFiles) > batchSize {
						logger.Info("Processing first %d files of %d total", batchSize, len(pendingFiles))
						pendingFiles = pendingFiles[:batchSize]
					}

					// Queue each file for processing using the worker pool
					for _, file := range pendingFiles {
						// Determine if the file is gzipped
						isGzipped := len(file) > 3 && file[len(file)-3:] == ".gz"

						// Add to worker queue instead of processing directly
						select {
						case fileQueue <- fileJob{path: file, isGzipped: isGzipped}:
							// Successfully queued
						default:
							// Queue is full, log warning
							logger.Warn("File processing queue is full, skipping file: %s", file)
						}
					}
				}
			case <-stop:
				return
			}
		}
	}()

	// NEW: Cleanup old parsed filesx
	go func() {
		for {
			select {
			case <-cleanupTicker.C:
				logger.Info("Running scheduled cleanup of old parsed files")

				// Clean up parsed files older than 18 hours
				if err := fileManager.CleanupOldParsedFiles(18 * time.Hour); err != nil {
					logger.Error("Failed to clean up old parsed files: %v", err)
				} else {
					logger.Info("Successfully cleaned up old parsed files")
				}

				// Get statistics after cleanup
				stats, err := fileManager.GetFileStats()
				if err != nil {
					logger.Error("Failed to get file statistics: %v", err)
				} else {
					logger.Info("File statistics after cleanup: %d pending files, %d processed files",
						stats["pending"], stats["processed"])

					// Update metrics
					metricsCollector.SetCustomMetric("pending_files", stats["pending"])
					metricsCollector.SetCustomMetric("processed_files", stats["processed"])
				}
			case <-stop:
				return
			}
		}
	}()

	// Set up graceful shutdown
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit
	logger.Info("Shutting down servers...")

	// Signal all goroutines to stop
	close(stop)

	// Stop the tickers
	processTicker.Stop()
	cleanupTicker.Stop()

	// Close the file queue and wait for workers to finish
	logger.Info("Waiting for worker pool to finish...")
	close(fileQueue)
	workerWg.Wait()

	// Stop the queue
	oddsQueue.Stop()

	// Create a deadline for server shutdown
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	// Shutdown the metrics server
	if err := metricsServer.Shutdown(ctx); err != nil {
		logger.Error("Metrics server forced to shutdown: %v", err)
	}

	// Shutdown the API server
	if err := server.Shutdown(ctx); err != nil {
		logger.Error("API server forced to shutdown: %v", err)
	}

	// Shutdown the storage
	store.Shutdown()

	logger.Info("Servers exited, goodbye!")
}
