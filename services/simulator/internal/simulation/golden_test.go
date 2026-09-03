package simulation

import (
	"encoding/json"
	"os"
	"path/filepath"
	"reflect"
	"testing"

	"media-planner/services/simulator/internal/domain"
)

type goldenScenario struct {
	Name             string                  `json:"name"`
	Config           domain.SimulationConfig `json:"config"`
	WorldFingerprint string                  `json:"world_fingerprint"`
	Observations     [][]domain.Observation  `json:"observations"`
}

func TestGoldenReplay(t *testing.T) {
	data, err := os.ReadFile(filepath.Join("..", "..", "testdata", "golden", "sim-v0.json"))
	if err != nil {
		t.Fatal(err)
	}
	var expected []goldenScenario
	if err := json.Unmarshal(data, &expected); err != nil {
		t.Fatal(err)
	}
	actual := buildGoldenScenarios(t)
	if !reflect.DeepEqual(actual, expected) {
		encoded, _ := json.MarshalIndent(actual, "", "  ")
		t.Fatalf("golden mismatch; reviewed replacement:\n%s", encoded)
	}
}

func buildGoldenScenarios(t *testing.T) []goldenScenario {
	t.Helper()
	base := testSimulationConfig(t)
	base.DurationHours = 3
	configs := []struct {
		name string
		cfg  domain.SimulationConfig
	}{
		{name: "baseline", cfg: base},
		{name: "campaign-seed-change", cfg: withCampaignSeed(base, 78)},
		{name: "world-seed-change", cfg: withWorldSeed(base, 43)},
	}
	result := make([]goldenScenario, 0, len(configs))
	for _, item := range configs {
		engine := New(loadTestModel(t))
		if err := engine.Reset(item.cfg); err != nil {
			t.Fatal(err)
		}
		scenario := goldenScenario{Name: item.name, Config: item.cfg, WorldFingerprint: engine.WorldFingerprint()}
		for range item.cfg.DurationHours {
			observations, err := engine.Step([]domain.ChannelAction{{ChannelID: "social_1", BudgetCap: 1500}, {ChannelID: "search_1", BudgetCap: 900}})
			if err != nil {
				t.Fatal(err)
			}
			scenario.Observations = append(scenario.Observations, observations)
		}
		result = append(result, scenario)
	}
	return result
}

func withCampaignSeed(cfg domain.SimulationConfig, seed int64) domain.SimulationConfig {
	cfg.CampaignSeed = seed
	return cfg
}

func withWorldSeed(cfg domain.SimulationConfig, seed int64) domain.SimulationConfig {
	cfg.WorldSeed = seed
	return cfg
}
