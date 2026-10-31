package models

import (
	"time"
)

// Outcome represents the outcome node in XML
type Outcome struct {
	ID               string  `json:"id"`
	Object           string  `json:"object"`
	ObjectFK         string  `json:"objectFK"`
	OutcomeTypeFK    int     `json:"outcome_typeFK"`
	OutcomeScopeFK   int     `json:"outcome_scopeFK"`
	OutcomeSubtypeFK int     `json:"outcome_subtypeFK"`
	IParam           int     `json:"iparam"`
	IParam2          int     `json:"iparam2"`
	DParam           float64 `json:"dparam"`
	DParam2          float64 `json:"dparam2"`
	SParam           string  `json:"sparam"`
	Del              string  `json:"del"`
	N                int     `json:"n"`
	UT               string  `json:"ut"`
}

// BettingOffer represents a betting offer node in XML
type BettingOffer struct {
	ID                   string    `json:"id"`
	OutcomeFK            string    `json:"outcomeFK"`
	OddsProviderFK       string    `json:"odds_providerFK"`
	BettingofferStatusFK int       `json:"bettingoffer_statusFK"`
	Odds                 float64   `json:"odds"`
	OddsOld              float64   `json:"odds_old"`
	Active               string    `json:"active"`
	IsBack               string    `json:"is_back"`
	IsSingle             string    `json:"is_single"`
	IsLive               string    `json:"is_live"`
	Volume               int       `json:"volume"`
	Currency             string    `json:"currency"`
	CouponKey            string    `json:"couponKey"`
	Del                  string    `json:"del"`
	N                    int       `json:"n"`
	UT                   string    `json:"ut"`
	ProviderName         string    `json:"provider_name"`
	Timestamp            time.Time `json:"timestamp"` // Added field for when we received/stored it
}

// OddsProvider represents an odds provider node in XML
type OddsProvider struct {
	ID        string `json:"id"`
	Name      string `json:"name"`
	URL       string `json:"url"`
	CountryFK string `json:"countryFK"`
	Bookmaker string `json:"bookmaker"`
	Preferred string `json:"preferred"`
	Betex     string `json:"betex"`
	Active    string `json:"active"`
	Del       string `json:"del"`
	N         int    `json:"n"`
	UT        string `json:"ut"`
}

// Event represents an event node in XML
type Event struct {
	ID                string `json:"id"`
	Name              string `json:"name"`
	TournamentStageFK string `json:"tournament_stageFK"`
	StartDate         string `json:"startdate"`
	EventStatusFK     string `json:"eventstatusFK"`
	StatusType        string `json:"status_type"`
	StatusDescFK      string `json:"status_descFK"`
	EnetID            string `json:"enetID"`
	EnetSportID       string `json:"enetSportID"`
	Del               string `json:"del"`
	Locked            string `json:"locked"`
	N                 int    `json:"n"`
	UT                string `json:"ut"`
}

// OddsUpdate represents an update to odds that we will store in DynamoDB
type OddsUpdate struct {
	EventID            string    `json:"eventId"`
	OutcomeID          string    `json:"outcomeId"`
	EventName          string    `json:"eventName"`
	EventStartDate     string    `json:"eventStartDate"`
	BettingOfferID     string    `json:"bettingOfferId"`
	ProviderID         string    `json:"providerId"`
	ProviderName       string    `json:"providerName"`
	Odds               float64   `json:"odds"`
	OddsOld            float64   `json:"oddsOld"`
	Active             string    `json:"active"`
	BettingOfferStatus int       `json:"bettingOfferStatus"`
	Timestamp          time.Time `json:"timestamp"`
	OutcomeTypeFK      int       `json:"outcomeTypeFK"`    // Tells you what type of market (1=1X2, 4=Over/Under)
	OutcomeSubtypeFK   int       `json:"outcomeSubtypeFK"` // Tells you which selection (1=win, 2=draw)
	OutcomeScopeFK     int       `json:"outcomeScopeFK"`   // Tells you time period (1=full match, 4=first half)
	IParam             int       `json:"iparam"`           // Often contains team ID for team-specific selections
	IsLiveOdds         bool      `json:"isLiveOdds"`       // Flags if this update is from in-play/live odds
	MatchStatus        string    `json:"matchStatus"`      // Current match status (e.g., "1H", "HT", "2H")
	MatchMinute        int       `json:"matchMinute"`      // Current match minute when odds were updated
	Score              string    `json:"score"`
}
