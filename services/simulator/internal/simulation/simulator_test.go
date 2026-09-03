package simulation

import (
	"reflect"
	"testing"

	"media-planner/services/simulator/internal/domain"
)

func testSimulationConfig(t *testing.T) domain.SimulationConfig {
	t.Helper()
	h, _ := domain.ParseHour("2026-09-03T06:00:00Z")
	return domain.SimulationConfig{WorldSeed: 42, CampaignSeed: 77, StartHour: h, DurationHours: 24, TimeZone: "Europe/Moscow"}
}

func TestResetStepReplayAndInvariants(t *testing.T) {
	model := loadTestModel(t)
	a, b := New(model), New(model)
	cfg := testSimulationConfig(t)
	if err := a.Reset(cfg); err != nil {
		t.Fatal(err)
	}
	if err := b.Reset(cfg); err != nil {
		t.Fatal(err)
	}
	actions := []domain.ChannelAction{{ChannelID: "search_1", BudgetCap: 900}, {ChannelID: "social_1", BudgetCap: 1500}}
	for step := 0; step < 24; step++ {
		x, err := a.Step(actions)
		if err != nil {
			t.Fatal(err)
		}
		y, err := b.Step([]domain.ChannelAction{actions[1], actions[0]})
		if err != nil {
			t.Fatal(err)
		}
		if !reflect.DeepEqual(x, y) || len(x) != 2 || x[0].ChannelID != "search_1" {
			t.Fatalf("step %d differs: %#v %#v", step, x, y)
		}
		for _, o := range x {
			if o.Conversions > o.Clicks || o.Clicks > o.Impressions || o.Impressions > o.Requests || o.UniqueReach > o.Impressions || o.Spend < 0 {
				t.Fatalf("bad observation: %#v", o)
			}
		}
	}
	before := a.CurrentHour()
	if _, err := a.Step(actions); err == nil {
		t.Fatal("expected finish error")
	}
	if a.CurrentHour() != before {
		t.Fatal("failed step mutated hour")
	}
}

func TestSparseAndInvalidActionsAreAtomic(t *testing.T) {
	e := New(loadTestModel(t))
	if err := e.Reset(testSimulationConfig(t)); err != nil {
		t.Fatal(err)
	}
	obs, err := e.Step(nil)
	if err != nil {
		t.Fatal(err)
	}
	for _, o := range obs {
		if o.Impressions != 0 || o.Spend != 0 || o.ECPM != nil {
			t.Fatalf("zero action bought media: %#v", o)
		}
	}
	before := e.CurrentHour()
	_, err = e.Step([]domain.ChannelAction{{ChannelID: "missing", BudgetCap: 1}})
	if err == nil || e.CurrentHour() != before {
		t.Fatal("invalid action was not atomic")
	}
}
