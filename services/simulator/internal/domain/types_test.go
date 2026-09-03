package domain

import (
	"encoding/json"
	"errors"
	"testing"
	"time"
)

func TestHourRoundTripAndAlignment(t *testing.T) {
	t.Parallel()
	h, err := ParseHour("2026-09-03T06:00:00Z")
	if err != nil {
		t.Fatal(err)
	}
	if h.String() != "2026-09-03T06:00:00Z" || h.Add(time.Hour).String() != "2026-09-03T07:00:00Z" {
		t.Fatalf("unexpected hour %s", h)
	}
	if _, err := ParseHour("2026-09-03T06:30:00Z"); err == nil {
		t.Fatal("expected alignment error")
	}
	b, err := json.Marshal(h)
	if err != nil || string(b) != `"2026-09-03T06:00:00Z"` {
		t.Fatalf("marshal=%s err=%v", b, err)
	}
}

func TestChannelIDValidation(t *testing.T) {
	t.Parallel()
	for _, valid := range []ChannelID{"social_1", "search-2", "a"} {
		if err := valid.Validate(); err != nil {
			t.Errorf("%q invalid: %v", valid, err)
		}
	}
	for _, invalid := range []ChannelID{"", "Social", "1start", "white space"} {
		if err := invalid.Validate(); err == nil {
			t.Errorf("%q unexpectedly valid", invalid)
		}
	}
}

func TestSimulationConfigValidation(t *testing.T) {
	t.Parallel()
	h, _ := ParseHour("2026-09-03T06:00:00Z")
	cfg := SimulationConfig{StartHour: h, DurationHours: 24, TimeZone: "Europe/Moscow"}
	if err := cfg.Validate(); err != nil {
		t.Fatal(err)
	}
	cfg.TimeZone = "Missing/Zone"
	if err := cfg.Validate(); err == nil {
		t.Fatal("expected timezone error")
	}
}

func TestDomainErrorIdentity(t *testing.T) {
	t.Parallel()
	err := NewError(CodeValidation, "invalid action").WithField("actions[0].budget_cap", "must_be_non_negative")
	if !errors.Is(err, ErrValidation) || err.Code != CodeValidation || len(err.Fields) != 1 {
		t.Fatalf("unexpected typed error: %#v", err)
	}
}
