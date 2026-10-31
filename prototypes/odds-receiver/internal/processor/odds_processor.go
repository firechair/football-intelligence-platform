// internal/processor/odds_processor.go
package processor

import (
	"time"

	"github.com/firechair/odds-receiver/internal/logging"
	"github.com/firechair/odds-receiver/internal/metrics"
	"github.com/firechair/odds-receiver/internal/models"
	"github.com/firechair/odds-receiver/internal/parser"
	"github.com/firechair/odds-receiver/internal/queue"
	"github.com/firechair/odds-receiver/internal/storage"
)

// OddsProcessor processes odds data
type OddsProcessor struct {
	store                   storage.Storage
	queue                   *queue.Queue
	logger                  logging.Logger
	metrics                 *metrics.Metrics
	serieATournamentStageID string
	targetBookmakerIDs      map[string]bool
}

// NewOddsProcessor creates a new OddsProcessor
func NewOddsProcessor(store storage.Storage, logger logging.Logger, serieATournamentStageID string, targetBookmakerIDs []string) *OddsProcessor {
	// Convert target bookmaker IDs to a map for faster lookups
	bookmakerMap := make(map[string]bool)
	for _, id := range targetBookmakerIDs {
		bookmakerMap[id] = true
	}

	return &OddsProcessor{
		store:                   store,
		logger:                  logger,
		metrics:                 metrics.NewMetrics(logger),
		serieATournamentStageID: serieATournamentStageID,
		targetBookmakerIDs:      bookmakerMap,
	}
}

// SetQueue sets the queue for the processor
func (p *OddsProcessor) SetQueue(q *queue.Queue) {
	p.queue = q
}

