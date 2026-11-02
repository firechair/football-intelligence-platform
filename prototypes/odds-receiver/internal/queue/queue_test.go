package queue

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

func newQueue(t *testing.T, dir string) *Queue {
	t.Helper()
	q, err := NewQueue(dir, quietLogger{})
	if err != nil {
		t.Fatal(err)
	}
	return q
}

func depth(t *testing.T, q *Queue) int {
	t.Helper()
	n, err := q.GetQueueStats()
	if err != nil {
		t.Fatal(err)
	}
	return n
}

func TestAStoredOperationLeavesTheQueue(t *testing.T) {
	q := newQueue(t, t.TempDir())
	if err := q.QueueStoreOperation(&models.OddsUpdate{BettingOfferID: "7001"}); err != nil {
		t.Fatal(err)
	}
	var stored []string
	q.processQueue(func(op *QueuedOperation) error {
		stored = append(stored, op.Data.BettingOfferID)
		return nil
	})
	if len(stored) != 1 || stored[0] != "7001" || depth(t, q) != 0 {
		t.Fatalf("stored %v, %d left", stored, depth(t, q))
	}
}

// A push with many offers queues them in a tight loop, often within one millisecond.
func TestOperationsQueuedInTheSameMillisecondAreAllKept(t *testing.T) {
	q := newQueue(t, t.TempDir())
	for i := 0; i < 50; i++ {
		if err := q.QueueStoreOperation(&models.OddsUpdate{BettingOfferID: fmt.Sprint(i)}); err != nil {
			t.Fatal(err)
		}
	}
	if n := depth(t, q); n != 50 {
		t.Fatalf("%d of 50 operations kept", n)
	}
}

func TestQueuedOperationsSurviveARestart(t *testing.T) {
	dir := t.TempDir()
	if err := newQueue(t, dir).QueueStoreOperation(&models.OddsUpdate{BettingOfferID: "7001"}); err != nil {
		t.Fatal(err)
	}
	restarted := newQueue(t, dir)
	calls := 0
	restarted.processQueue(func(*QueuedOperation) error { calls++; return nil })
	if calls != 1 {
		t.Fatalf("%d operations after restart", calls)
	}
}
