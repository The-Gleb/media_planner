package simulation

import (
	"fmt"
	"media-planner/services/simulator/internal/config"
	"media-planner/services/simulator/internal/domain"
	"os"
	"runtime"
	"sort"
	"strconv"
	"strings"
	"testing"
	"time"
)

func audienceScale(tb testing.TB, count int) (*Engine, domain.SimulationConfig, []domain.ChannelAction) {
	tb.Helper()
	model, err := config.LoadFile("../../configs/world-config.audience.json")
	if err != nil {
		tb.Fatal(err)
	}
	base := model.Model.Channels[0]
	model.Model.Channels = nil
	actions := []domain.ChannelAction{}
	for i := 0; i < 20; i++ {
		c := base
		c.ID = domain.ChannelID(fmt.Sprintf("channel_%02d", i))
		c.Segments = nil
		for j := 0; j < count; j++ {
			s := base.Segments[0]
			s.ID = fmt.Sprintf("segment_%03d", j)
			s.Geo = s.ID
			c.Segments = append(c.Segments, s)
		}
		model.Model.Channels = append(model.Model.Channels, c)
		actions = append(actions, domain.ChannelAction{ChannelID: c.ID, BudgetCap: 1000})
	}
	h, _ := domain.ParseHour("2026-09-03T06:00:00Z")
	cfg := domain.SimulationConfig{WorldSeed: 42, CampaignSeed: 77, StartHour: h, DurationHours: 2160, TimeZone: "UTC"}
	e := New(model)
	if err := e.Reset(cfg); err != nil {
		tb.Fatal(err)
	}
	return e, cfg, actions
}
func BenchmarkAudienceStep(b *testing.B) {
	for _, count := range []int{8, 128} {
		b.Run(fmt.Sprint(count), func(b *testing.B) {
			e, cfg, a := audienceScale(b, count)
			b.ResetTimer()
			for i := 0; i < b.N; i++ {
				if i > 0 && i%2160 == 0 {
					if err := e.Reset(cfg); err != nil {
						b.Fatal(err)
					}
				}
				if _, err := e.Step(a); err != nil {
					b.Fatal(err)
				}
			}
		})
	}
}
func TestAudienceLatency(t *testing.T) {
	if testing.Short() {
		t.Skip("scale validation")
	}
	previous := runtime.GOMAXPROCS(1)
	defer runtime.GOMAXPROCS(previous)
	for _, count := range []int{8, 128} {
		e, _, a := audienceScale(t, count)
		samples := make([]time.Duration, 100)
		for i := range samples {
			start := time.Now()
			if _, err := e.Step(a); err != nil {
				t.Fatal(err)
			}
			samples[i] = time.Since(start)
		}
		sort.Slice(samples, func(i, j int) bool { return samples[i] < samples[j] })
		limit := 100 * time.Millisecond
		if count == 128 {
			limit = 500 * time.Millisecond
		}
		t.Logf("20 x %d x 2: p95=%s", count, samples[94])
		if samples[94] > limit {
			t.Errorf("p95 exceeds %s", limit)
		}
	}
}

func TestAudienceLongRun(t *testing.T) {
	if os.Getenv("RUN_AUDIENCE_SCALE") != "1" {
		t.Skip("explicit 2160-hour scale run")
	}
	previous := runtime.GOMAXPROCS(1)
	defer runtime.GOMAXPROCS(previous)
	e, _, a := audienceScale(t, 128)
	for hour := 0; hour < 2160; hour++ {
		if _, err := e.Step(a); err != nil {
			t.Fatal(hour, err)
		}
	}
	status, err := os.ReadFile("/proc/self/status")
	if err != nil {
		t.Fatal(err)
	}
	for _, line := range strings.Split(string(status), "\n") {
		if strings.HasPrefix(line, "VmHWM:") {
			fields := strings.Fields(line)
			kb, err := strconv.ParseInt(fields[1], 10, 64)
			if err != nil {
				t.Fatal(err)
			}
			t.Log(line)
			if kb > 256*1024 {
				t.Fatal("RSS exceeds 256 MiB")
			}
		}
	}
}
