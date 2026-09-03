package simulation

import (
	"testing"
	"time"

	"media-planner/services/simulator/internal/config"
	"media-planner/services/simulator/internal/domain"
)

func scenarioConfig(t *testing.T, events []domain.ScenarioEvent, disableRandom bool) domain.SimulationConfig {
	t.Helper()
	start, err := domain.NewHour(time.Date(2026, time.September, 7, 0, 0, 0, 0, time.UTC))
	if err != nil {
		t.Fatal(err)
	}
	return domain.SimulationConfig{WorldSeed: 42, CampaignSeed: 7, StartHour: start, DurationHours: 48, TimeZone: "Europe/Moscow", ScenarioEvents: events, DisableRandomEvents: disableRandom}
}

func runHours(t *testing.T, engine *Engine, hours int, actions []domain.ChannelAction) [][]domain.Observation {
	t.Helper()
	result := make([][]domain.Observation, 0, hours)
	for range hours {
		observations, err := engine.Step(actions)
		if err != nil {
			t.Fatal(err)
		}
		result = append(result, observations)
	}
	return result
}

func TestDisableRandomEventsLeavesOnlyExplicitSchedule(t *testing.T) {
	loaded, err := config.LoadFile("../../configs/world-config.json")
	if err != nil {
		t.Fatal(err)
	}
	engine := New(loaded)
	if err := engine.Reset(scenarioConfig(t, nil, true)); err != nil {
		t.Fatal(err)
	}
	for id, schedule := range engine.events {
		if len(schedule) != 0 {
			t.Fatalf("channel %s has %d random events despite disable_random_events", id, len(schedule))
		}
	}
}

func TestExplicitCTRShockReducesClicksFromStartIndex(t *testing.T) {
	loaded, err := config.LoadFile("../../configs/world-config.json")
	if err != nil {
		t.Fatal(err)
	}
	actions := []domain.ChannelAction{{ChannelID: "social_1", BudgetCap: 100000}}
	shock := []domain.ScenarioEvent{{ChannelID: "social_1", Metric: "ctr", StartIndex: 24, DurationHours: 24, Multiplier: 0.1}}

	baseline := New(loaded)
	if err := baseline.Reset(scenarioConfig(t, nil, true)); err != nil {
		t.Fatal(err)
	}
	shocked := New(loaded)
	if err := shocked.Reset(scenarioConfig(t, shock, true)); err != nil {
		t.Fatal(err)
	}
	baseObs := runHours(t, baseline, 48, actions)
	shockObs := runHours(t, shocked, 48, actions)

	pick := func(observations []domain.Observation) domain.Observation {
		for _, observation := range observations {
			if observation.ChannelID == "social_1" {
				return observation
			}
		}
		t.Fatal("social_1 observation missing")
		return domain.Observation{}
	}
	var clicksBefore, clicksAfter, baseBefore, baseAfter int64
	for hour := range 48 {
		if hour < 24 {
			clicksBefore += pick(shockObs[hour]).Clicks
			baseBefore += pick(baseObs[hour]).Clicks
		} else {
			clicksAfter += pick(shockObs[hour]).Clicks
			baseAfter += pick(baseObs[hour]).Clicks
		}
	}
	if baseAfter == 0 {
		t.Fatal("baseline produced no clicks after hour 24")
	}
	if clicksBefore != baseBefore {
		t.Fatalf("clicks before the shock differ: %d vs %d", clicksBefore, baseBefore)
	}
	if clicksAfter*3 >= baseAfter {
		t.Fatalf("CTR x0.1 shock did not cut clicks enough: %d vs baseline %d", clicksAfter, baseAfter)
	}
}

func TestExplicitPauseZeroesImpressions(t *testing.T) {
	loaded, err := config.LoadFile("../../configs/world-config.json")
	if err != nil {
		t.Fatal(err)
	}
	engine := New(loaded)
	pause := []domain.ScenarioEvent{{ChannelID: "search_1", Metric: "pause", StartIndex: 2, DurationHours: 3}}
	if err := engine.Reset(scenarioConfig(t, pause, true)); err != nil {
		t.Fatal(err)
	}
	observations := runHours(t, engine, 6, []domain.ChannelAction{{ChannelID: "search_1", BudgetCap: 5000}})
	for hour, obs := range observations {
		paused := hour >= 2 && hour < 5
		if paused && obs[0].Impressions != 0 {
			t.Fatalf("hour %d should be paused, got %d impressions", hour, obs[0].Impressions)
		}
		if !paused && obs[0].Impressions == 0 {
			t.Fatalf("hour %d should serve impressions", hour)
		}
	}
}

func TestScenarioEventValidation(t *testing.T) {
	loaded, err := config.LoadFile("../../configs/world-config.json")
	if err != nil {
		t.Fatal(err)
	}
	unknownChannel := []domain.ScenarioEvent{{ChannelID: "nope", Metric: "ctr", StartIndex: 0, DurationHours: 1, Multiplier: 0.5}}
	if err := New(loaded).Reset(scenarioConfig(t, unknownChannel, true)); err == nil {
		t.Fatal("unknown channel must be rejected")
	}
	badMetric := scenarioConfig(t, []domain.ScenarioEvent{{ChannelID: "social_1", Metric: "vtr", StartIndex: 0, DurationHours: 1, Multiplier: 0.5}}, true)
	if err := badMetric.Validate(); err == nil {
		t.Fatal("unknown metric must be rejected")
	}
	lateStart := scenarioConfig(t, []domain.ScenarioEvent{{ChannelID: "social_1", Metric: "ctr", StartIndex: 48, DurationHours: 1, Multiplier: 0.5}}, true)
	if err := lateStart.Validate(); err == nil {
		t.Fatal("start_index beyond horizon must be rejected")
	}
}
