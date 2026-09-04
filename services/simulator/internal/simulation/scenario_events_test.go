package simulation

import (
	"testing"

	"media-planner/services/simulator/internal/domain"
)

func TestExplicitScenarioEventAppliesOnlyToSelectedChannelAndWindow(t *testing.T) {
	events := explicitEvents("social_1", []domain.ScenarioEvent{{
		ChannelID: "social_1", Metric: "ctr", StartIndex: 2, DurationHours: 3, Multiplier: 0.6,
	}, {
		ChannelID: "social_2", Metric: "pause", StartIndex: 0, DurationHours: 1,
	}})
	if len(events) != 1 {
		t.Fatalf("events=%d, want 1", len(events))
	}
	if got := evaluateEvents(events, 1).CTR; got != 1 {
		t.Fatalf("CTR before event=%v, want 1", got)
	}
	if got := evaluateEvents(events, 2).CTR; got != 0.6 {
		t.Fatalf("CTR during event=%v, want 0.6", got)
	}
	if got := evaluateEvents(events, 5).CTR; got != 1 {
		t.Fatalf("CTR after event=%v, want 1", got)
	}
}

func TestPauseScenarioIgnoresMultiplierAndPauses(t *testing.T) {
	events := explicitEvents("sms", []domain.ScenarioEvent{{
		ChannelID: "sms", Metric: "pause", StartIndex: 0, DurationHours: 1, Multiplier: 99,
	}})
	if factors := evaluateEvents(events, 0); !factors.Paused {
		t.Fatal("pause event did not pause channel")
	}
}
