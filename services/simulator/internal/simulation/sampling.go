package simulation

import (
	"crypto/sha256"
	"encoding/binary"
	"math"
	"math/rand/v2"
)

func deriveSeeds(seed int64, parts ...any) (uint64, uint64) {
	h := sha256.New()
	var buf [8]byte
	binary.BigEndian.PutUint64(buf[:], uint64(seed))
	h.Write(buf[:])
	for _, part := range parts {
		var value []byte
		switch v := part.(type) {
		case string:
			value = []byte(v)
		case int:
			binary.BigEndian.PutUint64(buf[:], uint64(v))
			value = append(value, buf[:]...)
		case int64:
			binary.BigEndian.PutUint64(buf[:], uint64(v))
			value = append(value, buf[:]...)
		default:
			panic("unsupported seed component")
		}
		binary.BigEndian.PutUint64(buf[:], uint64(len(value)))
		h.Write(buf[:])
		h.Write(value)
	}
	sum := h.Sum(nil)
	return binary.BigEndian.Uint64(sum[:8]), binary.BigEndian.Uint64(sum[8:16])
}

func newStream(seed int64, parts ...any) *rand.Rand {
	a, b := deriveSeeds(seed, parts...)
	return rand.New(rand.NewPCG(a, b))
}

func rangeFloat(r *rand.Rand, min, max float64) float64 {
	if min == max {
		return min
	}
	return min + r.Float64()*(max-min)
}

func rangeInt(r *rand.Rand, min, max int) int {
	if min == max {
		return min
	}
	return min + r.IntN(max-min+1)
}

func logUniform(r *rand.Rand, min, max float64) float64 {
	return math.Exp(rangeFloat(r, math.Log(min), math.Log(max)))
}

func logitUniform(r *rand.Rand, min, max float64) float64 {
	logit := func(p float64) float64 { return math.Log(p / (1 - p)) }
	x := rangeFloat(r, logit(min), logit(max))
	return 1 / (1 + math.Exp(-x))
}

func lognormalMeanOne(r *rand.Rand, sigma float64) float64 {
	if sigma == 0 {
		return 1
	}
	return math.Exp(sigma*r.NormFloat64() - sigma*sigma/2)
}
