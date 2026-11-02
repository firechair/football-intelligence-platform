// internal/api/handlers.go
package api

import (
	"bytes"
	"compress/gzip"
	"encoding/json"
	"fmt"
	"io"
	"io/ioutil"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/firechair/odds-receiver/internal/filemanager"
	"github.com/firechair/odds-receiver/internal/logging"
	"github.com/firechair/odds-receiver/internal/metrics"
	"github.com/firechair/odds-receiver/internal/parser"
	"github.com/firechair/odds-receiver/internal/processor"
	"github.com/firechair/odds-receiver/internal/queue"
	"github.com/firechair/odds-receiver/internal/storage"
	"github.com/gorilla/mux"
)

// Handler contains the HTTP handlers and dependencies
type Handler struct {
	store       storage.Storage
	processor   *processor.OddsProcessor
	logger      logging.Logger
	fileManager *filemanager.FileManager
	queue       *queue.Queue
	metrics     *metrics.Metrics
}

// NewHandler creates a new Handler
func NewHandler(store storage.Storage, logger logging.Logger, fileManager *filemanager.FileManager) *Handler {
	h := &Handler{
		store:       store,
		logger:      logger,
		fileManager: fileManager,
		metrics:     metrics.NewMetrics(logger),
	}

	// The processor will be set separately with SetProcessor

	return h
}

// SetProcessor sets the processor for the handler
func (h *Handler) SetProcessor(p *processor.OddsProcessor) {
	h.processor = p
}

// SetQueue sets the queue for the handler and processor
func (h *Handler) SetQueue(q *queue.Queue) {
	h.queue = q
	if h.processor != nil {
		h.processor.SetQueue(q)
	}
}

// Routes returns the router with all routes configured
func (h *Handler) Routes() http.Handler {
	r := mux.NewRouter()

	// Endpoint for receiving XML files (gzipped)
	r.HandleFunc("/receive_file.php", h.ReceiveFile).Methods("POST")

	// Endpoint for receiving plain XML
	r.HandleFunc("/receive.php", h.ReceivePlain).Methods("POST")

	// Health check
	r.HandleFunc("/health", h.HealthCheck).Methods("GET")

	// Enhanced health check with more details
	r.HandleFunc("/health/details", h.DetailedHealthCheck).Methods("GET")

	// Manual processing endpoints
	r.HandleFunc("/process-pending", h.ProcessPendingFiles).Methods("POST")

	// Metrics endpoint
	r.HandleFunc("/metrics", h.ServeMetrics).Methods("GET")

	// Setup middleware
	return h.logMiddleware(h.metricsMiddleware(r))
}

// ReceiveFile handles receiving gzipped XML files from Enetpulse
func (h *Handler) ReceiveFile(w http.ResponseWriter, r *http.Request) {
	h.logger.Info("Received gzipped XML file")
	h.metrics.RecordFileReceived()

	// Save the file using the file manager
	filePath, err := h.fileManager.SaveFile(r.Body, true)
	if err != nil {
		h.logger.Error("Error saving file: %v", err)
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}

	// IMPORTANT: Return 200 OK immediately as mentioned in the documentation
	// to acknowledge receipt (without parsing)
	w.WriteHeader(http.StatusOK)
	h.logger.Info("Acknowledged receipt of gzipped XML file: %s", filePath)

	// Process the file asynchronously
	go h.processFile(filePath, true)
}

