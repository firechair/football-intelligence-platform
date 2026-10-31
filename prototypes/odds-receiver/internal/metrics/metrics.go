// internal/metrics/metrics.go
package metrics

import (
	"encoding/json"
	"net/http"
	"sync"
	"sync/atomic"
	"time"

	"github.com/firechair/odds-receiver/internal/logging"
)

// Metrics tracks various performance metrics for the application
type Metrics struct {
	logger logging.Logger

	// Counters
	receivedFiles       int64
	parsedFiles         int64
	failedParses        int64
	successfulDynamoOps int64
	failedDynamoOps     int64

	// Queue metrics
	queuedOperations int64
	queueDepth       int64

	// Timing metrics
	totalProcessingTime int64 // nanoseconds
	processedItems      int64

	// Mutex for non-atomic operations
	mu sync.RWMutex

	// Map for storing custom metrics
	customMetrics map[string]interface{}
}

// NewMetrics creates a new metrics collector
func NewMetrics(logger logging.Logger) *Metrics {
	return &Metrics{
		logger:        logger,
		customMetrics: make(map[string]interface{}),
	}
}

// RecordFileReceived increments the received files counter
func (m *Metrics) RecordFileReceived() {
	atomic.AddInt64(&m.receivedFiles, 1)
}

// RecordFileParsed increments the parsed files counter
func (m *Metrics) RecordFileParsed() {
	atomic.AddInt64(&m.parsedFiles, 1)
}

// RecordParseFailure increments the failed parses counter
func (m *Metrics) RecordParseFailure() {
	atomic.AddInt64(&m.failedParses, 1)
}

// RecordDynamoSuccess increments the successful DynamoDB operations counter
func (m *Metrics) RecordDynamoSuccess() {
	atomic.AddInt64(&m.successfulDynamoOps, 1)
}

// RecordDynamoFailure increments the failed DynamoDB operations counter
func (m *Metrics) RecordDynamoFailure() {
	atomic.AddInt64(&m.failedDynamoOps, 1)
}

// RecordOperationQueued increments the queued operations counter
func (m *Metrics) RecordOperationQueued() {
	atomic.AddInt64(&m.queuedOperations, 1)
}

// SetQueueDepth sets the current queue depth
func (m *Metrics) SetQueueDepth(depth int64) {
	atomic.StoreInt64(&m.queueDepth, depth)
}

// RecordProcessingTime adds to the total processing time
func (m *Metrics) RecordProcessingTime(duration time.Duration) {
	atomic.AddInt64(&m.totalProcessingTime, int64(duration))
	atomic.AddInt64(&m.processedItems, 1)
}

// SetCustomMetric sets a custom metric
func (m *Metrics) SetCustomMetric(name string, value interface{}) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.customMetrics[name] = value
}

// GetCustomMetric gets a custom metric
func (m *Metrics) GetCustomMetric(name string) (interface{}, bool) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	value, exists := m.customMetrics[name]
	return value, exists
}

// GetMetrics returns all metrics as a JSON-serializable map
func (m *Metrics) GetMetrics() map[string]interface{} {
	// Calculate average processing time
	var avgProcessingTime float64
	processedItems := atomic.LoadInt64(&m.processedItems)
	if processedItems > 0 {
		totalTime := atomic.LoadInt64(&m.totalProcessingTime)
		avgProcessingTime = float64(totalTime) / float64(processedItems) / float64(time.Millisecond)
	}

	metrics := map[string]interface{}{
		"files": map[string]int64{
			"received":     atomic.LoadInt64(&m.receivedFiles),
			"parsed":       atomic.LoadInt64(&m.parsedFiles),
			"parse_failed": atomic.LoadInt64(&m.failedParses),
		},
		"dynamodb": map[string]int64{
			"successful_ops": atomic.LoadInt64(&m.successfulDynamoOps),
			"failed_ops":     atomic.LoadInt64(&m.failedDynamoOps),
		},
		"queue": map[string]int64{
			"operations_queued": atomic.LoadInt64(&m.queuedOperations),
			"current_depth":     atomic.LoadInt64(&m.queueDepth),
		},
		"performance": map[string]interface{}{
			"avg_processing_time_ms": avgProcessingTime,
			"items_processed":        processedItems,
		},
	}

	// Add custom metrics
	m.mu.RLock()
	customMetrics := make(map[string]interface{}, len(m.customMetrics))
	for k, v := range m.customMetrics {
		customMetrics[k] = v
	}
	m.mu.RUnlock()

	metrics["custom"] = customMetrics

	return metrics
}

// ServeHTTP implements http.Handler to expose metrics as JSON
func (m *Metrics) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	metrics := m.GetMetrics()

	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(metrics); err != nil {
		m.logger.Error("Failed to encode metrics: %v", err)
		http.Error(w, "Failed to encode metrics", http.StatusInternalServerError)
		return
	}
}
