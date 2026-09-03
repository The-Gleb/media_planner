package simulation

import (
	"math"
	"testing"
	"time"

	"media-planner/services/simulator/internal/config"
	"media-planner/services/simulator/internal/domain"
)

func TestHourlyAndWeekdayProfilesArePositiveAndNormalized(t *testing.T) {
	r := newStream(8, "sim-v0", "c", "profile", 0)
	h := generateHourly(config.HourlyPattern{
		PeaksCount: config.IntRange{Min: 2, Max: 2}, PeakCenterHour: config.FloatRange{Min: 22, Max: 23},
		PeakWidthHours: config.FloatRange{Min: 2, Max: 3}, PeakAmplitude: config.FloatRange{Min: .2, Max: .4},
	}, r)
	w := generateWeekday(config.WeekdayPattern{Variation: config.FloatRange{Min: .1, Max: .1}, WeekendModifier: config.FloatRange{Min: .8, Max: .8}}, r)
	for name, values := range map[string][]float64{"hour": h[:], "week": w[:]} {
		sum := 0.0
		for _, v := range values {
			if v <= 0 {
				t.Fatalf("%s non-positive", name)
			}
			sum += v
		}
		if math.Abs(sum/float64(len(values))-1) > 1e-12 {
			t.Fatalf("%s mean=%f", name, sum/float64(len(values)))
		}
	}
}

func TestLocalProfileClockAcrossDST(t *testing.T) {
	h, _ := domain.ParseHour("2026-10-25T00:00:00Z")
	hour, weekday, err := localClock(h, "Europe/Berlin")
	if err != nil || hour < 0 || hour > 23 || weekday < time.Sunday || weekday > time.Saturday {
		t.Fatalf("%d %v %v", hour, weekday, err)
	}
}
