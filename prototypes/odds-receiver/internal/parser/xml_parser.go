// internal/parser/xml_parser.go
package parser

import (
	"encoding/xml"
	"fmt"
	"strings"

	"github.com/firechair/odds-receiver/internal/logging"
	"github.com/firechair/odds-receiver/internal/models"
)

// OddsData represents the structured data extracted from XML
type OddsData struct {
	BettingOffers []models.BettingOffer
	Outcomes      []models.Outcome
	OddsProviders []models.OddsProvider
	Events        []models.Event
	LiveOdds      bool // Flag indicating if this is live odds data
}

// QueryResponse represents the flat XML structure (original format)
type QueryResponse struct {
	XMLName           xml.Name              `xml:"query-response"`
	BettingOffers     []models.BettingOffer `xml:"bettingoffer"`
	Outcomes          []models.Outcome      `xml:"outcome"`
	LiveOutcomes      []models.Outcome      `xml:"liveodds_outcome"`
	OddsProviders     []models.OddsProvider `xml:"odds_provider"`
	Events            []models.Event        `xml:"event"`
	LiveBettingOffers []models.BettingOffer `xml:"liveodds_bettingoffer"`
}

// ObjectFeed represents the nested XML structure
type ObjectFeed struct {
	XMLName xml.Name     `xml:"sport"`
	Sport   SportElement `xml:",any"`
}

// SportElement represents a sport in the nested structure
type SportElement struct {
	ID               string              `xml:"id,attr"`
	Name             string              `xml:"name,attr"`
	Tournaments      []TournamentElement `xml:"tournament_template>tournament"`
	TournamentStages []TournamentStage   `xml:"tournament_stage"`
	Events           []EventElement      `xml:"event"`
}

// TournamentElement represents a tournament in the nested structure
type TournamentElement struct {
	ID               string            `xml:"id,attr"`
	Name             string            `xml:"name,attr"`
	TournamentStages []TournamentStage `xml:"tournament_stage"`
}

// TournamentStage represents a tournament stage in the nested structure
type TournamentStage struct {
	ID     string         `xml:"id,attr"`
	Name   string         `xml:"name,attr"`
	Events []EventElement `xml:"event"`
}

// EventElement represents an event in the nested structure
type EventElement struct {
	ID                string             `xml:"id,attr"`
	Name              string             `xml:"name,attr"`
	StartDate         string             `xml:"startdate,attr"`
	TournamentStageFK string             `xml:"tournament_stageFK,attr"`
	StatusType        string             `xml:"status_type,attr"`
	EventParticipants []EventParticipant `xml:"event_participant"`
	Outcomes          []models.Outcome   `xml:"outcome"`
}

// EventParticipant represents an event participant in the nested structure
type EventParticipant struct {
	ID            string                `xml:"id,attr"`
	Number        string                `xml:"number,attr"`
	ParticipantFK string                `xml:"participantFK,attr"`
	EventFK       string                `xml:"eventFK,attr"`
	BettingOffers []models.BettingOffer `xml:"bettingoffer"`
}

// ParseWithLogger parses XML data with improved validation and structure detection
func ParseWithLogger(xmlData []byte, logger logging.Logger) (*OddsData, error) {
	// First try as query-response format
	var queryResp QueryResponse
	err := xml.Unmarshal(xmlData, &queryResp)

	// Check if it's a valid query-response
	if err == nil && (len(queryResp.BettingOffers) > 0 || len(queryResp.Outcomes) > 0 ||
		len(queryResp.OddsProviders) > 0 || len(queryResp.Events) > 0 ||
		len(queryResp.LiveOutcomes) > 0 || len(queryResp.LiveBettingOffers) > 0) {

		logger.Info("Detected query-response XML format with %d betting offers, %d outcomes, %d providers, %d events, %d live outcomes, %d live betting offers",
			len(queryResp.BettingOffers), len(queryResp.Outcomes), len(queryResp.OddsProviders),
			len(queryResp.Events), len(queryResp.LiveOutcomes), len(queryResp.LiveBettingOffers))

		// If no data found, return an error
		if len(queryResp.BettingOffers) == 0 && len(queryResp.Outcomes) == 0 &&
			len(queryResp.LiveOutcomes) == 0 && len(queryResp.LiveBettingOffers) == 0 {
			logger.Warn("No betting offers or outcomes found in XML data")
		}

		isLiveOdds := len(queryResp.LiveOutcomes) > 0 || len(queryResp.LiveBettingOffers) > 0

		// Construct the result from query-response
		result := &OddsData{
			BettingOffers: queryResp.BettingOffers,
			Outcomes:      queryResp.Outcomes,
			OddsProviders: queryResp.OddsProviders,
			Events:        queryResp.Events,
			LiveOdds:      isLiveOdds,
		}

		// Add live data if present
		if isLiveOdds {
			logger.Info("Processing live odds data with %d outcomes and %d betting offers",
				len(queryResp.LiveOutcomes), len(queryResp.LiveBettingOffers))

			// Simply append the live data to the result
			result.Outcomes = append(result.Outcomes, queryResp.LiveOutcomes...)
			result.BettingOffers = append(result.BettingOffers, queryResp.LiveBettingOffers...)
		}

		return validateOddsData(result, logger)
	}

	// If not query-response, try object feed format
	var objectFeed ObjectFeed
	err = xml.Unmarshal(xmlData, &objectFeed)

	// Check if it's a valid object feed
	if err == nil && objectFeed.XMLName.Local == "sport" {
		logger.Info("Detected object feed XML format for sport: %s", objectFeed.Sport.Name)

		// Construct the result from object feed
		result := extractDataFromObjectFeed(&objectFeed, logger)
		return validateOddsData(result, logger)
	}

	// Try one more approach - look for root element
	var root struct {
		XMLName xml.Name
	}

	if err := xml.Unmarshal(xmlData, &root); err == nil {
		return nil, fmt.Errorf("unsupported XML format with root element '%s'", root.XMLName.Local)
	}

	// If we get here, the XML is invalid or in an unsupported format
	return nil, fmt.Errorf("invalid or unsupported XML format: %w", err)
}