// ReceivePlain handles receiving plain XML from Enetpulse
func (h *Handler) ReceivePlain(w http.ResponseWriter, r *http.Request) {
	h.logger.Info("Received plain XML data")
	h.metrics.RecordFileReceived()

	// Check for multipart form data
	contentType := r.Header.Get("Content-Type")
	h.logger.Debug("Content-Type: %s", contentType)

	var xmlData []byte
	var err error

	if strings.Contains(contentType, "multipart/form-data") {
		h.logger.Info("Detected multipart form data, parsing form")

		// Parse the multipart form
		if err := r.ParseMultipartForm(32 << 20); err != nil { // 32MB max memory
			h.logger.Error("Error parsing multipart form: %v", err)
			http.Error(w, "Bad Request: "+err.Error(), http.StatusBadRequest)
			return
		}

		// Try to get the XML data from the form
		xmlValue := r.FormValue("xml")
		if xmlValue != "" {
			h.logger.Info("Found XML data in form field 'xml'")
			xmlData = []byte(xmlValue)
		} else {
			h.logger.Warn("No 'xml' field found in multipart form")

			// Dump form data for debugging
			h.logger.Debug("Form data keys: %v", r.PostForm)

			// Fall back to reading the body
			bodyBytes, err := ioutil.ReadAll(r.Body)
			if err != nil {
				h.logger.Error("Error reading request body: %v", err)
				http.Error(w, "Internal Server Error", http.StatusInternalServerError)
				return
			}
			xmlData = bodyBytes
		}
	} else {
		// Read the regular body
		bodyBytes, err := ioutil.ReadAll(r.Body)
		if err != nil {
			h.logger.Error("Error reading request body: %v", err)
			http.Error(w, "Internal Server Error", http.StatusInternalServerError)
			return
		}
		xmlData = bodyBytes
	}

	// Save the XML data to a file
	filePath, err := h.fileManager.SaveData(xmlData, false)
	if err != nil {
		h.logger.Error("Error saving file: %v", err)
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}

	// IMPORTANT: Per provider requirements, acknowledge receipt immediately without parsing
	w.WriteHeader(http.StatusOK)
	fmt.Fprintln(w, "XML_RECEIVED_OK") // This matches what the PHP code returns
	h.logger.Info("Acknowledged receipt of XML data: %s", filePath)

	// Process the file asynchronously
	go h.processFile(filePath, false)
}

// extractXMLFromMultipart extracts XML content from multipart form data
func (h *Handler) extractXMLFromMultipart(data []byte) ([]byte, error) {
	// Look for the XML content
	start := bytes.Index(data, []byte("<?xml"))
	if start == -1 {
		return nil, fmt.Errorf("no XML content found in multipart data")
	}

	// Find the next boundary after the XML
	end := bytes.Index(data[start:], []byte("--"))
	if end == -1 {
		// If no boundary found after XML, use the rest of the data
		return data[start:], nil
	}

	return data[start : start+end], nil
}

// isUsefulXML performs a quick check to see if the XML might contain betting offers
func (h *Handler) isUsefulXML(xmlData []byte) bool {
	// Check for key elements that indicate useful data
	return bytes.Contains(xmlData, []byte("<bettingoffer")) ||
		bytes.Contains(xmlData, []byte("<liveodds_bettingoffer")) ||
		bytes.Contains(xmlData, []byte("<outcome")) ||
		bytes.Contains(xmlData, []byte("<liveodds_outcome"))
}

