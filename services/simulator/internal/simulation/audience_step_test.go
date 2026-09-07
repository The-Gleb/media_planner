package simulation

import (
	"media-planner/services/simulator/internal/config"
	"media-planner/services/simulator/internal/domain"
	"reflect"
	"testing"
)

func TestAudienceReplayAndBudget(t *testing.T) {
	model, err := config.LoadFile("../../configs/world-config.audience.json")
	if err != nil {
		t.Fatal(err)
	}
	cfg := testSimulationConfig(t)
	cfg.DurationHours = 168
	cfg.Audience = domain.Audience{"social_1": {SegmentIDs: []string{"moscow_female_19_30"}}}
	a, b := New(model), New(model)
	if err := a.Reset(cfg); err != nil {
		t.Fatal(err)
	}
	if err := b.Reset(cfg); err != nil {
		t.Fatal(err)
	}
	all := New(model)
	untargeted := cfg
	untargeted.Audience = nil
	if err := all.Reset(untargeted); err != nil {
		t.Fatal(err)
	}
	if all.WorldFingerprint() != a.WorldFingerprint() {
		t.Fatal("targeting changed world")
	}
	actions := []domain.ChannelAction{{ChannelID: "social_1", BudgetCap: 100000}}
	for hour := 0; hour < 168; hour++ {
		prior := make(map[poolKey]runtimeState, len(a.pools))
		for k, v := range a.pools {
			prior[k] = v
		}
		x, err := a.Step(actions)
		if err != nil {
			t.Fatal(err)
		}
		y, err := b.Step(actions)
		if err != nil || !reflect.DeepEqual(x, y) {
			t.Fatal("replay", hour, err)
		}
		if !reflect.DeepEqual(a.pools, b.pools) {
			t.Fatal("pool replay", hour)
		}
		for _, o := range x {
			var impressions, reach int64
			for k, v := range a.pools {
				if k.Channel == o.ChannelID {
					impressions += v.Impressions - prior[k].Impressions
					reach += v.UniqueReach - prior[k].UniqueReach
				}
			}
			if impressions != o.Impressions || reach != o.UniqueReach {
				t.Fatal("aggregate mismatch", o)
			}
			if o.Spend > 100000000000 || o.Conversions > o.Clicks || o.Clicks > o.Impressions || o.Impressions > o.Requests || o.UniqueReach > o.Impressions {
				t.Fatal(o)
			}
		}
	}
	for key, s := range a.pools {
		if key.Channel == "social_1" && (key.Segment != "moscow_female_19_30") && s.Impressions != 0 {
			t.Fatal("delivery outside selection", key)
		}
	}
}

func TestEveryAudienceSelection(t *testing.T) {
	model, err := config.LoadFile("../../configs/world-config.audience.json")
	if err != nil {
		t.Fatal(err)
	}
	for _, c := range model.Model.Channels {
		if c.ID != "social_1" {
			continue
		}
		for _, segment := range c.Segments {
			{
				cfg := testSimulationConfig(t)
				cfg.Audience = domain.Audience{c.ID: {SegmentIDs: []string{segment.ID}}}
				e := New(model)
				if err := e.Reset(cfg); err != nil {
					t.Fatal(err)
				}
				if _, err := e.Step([]domain.ChannelAction{{ChannelID: c.ID, BudgetCap: 10000}}); err != nil {
					t.Fatal(err)
				}
				for key, state := range e.pools {
					if (key.Channel != c.ID || key.Segment != segment.ID) && state.Impressions != 0 {
						t.Fatal("selection leak", key)
					}
				}
			}
		}
	}
}

func TestControlledSegmentMultipliers(t *testing.T) {
	model, err := config.LoadFile("../../configs/world-config.audience.json")
	if err != nil {
		t.Fatal(err)
	}
	model.Model.Channels = model.Model.Channels[:1]
	c := &model.Model.Channels[0]
	c.Segments = c.Segments[:1]
	c.Segments[0].WarmCapacity = 100
	c.Segments[0].ColdCapacity = 0
	c.Segments[0].Multipliers = config.Multipliers{"cpm": 2, "ctr": 1000, "cr": 1000}
	c.Segments[0].WarmMultipliers = nil
	e := New(model)
	cfg := testSimulationConfig(t)
	cfg.DisableRandomEvents = true
	if err := e.Reset(cfg); err != nil {
		t.Fatal(err)
	}
	h := &e.world.Channels[0]
	h.BaseCPM = 100000000
	h.BaseRequestsPerDay = 2400
	h.RequestsSigma = 0
	h.CPMSigma = 0
	h.Dynamics = DynamicsParams{}
	for i := 0; i < 24; i++ {
		h.HourlySupply[i] = 1
		h.HourlyCPM[i] = 1
		h.HourlyCTR[i] = 1
		h.HourlyCR[i] = 1
	}
	for i := 0; i < 7; i++ {
		h.WeekdaySupply[i] = 1
		h.WeekdayCPM[i] = 1
		h.WeekdayCTR[i] = 1
		h.WeekdayCR[i] = 1
	}
	x, err := e.Step([]domain.ChannelAction{{ChannelID: h.ID, BudgetCap: 1000}})
	if err != nil {
		t.Fatal(err)
	}
	if x[0].Impressions != 100 || x[0].Clicks != 100 || x[0].Conversions != 100 || x[0].Spend != 20000000 {
		t.Fatal(x)
	}
	h.Segments[0].Multipliers["ctr"] = 0
	x, err = e.Step([]domain.ChannelAction{{ChannelID: h.ID, BudgetCap: 1000}})
	if err != nil || x[0].Clicks != 0 || x[0].UniqueReach != 0 {
		t.Fatal(x, err)
	}
}
