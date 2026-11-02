// internal/processor/odds_processor.go
package processor

import (
	"fmt"
	"strings"
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
	store              storage.Storage
	queue              *queue.Queue
	logger             logging.Logger
	metrics            *metrics.Metrics
	targetBookmakerIDs map[string]bool

	// Add outcome store
	outcomeStore *storage.OutcomeStore
}

// NewOddsProcessor creates a new OddsProcessor
func NewOddsProcessor(store storage.Storage, logger logging.Logger, targetBookmakerIDs []string) *OddsProcessor {
	// Convert target bookmaker IDs to a map for faster lookups
	bookmakerMap := make(map[string]bool)
	for _, id := range targetBookmakerIDs {
		bookmakerMap[id] = true
	}

	return &OddsProcessor{
		store:              store,
		logger:             logger,
		metrics:            metrics.NewMetrics(logger),
		targetBookmakerIDs: bookmakerMap,
	}
}

// SetOutcomeStore sets the outcome store for the processor
func (p *OddsProcessor) SetOutcomeStore(outcomeStore *storage.OutcomeStore) {
	p.outcomeStore = outcomeStore

	// Register callback for when pending offers become ready
	p.outcomeStore.SetPendingOfferCallback(p.handleReadyPendingOffer)
}

// handleReadyPendingOffer processes a pending offer that now has its outcome data available
func (p *OddsProcessor) handleReadyPendingOffer(pendingOffer storage.PendingOffer, outcome models.Outcome) {
	p.logger.Info("Processing previously pending betting offer %s with now available outcome %s",
		pendingOffer.Offer.ID, outcome.ID)

	// Set up required info for processing this betting offer
	now := time.Now()

	// The outcome names the provider's event; the coupon key only gives a slug like "inter-milan"
	eventID := pendingOffer.EventID
	if outcome.Object == "event" && outcome.ObjectFK != "" {
		eventID = outcome.ObjectFK
	}

	// Determine if this is a live odds update
	isLiveOdds := pendingOffer.Offer.IsLive == "yes"

	// If we have event start date, check if timestamp is after event start time
	if pendingOffer.EventStartDate != "" {
		eventStartTime, _ := time.Parse("2006-01-02 15:04:05", pendingOffer.EventStartDate)
		if now.After(eventStartTime) {
			isLiveOdds = true
		}
	}

	// Generate market description
	marketDescription := GetMarketDescription(
		outcome.OutcomeTypeFK,
		outcome.OutcomeSubtypeFK,
		outcome.OutcomeScopeFK,
		outcome.DParam)

	// Add team info from the iparam if available (common for markets like 1X2)
	if (outcome.OutcomeTypeFK == 1 || outcome.OutcomeTypeFK == 2) &&
		outcome.OutcomeSubtypeFK == 1 && outcome.IParam > 0 {
		marketDescription += fmt.Sprintf(" (Team ID: %d)", outcome.IParam)
	}

	// Create odds update
	update := &models.OddsUpdate{
		EventID:            eventID,
		EventName:          pendingOffer.EventName,
		EventStartDate:     pendingOffer.EventStartDate,
		OutcomeID:          outcome.ID,
		BettingOfferID:     pendingOffer.Offer.ID,
		ProviderID:         pendingOffer.Offer.OddsProviderFK,
		ProviderName:       pendingOffer.ProviderName,
		Odds:               pendingOffer.Offer.Odds,
		OddsOld:            pendingOffer.Offer.OddsOld,
		Active:             pendingOffer.Offer.Active,
		BettingOfferStatus: pendingOffer.Offer.BettingofferStatusFK,
		Timestamp:          now,
		OutcomeTypeFK:      outcome.OutcomeTypeFK,
		OutcomeSubtypeFK:   outcome.OutcomeSubtypeFK,
		OutcomeScopeFK:     outcome.OutcomeScopeFK,
		IParam:             outcome.IParam,
		IsLiveOdds:         isLiveOdds,
		MatchStatus:        "", // Not available from pending data
		MatchMinute:        0,  // Not available from pending data
		Score:              "", // Not available from pending data
		MarketDescription:  marketDescription,
	}

	// Store the odds update
	var err error
	if p.queue != nil {
		err = p.queue.QueueStoreOperation(update)
		if err != nil {
			p.logger.Error("Failed to queue odds update for pending offer: %v", err)
			p.metrics.RecordDynamoFailure()
			return
		}
		p.metrics.RecordOperationQueued()
	} else {
		err = p.store.StoreOddsUpdate(update)
		if err != nil {
			p.logger.Error("Failed to store odds update for pending offer: %v", err)
			p.metrics.RecordDynamoFailure()
			return
		}
		p.metrics.RecordDynamoSuccess()
	}

	p.logger.Info("Successfully processed pending betting offer %s with market type %s",
		pendingOffer.Offer.ID, marketDescription)
}

// IsTargetBookmaker checks if a bookmaker ID is in the target list
func (p *OddsProcessor) IsTargetBookmaker(bookmakerID string) bool {
	return p.targetBookmakerIDs[bookmakerID]
}

