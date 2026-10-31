// internal/storage/storage.go
package storage

import (
	"github.com/firechair/odds-receiver/internal/metrics"
	"github.com/firechair/odds-receiver/internal/models"
)

// Storage defines the interface for storage operations
type Storage interface {
	// StoreOddsUpdate stores an odds update
	StoreOddsUpdate(update *models.OddsUpdate) error

	// GetOddsHistoryForEvent gets historical odds for a specific event
	GetOddsHistoryForEvent(eventID string) ([]*models.OddsUpdate, error)

	// GetOddsHistoryForBettingOffer gets historical odds for a specific betting offer
	GetOddsHistoryForBettingOffer(bettingOfferID string) ([]*models.OddsUpdate, error)

	// // GetLiveOddsForEvent gets all live odds updates for a specific event
	// GetLiveOddsForEvent(eventID string) ([]*models.OddsUpdate, error)

	// // GetLatestLiveOddsForEvent gets the most recent live odds for each market for a specific event
	// GetLatestLiveOddsForEvent(eventID string) ([]*models.OddsUpdate, error)

	// Shutdown gracefully shuts down the storage
	Shutdown()

	// GetMetrics returns metrics for the storage
	GetMetrics() *metrics.Metrics
}
