package httptransport

import (
	"media-planner/services/simulator/internal/app"
	"media-planner/services/simulator/internal/config"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestAudienceHTTP(t *testing.T) {
	model, err := config.LoadFile("../../../configs/world-config.audience.json")
	if err != nil {
		t.Fatal(err)
	}
	ready := &Readiness{}
	ready.Set(true)
	h := NewHandler(app.NewRegistry(model), ready)
	call := func(method, path, body, etag string) *httptest.ResponseRecorder {
		req := httptest.NewRequest(method, path, strings.NewReader(body))
		req.Header.Set("Content-Type", "application/json")
		if etag == "*" {
			req.Header.Set("If-None-Match", "*")
		} else {
			req.Header.Set("If-Match", etag)
		}
		w := httptest.NewRecorder()
		h.ServeHTTP(w, req)
		return w
	}
	catalog := call("GET", "/v1/audience-segments", "", "")
	if catalog.Code != 200 || strings.Contains(catalog.Body.String(), "capacity") || strings.Contains(catalog.Body.String(), "multipliers") {
		t.Fatal(catalog.Body.String())
	}
	path := "/v1/simulations/audience-test"
	selection := `{"social_1":{"segment_ids":["moscow_female_25_34"]}}`
	reset := `{"world_seed":"42","campaign_seed":"77","start_hour":"2026-09-03T06:00:00Z","duration_hours":2,"time_zone":"UTC","audience":` + selection + `}`
	w := call("PUT", path, reset, "*")
	if w.Code != 201 {
		t.Fatal(w.Code, w.Body.String())
	}
	etag := w.Header().Get("ETag")
	step := `{"step_id":"11111111-1111-4111-8111-111111111111","actions":[{"channel_id":"social_1","budget_cap":"1000.000000"}],"audience":` + selection + `}`
	w = call("POST", path+"/steps", step, etag)
	if w.Code != 200 {
		t.Fatal(w.Code, w.Body.String())
	}
	etag = w.Header().Get("ETag")
	for _, bad := range []string{"null", "{}", `{"social_1":{"segment_ids":[]}}`, `{"social_1":{"segment_ids":["unknown"]}}`} {
		w = call("PUT", path, strings.Replace(reset, selection, bad, 1), etag)
		if w.Code != 422 {
			t.Fatal("bad reset", w.Code, w.Body.String())
		}
	}
	for _, method := range []string{"PUT", "POST"} {
		body, target := reset, path
		if method == "POST" {
			body, target = step, path+"/steps"
		}
		body = strings.Replace(body, `"segment_ids":`, `"temperature":"warm","segment_ids":`, 1)
		if bad := call(method, target, body, etag); bad.Code != 400 {
			t.Fatal("temperature accepted", bad.Code)
		}
	}
	mismatch := strings.Replace(strings.Replace(step, "11111111-1111-4111-8111-111111111111", "22222222-2222-4222-8222-222222222222", 1), "moscow_female_25_34", "moscow_female_35_44", 1)
	if w = call("POST", path+"/steps", mismatch, etag); w.Code != 422 {
		t.Fatal(w.Code, w.Body.String())
	}
	if w = call("POST", path+"/steps", strings.Replace(step, "11111111-1111-4111-8111-111111111111", "22222222-2222-4222-8222-222222222222", 1), etag); w.Code != http.StatusOK {
		t.Fatal(w.Code, w.Body.String())
	}
	if strings.Contains(w.Body.String(), "segment_id") {
		t.Fatal("detail leaked")
	}
}