// processFile processes a saved XML file
func (h *Handler) processFile(filePath string, isGzipped bool) {
	// Acquire a lock for this file to prevent concurrent processing
	unlock := h.fileManager.LockFileForProcessing(filePath)
	defer unlock()

	startTime := time.Now()
	h.logger.Info("Processing file: %s", filePath)

	var xmlData []byte
	var err error

	if isGzipped {
		xmlData, err = h.readGzippedFile(filePath)
	} else {
		xmlData, err = ioutil.ReadFile(filePath)
	}

	if err != nil {
		h.logger.Error("Error reading file %s: %v", filePath, err)
		h.metrics.RecordParseFailure()
		return
	}

	// Quick check if the XML might contain useful data before full parsing
	if !h.isUsefulXML(xmlData) {
		h.logger.Info("File %s does not contain betting offers or outcomes, skipping parsing", filePath)

		// Mark as processed to avoid reprocessing
		if err := h.fileManager.MarkFileAsParsed(filePath); err != nil {
			h.logger.Error("Error marking non-useful file as parsed %s: %v", filePath, err)
		} else {
			h.logger.Info("Marked non-useful file as parsed: %s", filePath)
		}
		return
	}

	// Check if this is multipart form data and extract XML if needed
	if bytes.Contains(xmlData, []byte("Content-Disposition: form-data")) {
		h.logger.Info("Detected multipart form data in file %s, extracting XML content", filePath)
		extractedXML, err := h.extractXMLFromMultipart(xmlData)
		if err != nil {
			h.logger.Error("Error extracting XML from multipart data in %s: %v", filePath, err)
			h.metrics.RecordParseFailure()
			return
		}
		xmlData = extractedXML
	}

	// Use the improved parser that can handle different XML formats and validates data
	data, err := parser.ParseWithLogger(xmlData, h.logger)
	if err != nil {
		h.logger.Error("Error parsing XML from %s: %v", filePath, err)
		h.metrics.RecordParseFailure()

		// Still mark as processed to avoid reprocessing failed files
		if err := h.fileManager.MarkFileAsParsed(filePath); err != nil {
			h.logger.Error("Error marking failed file as parsed %s: %v", filePath, err)
		} else {
			h.logger.Info("Marked failed file as parsed to avoid reprocessing: %s", filePath)
		}
		return
	}

	// Handle live odds detection
	if data.LiveOdds {
		h.logger.Info("Detected live odds data in file %s", filePath)
		h.metrics.SetCustomMetric("live_odds_detected", true)
		h.metrics.SetCustomMetric("last_live_odds_file", filepath.Base(filePath))
	}

	// Check if we have valid betting offers or outcomes
	if len(data.BettingOffers) == 0 && len(data.Outcomes) == 0 {
		h.logger.Info("No betting offers or outcomes found in file %s - this is likely a property update only", filePath)

		// Still mark as processed to avoid reprocessing
		if err := h.fileManager.MarkFileAsParsed(filePath); err != nil {
			h.logger.Error("Error marking property-only file as parsed %s: %v", filePath, err)
		} else {
			h.logger.Info("Marked property-only file as parsed: %s", filePath)
		}
		return
	}

	// Check if any betting offer is from a target bookmaker
	hasTargetBookmaker := false
	for _, offer := range data.BettingOffers {
		if h.processor.IsTargetBookmaker(offer.OddsProviderFK) {
			hasTargetBookmaker = true
			break
		}
	}

	if !hasTargetBookmaker && len(data.BettingOffers) > 0 {
		h.logger.Info("Skipping file %s - contains no betting offers from target bookmakers", filePath)

		// Mark as processed to avoid reprocessing
		if err := h.fileManager.MarkFileAsParsed(filePath); err != nil {
			h.logger.Error("Error marking non-target file as parsed %s: %v", filePath, err)
		} else {
			h.logger.Info("Marked non-target file as parsed: %s", filePath)
		}
		return
	}

	if err = h.processor.Process(data); err != nil {
		h.logger.Error("Error processing odds data from %s: %v", filePath, err)
		// Don't mark as processed if database upload failed
		return
	}

	// Mark the file as processed
	if err := h.fileManager.MarkFileAsParsed(filePath); err != nil {
		h.logger.Error("Error marking file as parsed %s: %v", filePath, err)
		return
	}

	// Mark as successfully processed (data is in database)
	if err := h.fileManager.MarkFileAsSuccessfullyProcessed(filePath); err != nil {
		h.logger.Warn("Error creating success marker for %s: %v", filePath, err)
	}

	// Record metrics
	h.metrics.RecordFileParsed()
	h.metrics.RecordProcessingTime(time.Since(startTime))

	// Record detailed statistics
	h.metrics.SetCustomMetric("betting_offers_processed", len(data.BettingOffers))
	h.metrics.SetCustomMetric("outcomes_processed", len(data.Outcomes))
	h.metrics.SetCustomMetric("events_processed", len(data.Events))
	h.metrics.SetCustomMetric("odds_providers_processed", len(data.OddsProviders))

	h.logger.Info("Successfully processed file %s in %v - %d betting offers, %d outcomes",
		filePath, time.Since(startTime), len(data.BettingOffers), len(data.Outcomes))
}

// readGzippedFile reads and decompresses a gzipped file
func (h *Handler) readGzippedFile(filePath string) ([]byte, error) {
	// Open the file
	file, err := os.Open(filePath)
	if err != nil {
		return nil, fmt.Errorf("error opening file: %w", err)
	}
	defer file.Close()

	// Decompress gzip
	gzReader, err := gzip.NewReader(file)
	if err != nil {
		return nil, fmt.Errorf("error creating gzip reader: %w", err)
	}
	defer gzReader.Close()

	// Read the decompressed data
	return io.ReadAll(gzReader)
}

// ProcessPendingFiles processes any pending files in the directory
func (h *Handler) ProcessPendingFiles(w http.ResponseWriter, r *http.Request) {
	h.logger.Info("Manual request to process pending files")

	// Get a list of pending files
	pendingFiles, err := h.fileManager.ListPendingFiles()
	if err != nil {
		h.logger.Error("Error listing pending files: %v", err)
		http.Error(w, "Error listing pending files", http.StatusInternalServerError)
		return
	}

	// Process files in batches to avoid overwhelming the system
	maxConcurrent := 100 // Process 100 files at a time
	if len(pendingFiles) > maxConcurrent {
		h.logger.Info("Processing first %d files of %d total", maxConcurrent, len(pendingFiles))
		// Only process a subset of files
		pendingFiles = pendingFiles[:maxConcurrent]
	}

	// Process each file asynchronously
	for _, filePath := range pendingFiles {
		// Determine if the file is gzipped
		isGzipped := filepath.Ext(filePath) == ".gz"
		go h.processFile(filePath, isGzipped)
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"status":  "processing",
		"message": fmt.Sprintf("Processing %d pending files", len(pendingFiles)),
		"files":   pendingFiles,
	})
}

