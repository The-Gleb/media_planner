package integration

import (
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
)

func TestPlannerComposeConfiguration(t *testing.T) {
	cmd := exec.Command("docker", "compose", "config")
	cmd.Dir = filepath.Join("..", "..")
	out, err := cmd.CombinedOutput()
	if err != nil {
		t.Fatalf("compose: %v: %s", err, out)
	}
	config := string(out)
	for _, required := range []string{"planner:", "published: \"8082\"", "read_only: true", "no-new-privileges:true"} {
		if !strings.Contains(config, required) {
			t.Fatalf("compose config missing %q", required)
		}
	}
}

func TestPlannerDirectAndFrontendProxyReadiness(t *testing.T) {
	planner := os.Getenv("PLANNER_BASE_URL")
	frontend := os.Getenv("FRONTEND_BASE_URL")
	if planner == "" || frontend == "" {
		t.Skip("set PLANNER_BASE_URL and FRONTEND_BASE_URL")
	}
	for _, url := range []string{planner + "/health/ready", frontend + "/planner-api/health/ready", frontend + "/health"} {
		response, err := http.Get(url)
		if err != nil {
			t.Fatal(err)
		}
		body, _ := io.ReadAll(response.Body)
		response.Body.Close()
		if response.StatusCode != http.StatusOK {
			t.Fatalf("%s: %d: %s", url, response.StatusCode, body)
		}
	}
}