// Parse maintains backward compatibility
func Parse(xmlData []byte) (*OddsData, error) {
	// Create a simple logger that prints to stdout/stderr
	logger := logging.NewStandardLogger()
	return ParseWithLogger(xmlData, logger)
}

// validateOddsData performs additional validation on the parsed data
func validateOddsData(data *OddsData, logger logging.Logger) (*OddsData, error) {
	// Check that we have some essential data
	if len(data.BettingOffers) == 0 {
		logger.Warn("No betting offers found in XML data")
	}

	if len(data.Outcomes) == 0 {
		logger.Warn("No outcomes found in XML data")
	}

	if len(data.BettingOffers) == 0 && len(data.Outcomes) == 0 {
		return nil, fmt.Errorf("no valid betting offers or outcomes found in XML data")
	}

	// Check that betting offers reference valid outcomes
	outcomeMap := make(map[string]bool)
	for _, outcome := range data.Outcomes {
		outcomeMap[outcome.ID] = true
	}

	var invalidOffers []string
	for _, offer := range data.BettingOffers {
		if offer.OutcomeFK != "" && !outcomeMap[offer.OutcomeFK] {
			invalidOffers = append(invalidOffers, offer.ID)
		}
	}

	if len(invalidOffers) > 0 {
		// Log the issue but don't stop processing
		if len(invalidOffers) > 10 {
			logger.Warn("%d betting offers reference non-existent outcomes. First 10: %v",
				len(invalidOffers), strings.Join(invalidOffers[:10], ", "))
		} else {
			logger.Warn("%d betting offers reference non-existent outcomes: %v",
				len(invalidOffers), strings.Join(invalidOffers, ", "))
		}
	}

	// Add more data validation as needed

	return data, nil
}

// extractDataFromObjectFeed extracts structured data from the nested object feed format
func extractDataFromObjectFeed(feed *ObjectFeed, logger logging.Logger) *OddsData {
	result := &OddsData{
		BettingOffers: []models.BettingOffer{},
		Outcomes:      []models.Outcome{},
		OddsProviders: []models.OddsProvider{},
		Events:        []models.Event{},
	}

	// Extract events directly from sport
	for _, event := range feed.Sport.Events {
		// Add the event
		resultEvent := models.Event{
			ID:                event.ID,
			Name:              event.Name,
			StartDate:         event.StartDate,
			TournamentStageFK: event.TournamentStageFK,
			StatusType:        event.StatusType,
		}
		result.Events = append(result.Events, resultEvent)

		// Extract outcomes
		result.Outcomes = append(result.Outcomes, event.Outcomes...)

		// Extract betting offers from event participants
		for _, participant := range event.EventParticipants {
			// No need to add participants to the result, just extract betting offers
			// result.ParticipantFK = append(result.ParticipantFK, participant)

			// Add betting offers if any
			if len(participant.BettingOffers) > 0 {
				result.BettingOffers = append(result.BettingOffers, participant.BettingOffers...)
			}
		}
	}

	// Extract events from tournament stages
	for _, stage := range feed.Sport.TournamentStages {
		for _, event := range stage.Events {
			// Add the event
			resultEvent := models.Event{
				ID:                event.ID,
				Name:              event.Name,
				StartDate:         event.StartDate,
				TournamentStageFK: stage.ID, // Use the parent stage ID
				StatusType:        event.StatusType,
			}
			result.Events = append(result.Events, resultEvent)

			// Extract outcomes
			result.Outcomes = append(result.Outcomes, event.Outcomes...)

			// Extract betting offers from event participants
			for _, participant := range event.EventParticipants {
				// Add betting offers if any
				if len(participant.BettingOffers) > 0 {
					result.BettingOffers = append(result.BettingOffers, participant.BettingOffers...)
				}
			}
		}
	}

	// Extract events from tournaments
	for _, tournament := range feed.Sport.Tournaments {
		for _, stage := range tournament.TournamentStages {
			for _, event := range stage.Events {
				// Add the event
				resultEvent := models.Event{
					ID:                event.ID,
					Name:              event.Name,
					StartDate:         event.StartDate,
					TournamentStageFK: stage.ID, // Use the parent stage ID
					StatusType:        event.StatusType,
				}
				result.Events = append(result.Events, resultEvent)

				// Extract outcomes
				result.Outcomes = append(result.Outcomes, event.Outcomes...)

				// Extract betting offers from event participants
				for _, participant := range event.EventParticipants {
					// Add betting offers if any
					if len(participant.BettingOffers) > 0 {
						result.BettingOffers = append(result.BettingOffers, participant.BettingOffers...)
					}
				}
			}
		}
	}

	// Log summary
	logger.Info("Extracted %d events, %d outcomes, %d betting offers from object feed",
		len(result.Events), len(result.Outcomes), len(result.BettingOffers))

	return result
}
