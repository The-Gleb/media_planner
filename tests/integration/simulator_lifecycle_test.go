package integration

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strconv"
	"testing"
)

const lifecycleID = "campaign-demo_1"

type lifecycleStep struct {
	Status         string `json:"status"`
	RemainingHours int    `json:"remaining_hours"`
	Observations   []struct {
		ChannelID   string  `json:"channel_id"`
		Requests    int64   `json:"requests"`
		Impressions int64   `json:"impressions"`
		UniqueReach int64   `json:"unique_reach"`
		Clicks      int64   `json:"clicks"`
		Conversions int64   `json:"conversions"`
		Spend       string  `json:"spend"`
		ECPM        *string `json:"ecpm"`
	} `json:"observations"`
}

func TestSimulatorBlackBoxLifecycle(t *testing.T) {
	base := os.Getenv("SIMULATOR_BASE_URL")
	if base == "" {
		t.Skip("set SIMULATOR_BASE_URL to run black-box lifecycle")
	}
	assertStatus(t, request(t, http.MethodGet, base+"/health/ready", "", nil), http.StatusOK)
	resetBody := `{"world_seed":"42001","campaign_seed":"77001","start_hour":"2026-09-03T06:00:00Z","duration_hours":24,"time_zone":"Europe/Moscow"}`
	etag := reset(t, base, resetBody)
	firstRun := make([][]byte, 0, 24)
	for hour := 0; hour < 24; hour++ {
		resp := request(t, http.MethodPost, base+"/v1/simulations/"+lifecycleID+"/steps", etag, stepBody(hour))
		assertStatus(t, resp, http.StatusOK)
		etag = resp.Header.Get("ETag")
		payload := readBody(t, resp)
		assertStepInvariants(t, payload, hour)
		firstRun = append(firstRun, payload)
	}
	resp := request(t, http.MethodPost, base+"/v1/simulations/"+lifecycleID+"/steps", etag, stepBody(24))
	assertStatus(t, resp, http.StatusConflict)
	resp = request(t, http.MethodDelete, base+"/v1/simulations/"+lifecycleID, etag, nil)
	assertStatus(t, resp, http.StatusNoContent)

	etag = reset(t, base, resetBody)
	for hour := 0; hour < 24; hour++ {
		resp = request(t, http.MethodPost, base+"/v1/simulations/"+lifecycleID+"/steps", etag, stepBody(hour))
		assertStatus(t, resp, http.StatusOK)
		etag = resp.Header.Get("ETag")
		if replay := readBody(t, resp); !bytes.Equal(replay, firstRun[hour]) {
			t.Fatalf("hour %d replay differs", hour)
		}
	}
}

func TestSimulatorRestartStartsEmpty(t *testing.T) {
	base := os.Getenv("SIMULATOR_BASE_URL")
	if base == "" || os.Getenv("CHECK_RESTART_EMPTY") == "" {
		t.Skip("set SIMULATOR_BASE_URL and CHECK_RESTART_EMPTY=1 after restarting the service")
	}
	resp := request(t, http.MethodGet, base+"/v1/simulations/"+lifecycleID+"/current-hour", "", nil)
	assertStatus(t, resp, http.StatusNotFound)
}

func reset(t *testing.T, base, body string) string {
	t.Helper()
	resp := request(t, http.MethodPut, base+"/v1/simulations/"+lifecycleID, "*", []byte(body))
	assertStatus(t, resp, http.StatusCreated)
	defer resp.Body.Close()
	if etag := resp.Header.Get("ETag"); etag != "" {
		return etag
	}
	t.Fatal("reset response has no ETag")
	return ""
}

func stepBody(hour int) []byte {
	actions := `[]`
	if hour > 0 {
		actions = `[{"channel_id":"social_1","budget_cap":"1500.000000"},{"channel_id":"search_1","budget_cap":"900.000000"}]`
	}
	return []byte(fmt.Sprintf(`{"step_id":"00000000-0000-4000-8000-%012x","actions":%s}`, hour+1, actions))
}

func request(t *testing.T, method, url, etag string, body []byte) *http.Response {
	t.Helper()
	req, err := http.NewRequest(method, url, bytes.NewReader(body))
	if err != nil {
		t.Fatal(err)
	}
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	if etag == "*" {
		req.Header.Set("If-None-Match", "*")
	} else if etag != "" {
		req.Header.Set("If-Match", etag)
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	return resp
}

func assertStatus(t *testing.T, resp *http.Response, want int) {
	t.Helper()
	if resp.StatusCode != want {
		body := readBody(t, resp)
		t.Fatalf("status=%d want=%d body=%s", resp.StatusCode, want, body)
	}
	if resp.Body != nil && (want == http.StatusNoContent || want >= 300 || resp.Request.Method == http.MethodGet) {
		resp.Body.Close()
	}
}

func readBody(t *testing.T, resp *http.Response) []byte {
	t.Helper()
	defer resp.Body.Close()
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		t.Fatal(err)
	}
	return body
}

func assertStepInvariants(t *testing.T, payload []byte, hour int) {
	t.Helper()
	var step lifecycleStep
	if err := json.Unmarshal(payload, &step); err != nil {
		t.Fatal(err)
	}
	if len(step.Observations) != 2 || step.RemainingHours != 23-hour {
		t.Fatalf("unexpected step %d: %+v", hour, step)
	}
	if hour == 23 && step.Status != "finished" {
		t.Fatalf("final status=%q", step.Status)
	}
	for _, observation := range step.Observations {
		if observation.Conversions > observation.Clicks || observation.Clicks > observation.Impressions || observation.Impressions > observation.Requests || observation.UniqueReach > observation.Impressions {
			t.Fatalf("funnel invariant: %+v", observation)
		}
		spend, err := strconv.ParseFloat(observation.Spend, 64)
		if err != nil || spend < 0 {
			t.Fatalf("invalid spend: %+v", observation)
		}
		cap := 0.0
		if hour > 0 && observation.ChannelID == "social_1" {
			cap = 1500
		} else if hour > 0 {
			cap = 900
		}
		if spend > cap || (observation.Impressions == 0) != (observation.ECPM == nil) {
			t.Fatalf("accounting invariant: %+v", observation)
		}
	}
}
