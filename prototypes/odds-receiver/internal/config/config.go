// internal/config/config.go
package config

import (
	"os"
	"strconv"
	"strings"
	"time"
)

// Config holds application configuration
type Config struct {
	// Server settings
	Port        string
	MetricsPort string

	// DynamoDB settings
	DynamoDBRegion string
	DynamoDBTable  string

	// File storage settings
	FilesDir string
	DataDir  string // Add this line

	// Queue settings
	QueueDir string

	// Batch processing settings
	BatchSize     int
	BatchInterval time.Duration

	// Filtering settings
	TargetBookmakerIDs []string
}

// Load loads configuration from environment variables
func Load() (*Config, error) {
	// Server settings
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	metricsPort := os.Getenv("METRICS_PORT")
	if metricsPort == "" {
		metricsPort = "9090"
	}

	// DynamoDB settings
	dynamoRegion := os.Getenv("DYNAMODB_REGION")
	if dynamoRegion == "" {
		dynamoRegion = "us-east-2" // Default region
	}

	dynamoTable := os.Getenv("DYNAMODB_TABLE")
	if dynamoTable == "" {
		dynamoTable = "odds-data" // Default table name
	}

	// File storage settings
	filesDir := os.Getenv("FILES_DIR")
	if filesDir == "" {
		filesDir = "./files" // Default files directory
	}

	dataDir := os.Getenv("DATA_DIR")
	if dataDir == "" {
		dataDir = "./data" // Default data directory
	}

	// Queue settings
	queueDir := os.Getenv("QUEUE_DIR")
	if queueDir == "" {
		queueDir = "./queue" // Default queue directory
	}

	// Batch processing settings
	batchSizeStr := os.Getenv("BATCH_SIZE")
	batchSize := 25 // Default batch size (DynamoDB limit is 25)
	if batchSizeStr != "" {
		if size, err := strconv.Atoi(batchSizeStr); err == nil && size > 0 && size <= 25 {
			batchSize = size
		}
	}

	batchIntervalStr := os.Getenv("BATCH_INTERVAL_SECONDS")
	batchInterval := 5 * time.Second // Default batch interval
	if batchIntervalStr != "" {
		if interval, err := strconv.Atoi(batchIntervalStr); err == nil && interval > 0 {
			batchInterval = time.Duration(interval) * time.Second
		}
	}

	// Target Bookmakers - comma-separated list of bookmaker IDs
	targetBookmakerIDsStr := os.Getenv("TARGET_BOOKMAKER_IDS")
	var targetBookmakerIDs []string
	if targetBookmakerIDsStr == "" {
		// Replace with your four specific bookmaker IDs
		targetBookmakerIDs = []string{"23", "124", "379", "455"} // Example IDs: Bookmaker A, Bookmaker H, etc.
	} else {
		targetBookmakerIDs = strings.Split(targetBookmakerIDsStr, ",")
	}

	return &Config{
		Port:               port,
		MetricsPort:        metricsPort,
		DynamoDBRegion:     dynamoRegion,
		DynamoDBTable:      dynamoTable,
		FilesDir:           filesDir,
		DataDir:            dataDir,
		QueueDir:           queueDir,
		BatchSize:          batchSize,
		BatchInterval:      batchInterval,
		TargetBookmakerIDs: targetBookmakerIDs,
	}, nil
}
