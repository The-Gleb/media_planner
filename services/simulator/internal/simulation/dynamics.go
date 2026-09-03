package simulation

import "math"

type DynamicsParams struct{ StartThreshold, PriceGrowth, ReachDecay, FrequencyReachDecay, CTRFatigue, FrequencyFatigue float64 }
type Dynamics struct{ Saturation, Frequency, NewUserProbability, PriceFactor, FatigueFactor float64 }

func dynamics(impressions, reach, capacity int64, p DynamicsParams) Dynamics {
	saturation := 0.0
	if capacity > 0 {
		saturation = clamp(float64(reach)/float64(capacity), 0, 1)
	}
	frequency := 1.0
	if reach > 0 {
		frequency = math.Max(1, float64(impressions)/float64(reach))
	}
	z := clamp((saturation-p.StartThreshold)/(1-p.StartThreshold), 0, 1)
	newUser := clamp(math.Pow(1-z, p.ReachDecay)*math.Exp(-p.FrequencyReachDecay*math.Max(frequency-1, 0)), 0, 1)
	return Dynamics{Saturation: saturation, Frequency: frequency, NewUserProbability: newUser, PriceFactor: 1 + p.PriceGrowth*z*z, FatigueFactor: math.Exp(-p.CTRFatigue*z - p.FrequencyFatigue*math.Max(frequency-1, 0))}
}
func clamp(v, min, max float64) float64 {
	if v < min {
		return min
	}
	if v > max {
		return max
	}
	return v
}
