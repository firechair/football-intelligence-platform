// internal/queue/queue.go
package queue

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"time"

	"github.com/firechair/odds-receiver/internal/logging"
	"github.com/firechair/odds-receiver/internal/models"
)

// Operation represents a type of database operation
type OperationType string

const (
	// StoreOperation represents a store operation
	StoreOperation OperationType = "store"
)

// QueuedOperation represents an operation that is queued for later execution
type QueuedOperation struct {
	Type       OperationType      `json:"type"`
	Data       *models.OddsUpdate `json:"data"`
	Timestamp  time.Time          `json:"timestamp"`
	RetryCount int                `json:"retry_count"`
}

// Queue provides persistent queueing for database operations
type Queue struct {
	queueDir    string
	logger      logging.Logger
	mutex       sync.Mutex
	processChan chan struct{}
	shutdownCh  chan struct{}
	wg          sync.WaitGroup
	seq         uint64 // operations queued in the same millisecond used to get the same file name
}

// NewQueue creates a new queue
func NewQueue(queueDir string, logger logging.Logger) (*Queue, error) {
	// Create queue directory if it doesn't exist
	if err := os.MkdirAll(queueDir, 0755); err != nil {
		return nil, fmt.Errorf("failed to create queue directory: %w", err)
	}

	queue := &Queue{
		queueDir:    queueDir,
		logger:      logger,
		processChan: make(chan struct{}, 1),
		shutdownCh:  make(chan struct{}),
	}

	return queue, nil
}

// Start begins processing the queue
func (q *Queue) Start(processor func(op *QueuedOperation) error) {
	q.wg.Add(1)
	go func() {
		defer q.wg.Done()
		q.logger.Info("Queue processor started")

		ticker := time.NewTicker(5 * time.Second)
		defer ticker.Stop()

		for {
			select {
			case <-q.shutdownCh:
				q.logger.Info("Queue processor shutting down")
				return
			case <-ticker.C:
				q.processQueue(processor)
			case <-q.processChan:
				q.processQueue(processor)
			}
		}
	}()
}

// Stop stops the queue processor
func (q *Queue) Stop() {
	close(q.shutdownCh)
	q.wg.Wait()
}

// Enqueue adds an operation to the queue
func (q *Queue) Enqueue(op *QueuedOperation) error {
	q.mutex.Lock()
	defer q.mutex.Unlock()

	// Generate a unique filename with timestamp and sequence number
	q.seq++
	timestamp := time.Now().Format("20060102-150405.000")
	filename := fmt.Sprintf("op_%s_%s_%06d.json", string(op.Type), timestamp, q.seq)
	filePath := filepath.Join(q.queueDir, filename)

	// Serialize the operation to JSON
	data, err := json.Marshal(op)
	if err != nil {
		return fmt.Errorf("failed to marshal operation: %w", err)
	}

	// Write to file
	if err := os.WriteFile(filePath, data, 0644); err != nil {
		return fmt.Errorf("failed to write queue file: %w", err)
	}

	// Signal the processor that there's new work
	select {
	case q.processChan <- struct{}{}:
	default:
		// Channel is already signaled, no need to signal again
	}

	return nil
}

// processQueue processes operations in the queue
func (q *Queue) processQueue(processor func(op *QueuedOperation) error) {
	q.mutex.Lock()
	defer q.mutex.Unlock()

	// Read all files in the queue directory
	files, err := os.ReadDir(q.queueDir)
	if err != nil {
		q.logger.Error("Failed to read queue directory: %v", err)
		return
	}

	for _, file := range files {
		if file.IsDir() {
			continue
		}

		// Read and parse the operation
		filePath := filepath.Join(q.queueDir, file.Name())
		data, err := os.ReadFile(filePath)
		if err != nil {
			q.logger.Error("Failed to read queue file %s: %v", filePath, err)
			continue
		}

		var op QueuedOperation
		if err := json.Unmarshal(data, &op); err != nil {
			q.logger.Error("Failed to unmarshal operation from %s: %v", filePath, err)
			// Move to a "failed" directory or delete after multiple failures?
			continue
		}

		// Process the operation
		err = processor(&op)
		if err != nil {
			op.RetryCount++

			// Exponential backoff - if retried too many times, give up
			maxRetries := 10
			if op.RetryCount <= maxRetries {
				// Calculate backoff time based on retry count
				backoff := time.Duration(1<<uint(op.RetryCount-1)) * time.Second
				if backoff > 1*time.Hour {
					backoff = 1 * time.Hour // Cap at 1 hour
				}

				q.logger.Warn("Operation failed, will retry after %v (attempt %d/%d): %v",
					backoff, op.RetryCount, maxRetries, err)

				// Update the filename to include retry count and backoff time
				newFilename := fmt.Sprintf("op_%s_%s_retry%d_next%s.json",
					string(op.Type),
					op.Timestamp.Format("20060102-150405.000"),
					op.RetryCount,
					time.Now().Add(backoff).Format("20060102-150405"))
				newFilePath := filepath.Join(q.queueDir, newFilename)

				// Re-save with updated retry count and new filename
				updatedData, err := json.Marshal(op)
				if err != nil {
					q.logger.Error("Failed to re-marshal operation: %v", err)
					continue
				}

				if err := os.WriteFile(newFilePath, updatedData, 0644); err != nil {
					q.logger.Error("Failed to update queue file: %v", err)
					continue
				}

				// Remove the old file
				if err := os.Remove(filePath); err != nil {
					q.logger.Error("Failed to remove old queue file %s: %v", filePath, err)
				}

				// Skip further processing
				continue
			} else {
				q.logger.Error("Operation failed after maximum retries: %v", err)
			}
		}

		// Operation succeeded or we've given up, remove the file
		if err := os.Remove(filePath); err != nil {
			q.logger.Error("Failed to remove queue file %s: %v", filePath, err)
		}
	}
}

// QueueStoreOperation queues a store operation
func (q *Queue) QueueStoreOperation(update *models.OddsUpdate) error {
	op := &QueuedOperation{
		Type:       StoreOperation,
		Data:       update,
		Timestamp:  time.Now(),
		RetryCount: 0,
	}
	return q.Enqueue(op)
}

// GetQueueStats returns statistics about the queue
func (q *Queue) GetQueueStats() (int, error) {
	// Read all files in the queue directory
	files, err := os.ReadDir(q.queueDir)
	if err != nil {
		return 0, fmt.Errorf("failed to read queue directory: %w", err)
	}

	count := 0
	for _, file := range files {
		if !file.IsDir() {
			count++
		}
	}

	return count, nil
}

// GetQueueDir returns the queue directory
func (q *Queue) GetQueueDir() string {
	return q.queueDir
}