// SetQueue sets the queue for the processor
func (p *OddsProcessor) SetQueue(q *queue.Queue) {
	p.queue = q
}

// Extract event information from couponKey
func extractEventFromCouponKey(couponKey string) (string, string, string) {
	// Skip empty coupon keys
	if couponKey == "" {
		return "", "", ""
	}

	// Clean up the coupon key
	couponKey = strings.TrimSpace(couponKey)

	// Handle different coupon key formats

	// Format: "/evento/calcio/ita-serie-a/juventus-genoa"
	if strings.HasPrefix(couponKey, "/evento/") {
		parts := strings.Split(couponKey, "/")
		cleanParts := []string{}
		for _, part := range parts {
			if part != "" {
				cleanParts = append(cleanParts, part)
			}
		}

		// Check if we have enough parts
		if len(cleanParts) < 4 {
			return "", "", ""
		}

		// Extract league and match
		league := cleanParts[2]
		matchPart := cleanParts[3]

		// Process match part
		matchTeams := strings.Split(matchPart, "-")
		if len(matchTeams) < 2 {
			return matchPart, matchPart, league
		}

		// Format team names
		homeTeam := strings.ToTitle(matchTeams[0])
		awayTeam := strings.ToTitle(matchTeams[1])

		eventName := fmt.Sprintf("%s vs %s", homeTeam, awayTeam)
		return matchPart, eventName, league
	}

	// Format: "&bs=170788949-287367663~3/1~0&bet=1"
	if strings.Contains(couponKey, "&bs=") {
		// Extract the match ID from this format
		startIdx := strings.Index(couponKey, "&bs=")
		if startIdx >= 0 {
			parts := strings.Split(couponKey[startIdx+4:], "-")
			if len(parts) >= 2 {
				matchID := parts[0]
				// We don't have team names in this format, so use match ID for both
				return matchID, matchID, ""
			}
		}
	}

	// Handle other formats
	// ...

	// Default: couldn't parse
	return "", "", ""
}

