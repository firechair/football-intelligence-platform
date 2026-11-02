package processor

import (
	"strings"
	"sync"
	"testing"

	"github.com/firechair/odds-receiver/internal/metrics"
	"github.com/firechair/odds-receiver/internal/models"
	"github.com/firechair/odds-receiver/internal/parser"
	"github.com/firechair/odds-receiver/internal/storage"
)

type quietLogger struct{}

func (quietLogger) Debug(string, ...interface{})          {}
func (quietLogger) Info(string, ...interface{})           {}
func (quietLogger) Warn(string, ...interface{})           {}
func (quietLogger) Error(string, ...interface{})          {}
func (quietLogger) ErrorWithStack(string, ...interface{}) {}

// memoryStorage stands in for DynamoDB.
type memoryStorage struct {
	mu      sync.Mutex
	updates []*models.OddsUpdate
}

func (m *memoryStorage) StoreOddsUpdate(u *models.OddsUpdate) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.updates = append(m.updates, u)
	return nil
}
func (m *memoryStorage) GetOddsHistoryForEvent(string) ([]*models.OddsUpdate, error) { return nil, nil }
func (m *memoryStorage) GetOddsHistoryForBettingOffer(string) ([]*models.OddsUpdate, error) {
	return nil, nil
}
func (m *memoryStorage) Shutdown()                    {}
func (m *memoryStorage) GetMetrics() *metrics.Metrics { return metrics.NewMetrics(quietLogger{}) }

func (m *memoryStorage) stored() []*models.OddsUpdate {
	m.mu.Lock()
	defer m.mu.Unlock()
	return append([]*models.OddsUpdate(nil), m.updates...)
}

func newProcessor(t *testing.T) (*OddsProcessor, *memoryStorage, *storage.OutcomeStore) {
	t.Helper()
	store := &memoryStorage{}
	outcomes, err := storage.NewOutcomeStore(t.TempDir(), quietLogger{})
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(outcomes.Shutdown)
	p := NewOddsProcessor(store, quietLogger{}, []string{"16"})
	p.SetOutcomeStore(outcomes)
	return p, store, outcomes
}

var (
	match    = models.Event{ID: "9001", Name: "Inter-AC Milan", StartDate: "2099-03-22 20:45:00", StatusType: "notstarted"}
	homeWin  = models.Outcome{ID: "5001", Object: "event", ObjectFK: "9001", OutcomeTypeFK: 1, OutcomeSubtypeFK: 1, OutcomeScopeFK: 1, N: 1}
	provider = models.OddsProvider{ID: "16", Name: "Bookmaker A"}
)

func offer(id, outcomeID, providerID string) models.BettingOffer {
	return models.BettingOffer{ID: id, OutcomeFK: outcomeID, OddsProviderFK: providerID, Odds: 2.10, OddsOld: 2.05, Active: "yes", IsLive: "no"}
}

func TestAnOfferWithAKnownOutcomeIsStored(t *testing.T) {
	p, store, _ := newProcessor(t)
	err := p.Process(&parser.OddsData{
		Events: []models.Event{match}, Outcomes: []models.Outcome{homeWin},
		OddsProviders: []models.OddsProvider{provider}, BettingOffers: []models.BettingOffer{offer("7001", "5001", "16")},
	})
	if err != nil {
		t.Fatal(err)
	}
	got := store.stored()
	if len(got) != 1 {
		t.Fatalf("stored %d updates", len(got))
	}
	u := got[0]
	if u.EventID != "9001" || u.EventName != "Inter-AC Milan" || u.ProviderName != "Bookmaker A" || u.Odds != 2.10 {
		t.Errorf("stored %+v", u)
	}
	if !strings.HasPrefix(u.MarketDescription, "1X2 - Home Win") || u.IsLiveOdds {
		t.Errorf("market %q, live %v", u.MarketDescription, u.IsLiveOdds)
	}
}

func TestDeletedInactiveAndUntrackedOffersAreSkipped(t *testing.T) {
	p, store, _ := newProcessor(t)
	deleted, inactive := offer("7001", "5001", "16"), offer("7002", "5001", "16")
	deleted.Del, inactive.Active = "yes", "no"
	err := p.Process(&parser.OddsData{
		Events: []models.Event{match}, Outcomes: []models.Outcome{homeWin},
		BettingOffers: []models.BettingOffer{deleted, inactive, offer("7003", "5001", "99")},
	})
	if err != nil {
		t.Fatal(err)
	}
	if n := len(store.stored()); n != 0 {
		t.Fatalf("stored %d updates", n)
	}
}

// Pushes arrive in pieces: an offer can come before the outcome it prices.
func TestAnOfferArrivingBeforeItsOutcomeIsStoredOnceTheOutcomeArrives(t *testing.T) {
	p, store, outcomes := newProcessor(t)
	early := offer("7001", "5001", "16")
	early.CouponKey = "/evento/calcio/ita-serie-a/inter-milan"
	if err := p.Process(&parser.OddsData{OddsProviders: []models.OddsProvider{provider}, BettingOffers: []models.BettingOffer{early}}); err != nil {
		t.Fatal(err)
	}
	if len(store.stored()) != 0 || outcomes.GetPendingOffersCount() != 1 {
		t.Fatalf("stored %d, pending %d", len(store.stored()), outcomes.GetPendingOffersCount())
	}

	if err := p.Process(&parser.OddsData{Events: []models.Event{match}, Outcomes: []models.Outcome{homeWin}}); err != nil {
		t.Fatal(err)
	}
	got := store.stored()
	if len(got) != 1 || outcomes.GetPendingOffersCount() != 0 {
		t.Fatalf("stored %d, pending %d", len(got), outcomes.GetPendingOffersCount())
	}
	if got[0].BettingOfferID != "7001" || got[0].Odds != 2.10 || !strings.HasPrefix(got[0].MarketDescription, "1X2 - Home Win") {
		t.Errorf("stored %+v", got[0])
	}
}
