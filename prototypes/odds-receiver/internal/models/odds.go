package models

import (
	"time"
)

// Outcome represents the outcome node in XML
type Outcome struct {
    ID               string  `xml:"id,attr" json:"id"`
    Object           string  `xml:"object,attr" json:"object"`
    ObjectFK         string  `xml:"objectFK,attr" json:"objectFK"`
    OutcomeTypeFK    int     `xml:"outcome_typeFK,attr" json:"outcome_typeFK"`
    OutcomeScopeFK   int     `xml:"outcome_scopeFK,attr" json:"outcome_scopeFK"`
    OutcomeSubtypeFK int     `xml:"outcome_subtypeFK,attr" json:"outcome_subtypeFK"`
    IParam           int     `xml:"iparam,attr" json:"iparam"`
    IParam2          int     `xml:"iparam2,attr" json:"iparam2"`
    DParam           float64 `xml:"dparam,attr" json:"dparam"`
    DParam2          float64 `xml:"dparam2,attr" json:"dparam2"`
    SParam           string  `xml:"sparam,attr" json:"sparam"`
    Del              string  `xml:"del,attr" json:"del"`
    N                int     `xml:"n,attr" json:"n"`
    UT               string  `xml:"ut,attr" json:"ut"`
}

// BettingOffer represents a betting offer node in XML
type BettingOffer struct {
    ID                   string    `xml:"id,attr" json:"id"`
    OutcomeFK            string    `xml:"outcomeFK,attr" json:"outcomeFK"`
    OddsProviderFK       string    `xml:"odds_providerFK,attr" json:"odds_providerFK"`
    BettingofferStatusFK int       `xml:"bettingoffer_statusFK,attr" json:"bettingoffer_statusFK"`
    Odds                 float64   `xml:"odds,attr" json:"odds"`
    OddsOld              float64   `xml:"odds_old,attr" json:"odds_old"`
    Active               string    `xml:"active,attr" json:"active"`
    IsBack               string    `xml:"is_back,attr" json:"is_back"`
    IsSingle             string    `xml:"is_single,attr" json:"is_single"`
    IsLive               string    `xml:"is_live,attr" json:"is_live"`
    Volume               int       `xml:"volume,attr" json:"volume"`
    Currency             string    `xml:"currency,attr" json:"currency"`
    CouponKey            string    `xml:"couponKey,attr" json:"couponKey"`
    Del                  string    `xml:"del,attr" json:"del"`
    N                    int       `xml:"n,attr" json:"n"`
    UT                   string    `xml:"ut,attr" json:"ut"`
    ProviderName         string    `json:"provider_name"` // Not in XML, filled in later
    Timestamp            time.Time `json:"timestamp"`     // Not in XML, filled in later
}

// OddsProvider represents an odds provider node in XML
type OddsProvider struct {
    ID        string `xml:"id,attr" json:"id"`
    Name      string `xml:"name,attr" json:"name"`
    URL       string `xml:"url,attr" json:"url"`
    CountryFK string `xml:"countryFK,attr" json:"countryFK"`
    Bookmaker string `xml:"bookmaker,attr" json:"bookmaker"`
    Preferred string `xml:"preferred,attr" json:"preferred"`
    Betex     string `xml:"betex,attr" json:"betex"`
    Active    string `xml:"active,attr" json:"active"`
    Del       string `xml:"del,attr" json:"del"`
    N         int    `xml:"n,attr" json:"n"`
    UT        string `xml:"ut,attr" json:"ut"`
}

// Event represents an event node in XML
type Event struct {
    ID                string `xml:"id,attr" json:"id"`
    Name              string `xml:"name,attr" json:"name"`
    TournamentStageFK string `xml:"tournament_stageFK,attr" json:"tournament_stageFK"`
    StartDate         string `xml:"startdate,attr" json:"startdate"`
    EventStatusFK     string `xml:"eventstatusFK,attr" json:"eventstatusFK"`
    StatusType        string `xml:"status_type,attr" json:"status_type"`
    StatusDescFK      string `xml:"status_descFK,attr" json:"status_descFK"`
    EnetID            string `xml:"enetID,attr" json:"enetID"`
    EnetSportID       string `xml:"enetSportID,attr" json:"enetSportID"`
    Del               string `xml:"del,attr" json:"del"`
    Locked            string `xml:"locked,attr" json:"locked"`
    N                 int    `xml:"n,attr" json:"n"`
    UT                string `xml:"ut,attr" json:"ut"`
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
	OutcomeTypeFK      int       `json:"outcomeTypeFK"`    // Market type (1=1X2, 4=Over/Under)
	OutcomeSubtypeFK   int       `json:"outcomeSubtypeFK"` // Selection type (1=win, 2=draw)
	OutcomeScopeFK     int       `json:"outcomeScopeFK"`   // Time period (1=full match, 4=first half)
	IParam             int       `json:"iparam"`           // Often contains team ID for team-specific selections
	IsLiveOdds         bool      `json:"isLiveOdds"`       // Flags if this update is from in-play/live odds
	MatchStatus        string    `json:"matchStatus"`      // Current match status (e.g., "1H", "HT", "2H")
	MatchMinute        int       `json:"matchMinute"`      // Current match minute when odds were updated
	Score              string    `json:"score"`            // Current score if available
	MarketDescription  string    `json:"marketDescription"` // Human-readable market description
}
