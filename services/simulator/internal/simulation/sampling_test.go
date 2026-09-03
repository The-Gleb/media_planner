package simulation

import (
	"math"
	"testing"
)

func TestDerivedStreamsAreStableAndSeparated(t *testing.T) {
	a1, b1 := deriveSeeds(42, "sim-v0", "social_1", "clicks", 7)
	a2, b2 := deriveSeeds(42, "sim-v0", "social_1", "clicks", 7)
	a3, b3 := deriveSeeds(42, "sim-v0", "social_1", "conversions", 7)
	if a1 != a2 || b1 != b2 || (a1 == a3 && b1 == b3) {
		t.Fatalf("unstable or unseparated seeds: %x/%x %x/%x", a1, b1, a3, b3)
	}
	r1 := newStream(42, "sim-v0", "social_1", "clicks", 7)
	r2 := newStream(42, "sim-v0", "social_1", "clicks", 7)
	for i := 0; i < 16; i++ {
		if r1.Uint64() != r2.Uint64() {
			t.Fatal("fixed stream diverged")
		}
	}
}

func TestLognormalNoiseHasMeanNearOne(t *testing.T) {
	r := newStream(99, "sim-v0", "market", "noise", 0)
	const n = 100000
	sum := 0.0
	for i := 0; i < n; i++ {
		sum += lognormalMeanOne(r, 0.2)
	}
	if mean := sum / n; math.Abs(mean-1) > 0.01 {
		t.Fatalf("mean=%f", mean)
	}
}
