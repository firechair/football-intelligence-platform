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

	// Queue settings
	QueueDir string

	// Batch processing settings
	BatchSize     int
	BatchInterval time.Duration

	// Filtering settings
	SerieATournamentStageID string
	TargetBookmakerIDs      []string
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
		dynamoRegion = "us-east-1" // Default region
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

	// Serie A Tournament Stage ID - this is the ID for Serie A in Enetpulse system
	serieATournamentStageID := os.Getenv("SERIE_A_TOURNAMENT_STAGE_ID")
	if serieATournamentStageID == "" {
		// You'll need to find the actual ID for Serie A
		serieATournamentStageID = "885640" // Example ID, replace with actual
	}

	// Target Bookmakers - comma-separated list of bookmaker IDs
	targetBookmakerIDsStr := os.Getenv("TARGET_BOOKMAKER_IDS")
	var targetBookmakerIDs []string
	if targetBookmakerIDsStr == "" {
		// Replace with your four specific bookmaker IDs
		targetBookmakerIDs = []string{"23", "7", "135", "370"} // Example IDs: Bookmaker A, Bookmaker H, etc.
	} else {
		targetBookmakerIDs = strings.Split(targetBookmakerIDsStr, ",")
	}

	return &Config{
		Port:                    port,
		MetricsPort:             metricsPort,
		DynamoDBRegion:          dynamoRegion,
		DynamoDBTable:           dynamoTable,
		FilesDir:                filesDir,
		QueueDir:                queueDir,
		BatchSize:               batchSize,
		BatchInterval:           batchInterval,
		SerieATournamentStageID: serieATournamentStageID,
		TargetBookmakerIDs:      targetBookmakerIDs,
	}, nil
}