// ProcessPendingFile processes a specific pending file
func (h *Handler) ProcessPendingFile(filePath string, isGzipped bool) {
	h.processFile(filePath, isGzipped)
}

// HealthCheck returns a 200 OK status for health checks
func (h *Handler) HealthCheck(w http.ResponseWriter, r *http.Request) {
	w.WriteHeader(http.StatusOK)
	w.Write([]byte("OK"))
}

// DetailedHealthCheck returns detailed health information
func (h *Handler) DetailedHealthCheck(w http.ResponseWriter, r *http.Request) {
	// Check queue status
	queueDepth := 0
	if h.queue != nil {
		// Get queue depth (files in queue directory)
		files, err := ioutil.ReadDir(h.queue.GetQueueDir())
		if err == nil {
			for _, file := range files {
				if !file.IsDir() {
					queueDepth++
				}
			}
		}
	}

	// Get file statistics
	fileStats, err := h.fileManager.GetFileStats()
	if err != nil {
		fileStats = map[string]int{
			"pending":   0,
			"processed": 0,
		}
	}

	// Get metrics from components
	storageMetrics := h.store.GetMetrics().GetMetrics()
	processorMetrics := h.processor.GetMetrics().GetMetrics()

	// Combine everything into one health report
	health := map[string]interface{}{
		"status":    "OK",
		"timestamp": time.Now().Format(time.RFC3339),
		"queue": map[string]interface{}{
			"depth": queueDepth,
		},
		"files":     fileStats,
		"storage":   storageMetrics,
		"processor": processorMetrics,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(health)
}

// ServeMetrics serves metrics as JSON
func (h *Handler) ServeMetrics(w http.ResponseWriter, r *http.Request) {
	// Combine metrics from all components
	combinedMetrics := map[string]interface{}{
		"api":       h.metrics.GetMetrics(),
		"storage":   h.store.GetMetrics().GetMetrics(),
		"processor": h.processor.GetMetrics().GetMetrics(),
	}

	// Add file statistics
	fileStats, err := h.fileManager.GetFileStats()
	if err == nil {
		combinedMetrics["files"] = fileStats
	}

	// Add queue statistics
	if h.queue != nil {
		queueStats, err := h.queue.GetQueueStats()
		if err == nil {
			combinedMetrics["queue_depth"] = queueStats
		}
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(combinedMetrics)
}

// logMiddleware logs all requests
func (h *Handler) logMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		h.logger.Info("Request: %s %s from %s", r.Method, r.URL.Path, r.RemoteAddr)

		// Create a response writer wrapper to capture the status code
		wrw := &responseWriterWrapper{
			ResponseWriter: w,
			statusCode:     http.StatusOK,
		}

		next.ServeHTTP(wrw, r)

		h.logger.Info("Response: %d %s in %v", wrw.statusCode, http.StatusText(wrw.statusCode), time.Since(start))
	})
}

// metricsMiddleware collects metrics about requests
func (h *Handler) metricsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()

		// Create a response writer wrapper to capture the status code
		wrw := &responseWriterWrapper{
			ResponseWriter: w,
			statusCode:     http.StatusOK,
		}

		next.ServeHTTP(wrw, r)

		// Record request duration
		duration := time.Since(start)

		// Update custom metrics
		h.metrics.SetCustomMetric("http_requests_total", 1)
		h.metrics.SetCustomMetric("http_request_duration_milliseconds", float64(duration.Milliseconds()))

		// Set status code metrics
		statusMetric := fmt.Sprintf("http_response_status_%d", wrw.statusCode)
		h.metrics.SetCustomMetric(statusMetric, 1)
	})
}

// responseWriterWrapper wraps http.ResponseWriter to capture the status code
type responseWriterWrapper struct {
	http.ResponseWriter
	statusCode int
}

// WriteHeader captures the status code
func (w *responseWriterWrapper) WriteHeader(statusCode int) {
	w.statusCode = statusCode
	w.ResponseWriter.WriteHeader(statusCode)
}
