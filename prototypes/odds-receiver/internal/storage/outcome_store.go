// internal/storage/outcome_store.go
package storage

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

// OutcomeStore manages persistent storage of outcome information
type OutcomeStore struct {
	storeDir      string
	logger        logging.Logger
	cacheMutex    sync.RWMutex
	outcomeCache  map[string]models.Outcome
	providerCache map[string]string
	lastSave      time.Time
	saveTicker    *time.Ticker
	shutdownCh    chan struct{}
	wg            sync.WaitGroup

	// New: Pending offers functionality
	pendingOffersMutex sync.RWMutex
	pendingOffers      map[string][]PendingOffer // Key is outcomeFK

	// Add this field to the struct
	onPendingOfferReady PendingOfferCallback
}

// PendingOffer represents a betting offer waiting for its outcome data
type PendingOffer struct {
	Offer          models.BettingOffer `json:"offer"`
	TimestampAdded time.Time           `json:"timestamp_added"`
	EventID        string              `json:"event_id"`         // Additional context for processing
	EventName      string              `json:"event_name"`       // Additional context for processing
	EventStartDate string              `json:"event_start_date"` // Additional context for processing
	ProviderName   string              `json:"provider_name"`    // Additional context for processing
}

// NewOutcomeStore creates a new outcome store
func NewOutcomeStore(dataDir string, logger logging.Logger) (*OutcomeStore, error) {
	// Create store directory if it doesn't exist
	storeDir := filepath.Join(dataDir, "outcomes")
	if err := os.MkdirAll(storeDir, 0755); err != nil {
		return nil, fmt.Errorf("failed to create outcome store directory: %w", err)
	}

	store := &OutcomeStore{
		storeDir:      storeDir,
		logger:        logger,
		outcomeCache:  make(map[string]models.Outcome),
		providerCache: make(map[string]string),
		pendingOffers: make(map[string][]PendingOffer), // Initialize the pending offers map
		lastSave:      time.Now(),
		saveTicker:    time.NewTicker(5 * time.Minute),
		shutdownCh:    make(chan struct{}),
	}

	// Load existing data from disk if available
	if err := store.loadFromDisk(); err != nil {
		logger.Warn("Failed to load outcome data from disk: %v", err)
	}

	// Start background saving
	store.startAutoSave()

	return store, nil
}

// startAutoSave starts a background goroutine to periodically save outcome data
func (s *OutcomeStore) startAutoSave() {
	s.wg.Add(1)
	go func() {
		defer s.wg.Done()
		for {
			select {
			case <-s.saveTicker.C:
				s.SaveToDisk()
			case <-s.shutdownCh:
				s.logger.Info("OutcomeStore shutting down, saving data...")
				s.SaveToDisk()
				return
			}
		}
	}()
}

// StoreOutcome stores an outcome in the cache and flags it for persistence
// Also processes any pending offers for this outcome
func (s *OutcomeStore) StoreOutcome(outcome models.Outcome) {
	// Skip deleted outcomes
	if outcome.Del == "yes" {
		s.cacheMutex.Lock()
		delete(s.outcomeCache, outcome.ID)
		s.cacheMutex.Unlock()
		s.logger.Debug("Removed deleted outcome %s from cache", outcome.ID)
		return
	}

	s.cacheMutex.Lock()
	// Only store if it's a new outcome or a newer version of an existing one
	existingOutcome, exists := s.outcomeCache[outcome.ID]
	if !exists || existingOutcome.N < outcome.N {
		s.outcomeCache[outcome.ID] = outcome
		s.logger.Debug("Stored outcome %s: Type=%d, Subtype=%d, Scope=%d",
			outcome.ID, outcome.OutcomeTypeFK, outcome.OutcomeSubtypeFK, outcome.OutcomeScopeFK)
	}
	s.cacheMutex.Unlock()

	// Check if there are any pending offers for this outcome
	s.pendingOffersMutex.Lock()
	pendingOffers, ok := s.pendingOffers[outcome.ID]
	if ok {
		s.logger.Info("Found %d pending offers for outcome %s, processing them now",
			len(pendingOffers), outcome.ID)

		// Remove from pending map - we'll process them now
		delete(s.pendingOffers, outcome.ID)
		s.pendingOffersMutex.Unlock()

		// Process each pending offer outside the lock
		for _, pendingOffer := range pendingOffers {
			s.ProcessPendingOffer(pendingOffer, outcome)
		}
	} else {
		s.pendingOffersMutex.Unlock()
	}
}

