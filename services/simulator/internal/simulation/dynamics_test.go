package simulation

import "testing"

func TestSaturationDynamicsMonotonic(t *testing.T) {
	p := DynamicsParams{StartThreshold: .2, PriceGrowth: 1, ReachDecay: 2, FrequencyReachDecay: .2, CTRFatigue: .8, FrequencyFatigue: .1}
	low := dynamics(100, 80, 1000, p)
	high := dynamics(900, 700, 1000, p)
	frequent := dynamics(3000, 700, 1000, p)
	if low.Saturation >= high.Saturation || low.NewUserProbability <= high.NewUserProbability || low.PriceFactor >= high.PriceFactor || low.FatigueFactor <= high.FatigueFactor {
		t.Fatalf("non-monotonic saturation: %#v %#v", low, high)
	}
	if frequent.NewUserProbability >= high.NewUserProbability || frequent.FatigueFactor >= high.FatigueFactor {
		t.Fatalf("non-monotonic frequency: %#v %#v", high, frequent)
	}
}
