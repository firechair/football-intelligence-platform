package parser

import (
	"strings"
	"testing"
)

type quietLogger struct{}

func (quietLogger) Debug(string, ...interface{})          {}
func (quietLogger) Info(string, ...interface{})           {}
func (quietLogger) Warn(string, ...interface{})           {}
func (quietLogger) Error(string, ...interface{})          {}
func (quietLogger) ErrorWithStack(string, ...interface{}) {}

// A push in the provider's format: every value is an attribute. Data is synthetic.
const pushUpdate = `<?xml version="1.0" encoding="UTF-8"?>
<spocosy version="1.0">
<subscription-update subscriptionid="1" requestid="1" last_push="2025-03-20 17:00:00" current_push="2025-03-20 17:00:05" exec="0.01">
<event id="9001" name="Inter-AC Milan" tournament_stageFK="1001" startdate="2099-03-22 20:45:00" status_type="notstarted" n="1" del="no"/>
<outcome id="5001" object="event" objectFK="9001" outcome_typeFK="1" outcome_scopeFK="1" outcome_subtypeFK="1" iparam="43" n="2" del="no"/>
<odds_provider id="16" name="Bookmaker A" active="yes" n="1" del="no"/>
<bettingoffer id="7001" outcomeFK="5001" odds_providerFK="16" odds="2.10" odds_old="2.05" active="yes" is_live="no" n="3" del="no"/>
</subscription-update>
</spocosy>`

func TestReadsEveryAttributeOfAPushUpdate(t *testing.T) {
	data, err := ParseWithLogger([]byte(pushUpdate), quietLogger{})
	if err != nil {
		t.Fatal(err)
	}
	if len(data.BettingOffers) != 1 || len(data.Outcomes) != 1 || len(data.Events) != 1 || len(data.OddsProviders) != 1 {
		t.Fatalf("got %d offers, %d outcomes, %d events, %d providers", len(data.BettingOffers), len(data.Outcomes), len(data.Events), len(data.OddsProviders))
	}
	offer := data.BettingOffers[0]
	if offer.Odds != 2.10 || offer.OddsOld != 2.05 || offer.OutcomeFK != "5001" || offer.OddsProviderFK != "16" {
		t.Errorf("offer read as %+v", offer)
	}
	outcome := data.Outcomes[0]
	if outcome.ObjectFK != "9001" || outcome.OutcomeTypeFK != 1 || outcome.N != 2 {
		t.Errorf("outcome read as %+v", outcome)
	}
	if data.Events[0].Name != "Inter-AC Milan" || data.OddsProviders[0].Name != "Bookmaker A" {
		t.Errorf("event %+v, provider %+v", data.Events[0], data.OddsProviders[0])
	}
}

// The first version, committed on 2025-03-18, read this format with every value empty.
func TestReadsAttributesInTheQueryResponseFormat(t *testing.T) {
	doc := `<query-response><outcome id="5001" object="event" objectFK="9001" outcome_typeFK="1"/>` +
		`<bettingoffer id="7001" outcomeFK="5001" odds_providerFK="16" odds="2.10"/></query-response>`
	data, err := ParseWithLogger([]byte(doc), quietLogger{})
	if err != nil {
		t.Fatal(err)
	}
	if offer := data.BettingOffers[0]; offer.Odds != 2.10 || offer.OutcomeFK != "5001" {
		t.Errorf("offer read as %+v", offer)
	}
}

func TestExtractsTheXMLFromAMultipartBody(t *testing.T) {
	body := "--b\r\nContent-Disposition: form-data; name=\"xml\"\r\n\r\n" + pushUpdate + "\r\n--b--\r\n"
	data, err := ParseWithLogger([]byte(body), quietLogger{})
	if err != nil {
		t.Fatal(err)
	}
	if len(data.BettingOffers) != 1 {
		t.Fatalf("got %d offers", len(data.BettingOffers))
	}
}

func TestAnUpdateWithOnlyPropertiesIsNotAnError(t *testing.T) {
	doc := `<spocosy version="1.0"><subscription-update subscriptionid="1">` +
		`<property id="1" object="event" objectFK="9001" name="Round" value="29"/></subscription-update></spocosy>`
	data, err := ParseWithLogger([]byte(doc), quietLogger{})
	if err != nil {
		t.Fatal(err)
	}
	if len(data.BettingOffers) != 0 {
		t.Errorf("got %d offers", len(data.BettingOffers))
	}
}

func TestRejectsAnUnknownFormat(t *testing.T) {
	_, err := ParseWithLogger([]byte(`<weather city="Rome"/>`), quietLogger{})
	if err == nil || !strings.Contains(err.Error(), "weather") {
		t.Fatalf("got %v", err)
	}
}
