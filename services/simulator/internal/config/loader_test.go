package config

import (
	"bytes"
	"os"
	"strings"
	"testing"
)

func TestLoadFileAndDigestStable(t *testing.T) {
	t.Parallel()
	first, err := LoadFile("../../configs/world-config.json")
	if err != nil {
		t.Fatal(err)
	}
	second, err := Load(bytes.NewReader(first.Normalized))
	if err != nil {
		t.Fatal(err)
	}
	if first.Digest != second.Digest || len(first.Model.Channels) != 2 {
		t.Fatalf("unstable load: %s != %s", first.Digest, second.Digest)
	}
}

func TestLoadRejectsUnknownField(t *testing.T) {
	t.Parallel()
	b, err := os.ReadFile("../../configs/world-config.json")
	if err != nil {
		t.Fatal(err)
	}
	b = bytes.Replace(b, []byte(`"engine_version": "sim-v0"`), []byte(`"engine_version": "sim-v0", "unknown": true`), 1)
	if _, err := Load(bytes.NewReader(b)); err == nil || !strings.Contains(err.Error(), "unknown") {
		t.Fatalf("expected unknown-field error, got %v", err)
	}
}

func TestLoadRejectsCrossFieldAndDuplicateChannel(t *testing.T) {
	t.Parallel()
	b, err := os.ReadFile("../../configs/world-config.json")
	if err != nil {
		t.Fatal(err)
	}
	badRange := bytes.Replace(b, []byte(`"min": 80, "max": 180`), []byte(`"min": 180, "max": 80`), 1)
	if _, err := Load(bytes.NewReader(badRange)); err == nil {
		t.Fatal("expected min/max error")
	}
	duplicate := bytes.Replace(b, []byte(`"id": "search_1"`), []byte(`"id": "social_1"`), 1)
	if _, err := Load(bytes.NewReader(duplicate)); err == nil {
		t.Fatal("expected duplicate channel error")
	}
}
