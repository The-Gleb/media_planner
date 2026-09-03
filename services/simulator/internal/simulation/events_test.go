package simulation

import (
	"math"
	"testing"
)

func TestEventFactorsAndPausePrecedence(t *testing.T) {
	events := []EventSchedule{
		{Kind: eventDrift, Metric: metricCPM, StartIndex: 2, DurationHours: 4, Direction: 1, LogStrength: math.Log(2)},
		{Kind: eventShock, Metric: metricCPM, StartIndex: 3, DurationHours: 2, Multiplier: 1.5},
		{Kind: eventShock, Metric: metricPause, StartIndex: 4, DurationHours: 1, Multiplier: 0},
	}
	f2 := evaluateEvents(events, 2)
	f4 := evaluateEvents(events, 4)
	f8 := evaluateEvents(events, 8)
	if f2.CPM <= 1 || f4.CPM <= f2.CPM || !f4.Paused || math.Abs(f8.CPM-2) > 1e-12 {
		t.Fatalf("bad factors: %#v %#v %#v", f2, f4, f8)
	}
}