// ProcessPendingOffer processes a pending offer with its now-available outcome
func (s *OutcomeStore) ProcessPendingOffer(pendingOffer PendingOffer, outcome models.Outcome) {
	// Since this is outside the OddsProcessor, we need to signal that this betting offer
	// can now be processed - this will be handled by a callback registered by the processor
	if s.onPendingOfferReady != nil {
		s.logger.Info("Processing pending offer %s with outcome %s after waiting %v",
			pendingOffer.Offer.ID, outcome.ID, time.Since(pendingOffer.TimestampAdded))
		s.onPendingOfferReady(pendingOffer, outcome)
	}
}

// Callback function type for when a pending offer is ready to be processed
type PendingOfferCallback func(PendingOffer, models.Outcome)

// Store the callback function
// var onPendingOfferReady PendingOfferCallback

// SetPendingOfferCallback sets the callback function for when a pending offer is ready
func (s *OutcomeStore) SetPendingOfferCallback(callback PendingOfferCallback) {
	s.onPendingOfferReady = callback
}

// StorePendingOffer stores a betting offer that is waiting for its outcome data
func (s *OutcomeStore) StorePendingOffer(offer models.BettingOffer, eventID, eventName, eventStartDate, providerName string) {
	s.pendingOffersMutex.Lock()
	defer s.pendingOffersMutex.Unlock()

	pendingOffer := PendingOffer{
		Offer:          offer,
		TimestampAdded: time.Now(),
		EventID:        eventID,
		EventName:      eventName,
		EventStartDate: eventStartDate,
		ProviderName:   providerName,
	}

	s.pendingOffers[offer.OutcomeFK] = append(s.pendingOffers[offer.OutcomeFK], pendingOffer)
	s.logger.Info("Stored betting offer %s as pending for outcome %s", offer.ID, offer.OutcomeFK)
}

// GetPendingOffersCount returns the number of pending offers
func (s *OutcomeStore) GetPendingOffersCount() int {
	s.pendingOffersMutex.RLock()
	defer s.pendingOffersMutex.RUnlock()

	count := 0
	for _, offers := range s.pendingOffers {
		count += len(offers)
	}
	return count
}

// StoreProvider stores a provider name by ID
func (s *OutcomeStore) StoreProvider(providerID, providerName string) {
	s.cacheMutex.Lock()
	defer s.cacheMutex.Unlock()

	s.providerCache[providerID] = providerName
}

// GetOutcome retrieves an outcome by ID
func (s *OutcomeStore) GetOutcome(outcomeID string) (models.Outcome, bool) {
	s.cacheMutex.RLock()
	defer s.cacheMutex.RUnlock()

	outcome, exists := s.outcomeCache[outcomeID]
	return outcome, exists
}

// GetProvider retrieves a provider name by ID
func (s *OutcomeStore) GetProvider(providerID string) (string, bool) {
	s.cacheMutex.RLock()
	defer s.cacheMutex.RUnlock()

	name, exists := s.providerCache[providerID]
	return name, exists
}

// GetOutcomeCount returns the number of outcomes in the store
func (s *OutcomeStore) GetOutcomeCount() int {
	s.cacheMutex.RLock()
	defer s.cacheMutex.RUnlock()

	return len(s.outcomeCache)
}

