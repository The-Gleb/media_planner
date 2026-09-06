package simulation

import (
	"fmt"
	"math"
	"math/big"
	"sort"

	"media-planner/services/simulator/internal/domain"
)

// Synthetic sim-v2 delivery policy. Neither prices nor response rates are inputs.
// Supply normalization cancels when scores are normalized to shares.
func deliveryScore(warm bool, supply, capacity, reach, impressions int64) float64 {
	if supply <= 0 || capacity <= 0 {
		return 0
	}
	priority := 1.0
	if warm {
		priority = 4
	}
	saturation := clamp(float64(reach)/float64(capacity), 0, 1)
	frequency := float64(impressions) / float64(max(reach, 1))
	return priority * float64(supply) * math.Max(.05, 1-saturation) * math.Max(.05, 1/(1+math.Max(frequency-1, 0)))
}

func deliveryWeights(p []poolHour, history map[poolKey]runtimeState) ([]int64, error) {
	scores := make([]float64, len(p))
	peak := 0.0
	for i, v := range p {
		if !v.selected {
			continue
		}
		h := history[v.key]
		scores[i] = deliveryScore(v.key.Temperature == "warm", v.requests, v.capacity, h.UniqueReach, h.Impressions)
		if math.IsInf(scores[i], 0) || math.IsNaN(scores[i]) {
			return nil, fmt.Errorf("invalid delivery score")
		}
		peak = math.Max(peak, scores[i])
	}
	weights := make([]int64, len(p))
	if peak > 0 {
		for i, s := range scores {
			if s > 0 {
				weights[i] = max(1, int64(math.Round(s/peak*1e9)))
			}
		}
	}
	return weights, nil
}

// allocateDelivery allocates impressions, not money shares. Rational water filling
// handles supply exhaustion; a per-pool micro reserve makes ceiling costs safe.
func allocateDelivery(p []poolHour, weights []int64, budget domain.MoneyMicros) ([]int64, error) {
	if len(p) != len(weights) || budget < 0 {
		return nil, fmt.Errorf("invalid allocation input")
	}
	out := make([]int64, len(p))
	active := []int{}
	full := new(big.Int)
	for i, v := range p {
		if v.requests < 0 || v.cpm <= 0 || weights[i] < 0 {
			return nil, fmt.Errorf("invalid pool input")
		}
		if !v.selected || v.requests == 0 || weights[i] == 0 {
			continue
		}
		active = append(active, i)
		product := new(big.Int).Mul(big.NewInt(v.requests), big.NewInt(int64(v.cpm)))
		product.Add(product, big.NewInt(999))
		product.Quo(product, big.NewInt(1000))
		full.Add(full, product)
	}
	if budget == 0 || len(active) == 0 {
		return out, nil
	}
	if full.Cmp(big.NewInt(int64(budget))) <= 0 {
		for _, i := range active {
			out[i] = p[i].requests
		}
		return out, nil
	}
	left := new(big.Rat).SetInt64(max(0, int64(budget)-int64(len(active))))
	fractions := make([]*big.Rat, len(p))
	candidates := append([]int(nil), active...)
	for len(active) > 0 {
		denom := new(big.Int)
		for _, i := range active {
			denom.Add(denom, new(big.Int).Mul(big.NewInt(weights[i]), big.NewInt(int64(p[i].cpm))))
		}
		level := new(big.Rat).Quo(new(big.Rat).Mul(left, big.NewRat(1000, 1)), new(big.Rat).SetInt(denom))
		next := []int{}
		saturated := false
		for _, i := range active {
			wanted := new(big.Rat).Mul(level, new(big.Rat).SetInt64(weights[i]))
			if wanted.Cmp(new(big.Rat).SetInt64(p[i].requests)) >= 0 {
				out[i] = p[i].requests
				saturated = true
				cost := new(big.Rat).SetFrac(new(big.Int).Mul(big.NewInt(out[i]), big.NewInt(int64(p[i].cpm))), big.NewInt(1000))
				left.Sub(left, cost)
			} else {
				next = append(next, i)
			}
		}
		if saturated {
			active = next
			continue
		}
		for _, i := range active {
			wanted := new(big.Rat).Mul(level, new(big.Rat).SetInt64(weights[i]))
			n := new(big.Int).Quo(wanted.Num(), wanted.Denom())
			if !n.IsInt64() {
				return nil, fmt.Errorf("allocation overflow")
			}
			out[i] = n.Int64()
			fractions[i] = new(big.Rat).Sub(wanted, new(big.Rat).SetInt(n))
		}
		break
	}
	costs := make([]int64, len(p))
	used := int64(0)
	for _, i := range candidates {
		cost, err := domain.MulDivCeil(out[i], int64(p[i].cpm), 1000)
		if err != nil {
			return nil, err
		}
		costs[i] = cost
		used, err = checkedAdd(used, cost)
		if err != nil {
			return nil, err
		}
	}
	if used > int64(budget) {
		return nil, fmt.Errorf("allocation exceeds cap")
	}
	// Stable pool-key order is independent of caller/map iteration.
	sort.Slice(candidates, func(a, b int) bool {
		i, j := candidates[a], candidates[b]
		fi, fj := fractions[i], fractions[j]
		if fi == nil {
			fi = new(big.Rat)
		}
		if fj == nil {
			fj = new(big.Rat)
		}
		if cmp := fi.Cmp(fj); cmp != 0 {
			return cmp > 0
		}
		x, y := p[i].key, p[j].key
		if x.Channel != y.Channel {
			return x.Channel < y.Channel
		}
		if x.Segment != y.Segment {
			return x.Segment < y.Segment
		}
		if x.Temperature != y.Temperature {
			return x.Temperature < y.Temperature
		}
		return i < j
	})
	for _, i := range candidates {
		remaining := int64(budget) - used
		limit := new(big.Int).Mul(big.NewInt(costs[i]+remaining), big.NewInt(1000))
		limit.Quo(limit, big.NewInt(int64(p[i].cpm)))
		available := p[i].requests
		if limit.Cmp(big.NewInt(available)) < 0 {
			available = limit.Int64()
		}
		chunk := int64(1)
		if p[i].cpm < 1000 {
			chunk = (1000 + int64(p[i].cpm) - 1) / int64(p[i].cpm)
		}
		add := min(max(0, available-out[i]), chunk)
		cost, err := domain.MulDivCeil(out[i]+add, int64(p[i].cpm), 1000)
		if err != nil {
			return nil, err
		}
		if cost-costs[i] > remaining {
			return nil, fmt.Errorf("rounding exceeds cap")
		}
		out[i] += add
		used += cost - costs[i]
	}
	return out, nil
}
