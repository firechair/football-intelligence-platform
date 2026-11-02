package api

import (
	"bytes"
	"compress/gzip"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/firechair/odds-receiver/internal/filemanager"
	"github.com/firechair/odds-receiver/internal/metrics"
	"github.com/firechair/odds-receiver/internal/models"
	"github.com/firechair/odds-receiver/internal/processor"
	"github.com/firechair/odds-receiver/internal/queue"
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

type receiver struct {
	handler *Handler
	files   *filemanager.FileManager
	store   *memoryStorage
}

// newReceiver wires the service as cmd/server/main.go does, with memory in place of DynamoDB.
func newReceiver(t *testing.T) *receiver {
	t.Helper()
	dir := t.TempDir()
	log := quietLogger{}
	store := &memoryStorage{}
	files, err := filemanager.NewFileManager(dir+"/files", log)
	if err != nil {
		t.Fatal(err)
	}
	outcomes, err := storage.NewOutcomeStore(dir+"/data", log)
	if err != nil {
		t.Fatal(err)
	}
	q, err := queue.NewQueue(dir+"/queue", log)
	if err != nil {
		t.Fatal(err)
	}
	q.Start(func(op *queue.QueuedOperation) error { return store.StoreOddsUpdate(op.Data) })
	t.Cleanup(func() { q.Stop(); outcomes.Shutdown() })

	p := processor.NewOddsProcessor(store, log, []string{"16"})
	p.SetQueue(q)
	p.SetOutcomeStore(outcomes)
	h := NewHandler(store, log, files)
	h.SetQueue(q)
	h.SetProcessor(p)
	return &receiver{handler: h, files: files, store: store}
}

// waitFor polls instead of sleeping: processing happens after the reply.
func waitFor(t *testing.T, what string, ok func() bool) {
	t.Helper()
	deadline := time.Now().Add(5 * time.Second)
	for !ok() {
		if time.Now().After(deadline) {
			t.Fatalf("timed out waiting for %s", what)
		}
		time.Sleep(10 * time.Millisecond)
	}
}

func push(events, outcomes, offers string) string {
	return `<?xml version="1.0" encoding="UTF-8"?><spocosy version="1.0"><subscription-update subscriptionid="1">` +
		`<odds_provider id="16" name="Bookmaker A"/>` + events + outcomes + offers + `</subscription-update></spocosy>`
}

const (
	match   = `<event id="9001" name="Inter-AC Milan" startdate="2099-03-22 20:45:00" status_type="notstarted"/>`
	homeWin = `<outcome id="5001" object="event" objectFK="9001" outcome_typeFK="1" outcome_subtypeFK="1" outcome_scopeFK="1" n="1"/>`
	tracked = `<bettingoffer id="7001" outcomeFK="5001" odds_providerFK="16" odds="2.10" active="yes"/>`
)

func TestAGzippedPushIsAcknowledgedAndThenStored(t *testing.T) {
	r := newReceiver(t)
	server := httptest.NewServer(r.handler.Routes())
	defer server.Close()

	var body bytes.Buffer
	gz := gzip.NewWriter(&body)
	gz.Write([]byte(push(match, homeWin, tracked)))
	gz.Close()
	resp, err := http.Post(server.URL+"/receive_file.php", "application/octet-stream", &body)
	if err != nil {
		t.Fatal(err)
	}
	resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("status %d", resp.StatusCode)
	}

	waitFor(t, "the stored update", func() bool { return len(r.store.stored()) == 1 })
	if u := r.store.stored()[0]; u.EventName != "Inter-AC Milan" || u.Odds != 2.10 || u.ProviderName != "Bookmaker A" {
		t.Errorf("stored %+v", u)
	}
}

func TestAPlainPushGetsTheReplyThePHPReceiverGave(t *testing.T) {
	r := newReceiver(t)
	server := httptest.NewServer(r.handler.Routes())
	defer server.Close()

	resp, err := http.Post(server.URL+"/receive.php", "text/xml", strings.NewReader(push(match, homeWin, tracked)))
	if err != nil {
		t.Fatal(err)
	}
	reply, _ := io.ReadAll(resp.Body)
	resp.Body.Close()
	if resp.StatusCode != http.StatusOK || strings.TrimSpace(string(reply)) != "XML_RECEIVED_OK" {
		t.Fatalf("status %d, reply %q", resp.StatusCode, reply)
	}
	waitFor(t, "the stored update", func() bool { return len(r.store.stored()) == 1 })
}
