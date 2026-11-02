// internal/parser/xml_parser.go
package parser

import (
	"bytes"
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

// SpocosyUpdate represents the Spocosy XML format
type SpocosyUpdate struct {
	XMLName            xml.Name           `xml:"spocosy"`
	Version            string             `xml:"version,attr"`
	SubscriptionUpdate SubscriptionUpdate `xml:"subscription-update"`
}

// SubscriptionUpdate represents the subscription-update element in Spocosy format
type SubscriptionUpdate struct {
	XMLName        xml.Name              `xml:"subscription-update"`
	SubscriptionID string                `xml:"subscriptionid,attr"`
	RequestID      string                `xml:"requestid,attr"`
	LastPush       string                `xml:"last_push,attr"`
	CurrentPush    string                `xml:"current_push,attr"`
	Exec           string                `xml:"exec,attr"`
	Properties     []Property            `xml:"property"`
	BettingOffers  []models.BettingOffer `xml:"bettingoffer"`
	Outcomes       []models.Outcome      `xml:"outcome"`
	Events         []models.Event        `xml:"event"`
	OddsProviders  []models.OddsProvider `xml:"odds_provider"`
}

// Property represents a property element in Spocosy format
type Property struct {
	ID       string `xml:"id,attr"`
	Object   string `xml:"object,attr"`
	ObjectFK string `xml:"objectFK,attr"`
	Type     string `xml:"type,attr"`
	Name     string `xml:"name,attr"`
	Value    string `xml:"value,attr"`
	N        string `xml:"n,attr"`
	UT       string `xml:"ut,attr"`
	Del      string `xml:"del,attr"`
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
	// Check if this is multipart form data
	if bytes.Contains(xmlData, []byte("Content-Disposition: form-data")) {
		logger.Info("Detected multipart form data, extracting XML content")

		// Look for the XML content
		startTag := []byte("<?xml")
		start := bytes.Index(xmlData, startTag)
		if start == -1 {
			return nil, fmt.Errorf("no XML content found in multipart data")
		}

		// Find the end of the XML by looking for the next boundary
		// Try different boundary patterns
		possibleBoundaries := [][]byte{
			[]byte("\r\n--"),
			[]byte("\n--"),
			[]byte("--"),
		}

		end := len(xmlData)
		for _, boundary := range possibleBoundaries {
			boundaryIndex := bytes.Index(xmlData[start:], boundary)
			if boundaryIndex != -1 {
				end = start + boundaryIndex
				logger.Info("Found boundary at offset %d from XML start", boundaryIndex)
				break
			}
		}

		// Extract just the XML content
		xmlData = xmlData[start:end]
		logger.Info("Extracted XML content of length %d bytes", len(xmlData))
	}

	// Try as spocosy format first
	var spocosyData SpocosyUpdate
	err := xml.Unmarshal(xmlData, &spocosyData)

	logger.Debug("After unmarshaling, XML root name: %s", spocosyData.XMLName.Local)

	// Check if it's a valid spocosy format
	if err == nil && spocosyData.XMLName.Local == "spocosy" {
		logger.Info("Detected spocosy XML format with subscription ID: %s",
			spocosyData.SubscriptionUpdate.SubscriptionID)

		// Convert spocosy data to OddsData
		result := &OddsData{
			BettingOffers: spocosyData.SubscriptionUpdate.BettingOffers,
			Outcomes:      spocosyData.SubscriptionUpdate.Outcomes,
			Events:        spocosyData.SubscriptionUpdate.Events,
			OddsProviders: spocosyData.SubscriptionUpdate.OddsProviders,
			LiveOdds:      false, // Determine if this is live odds
		}

		logger.Info("Extracted %d betting offers, %d outcomes, %d events from spocosy format",
			len(result.BettingOffers), len(result.Outcomes), len(result.Events))

		// If there are no betting offers or outcomes but there are properties,
		// we'll consider this a successful parse but with no actionable data
		if len(result.BettingOffers) == 0 && len(result.Outcomes) == 0 && len(result.Events) == 0 {
			if len(spocosyData.SubscriptionUpdate.Properties) > 0 {
				logger.Info("No betting offers, outcomes, or events found in spocosy update, but %d properties found",
					len(spocosyData.SubscriptionUpdate.Properties))
			} else {
				logger.Info("Empty spocosy update received - this may contain only metadata")
			}

			// Return an empty result but don't consider it an error
			return &OddsData{
				BettingOffers: []models.BettingOffer{},
				Outcomes:      []models.Outcome{},
				Events:        []models.Event{},
				OddsProviders: []models.OddsProvider{},
				LiveOdds:      false,
			}, nil
		}

		return validateOddsData(result, logger)
	} else if err != nil {
		logger.Warn("Failed to parse as spocosy format: %v", err)
	}

	// Continue with other formats as before...
	// Try as query-response format
	var queryResp QueryResponse
	err = xml.Unmarshal(xmlData, &queryResp)

	// Check if it's a valid query-response
	if err == nil && (len(queryResp.BettingOffers) > 0 || len(queryResp.Outcomes) > 0 ||
		len(queryResp.OddsProviders) > 0 || len(queryResp.Events) > 0 ||
		len(queryResp.LiveOutcomes) > 0 || len(queryResp.LiveBettingOffers) > 0) {

		logger.Info("Detected query-response XML format with %d betting offers, %d outcomes, %d providers, %d events, %d live outcomes, %d live betting offers",
			len(queryResp.BettingOffers), len(queryResp.Outcomes), len(queryResp.OddsProviders),
			len(queryResp.Events), len(queryResp.LiveOutcomes), len(queryResp.LiveBettingOffers))

		// Process query-response format...
		// (existing code)

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
	} else if err != nil {
		logger.Warn("Failed to parse as query-response format: %v", err)
	}

	// Try object feed format as a last resort
	var objectFeed ObjectFeed
	err = xml.Unmarshal(xmlData, &objectFeed)

	// Check if it's a valid object feed
	if err == nil && objectFeed.XMLName.Local == "sport" {
		logger.Info("Detected object feed XML format for sport: %s", objectFeed.Sport.Name)

		// Construct the result from object feed
		result := extractDataFromObjectFeed(&objectFeed, logger)
		return validateOddsData(result, logger)
	} else if err != nil {
		logger.Warn("Failed to parse as object feed format: %v", err)
	}

	// If all parsing attempts fail, log the raw XML for debugging
	// Truncate for logging if it's very large
	xmlToLog := xmlData
	if len(xmlData) > 1000 {
		xmlToLog = xmlData[:1000]
	}
	logger.Error("Failed to parse XML with any known format. First 1000 bytes: %s", string(xmlToLog))

	// Look for the root element to provide a better error message
	rootStart := bytes.Index(xmlData, []byte("<"))
	if rootStart != -1 {
		endOfTag := bytes.Index(xmlData[rootStart:], []byte(">"))
		if endOfTag != -1 && endOfTag > 1 {
			tag := string(xmlData[rootStart+1 : rootStart+endOfTag])
			spaceIndex := strings.Index(tag, " ")
			if spaceIndex != -1 {
				tag = tag[:spaceIndex]
			}
			return nil, fmt.Errorf("unsupported XML format with root element '%s'", tag)
		}
	}

	return nil, fmt.Errorf("invalid or unsupported XML format")
}

// Parse maintains backward compatibility
func Parse(xmlData []byte) (*OddsData, error) {
	// Create a simple logger that prints to stdout/stderr
	logger := logging.NewStandardLogger()
	return ParseWithLogger(xmlData, logger)
}

// validateOddsData performs additional validation on the parsed data
func validateOddsData(data *OddsData, logger logging.Logger) (*OddsData, error) {
	// Log what we found
	logger.Info("Validating parsed data: %d betting offers, %d outcomes, %d events, %d providers",
		len(data.BettingOffers), len(data.Outcomes), len(data.Events), len(data.OddsProviders))

	// Warn if we're missing some data types
	if len(data.BettingOffers) == 0 {
		logger.Warn("No betting offers found in XML data")
	}

	if len(data.Outcomes) == 0 {
		logger.Warn("No outcomes found in XML data")
	}

	// Check that betting offers reference valid outcomes, if we have both
	if len(data.BettingOffers) > 0 && len(data.Outcomes) > 0 {
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
	}

	// Even if we don't have both betting offers and outcomes, we still want to process
	// what we have - the rest might come in later updates
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