// Process processes the parsed XML data
func (p *OddsProcessor) Process(data *parser.OddsData) error {
	now := time.Now()
	startTime := time.Now()

	// First, store any outcomes we find for future reference
	if len(data.Outcomes) > 0 {
		p.logger.Info("Storing %d outcomes for future reference", len(data.Outcomes))
		for _, outcome := range data.Outcomes {
			p.outcomeStore.StoreOutcome(outcome)
		}
	}

	// Also store any odds providers we find
	if len(data.OddsProviders) > 0 {
		p.logger.Info("Storing %d odds providers for future reference", len(data.OddsProviders))
		for _, provider := range data.OddsProviders {
			p.outcomeStore.StoreProvider(provider.ID, provider.Name)
		}
	}

	// Track live odds metrics separately
	liveOffersProcessed := 0

	p.logger.Info("Processing odds data with %d betting offers, %d outcomes (isLiveData: %v)",
		len(data.BettingOffers), len(data.Outcomes), data.LiveOdds)

	// Keep count of offers processed
	processed := 0
	skipped := 0
	skippedNoMarketInfo := 0
	filteredByBookmaker := 0
	queuedAsPending := 0

	// Build a map of events for filtering and easy lookup of event details
	eventDetails := make(map[string]models.Event)
	for _, event := range data.Events {
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
			// Try to find the event ID via stored outcomes
			outcome, found := p.outcomeStore.GetOutcome(outcomeID)
			if found && outcome.Object == "event" {
				eventID = outcome.ObjectFK
			}
		}

		// If eventID is still empty, try to extract it from couponKey
		if eventID == "" && offer.CouponKey != "" {
			matchId, eventName, _ := extractEventFromCouponKey(offer.CouponKey)
			if matchId != "" {
				// Use matchId as eventID
				eventID = matchId
				p.logger.Debug("Using match ID %s from couponKey: %s", eventID, offer.CouponKey)

				// If we have the match name but no event in the database,
				// we can create a minimal event record
				if _, exists := eventDetails[eventID]; !exists {
					eventDetails[eventID] = models.Event{
						ID:        eventID,
						Name:      eventName,
						StartDate: time.Now().Format("2006-01-02 15:04:05"), // Approximate
					}
				}
			}
		}

		// Find the associated outcome
		var outcomeInfo models.Outcome

		// First try in the current data
		outcomeFound := false
		for _, outcome := range data.Outcomes {
			if outcome.ID == offer.OutcomeFK {
				outcomeInfo = outcome
				outcomeFound = true
				break
			}
		}

		// If not found in current data, try from our stored outcomes
		if !outcomeFound {
			outcome, found := p.outcomeStore.GetOutcome(offer.OutcomeFK)
			if found {
				outcomeInfo = outcome
				outcomeFound = true
			} else {
				// MODIFICATION: Instead of skipping, store as pending

				// Find provider name for the context
				var providerName string
				for _, provider := range data.OddsProviders {
					if provider.ID == offer.OddsProviderFK {
						providerName = provider.Name
						break
					}
				}

				// If provider name not found in current data, try from stored providers
				if providerName == "" {
					if name, found := p.outcomeStore.GetProvider(offer.OddsProviderFK); found {
						providerName = name
					} else {
						providerName = "Provider " + offer.OddsProviderFK
					}
				}

				// Get event details
				var eventName, eventStartDate string
				if event, exists := eventDetails[eventID]; exists {
					eventName = event.Name
					eventStartDate = event.StartDate
				} else if matchId, name, _ := extractEventFromCouponKey(offer.CouponKey); matchId != "" && matchId == eventID {
					eventName = name
					// Use current time as an approximation for start date if not available
					eventStartDate = time.Now().Format("2006-01-02 15:04:05")
				}

				// Store the betting offer as pending, even without an event ID: the outcome will give it
				p.outcomeStore.StorePendingOffer(offer, eventID, eventName, eventStartDate, providerName)
				queuedAsPending++
				continue
			}
		}

		// Skip if we still don't have an eventID. Checked after the outcome lookup, so that an offer
		// whose outcome has not arrived yet waits for it instead of being dropped.
		if eventID == "" {
			p.logger.Warn("Skipping betting offer %s: could not determine event ID", offer.ID)
			skipped++
			continue
		}

		// Find provider name
		var providerName string

		// First try in the current data
		for _, provider := range data.OddsProviders {
			if provider.ID == offer.OddsProviderFK {
				providerName = provider.Name
				break
			}
		}

		// If not found, try from our stored providers
		if providerName == "" {
			if name, found := p.outcomeStore.GetProvider(offer.OddsProviderFK); found {
				providerName = name
			} else {
				providerName = "Provider " + offer.OddsProviderFK
			}
		}

		// Lookup event details (name and start date)
		var eventName, eventStartDate string
		if event, exists := eventDetails[eventID]; exists {
			eventName = event.Name
			eventStartDate = event.StartDate
		} else if matchId, name, _ := extractEventFromCouponKey(offer.CouponKey); matchId == eventID {
			eventName = name
			// Use current time as an approximation for start date if not available
			eventStartDate = time.Now().Format("2006-01-02 15:04:05")
		}

		// Determine match status and additional info
		matchStatus := ""
		matchMinute := 0
		score := ""

		// Determine match status from event status type
		if eventID != "" {
			if event, exists := eventDetails[eventID]; exists {
				// Parse status information
				if event.StatusType == "playing" || event.StatusType == "inprogress" {
					matchStatus = "LIVE" // Default live status
				} else if event.StatusType == "notstarted" {
					matchStatus = "PREMATCH"
				} else if event.StatusType == "finished" {
					matchStatus = "FINISHED"
				}
			}
		}

		// Determine if this is a live odds update
		isLiveOdds := data.LiveOdds || offer.IsLive == "yes"

		// For more precise detection, check if the timestamp is after event start time
		if eventStartDate != "" {
			eventStartTime, _ := time.Parse("2006-01-02 15:04:05", eventStartDate)
			if now.After(eventStartTime) {
				isLiveOdds = true
			}
		}

		// Generate market description
		marketDescription := GetMarketDescription(
			outcomeInfo.OutcomeTypeFK,
			outcomeInfo.OutcomeSubtypeFK,
			outcomeInfo.OutcomeScopeFK,
			outcomeInfo.DParam)

		// Add team info from the iparam if available
		// This is common for markets like 1X2 where iparam is the team ID
		if (outcomeInfo.OutcomeTypeFK == 1 || outcomeInfo.OutcomeTypeFK == 2) &&
			outcomeInfo.OutcomeSubtypeFK == 1 && outcomeInfo.IParam > 0 {
			marketDescription += fmt.Sprintf(" (Team ID: %d)", outcomeInfo.IParam)
		}

		// Log detailed market information
		p.logger.Debug("Processing bet offer %s: Event: %s, Market: %s, Odds: %.2f",
			offer.ID, eventName, marketDescription, offer.Odds)

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
			MarketDescription:  marketDescription,
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
	p.metrics.SetCustomMetric("skipped_no_market_info", skippedNoMarketInfo)
	p.metrics.SetCustomMetric("filtered_by_bookmaker", filteredByBookmaker)
	p.metrics.SetCustomMetric("offers_queued_as_pending", queuedAsPending)
	p.metrics.SetCustomMetric("live_offers_processed", liveOffersProcessed)
	p.metrics.SetCustomMetric("outcome_store_size", p.outcomeStore.GetOutcomeCount())
	p.metrics.SetCustomMetric("pending_offers_count", p.outcomeStore.GetPendingOffersCount())

	p.logger.Info("Processed %d betting offers (%d live), skipped %d (filtered: %d by bookmaker), queued %d as pending (took %v)",
		processed, liveOffersProcessed, skipped, filteredByBookmaker, queuedAsPending, time.Since(startTime))

	return nil
}

// GetMetrics returns the processor metrics
func (p *OddsProcessor) GetMetrics() *metrics.Metrics {
	return p.metrics
}
