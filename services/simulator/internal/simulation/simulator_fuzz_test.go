package simulation

import (
	"math"
	"testing"

	"media-planner/services/simulator/internal/domain"
)

func FuzzSimulatorStep(f *testing.F) {
	f.Add(int64(42), int64(77), float64(0))
	f.Add(int64(-1), int64(0), float64(1500))
	f.Add(int64(9), int64(8), math.NaN())
	model := loadTestModel(f)
	f.Fuzz(func(t *testing.T, worldSeed, campaignSeed int64, budget float64) {
		h, _ := domain.ParseHour("2026-09-03T06:00:00Z")
		engine := New(model)
		if err := engine.Reset(domain.SimulationConfig{WorldSeed: worldSeed, CampaignSeed: campaignSeed, StartHour: h, DurationHours: 1, TimeZone: "Europe/Moscow"}); err != nil {
			t.Fatal(err)
		}
		before := engine.CurrentHour()
		obs, err := engine.Step([]domain.ChannelAction{{ChannelID: "social_1", BudgetCap: budget}})
		if err != nil {
			if engine.CurrentHour() != before {
				t.Fatal("failed step mutated state")
			}
			return
		}
		for _, o := range obs {
			if o.Conversions > o.Clicks || o.Clicks > o.Impressions || o.Impressions > o.Requests || o.UniqueReach > o.Impressions || o.Spend < 0 {
				t.Fatalf("invariant: %#v", o)
			}
		}
	})
}
