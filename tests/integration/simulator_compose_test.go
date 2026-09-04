package integration

import (
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
)

func TestComposeConfiguration(t *testing.T) {
	cmd := exec.Command("docker", "compose", "config")
	cmd.Dir = filepath.Join("..", "..")
	out, err := cmd.CombinedOutput()
	if err != nil {
		t.Fatalf("compose: %v: %s", err, out)
	}
	configuration := string(out)
	for _, required := range []string{"read_only: true", "target: /etc/media-planner/world-config.json", "host_ip: 127.0.0.1", "frontend:", "simulator:", "published: \"8081\"", "planner:", "published: \"8082\""} {
		if !strings.Contains(configuration, required) {
			t.Fatalf("compose config missing %q", required)
		}
	}
	if strings.Contains(configuration, "internal: true") {
		t.Fatal("local Compose network must allow published host ports")
	}
	if os.Getenv("RUN_COMPOSE_TESTS") == "" {
		t.Log("set RUN_COMPOSE_TESTS=1 to additionally verify the running container")
		return
	}
	cmd = exec.Command("docker", "compose", "ps", "--status", "running", "--services")
	cmd.Dir = filepath.Join("..", "..")
	out, err = cmd.CombinedOutput()
	services := strings.Fields(string(out))
	if err != nil || !contains(services, "simulator") || !contains(services, "frontend") {
		t.Fatalf("running services: %v: %q", err, out)
	}
}

func contains(values []string, target string) bool {
	for _, value := range values {
		if value == target {
			return true
		}
	}
	return false
}
