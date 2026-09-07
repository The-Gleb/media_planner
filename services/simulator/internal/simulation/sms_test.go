package simulation

import (
	"reflect"
	"testing"

	"media-planner/services/simulator/internal/config"
	"media-planner/services/simulator/internal/domain"
)

func smsEngine(t *testing.T) *Engine {
	t.Helper()
	m, err := config.LoadFile("../../configs/world-config.audience.json")
	if err != nil {
		t.Fatal(err)
	}
	for _, c := range m.Model.Channels {
		if c.ID == "sms" {
			c.Segments = c.Segments[:1]
			c.Segments[0].WarmCapacity = 2
			c.Segments[0].ColdCapacity = 3
			m.Model.Channels = []config.ChannelModelConfig{c}
			break
		}
	}
	e := New(m)
	cfg := testSimulationConfig(t)
	cfg.DurationHours = 400
	cfg.DisableRandomEvents = true
	if err := e.Reset(cfg); err != nil {
		t.Fatal(err)
	}
	return e
}

func smsStep(t *testing.T, e *Engine, budget float64) domain.Observation {
	t.Helper()
	obs, err := e.Step([]domain.ChannelAction{{ChannelID: "sms", BudgetCap: budget}})
	if err != nil {
		t.Fatal(err)
	}
	o := obs[0]
	if o.Spend != domain.MoneyMicros(o.Impressions*14680000) || o.UniqueReach > o.Impressions || o.Clicks > o.Impressions || o.Conversions > o.Clicks || o.Impressions > o.Requests {
		t.Fatalf("SMS invariants: %+v", o)
	}
	if float64(o.Spend)/1e6 > budget {
		t.Fatal("budget exceeded")
	}
	if o.Impressions == 0 && o.ECPM != nil {
		t.Fatal("non-null empty eCPM")
	}
	if o.Impressions > 0 && (o.ECPM == nil || int64(*o.ECPM) != 14680000000) {
		t.Fatal("incorrect effective CPM")
	}
	return o
}

func TestSMSWeeklyCooldownAndRepeatReach(t *testing.T) {
	e := smsEngine(t)
	for hour := 0; hour <= 336; hour++ {
		o := smsStep(t, e, 1e6)
		want := int64(0)
		if hour%168 == 0 {
			want = 5
		}
		if o.Impressions != want {
			t.Fatalf("hour %d: got %d want %d", hour, o.Impressions, want)
		}
		if hour == 0 && o.UniqueReach != 5 || hour > 0 && o.UniqueReach != 0 {
			t.Fatalf("reach at %d: %d", hour, o.UniqueReach)
		}
		for key, state := range e.pools {
			_, unavailable := activeSMSCooldown(e.smsCooldown[key], e.steps-1)
			capacity := int64(3)
			if key.Temperature == "warm" {
				capacity = 2
			}
			unreached := capacity - state.UniqueReach
			eligible := state.UniqueReach - unavailable
			if unreached < 0 || eligible < 0 || unreached+eligible+unavailable != capacity {
				t.Fatal("recipient conservation")
			}
		}
	}
}

func TestSMSBudgetPriceAndReplay(t *testing.T) {
	a, b := smsEngine(t), smsEngine(t)
	for _, budget := range []float64{0, 14.679999, 14.68, 29.36, 1e6, 1e6} {
		x, y := smsStep(t, a, budget), smsStep(t, b, budget)
		if !reflect.DeepEqual(x, y) || !reflect.DeepEqual(a.smsCooldown, b.smsCooldown) {
			t.Fatal("replay mismatch")
		}
		if budget < 14.68 && x.Impressions != 0 {
			t.Fatal("fractional message")
		}
		if budget == 14.68 && x.Impressions != 1 {
			t.Fatal("exact message budget")
		}
		if budget == 29.36 && x.Impressions != 2 {
			t.Fatal("exact two-message budget")
		}
	}
	if err := a.Reset(a.cfg); err != nil {
		t.Fatal(err)
	}
	if len(a.smsCooldown) != 0 {
		t.Fatal("reset retained cooldown")
	}
	if smsStep(t, a, 1e6).UniqueReach != 5 {
		t.Fatal("reset retained reach")
	}
}

func TestSMSIgnoresAuctionPriceAndHonorsSupply(t *testing.T) {
	e := smsEngine(t)
	// All auction factors (including geographic/saturation factors in the config)
	// must leave SMS message price unchanged.
	e.world.Channels[0].BaseCPM *= 100
	for i := range e.world.Channels[0].HourlyCPM {
		e.world.Channels[0].HourlyCPM[i] = 100
	}
	o := smsStep(t, e, 14.68)
	if o.Impressions != 1 {
		t.Fatal("auction price affected SMS")
	}
	e.world.Channels[0].BaseRequestsPerDay = 0
	if smsStep(t, e, 1e6).Impressions != 0 {
		t.Fatal("ignored supply")
	}
}

func TestSMSRejectedStepDoesNotConsumeRecipients(t *testing.T) {
	e := smsEngine(t)
	before := e.CurrentHour()
	_, err := e.Step([]domain.ChannelAction{{ChannelID: "sms", BudgetCap: -1}})
	if err == nil || e.CurrentHour() != before || len(e.smsCooldown) != 0 {
		t.Fatal("rejected step mutated state")
	}
	if smsStep(t, e, 1e6).UniqueReach != 5 {
		t.Fatal("lost recipients")
	}
}

func TestSMSStaggeredCohortsAndAtomicFailure(t *testing.T) {
	e := smsEngine(t)
	if smsStep(t, e, 14.68).Impressions != 1 {
		t.Fatal("first cohort")
	}
	if smsStep(t, e, 1e6).Impressions != 4 {
		t.Fatal("second cohort")
	}
	for hour := 2; hour < 168; hour++ {
		smsStep(t, e, 0)
	}
	if smsStep(t, e, 1e6).Impressions != 1 {
		t.Fatal("cohorts released early or late")
	}
	if smsStep(t, e, 1e6).Impressions != 4 {
		t.Fatal("second cohort not released")
	}

	e = smsEngine(t)
	// Fail after allocating SMS but before committing the whole step.
	broken := e.world.Channels[0]
	broken.ID = "broken"
	broken.SMS = nil
	broken.BaseCPM = -1
	e.world.Channels = append(e.world.Channels, broken)
	before := e.CurrentHour()
	_, err := e.Step([]domain.ChannelAction{{ChannelID: "sms", BudgetCap: 1e6}})
	if err == nil || e.CurrentHour() != before || len(e.smsCooldown) != 0 || len(e.pools) != 0 {
		t.Fatal("failed step partially committed SMS state")
	}
	e.world.Channels = e.world.Channels[:1]
	if smsStep(t, e, 1e6).UniqueReach != 5 {
		t.Fatal("failed step consumed recipients")
	}
}
