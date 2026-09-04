package integration

import (
	"bytes"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"testing"
)

func TestPlannerIndependentLifecycle(t *testing.T) {
	if os.Getenv("RUN_PLANNER_LIFECYCLE") == "" {
		t.Skip("set RUN_PLANNER_LIFECYCLE=1")
	}
	simulator := requiredEnv(t, "SIMULATOR_BASE_URL")
	frontend := requiredEnv(t, "FRONTEND_BASE_URL")
	before := getBody(t, simulator+"/health/ready")
	runPlannerCompose(t, "stop", "planner")
	defer runPlannerCompose(t, "up", "-d", "--wait", "planner")
	if got := getStatus(t, frontend+"/health"); got != http.StatusOK {
		t.Fatalf("frontend stopped with planner: %d", got)
	}
	if after := getBody(t, simulator+"/health/ready"); !bytes.Equal(before, after) {
		t.Fatalf("planner stop affected simulator: before=%s after=%s", before, after)
	}
}

func requiredEnv(t *testing.T, key string) string {
	t.Helper()
	value := os.Getenv(key)
	if value == "" {
		t.Fatalf("%s is required", key)
	}
	return value
}
func getBody(t *testing.T, url string) []byte {
	t.Helper()
	response, err := http.Get(url)
	if err != nil {
		t.Fatal(err)
	}
	defer response.Body.Close()
	body, _ := io.ReadAll(response.Body)
	if response.StatusCode != http.StatusOK {
		t.Fatalf("%s: %d: %s", url, response.StatusCode, body)
	}
	return body
}
func getStatus(t *testing.T, url string) int {
	t.Helper()
	response, err := http.Get(url)
	if err != nil {
		return 0
	}
	response.Body.Close()
	return response.StatusCode
}
func runPlannerCompose(t *testing.T, args ...string) {
	t.Helper()
	cmd := exec.Command("docker", append([]string{"compose"}, args...)...)
	cmd.Dir = filepath.Join("..", "..")
	if out, err := cmd.CombinedOutput(); err != nil {
		t.Fatalf("docker compose %v: %v: %s", args, err, out)
	}
}
