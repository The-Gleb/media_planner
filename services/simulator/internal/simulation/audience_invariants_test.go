package simulation

import (
	"math"
	"media-planner/services/simulator/internal/config"
	"media-planner/services/simulator/internal/domain"
	"testing"
)

func TestAudienceBudgetAndSupply(t *testing.T) {
	p := []poolHour{{raw: 1.4}, {raw: 1.4}, {raw: 1.4}}
	if err := roundedSupply(p); err != nil {
		t.Fatal(err)
	}
	if p[0].requests+p[1].requests+p[2].requests != 4 {
		t.Fatal(p)
	}
	p = []poolHour{{requests: 100, cpm: 100000000, selected: true}, {requests: 1000, cpm: 200000000, selected: true}, {requests: 999, cpm: 1, selected: false}}
	for _, budget := range []domain.MoneyMicros{0, 1, 123456789, 1000000000} {
		grants, err := allocateDelivery(p, []int64{1, 1, 0}, budget)
		if err != nil {
			t.Fatal(err)
		}
		var sum domain.MoneyMicros
		for i, g := range grants {
			spend, _, err := spendAndECPM(g, p[i].cpm)
			sum += spend
			if err != nil || g > p[i].requests {
				t.Fatal(err)
			}
		}
		if sum > budget || grants[2] != 0 {
			t.Fatal(grants)
		}
	}
}
func TestSaturatedPoolsAndPause(t *testing.T) {
	model, err := config.LoadFile("../../configs/world-config.audience.json")
	if err != nil {
		t.Fatal(err)
	}
	model.Model.Channels = model.Model.Channels[:1]
	c := &model.Model.Channels[0]
	for i := range c.Segments {
		c.Segments[i].WarmCapacity = 1
		c.Segments[i].ColdCapacity = 0
	}
	cfg := testSimulationConfig(t)
	cfg.DisableRandomEvents = true
	cfg.ScenarioEvents = []domain.ScenarioEvent{{ChannelID: c.ID, Metric: "pause", StartIndex: 1, DurationHours: 1}}
	e := New(model)
	if err := e.Reset(cfg); err != nil {
		t.Fatal(err)
	}
	first, err := e.Step([]domain.ChannelAction{{ChannelID: c.ID, BudgetCap: 1000000}})
	if err != nil {
		t.Fatal(err)
	}
	if first[0].UniqueReach > 8 {
		t.Fatal(first)
	}
	paused, err := e.Step([]domain.ChannelAction{{ChannelID: c.ID, BudgetCap: 1000000}})
	if err != nil || paused[0].Requests != 0 || paused[0].Spend != 0 {
		t.Fatal(paused, err)
	}
	next, err := e.Step([]domain.ChannelAction{{ChannelID: c.ID, BudgetCap: 1000000}})
	if err != nil || next[0].UniqueReach != 0 || next[0].Impressions == 0 {
		t.Fatal(next, err)
	}
	before := e.CurrentHour()
	e.world.Channels[0].BaseRequestsPerDay = math.MaxInt64
	e.world.Channels[0].Segments[0].Multipliers["supply"] = math.MaxFloat64
	if _, err := e.Step(nil); err == nil || e.CurrentHour() != before {
		t.Fatal("non-atomic overflow")
	}
}
func FuzzAudienceBudget(f *testing.F) {
	f.Add(int64(10000000), int64(100), int64(200))
	f.Fuzz(func(t *testing.T, b, n, m int64) {
		if b < 0 || b > 1000000000000 || n < 0 || n > 10000000 || m < 0 || m > 10000000 {
			return
		}
		p := []poolHour{{requests: n, cpm: 123456789, selected: true}, {requests: m, cpm: 98765432, selected: true}}
		g, err := allocateDelivery(p, []int64{4, 1}, domain.MoneyMicros(b))
		if err != nil {
			t.Fatal(err)
		}
		c0, _ := domain.MulDivCeil(g[0], int64(p[0].cpm), 1000)
		c1, _ := domain.MulDivCeil(g[1], int64(p[1].cpm), 1000)
		if c0+c1 > b {
			t.Fatal("cap", g, b)
		}
		if g[0] < 0 || g[1] < 0 || g[0] > n || g[1] > m {
			t.Fatal(g)
		}
	})
}
