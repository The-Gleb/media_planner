package integration

import (
	"bytes"
	"encoding/json"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"testing"
)

func TestFrontendProxyAndIndependentLifecycle(t *testing.T) {
	frontend := os.Getenv("FRONTEND_BASE_URL")
	simulator := os.Getenv("SIMULATOR_BASE_URL")
	if frontend == "" || simulator == "" {
		t.Skip("set FRONTEND_BASE_URL and SIMULATOR_BASE_URL to run frontend integration")
	}
	for _, url := range []string{frontend + "/health", frontend + "/api/health/ready", frontend + "/api/v1/world-metadata"} {
		resp, err := http.Get(url)
		if err != nil {
			t.Fatal(err)
		}
		body, _ := io.ReadAll(resp.Body)
		resp.Body.Close()
		if resp.StatusCode != http.StatusOK {
			t.Fatalf("GET %s status=%d body=%s", url, resp.StatusCode, body)
		}
		if url == frontend+"/api/v1/world-metadata" {
			var metadata map[string]any
			if err := json.Unmarshal(body, &metadata); err != nil || metadata["channel_ids"] == nil || metadata["currency"] == nil {
				t.Fatalf("invalid proxied metadata: %s", body)
			}
		}
	}
	if os.Getenv("RUN_FRONTEND_LIFECYCLE") == "" {
		t.Log("set RUN_FRONTEND_LIFECYCLE=1 to stop/restart the frontend around an active campaign")
		return
	}

	const id = "frontend-lifecycle"
	cleanupSimulation(t, simulator, id)
	defer cleanupSimulation(t, simulator, id)
	body := []byte(`{"world_seed":"1","campaign_seed":"2","start_hour":"2026-09-03T06:00:00Z","duration_hours":2,"time_zone":"Europe/Moscow"}`)
	created := request(t, http.MethodPut, simulator+"/v1/simulations/"+id, "*", body)
	assertStatus(t, created, http.StatusCreated)
	created.Body.Close()
	before := request(t, http.MethodGet, simulator+"/v1/simulations/"+id+"/current-hour", "", nil)
	if before.StatusCode != http.StatusOK {
		t.Fatalf("current before frontend stop: status=%d", before.StatusCode)
	}
	beforeBody := readBody(t, before)

	runCompose(t, "stop", "frontend")
	after := request(t, http.MethodGet, simulator+"/v1/simulations/"+id+"/current-hour", "", nil)
	if after.StatusCode != http.StatusOK {
		t.Fatalf("current after frontend stop: status=%d", after.StatusCode)
	}
	afterBody := readBody(t, after)
	if !bytes.Equal(beforeBody, afterBody) {
		t.Fatalf("frontend stop mutated simulator: before=%s after=%s", beforeBody, afterBody)
	}
	runCompose(t, "up", "-d", "--wait", "frontend")
}

func runCompose(t *testing.T, args ...string) {
	t.Helper()
	cmd := exec.Command("docker", append([]string{"compose"}, args...)...)
	cmd.Dir = filepath.Join("..", "..")
	if output, err := cmd.CombinedOutput(); err != nil {
		t.Fatalf("docker compose %v: %v: %s", args, err, output)
	}
}
