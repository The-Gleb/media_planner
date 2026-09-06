package simulation

import (
	"encoding/json"
	"fmt"
	"math"
	"math/rand/v2"
	"media-planner/services/simulator/internal/domain"
	"slices"
	"sort"
	"time"
)

type poolKey struct {
	Channel              domain.ChannelID
	Segment, Temperature string
}
type poolHour struct {
	key                poolKey
	capacity, requests int64
	raw                float64
	cpm                domain.MoneyMicros
	ctr, cr            float64
	dyn                Dynamics
	selected           bool
}

func checkedAdd(a, b int64) (int64, error) {
	if a < 0 || b < 0 || a > math.MaxInt64-b {
		return 0, fmt.Errorf("counter overflow")
	}
	return a + b, nil
}

// roundedSupply preserves the rounded total instead of rounding each split independently.
func roundedSupply(p []poolHour) error {
	var total float64
	var floors int64
	for i := range p {
		if math.IsNaN(p[i].raw) || math.IsInf(p[i].raw, 0) || p[i].raw < 0 || p[i].raw >= float64(math.MaxInt64) {
			return fmt.Errorf("invalid supply")
		}
		total += p[i].raw
		p[i].requests = int64(math.Floor(p[i].raw))
		var err error
		floors, err = checkedAdd(floors, p[i].requests)
		if err != nil {
			return err
		}
	}
	if math.IsInf(total, 0) || total >= float64(math.MaxInt64) {
		return fmt.Errorf("supply overflow")
	}
	remainder := int64(math.Round(total)) - floors
	if remainder < 0 || remainder > int64(len(p)) {
		return fmt.Errorf("supply rounding overflow")
	}
	order := make([]int, len(p))
	for i := range order {
		order[i] = i
	}
	sort.SliceStable(order, func(i, j int) bool {
		return p[order[i]].raw-float64(p[order[i]].requests) > p[order[j]].raw-float64(p[order[j]].requests)
	})
	for _, i := range order[:int(remainder)] {
		p[i].requests++
	}
	return nil
}

