// internal/storage/dynamodb.go
package storage

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/feature/dynamodb/attributevalue"
	"github.com/aws/aws-sdk-go-v2/service/dynamodb"
	"github.com/aws/aws-sdk-go-v2/service/dynamodb/types"

	"github.com/firechair/odds-receiver/internal/logging"
	"github.com/firechair/odds-receiver/internal/metrics"
	"github.com/firechair/odds-receiver/internal/models"
)

// DynamoDBStorage implements the Storage interface using DynamoDB
type DynamoDBStorage struct {
	client    *dynamodb.Client
	tableName string
	logger    logging.Logger
	metrics   *metrics.Metrics

	// For batch processing
	batchMutex   sync.Mutex
	batchItems   []models.OddsUpdate
	batchMaxSize int
	batchTicker  *time.Ticker
	shutdownCh   chan struct{}
	wg           sync.WaitGroup
}

// NewDynamoDB creates a new DynamoDB storage
func NewDynamoDB(region, tableName string, logger logging.Logger) (*DynamoDBStorage, error) {
	// Load AWS configuration
	cfg, err := config.LoadDefaultConfig(context.TODO(), config.WithRegion(region))
	if err != nil {
		return nil, fmt.Errorf("unable to load SDK config: %w", err)
	}

	// Create DynamoDB client
	client := dynamodb.NewFromConfig(cfg)

	storage := &DynamoDBStorage{
		client:       client,
		tableName:    tableName,
		logger:       logger,
		metrics:      metrics.NewMetrics(logger),
		batchItems:   make([]models.OddsUpdate, 0, 25),
		batchMaxSize: 25, // DynamoDB batch write allows max 25 items
		batchTicker:  time.NewTicker(5 * time.Second),
		shutdownCh:   make(chan struct{}),
	}

	// Ensure the table exists
	err = storage.ensureTableExists()
	if err != nil {
		return nil, fmt.Errorf("error ensuring table exists: %w", err)
	}

	// Start batch processor
	storage.startBatchProcessor()

	return storage, nil
}

// ensureTableExists creates the DynamoDB table if it doesn't exist
func (d *DynamoDBStorage) ensureTableExists() error {
	// Check if table exists
	_, err := d.client.DescribeTable(context.TODO(), &dynamodb.DescribeTableInput{
		TableName: aws.String(d.tableName),
	})

	// If table exists, return
	if err == nil {
		return nil
	}

	// Create the table
	_, err = d.client.CreateTable(context.TODO(), &dynamodb.CreateTableInput{
		TableName: aws.String(d.tableName),
		AttributeDefinitions: []types.AttributeDefinition{
			{
				AttributeName: aws.String("eventId"),
				AttributeType: types.ScalarAttributeTypeS,
			},
			{
				AttributeName: aws.String("bettingOfferId"),
				AttributeType: types.ScalarAttributeTypeS,
			},
			{
				AttributeName: aws.String("timestamp"),
				AttributeType: types.ScalarAttributeTypeS,
			},
		},
		KeySchema: []types.KeySchemaElement{
			{
				AttributeName: aws.String("eventId"),
				KeyType:       types.KeyTypeHash,
			},
			{
				AttributeName: aws.String("bettingOfferId"),
				KeyType:       types.KeyTypeRange,
			},
		},
		GlobalSecondaryIndexes: []types.GlobalSecondaryIndex{
			{
				IndexName: aws.String("bettingOffer-timestamp-index"),
				KeySchema: []types.KeySchemaElement{
					{
						AttributeName: aws.String("bettingOfferId"),
						KeyType:       types.KeyTypeHash,
					},
					{
						AttributeName: aws.String("timestamp"),
						KeyType:       types.KeyTypeRange,
					},
				},
				Projection: &types.Projection{
					ProjectionType: types.ProjectionTypeAll,
				},
				ProvisionedThroughput: &types.ProvisionedThroughput{
					ReadCapacityUnits:  aws.Int64(5),
					WriteCapacityUnits: aws.Int64(5),
				},
			},
		},
		ProvisionedThroughput: &types.ProvisionedThroughput{
			ReadCapacityUnits:  aws.Int64(5),
			WriteCapacityUnits: aws.Int64(5),
		},
	})

	if err != nil {
		return fmt.Errorf("failed to create table: %w", err)
	}

	// Wait for table to be created
	waiter := dynamodb.NewTableExistsWaiter(d.client)
	err = waiter.Wait(context.TODO(), &dynamodb.DescribeTableInput{
		TableName: aws.String(d.tableName),
	}, 5*time.Minute)

	if err != nil {
		return fmt.Errorf("failed to wait for table creation: %w", err)
	}

	return nil
}

