package simulation

import (
	"math"
	"testing"
)

func TestBinomialBoundariesAndStableSequence(t *testing.T) {
	r := newStream(1, "sim-v0", "c", "binomial", 0)
	for _, tc := range []struct {
		n    int64
		p    float64
		want int64
	}{{0, .5, 0}, {10, 0, 0}, {10, 1, 10}} {
		got, err := sampleBinomial(r, tc.n, tc.p)
		if err != nil || got != tc.want {
			t.Fatalf("(%d,%f)=%d,%v", tc.n, tc.p, got, err)
		}
	}
	r1 := newStream(2, "sim-v0", "c", "binomial", 0)
	r2 := newStream(2, "sim-v0", "c", "binomial", 0)
	for i := 0; i < 50; i++ {
		a, _ := sampleBinomial(r1, 1_000_000, .21)
		b, _ := sampleBinomial(r2, 1_000_000, .21)
		if a != b || a < 0 || a > 1_000_000 {
			t.Fatalf("unstable binomial %d %d", a, b)
		}
	}
}

func TestBinomialStatistics(t *testing.T) {
	r := newStream(3, "sim-v0", "c", "binomial", 0)
	const samples, n = 20000, int64(100)
	const p = .3
	var sum, sum2 float64
	for i := 0; i < samples; i++ {
		x, err := sampleBinomial(r, n, p)
		if err != nil {
			t.Fatal(err)
		}
		sum += float64(x)
		sum2 += float64(x * x)
	}
	mean := sum / samples
	variance := sum2/samples - mean*mean
	if math.Abs(mean-float64(n)*p) > .15 || math.Abs(variance-float64(n)*p*(1-p)) > .5 {
		t.Fatalf("mean=%f variance=%f", mean, variance)
	}
}