func (e *Engine) stepAudience(budgets map[domain.ChannelID]domain.MoneyMicros) ([]domain.Observation, error) {
	fail := func(err error) ([]domain.Observation, error) {
		return nil, domain.NewError(domain.CodeInternal, "audience step failed: "+err.Error())
	}
	next := make(map[poolKey]runtimeState, len(e.pools))
	for k, v := range e.pools {
		next[k] = v
	}
	hour, weekday, err := localClock(e.current, e.cfg.TimeZone)
	if err != nil {
		return fail(err)
	}
	observations := make([]domain.Observation, 0, len(e.world.Channels))
	for _, c := range e.world.Channels {
		factors := evaluateEvents(e.events[c.ID], e.steps)
		noise := func(tag string, sigma float64) float64 {
			return lognormalMeanOne(newStream(e.cfg.CampaignSeed, e.model.Model.EngineVersion, string(c.ID), tag, e.steps), sigma)
		}
		supply := float64(c.BaseRequestsPerDay) / 24 * c.HourlySupply[hour] * c.WeekdaySupply[int(weekday)] * factors.Supply * noise("noise/requests", c.RequestsSigma)
		if factors.Paused {
			supply = 0
		}
		price := c.BaseCPM.Float64() * c.HourlyCPM[hour] * c.WeekdayCPM[int(weekday)] * factors.CPM * noise("noise/cpm", c.CPMSigma)
		baseCTR := c.BaseCTR * c.HourlyCTR[hour] * c.WeekdayCTR[int(weekday)] * factors.CTR
		baseCR := c.BaseCR * c.HourlyCR[hour] * c.WeekdayCR[int(weekday)] * factors.CR
		p := []poolHour{}
		selection := e.cfg.Audience[c.ID]
		for _, s := range c.Segments {
			for _, temperature := range []string{"cold", "warm"} {
				capacity, m := s.ColdCapacity, s.ColdMultipliers
				if temperature == "warm" {
					capacity, m = s.WarmCapacity, s.WarmMultipliers
				}
				key := poolKey{c.ID, s.ID, temperature}
				state := e.pools[key]
				dyn := dynamics(state.Impressions, state.UniqueReach, capacity, c.Dynamics)
				raw := 0.0
				if capacity > 0 && c.AudienceCapacity > 0 {
					raw = supply * (float64(capacity) / float64(c.AudienceCapacity)) * s.Multipliers.Get("supply")
				}
				cpm, err := domain.QuantizeFloat64(price * s.Multipliers.Get("cpm") * m.Get("cpm") * dyn.PriceFactor)
				if err != nil || cpm <= 0 {
					return fail(fmt.Errorf("invalid CPM"))
				}
				ctr := baseCTR * s.Multipliers.Get("ctr") * m.Get("ctr") * dyn.FatigueFactor
				cr := baseCR * s.Multipliers.Get("cr") * m.Get("cr")
				if math.IsNaN(ctr) || math.IsNaN(cr) {
					return fail(fmt.Errorf("invalid probability"))
				}
				selected := slices.Contains(selection.SegmentIDs, s.ID)
				p = append(p, poolHour{key, capacity, 0, raw, cpm, clamp(ctr, 0, 1), clamp(cr, 0, 1), dyn, selected})
			}
		}
		if err := roundedSupply(p); err != nil {
			return fail(err)
		}
		weights, err := deliveryWeights(p, e.pools)
		if err != nil {
			return fail(err)
		}
		allocated, err := allocateDelivery(p, weights, budgets[c.ID])
		if err != nil {
			return fail(err)
		}
		obs := domain.Observation{ChannelID: c.ID, Hour: e.current}
		for i, v := range p {
			impressions := allocated[i]
			stream := func(purpose string) *rand.Rand {
				tag, _ := json.Marshal([]string{v.key.Segment, v.key.Temperature, purpose})
				return newStream(e.cfg.CampaignSeed, e.model.Model.EngineVersion, string(c.ID), string(tag), e.steps)
			}
			reach, err := sampleBinomial(stream("reach"), impressions, v.dyn.NewUserProbability)
			if err != nil {
				return fail(err)
			}
			state := e.pools[v.key]
			reach = min64(reach, v.capacity-state.UniqueReach)
			clicks, err := sampleBinomial(stream("clicks"), impressions, v.ctr)
			if err != nil {
				return fail(err)
			}
			conversions, err := sampleBinomial(stream("conversions"), clicks, v.cr)
			if err != nil {
				return fail(err)
			}
			spend, _, err := spendAndECPM(impressions, v.cpm)
			if err != nil {
				return fail(err)
			}
			for _, pair := range []struct {
				dst   *int64
				value int64
			}{{&obs.Requests, v.requests}, {&obs.Impressions, impressions}, {&obs.UniqueReach, reach}, {&obs.Clicks, clicks}, {&obs.Conversions, conversions}, {&state.Impressions, impressions}, {&state.UniqueReach, reach}} {
				*pair.dst, err = checkedAdd(*pair.dst, pair.value)
				if err != nil {
					return fail(err)
				}
			}
			sum, err := checkedAdd(int64(obs.Spend), int64(spend))
			if err != nil {
				return fail(err)
			}
			obs.Spend = domain.MoneyMicros(sum)
			next[v.key] = state
		}
		if obs.Spend > budgets[c.ID] {
			return fail(fmt.Errorf("budget exceeded"))
		}
		if obs.Impressions > 0 {
			value, err := domain.MulDivCeil(int64(obs.Spend), 1000, obs.Impressions)
			if err != nil {
				return fail(err)
			}
			ecpm := domain.DecimalMoney(value)
			obs.ECPM = &ecpm
		}
		observations = append(observations, obs)
	}
	sort.Slice(observations, func(i, j int) bool { return observations[i].ChannelID < observations[j].ChannelID })
	e.pools = next
	e.steps++
	e.current = e.current.Add(time.Hour)
	return observations, nil
}