// startBatchProcessor starts the background batch processor
func (d *DynamoDBStorage) startBatchProcessor() {
	d.wg.Add(1)
	go func() {
		defer d.wg.Done()
		for {
			select {
			case <-d.batchTicker.C:
				d.flushBatch()
			case <-d.shutdownCh:
				d.logger.Info("Batch processor shutting down, flushing remaining items")
				d.flushBatch()
				return
			}
		}
	}()
}

// StoreOddsUpdate stores an odds update in DynamoDB
func (d *DynamoDBStorage) StoreOddsUpdate(update *models.OddsUpdate) error {
	// Add to batch
	d.batchMutex.Lock()
	defer d.batchMutex.Unlock()

	d.batchItems = append(d.batchItems, *update)

	// If batch is full, flush it
	if len(d.batchItems) >= d.batchMaxSize {
		return d.flushBatchLocked()
	}

	return nil
}

// flushBatch flushes the current batch to DynamoDB
func (d *DynamoDBStorage) flushBatch() error {
	d.batchMutex.Lock()
	defer d.batchMutex.Unlock()

	return d.flushBatchLocked()
}

// flushBatchLocked flushes the current batch to DynamoDB (assumes mutex is already locked)
func (d *DynamoDBStorage) flushBatchLocked() error {
	if len(d.batchItems) == 0 {
		return nil
	}

	d.logger.Info("Flushing batch of %d items to DynamoDB", len(d.batchItems))
	startTime := time.Now()

	// Convert items to DynamoDB format
	writeRequests := make([]types.WriteRequest, 0, len(d.batchItems))

	for _, update := range d.batchItems {
		// Convert timestamp to ISO8601 string for sorting
		timestampStr := update.Timestamp.Format(time.RFC3339)

		// Create item to store
		item := map[string]types.AttributeValue{
			"eventId":            &types.AttributeValueMemberS{Value: update.EventID},
			"eventName":          &types.AttributeValueMemberS{Value: update.EventName},
			"eventStartDate":     &types.AttributeValueMemberS{Value: update.EventStartDate},
			"outcomeId":          &types.AttributeValueMemberS{Value: update.OutcomeID},
			"bettingOfferId":     &types.AttributeValueMemberS{Value: update.BettingOfferID},
			"providerId":         &types.AttributeValueMemberS{Value: update.ProviderID},
			"providerName":       &types.AttributeValueMemberS{Value: update.ProviderName},
			"odds":               &types.AttributeValueMemberN{Value: fmt.Sprintf("%f", update.Odds)},
			"oddsOld":            &types.AttributeValueMemberN{Value: fmt.Sprintf("%f", update.OddsOld)},
			"active":             &types.AttributeValueMemberS{Value: update.Active},
			"bettingOfferStatus": &types.AttributeValueMemberN{Value: fmt.Sprintf("%d", update.BettingOfferStatus)},
			"timestamp":          &types.AttributeValueMemberS{Value: timestampStr},
			"outcomeTypeFK":      &types.AttributeValueMemberN{Value: fmt.Sprintf("%d", update.OutcomeTypeFK)},    // Tells you what type of market (1=1X2, 4=Over/Under)
			"outcomeSubtypeFK":   &types.AttributeValueMemberN{Value: fmt.Sprintf("%d", update.OutcomeSubtypeFK)}, // Tells you which selection (1=win, 2=draw)
			"outcomeScopeFK":     &types.AttributeValueMemberN{Value: fmt.Sprintf("%d", update.OutcomeScopeFK)},   // Tells you time period (1=full match, 4=first half)
			"iparam":             &types.AttributeValueMemberN{Value: fmt.Sprintf("%d", update.IParam)},           // Often contains team ID for team-specific selections
			"isLiveOdds":         &types.AttributeValueMemberBOOL{Value: update.IsLiveOdds},
		}

		writeRequests = append(writeRequests, types.WriteRequest{
			PutRequest: &types.PutRequest{
				Item: item,
			},
		})
	}

	// Process in chunks of 25 items (DynamoDB limit)
	for i := 0; i < len(writeRequests); i += 25 {
		end := i + 25
		if end > len(writeRequests) {
			end = len(writeRequests)
		}

		chunk := writeRequests[i:end]

		// Put items in DynamoDB
		result, err := d.client.BatchWriteItem(context.TODO(), &dynamodb.BatchWriteItemInput{
			RequestItems: map[string][]types.WriteRequest{
				d.tableName: chunk,
			},
		})

		if err != nil {
			d.logger.Error("Failed to batch write items to DynamoDB: %v", err)
			d.metrics.RecordDynamoFailure()
			return fmt.Errorf("failed to batch write items: %w", err)
		}

		// Check for unprocessed items
		if unprocessed, ok := result.UnprocessedItems[d.tableName]; ok && len(unprocessed) > 0 {
			d.logger.Warn("Some items were not processed, will retry: %d items", len(unprocessed))

			// Store the original items that correspond to the unprocessed requests
			// We need to map from the write requests back to our original items
			for _, request := range unprocessed {
				if request.PutRequest != nil {
					// Extract identifying information
					var eventID, bettingOfferID string

					if ev, ok := request.PutRequest.Item["eventId"].(*types.AttributeValueMemberS); ok {
						eventID = ev.Value
					}

					if bo, ok := request.PutRequest.Item["bettingOfferId"].(*types.AttributeValueMemberS); ok {
						bettingOfferID = bo.Value
					}

					if eventID != "" && bettingOfferID != "" {
						// Convert back to a regular OddsUpdate
						update := &models.OddsUpdate{}
						if err := attributevalue.UnmarshalMap(request.PutRequest.Item, update); err != nil {
							d.logger.Error("Failed to unmarshal unprocessed item: %v", err)
							continue
						}

						// Re-add to our batch (it will be processed in the next batch or flush)
						d.batchItems = append(d.batchItems, *update)
						d.logger.Info("Re-queued unprocessed item for event %s, betting offer %s",
							eventID, bettingOfferID)
					}
				}
			}
		}
	}

	// Record metrics
	d.metrics.RecordDynamoSuccess()
	d.metrics.RecordProcessingTime(time.Since(startTime))

	// Clear the batch
	d.batchItems = d.batchItems[:0]

	return nil
}

