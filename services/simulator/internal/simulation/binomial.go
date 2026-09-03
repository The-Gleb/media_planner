package simulation

import (
	"errors"
	"math"
	"math/rand/v2"
)

const binomialSamplerVersion = "binomial-btrd-v1"

// sampleBinomial uses exact inversion for small means and an exact recursive
// beta split for larger problems. Floating arithmetic only chooses random
// variates; the returned value always lies in [0,n].
func sampleBinomial(r *rand.Rand, n int64, p float64) (int64, error) {
	if n < 0 || math.IsNaN(p) || p < 0 || p > 1 {
		return 0, errors.New("invalid binomial parameters")
	}
	if n == 0 || p == 0 {
		return 0, nil
	}
	if p == 1 {
		return n, nil
	}
	originalN, reflected := n, false
	if p > .5 {
		p, reflected = 1-p, true
	}
	offset := int64(0)
	for float64(n)*p >= 30 {
		a := n/2 + 1
		b := n - a + 1
		x := sampleBeta(r, float64(a), float64(b))
		if x >= p {
			n = a - 1
			p /= x
		} else {
			offset += a
			n = b - 1
			p = (p - x) / (1 - x)
		}
		p = math.Max(0, math.Min(1, p))
		if n == 0 || p == 0 {
			break
		}
		if p == 1 {
			offset += n
			n = 0
			break
		}
	}
	if n > 0 && p > 0 {
		q := 1 - p
		prob := math.Exp(float64(n) * math.Log(q))
		u := r.Float64()
		x := int64(0)
		ratio := p / q
		for u > prob && x < n {
			u -= prob
			x++
			prob *= (float64(n-x+1) / float64(x)) * ratio
		}
		offset += x
	}
	if reflected {
		return originalN - offset, nil
	}
	return offset, nil
}

func sampleBeta(r *rand.Rand, alpha, beta float64) float64 {
	x := sampleGamma(r, alpha)
	y := sampleGamma(r, beta)
	return x / (x + y)
}

func sampleGamma(r *rand.Rand, shape float64) float64 {
	if shape < 1 {
		return sampleGamma(r, shape+1) * math.Pow(r.Float64(), 1/shape)
	}
	d := shape - 1.0/3.0
	c := 1 / math.Sqrt(9*d)
	for {
		x := r.NormFloat64()
		v := 1 + c*x
		if v <= 0 {
			continue
		}
		v = v * v * v
		u := r.Float64()
		if u < 1-.0331*x*x*x*x || math.Log(u) < .5*x*x+d*(1-v+math.Log(v)) {
			return d * v
		}
	}
}
