package simulation

import (
	"fmt"
	"testing"

	"media-planner/services/simulator/internal/config"
	"media-planner/services/simulator/internal/domain"
)

func BenchmarkBinomialLarge(b *testing.B) {
	r := newStream(1, "sim-v0", "bench", "binomial", 0)
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		if _, err := sampleBinomial(r, 10_000_000, .17); err != nil {
			b.Fatal(err)
		}
	}
}

func BenchmarkResetAndStep(b *testing.B) {
	model := loadTestModel(b)
	h, _ := domain.ParseHour("2026-09-03T06:00:00Z")
	cfg := domain.SimulationConfig{WorldSeed: 42, CampaignSeed: 77, StartHour: h, DurationHours: 2160, TimeZone: "Europe/Moscow"}
	actions := []domain.ChannelAction{{ChannelID: "social_1", BudgetCap: 1500}, {ChannelID: "search_1", BudgetCap: 900}}
	b.Run("reset", func(b *testing.B) {
		for i := 0; i < b.N; i++ {
			engine := New(model)
			if err := engine.Reset(cfg); err != nil {
				b.Fatal(err)
			}
		}
	})
	engine := New(model)
	if err := engine.Reset(cfg); err != nil {
		b.Fatal(err)
	}
	b.Run("step", func(b *testing.B) {
		for i := 0; i < b.N; i++ {
			if i > 0 && i%cfg.DurationHours == 0 {
				if err := engine.Reset(cfg); err != nil {
					b.Fatal(err)
				}
			}
			if _, err := engine.Step(actions); err != nil {
				b.Fatal(err)
			}
		}
	})
}

func BenchmarkStep20Channels(b *testing.B) {
	model := loadTestModel(b)
	templates := model.Model.Channels
	model.Model.Channels = make([]config.ChannelModelConfig, 20)
	actions := make([]domain.ChannelAction, 20)
	for i := range model.Model.Channels {
		model.Model.Channels[i] = templates[i%len(templates)]
		model.Model.Channels[i].ID = domain.ChannelID(fmt.Sprintf("bench_%02d", i))
		actions[i] = domain.ChannelAction{ChannelID: model.Model.Channels[i].ID, BudgetCap: 1000}
	}
	h, _ := domain.ParseHour("2026-09-03T06:00:00Z")
	cfg := domain.SimulationConfig{WorldSeed: 42, CampaignSeed: 77, StartHour: h, DurationHours: domain.MaxDurationHours, TimeZone: "Europe/Moscow"}
	engine := New(model)
	if err := engine.Reset(cfg); err != nil {
		b.Fatal(err)
	}
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		if i > 0 && i%cfg.DurationHours == 0 {
			if err := engine.Reset(cfg); err != nil {
				b.Fatal(err)
			}
		}
		if _, err := engine.Step(actions); err != nil {
			b.Fatal(err)
		}
	}
}

func BenchmarkReplay2160Hours(b *testing.B) {
	model := loadTestModel(b)
	h, _ := domain.ParseHour("2026-09-03T06:00:00Z")
	cfg := domain.SimulationConfig{WorldSeed: 42, CampaignSeed: 77, StartHour: h, DurationHours: domain.MaxDurationHours, TimeZone: "Europe/Moscow"}
	actions := []domain.ChannelAction{{ChannelID: "social_1", BudgetCap: 1500}, {ChannelID: "search_1", BudgetCap: 900}}
	for i := 0; i < b.N; i++ {
		engine := New(model)
		if err := engine.Reset(cfg); err != nil {
			b.Fatal(err)
		}
		for range cfg.DurationHours {
			if _, err := engine.Step(actions); err != nil {
				b.Fatal(err)
			}
		}
	}
}