// SaveToDisk persists the outcome cache to disk
func (s *OutcomeStore) SaveToDisk() error {
	// First save outcomes. Marshal under the lock: pushes keep writing to these maps.
	s.cacheMutex.RLock()
	outcomeCount, providerCount := len(s.outcomeCache), len(s.providerCache)
	if outcomeCount == 0 {
		s.cacheMutex.RUnlock()
		return nil
	}
	jsonData, err := json.Marshal(struct {
		Outcomes  map[string]models.Outcome `json:"outcomes"`
		Providers map[string]string         `json:"providers"`
		Timestamp time.Time                 `json:"timestamp"`
	}{
		Outcomes:  s.outcomeCache,
		Providers: s.providerCache,
		Timestamp: time.Now(),
	})
	s.cacheMutex.RUnlock()
	if err != nil {
		return fmt.Errorf("failed to marshal outcome data: %w", err)
	}

	// Write to file
	filePath := filepath.Join(s.storeDir, "outcomes.json")
	tempPath := filePath + ".tmp"

	if err := os.WriteFile(tempPath, jsonData, 0644); err != nil {
		return fmt.Errorf("failed to write outcome data to temp file: %w", err)
	}

	// Atomic rename to avoid corruption
	if err := os.Rename(tempPath, filePath); err != nil {
		return fmt.Errorf("failed to rename temp outcome file: %w", err)
	}

	// Now save pending offers
	s.pendingOffersMutex.RLock()
	pendingOffersCount := 0
	for _, offers := range s.pendingOffers {
		pendingOffersCount += len(offers)
	}

	var pendingJSON []byte
	if pendingOffersCount > 0 {
		pendingJSON, err = json.Marshal(struct {
			PendingOffers map[string][]PendingOffer `json:"pending_offers"`
			Timestamp     time.Time                 `json:"timestamp"`
		}{
			PendingOffers: s.pendingOffers,
			Timestamp:     time.Now(),
		})
	}
	s.pendingOffersMutex.RUnlock()

	if pendingOffersCount > 0 {
		if err != nil {
			return fmt.Errorf("failed to marshal pending offers data: %w", err)
		}

		// Write pending offers to file
		pendingPath := filepath.Join(s.storeDir, "pending_offers.json")
		tempPendingPath := pendingPath + ".tmp"

		if err := os.WriteFile(tempPendingPath, pendingJSON, 0644); err != nil {
			return fmt.Errorf("failed to write pending offers to temp file: %w", err)
		}

		// Atomic rename
		if err := os.Rename(tempPendingPath, pendingPath); err != nil {
			return fmt.Errorf("failed to rename temp pending offers file: %w", err)
		}
	}

	s.logger.Info("Saved %d outcomes, %d providers, and %d pending offers to disk",
		outcomeCount, providerCount, pendingOffersCount)
	s.lastSave = time.Now()

	return nil
}

// loadFromDisk loads outcome data from disk
func (s *OutcomeStore) loadFromDisk() error {
	// Load outcomes
	filePath := filepath.Join(s.storeDir, "outcomes.json")

	// Check if file exists
	if _, err := os.Stat(filePath); os.IsNotExist(err) {
		// Not an error, just no data yet
	} else {
		// Read file
		data, err := os.ReadFile(filePath)
		if err != nil {
			return fmt.Errorf("failed to read outcome file: %w", err)
		}

		// Unmarshal JSON
		var fileData struct {
			Outcomes  map[string]models.Outcome `json:"outcomes"`
			Providers map[string]string         `json:"providers"`
			Timestamp time.Time                 `json:"timestamp"`
		}

		if err := json.Unmarshal(data, &fileData); err != nil {
			return fmt.Errorf("failed to unmarshal outcome data: %w", err)
		}

		// Update cache
		s.cacheMutex.Lock()
		s.outcomeCache = fileData.Outcomes
		s.providerCache = fileData.Providers
		s.cacheMutex.Unlock()

		s.logger.Info("Loaded %d outcomes and %d providers from disk (last saved: %s)",
			len(s.outcomeCache), len(s.providerCache), fileData.Timestamp.Format(time.RFC3339))
	}

	// Load pending offers
	pendingPath := filepath.Join(s.storeDir, "pending_offers.json")

	// Check if pending offers file exists
	if _, err := os.Stat(pendingPath); os.IsNotExist(err) {
		// Not an error, just no pending offers
		return nil
	}

	// Read pending offers file
	pendingData, err := os.ReadFile(pendingPath)
	if err != nil {
		return fmt.Errorf("failed to read pending offers file: %w", err)
	}

	// Unmarshal JSON
	var pendingFileData struct {
		PendingOffers map[string][]PendingOffer `json:"pending_offers"`
		Timestamp     time.Time                 `json:"timestamp"`
	}

	if err := json.Unmarshal(pendingData, &pendingFileData); err != nil {
		return fmt.Errorf("failed to unmarshal pending offers data: %w", err)
	}

	// Update pending offers cache
	s.pendingOffersMutex.Lock()
	s.pendingOffers = pendingFileData.PendingOffers
	s.pendingOffersMutex.Unlock()

	// Count pending offers
	pendingCount := 0
	for _, offers := range pendingFileData.PendingOffers {
		pendingCount += len(offers)
	}

	s.logger.Info("Loaded %d pending offers from disk (last saved: %s)",
		pendingCount, pendingFileData.Timestamp.Format(time.RFC3339))

	return nil
}

// Shutdown stops the auto-save process and ensures data is saved
func (s *OutcomeStore) Shutdown() {
	close(s.shutdownCh)
	s.saveTicker.Stop()
	s.wg.Wait()
}
