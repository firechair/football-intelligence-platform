package storage

import (
	"fmt"
	"testing"

	"github.com/firechair/odds-receiver/internal/models"
)

type quietLogger struct{}

func (quietLogger) Debug(string, ...interface{})          {}
func (quietLogger) Info(string, ...interface{})           {}
func (quietLogger) Warn(string, ...interface{})           {}
func (quietLogger) Error(string, ...interface{})          {}
func (quietLogger) ErrorWithStack(string, ...interface{}) {}

func newStore(t *testing.T, dir string) *OutcomeStore {
	t.Helper()
	s, err := NewOutcomeStore(dir, quietLogger{})
	if err != nil {
		t.Fatal(err)
	}
	return s
}

var homeWin = models.Outcome{ID: "5001", Object: "event", ObjectFK: "9001", OutcomeTypeFK: 1, OutcomeSubtypeFK: 1, N: 2}

func TestAPendingOfferIsReleasedWhenItsOutcomeArrives(t *testing.T) {
	s := newStore(t, t.TempDir())
	defer s.Shutdown()
	var released []string
	s.SetPendingOfferCallback(func(p PendingOffer, o models.Outcome) {
		released = append(released, p.Offer.ID+"->"+o.ID)
	})

	s.StorePendingOffer(models.BettingOffer{ID: "7001", OutcomeFK: "5001"}, "", "", "", "Bookmaker A")
	if s.GetPendingOffersCount() != 1 || len(released) != 0 {
		t.Fatalf("pending %d, released %v", s.GetPendingOffersCount(), released)
	}
	s.StoreOutcome(homeWin)
	if s.GetPendingOffersCount() != 0 || len(released) != 1 || released[0] != "7001->5001" {
		t.Fatalf("pending %d, released %v", s.GetPendingOffersCount(), released)
	}
}

func TestAnOlderVersionOfAnOutcomeIsIgnored(t *testing.T) {
	s := newStore(t, t.TempDir())
	defer s.Shutdown()
	s.StoreOutcome(homeWin)
	older := homeWin
	older.N = 1
	older.OutcomeTypeFK = 4
	s.StoreOutcome(older)
	if got, _ := s.GetOutcome("5001"); got.OutcomeTypeFK != 1 {
		t.Fatalf("kept version %+v", got)
	}
}

// The autosave runs every five minutes while pushes keep arriving. Run with -race.
func TestSavingWhileOutcomesArriveIsSafe(t *testing.T) {
	s := newStore(t, t.TempDir())
	defer s.Shutdown()
	s.StoreOutcome(homeWin)
	done := make(chan struct{})
	go func() {
		defer close(done)
		for i := 0; i < 2000; i++ {
			o := homeWin
			o.ID = fmt.Sprint(i)
			s.StoreOutcome(o)
			s.StorePendingOffer(models.BettingOffer{ID: fmt.Sprint(i), OutcomeFK: "waiting-" + o.ID}, "", "", "", "")
		}
	}()
	for i := 0; i < 50; i++ {
		if err := s.SaveToDisk(); err != nil {
			t.Fatal(err)
		}
	}
	<-done
}

func TestAReleasedOfferDoesNotComeBackAfterARestart(t *testing.T) {
	dir := t.TempDir()
	s := newStore(t, dir)
	s.SetPendingOfferCallback(func(PendingOffer, models.Outcome) {})
	s.StoreOutcome(models.Outcome{ID: "5009", Object: "event", ObjectFK: "9002", N: 1})
	s.StorePendingOffer(models.BettingOffer{ID: "7001", OutcomeFK: "5001"}, "", "", "", "")
	if err := s.SaveToDisk(); err != nil {
		t.Fatal(err)
	}
	s.StoreOutcome(homeWin)
	s.Shutdown()

	restarted := newStore(t, dir)
	defer restarted.Shutdown()
	if n := restarted.GetPendingOffersCount(); n != 0 {
		t.Fatalf("%d released offers pending again after restart", n)
	}
}

func TestADeletedOutcomeDoesNotComeBackAfterARestart(t *testing.T) {
	dir := t.TempDir()
	s := newStore(t, dir)
	s.StoreOutcome(homeWin)
	if err := s.SaveToDisk(); err != nil {
		t.Fatal(err)
	}
	deleted := homeWin
	deleted.Del = "yes"
	s.StoreOutcome(deleted)
	s.Shutdown()

	restarted := newStore(t, dir)
	defer restarted.Shutdown()
	if _, ok := restarted.GetOutcome("5001"); ok {
		t.Fatal("deleted outcome is back after restart")
	}
}

func TestOutcomesAndPendingOffersSurviveARestart(t *testing.T) {
	dir := t.TempDir()
	s := newStore(t, dir)
	s.StoreOutcome(homeWin)
	s.StoreProvider("16", "Bookmaker A")
	s.StorePendingOffer(models.BettingOffer{ID: "7002", OutcomeFK: "5002"}, "", "", "", "Bookmaker A")
	s.Shutdown()

	restarted := newStore(t, dir)
	defer restarted.Shutdown()
	if _, ok := restarted.GetOutcome("5001"); !ok {
		t.Error("outcome lost on restart")
	}
	if name, _ := restarted.GetProvider("16"); name != "Bookmaker A" {
		t.Errorf("provider read as %q", name)
	}
	if restarted.GetPendingOffersCount() != 1 {
		t.Errorf("%d pending offers after restart", restarted.GetPendingOffersCount())
	}
}