// Shutdown closes the batch processor and waits for it to finish
func (d *DynamoDBStorage) Shutdown() {
	close(d.shutdownCh)
	d.wg.Wait()
	d.batchTicker.Stop()
}

// GetOddsHistoryForEvent gets historical odds for a specific event
func (d *DynamoDBStorage) GetOddsHistoryForEvent(eventID string) ([]*models.OddsUpdate, error) {
	input := &dynamodb.QueryInput{
		TableName:              aws.String(d.tableName),
		KeyConditionExpression: aws.String("eventId = :eventId"),
		ExpressionAttributeValues: map[string]types.AttributeValue{
			":eventId": &types.AttributeValueMemberS{Value: eventID},
		},
	}

	result, err := d.client.Query(context.TODO(), input)
	if err != nil {
		d.logger.Error("Failed to query odds history: %v", err)
		return nil, fmt.Errorf("failed to query odds history: %w", err)
	}

	var updates []*models.OddsUpdate
	for _, item := range result.Items {
		update := &models.OddsUpdate{}
		err = attributevalue.UnmarshalMap(item, update)
		if err != nil {
			d.logger.Error("Failed to unmarshal odds update: %v", err)
			return nil, fmt.Errorf("failed to unmarshal odds update: %w", err)
		}
		updates = append(updates, update)
	}

	return updates, nil
}

// GetOddsHistoryForBettingOffer gets historical odds for a specific betting offer
func (d *DynamoDBStorage) GetOddsHistoryForBettingOffer(bettingOfferID string) ([]*models.OddsUpdate, error) {
	input := &dynamodb.QueryInput{
		TableName:              aws.String(d.tableName),
		IndexName:              aws.String("bettingOffer-timestamp-index"),
		KeyConditionExpression: aws.String("bettingOfferId = :bettingOfferId"),
		ExpressionAttributeValues: map[string]types.AttributeValue{
			":bettingOfferId": &types.AttributeValueMemberS{Value: bettingOfferID},
		},
	}

	result, err := d.client.Query(context.TODO(), input)
	if err != nil {
		d.logger.Error("Failed to query odds history: %v", err)
		return nil, fmt.Errorf("failed to query odds history: %w", err)
	}

	var updates []*models.OddsUpdate
	for _, item := range result.Items {
		update := &models.OddsUpdate{}
		err = attributevalue.UnmarshalMap(item, update)
		if err != nil {
			d.logger.Error("Failed to unmarshal odds update: %v", err)
			return nil, fmt.Errorf("failed to unmarshal odds update: %w", err)
		}
		updates = append(updates, update)
	}

	return updates, nil
}

// GetMetrics returns the storage metrics
func (d *DynamoDBStorage) GetMetrics() *metrics.Metrics {
	return d.metrics
}