// Process processes the parsed XML data
func (p *OddsProcessor) Process(data *parser.OddsData) error {
	now := time.Now()
	startTime := time.Now()

	// Track live odds metrics separately
	liveOffersProcessed := 0

	p.logger.Info("Processing odds data with %d betting offers (isLiveData: %v)",
		len(data.BettingOffers), data.LiveOdds)

	// Keep count of offers processed
	processed := 0
	skipped := 0
	filteredByTournament := 0
	filteredByBookmaker := 0

	// Build a map of events for Serie A filtering and easy lookup of event details
	serieAEvents := make(map[string]bool)
	eventDetails := make(map[string]models.Event)
	for _, event := range data.Events {
		if event.TournamentStageFK == p.serieATournamentStageID {
			serieAEvents[event.ID] = true
		}
		// Store event details for later lookup
		eventDetails[event.ID] = event
	}

	// Map outcomes to events for easy lookup
	outcomeToEvent := make(map[string]string)
	for _, outcome := range data.Outcomes {
		if outcome.Object == "event" {
			outcomeToEvent[outcome.ID] = outcome.ObjectFK
		}
	}

	// Process betting offers
	for _, offer := range data.BettingOffers {
		// Skip deleted or inactive offers
		if offer.Del == "yes" || offer.Active == "no" {
			skipped++
			continue
		}

		// Check if the bookmaker is in our target list
		if !p.targetBookmakerIDs[offer.OddsProviderFK] {
			filteredByBookmaker++
			skipped++
			continue
		}

		// Find the event ID for this betting offer
		eventID := ""
		outcomeID := offer.OutcomeFK

		// If we know which event this outcome is for
		if outcomeEventID, exists := outcomeToEvent[outcomeID]; exists {
			eventID = outcomeEventID
		} else {
			// Try to find the event ID via the outcomes
			for _, outcome := range data.Outcomes {
				if outcome.ID == outcomeID && outcome.Object == "event" {
					eventID = outcome.ObjectFK
					break
				}
			}
		}

		// Check if the event is from Serie A
		if eventID != "" && !serieAEvents[eventID] {
			filteredByTournament++
			skipped++
			continue
		}

		// Find the associated outcome
		var outcomeInfo models.Outcome
		for _, outcome := range data.Outcomes {
			if outcome.ID == offer.OutcomeFK {
				outcomeInfo = outcome
				break
			}
		}

		// Find provider name
		var providerName string
		for _, provider := range data.OddsProviders {
			if provider.ID == offer.OddsProviderFK {
				providerName = provider.Name
				break
			}
		}

		// Lookup event details (name and start date)
		var eventName, eventStartDate string
		if event, exists := eventDetails[eventID]; exists {
			eventName = event.Name
			eventStartDate = event.StartDate
		}

		// Extract match status information (for live odds)
		// This could come from additional event information or properties
		matchStatus := ""
		matchMinute := 0
		score := ""

		// Determine match status from event status type
		if eventID != "" {
			if event, exists := eventDetails[eventID]; exists {
				// Parse status information
				if event.StatusType == "playing" || event.StatusType == "inprogress" {
					matchStatus = "LIVE" // Default live status

					// More advanced parsing might extract specific period (1H, 2H, etc.)
					// and current minute from properties or another source
				} else if event.StatusType == "notstarted" {
					matchStatus = "PREMATCH"
				} else if event.StatusType == "finished" {
					matchStatus = "FINISHED"
				}
			}
		}

		// Determine if this is a live odds update
		isLiveOdds := data.LiveOdds

		// For more precise detection, check if the timestamp is after event start time
		// This requires parsing the event start date
		eventStartTime, err := time.Parse("2006-01-02 15:04:05", eventStartDate)
		if err == nil && now.After(eventStartTime) {
			isLiveOdds = true
		}

		// Create odds update
		update := &models.OddsUpdate{
			EventID:            eventID,
			EventName:          eventName,
			EventStartDate:     eventStartDate,
			OutcomeID:          outcomeInfo.ID,
			BettingOfferID:     offer.ID,
			ProviderID:         offer.OddsProviderFK,
			ProviderName:       providerName,
			Odds:               offer.Odds,
			OddsOld:            offer.OddsOld,
			Active:             offer.Active,
			BettingOfferStatus: offer.BettingofferStatusFK,
			Timestamp:          now,
			OutcomeTypeFK:      outcomeInfo.OutcomeTypeFK,
			OutcomeSubtypeFK:   outcomeInfo.OutcomeSubtypeFK,
			OutcomeScopeFK:     outcomeInfo.OutcomeScopeFK,
			IParam:             outcomeInfo.IParam,
			IsLiveOdds:         isLiveOdds,
			MatchStatus:        matchStatus,
			MatchMinute:        matchMinute,
			Score:              score,
		}

		// Track live odds separately for metrics
		if isLiveOdds {
			liveOffersProcessed++
		}

		// If we have a queue, use it
		if p.queue != nil {
			err := p.queue.QueueStoreOperation(update)
			if err != nil {
				p.logger.Error("Failed to queue odds update: %v", err)
				p.metrics.RecordDynamoFailure()
				return err
			}
			p.metrics.RecordOperationQueued()
		} else {
			// Otherwise store directly
			err := p.store.StoreOddsUpdate(update)
			if err != nil {
				p.logger.Error("Failed to store odds update: %v", err)
				p.metrics.RecordDynamoFailure()
				return err
			}
			p.metrics.RecordDynamoSuccess()
		}

		processed++
	}

	// Record metrics
	p.metrics.RecordProcessingTime(time.Since(startTime))

	// Set custom metrics
	p.metrics.SetCustomMetric("offers_processed", processed)
	p.metrics.SetCustomMetric("offers_skipped", skipped)
	p.metrics.SetCustomMetric("filtered_by_tournament", filteredByTournament)
	p.metrics.SetCustomMetric("filtered_by_bookmaker", filteredByBookmaker)
	p.metrics.SetCustomMetric("live_offers_processed", liveOffersProcessed)

	p.logger.Info("Processed %d betting offers (%d live), skipped %d (filtered: %d by tournament, %d by bookmaker) (took %v)",
		processed, liveOffersProcessed, skipped, filteredByTournament, filteredByBookmaker, time.Since(startTime))

	return nil
}

// GetMetrics returns the processor metrics
func (p *OddsProcessor) GetMetrics() *metrics.Metrics {
	return p.metrics
}
