package httptransport

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"media-planner/services/simulator/internal/app"
	"media-planner/services/simulator/internal/config"
)

func testHandler(t *testing.T) http.Handler {
	t.Helper()
	model, err := config.LoadFile("../../../configs/world-config.json")
	if err != nil {
		t.Fatal(err)
	}
	ready := &Readiness{}
	ready.Set(true)
	return NewHandler(app.NewRegistry(model), ready)
}

func TestParseSimulationID(t *testing.T) {
	for _, id := range []string{"campaign-demo_1", "demo.2026", "11111111-1111-4111-8111-111111111111"} {
		if _, err := parseSimulationID(id); err != nil {
			t.Errorf("valid id %q: %v", id, err)
		}
	}
	for _, id := range []string{"", "-campaign", "campaign/id", "campaign id", "кампания", strings.Repeat("a", 129)} {
		if _, err := parseSimulationID(id); err == nil {
			t.Errorf("invalid id accepted: %q", id)
		}
	}
}

func TestWorldMetadata(t *testing.T) {
	h := testHandler(t)
	req := httptest.NewRequest(http.MethodGet, "/v1/world-metadata", nil)
	rr := httptest.NewRecorder()
	h.ServeHTTP(rr, req)
	if rr.Code != http.StatusOK {
		t.Fatalf("status=%d body=%s", rr.Code, rr.Body.String())
	}
	var metadata app.WorldMetadata
	if err := json.Unmarshal(rr.Body.Bytes(), &metadata); err != nil {
		t.Fatal(err)
	}
	if metadata.Currency != "RUB" || len(metadata.ChannelIDs) != 2 {
		t.Fatalf("metadata=%+v", metadata)
	}
	if strings.Contains(rr.Body.String(), "base_cpm") || strings.Contains(rr.Body.String(), "audience_capacity") {
		t.Fatalf("metadata leaks hidden model: %s", rr.Body.String())
	}
}

func TestHTTPResetCurrentStepDelete(t *testing.T) {
	h := testHandler(t)
	id := "campaign-demo_1"
	resetBody := `{"world_seed":"42","campaign_seed":"77","start_hour":"2026-09-03T06:00:00Z","duration_hours":2,"time_zone":"Europe/Moscow"}`
	req := httptest.NewRequest(http.MethodPut, "/v1/simulations/"+id, bytes.NewBufferString(resetBody))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("If-None-Match", "*")
	rr := httptest.NewRecorder()
	h.ServeHTTP(rr, req)
	if rr.Code != http.StatusCreated || rr.Header().Get("ETag") == "" {
		t.Fatalf("reset %d %s", rr.Code, rr.Body.String())
	}
	etag := rr.Header().Get("ETag")
	stepBody := `{"step_id":"a04ea33b-b91a-4faa-a0b5-f2869efbdf17","actions":[{"channel_id":"social_1","budget_cap":"10.000000"}]}`
	req = httptest.NewRequest(http.MethodPost, "/v1/simulations/"+id+"/steps", bytes.NewBufferString(stepBody))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("If-Match", etag)
	rr = httptest.NewRecorder()
	h.ServeHTTP(rr, req)
	if rr.Code != http.StatusOK || !bytes.Contains(rr.Body.Bytes(), []byte(`"observed_hour":"2026-09-03T06:00:00Z"`)) {
		t.Fatalf("step %d %s", rr.Code, rr.Body.String())
	}
	nextETag := rr.Header().Get("ETag")
	req = httptest.NewRequest(http.MethodGet, "/v1/simulations/"+id+"/current-hour", nil)
	rr = httptest.NewRecorder()
	h.ServeHTTP(rr, req)
	if rr.Code != http.StatusOK || rr.Header().Get("ETag") != nextETag {
		t.Fatalf("current %d %s", rr.Code, rr.Body.String())
	}
	req = httptest.NewRequest(http.MethodDelete, "/v1/simulations/"+id, nil)
	req.Header.Set("If-Match", nextETag)
	rr = httptest.NewRecorder()
	h.ServeHTTP(rr, req)
	if rr.Code != http.StatusNoContent {
		t.Fatalf("delete %d %s", rr.Code, rr.Body.String())
	}
}
