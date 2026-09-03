package simulation

import (
	"testing"

	"media-planner/services/simulator/internal/config"
)

type testTB interface {
	Helper()
	Fatal(args ...any)
}

func loadTestModel(t testTB) config.Loaded {
	t.Helper()
	loaded, err := config.LoadFile("../../configs/world-config.json")
	if err != nil {
		t.Fatal(err)
	}
	return loaded
}

func TestWorldGenerationStableAndSeeded(t *testing.T) {
	model := loadTestModel(t)
	a, err := generateWorld(model, 42)
	if err != nil {
		t.Fatal(err)
	}
	b, err := generateWorld(model, 42)
	if err != nil {
		t.Fatal(err)
	}
	c, err := generateWorld(model, 43)
	if err != nil {
		t.Fatal(err)
	}
	if a.Fingerprint != b.Fingerprint || a.Fingerprint == c.Fingerprint || len(a.Channels) != 2 {
		t.Fatalf("fingerprints %s %s %s", a.Fingerprint, b.Fingerprint, c.Fingerprint)
	}
	for _, channel := range a.Channels {
		if channel.BaseCPM <= 0 || channel.BaseCTR <= 0 || channel.BaseCTR >= 1 || channel.AudienceCapacity <= 0 {
			t.Fatalf("bad channel: %#v", channel)
		}
	}
}
