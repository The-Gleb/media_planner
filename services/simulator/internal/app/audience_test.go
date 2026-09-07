package app

import (
	"media-planner/services/simulator/internal/config"
	"media-planner/services/simulator/internal/domain"
	"reflect"
	"testing"
)

func TestAudienceImmutableAndReplay(t *testing.T) {
	model, err := config.LoadFile("../../configs/world-config.audience.json")
	if err != nil {
		t.Fatal(err)
	}
	r := NewRegistry(model)
	hour, _ := domain.ParseHour("2026-09-03T06:00:00Z")
	a := domain.Audience{"social_1": {SegmentIDs: []string{"moscow_female_19_30"}}}
	cfg := domain.SimulationConfig{WorldSeed: 42, CampaignSeed: 77, StartHour: hour, TimeZone: "UTC", DurationHours: 168, Audience: a}
	_, etag, _, err := r.Reset("demo", cfg, "", true)
	if err != nil {
		t.Fatal(err)
	}
	actions := []domain.ChannelAction{{ChannelID: "social_1", BudgetCap: 1000}}
	first, next, err := r.Step("demo", "one", etag, actions, a)
	if err != nil {
		t.Fatal(err)
	}
	same, _, err := r.Step("demo", "one", etag, actions)
	if err != nil || !reflect.DeepEqual(first, same) {
		t.Fatal("replay", err)
	}
	changed := domain.Audience{"social_1": {SegmentIDs: []string{"moscow_female_31_45"}}}
	if _, _, err := r.Step("demo", "two", next, actions, changed); err == nil {
		t.Fatal("changed selection")
	}
	if _, _, err := r.Step("demo", "one", next, actions, changed); err == nil {
		t.Fatal("changed replay")
	}
	a["social_1"].SegmentIDs[0] = "invalid"
	if _, _, _, err := r.Reset("demo", cfg, next, false); err == nil {
		t.Fatal("invalid reset")
	}
	if _, _, err := r.Step("demo", "two", next, actions); err != nil {
		t.Fatal("error mutated state", err)
	}
}
