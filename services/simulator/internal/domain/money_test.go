package domain

import (
	"math"
	"testing"
)

func TestParseMoney(t *testing.T) {
	t.Parallel()
	cases := []struct {
		in   string
		want MoneyMicros
		text string
	}{
		{"0", 0, "0.000000"},
		{"1", 1_000_000, "1.000000"},
		{"12.34", 12_340_000, "12.340000"},
		{"0.000001", 1, "0.000001"},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.in, func(t *testing.T) {
			got, err := ParseMoney(tc.in)
			if err != nil || got != tc.want || got.String() != tc.text {
				t.Fatalf("ParseMoney(%q)=(%v,%v,%q), want (%v,nil,%q)", tc.in, got, err, got.String(), tc.want, tc.text)
			}
		})
	}
}

func TestParseMoneyRejectsInvalid(t *testing.T) {
	t.Parallel()
	for _, in := range []string{"", "-1", "+1", "1.0000001", "1e3", " 1", "9223372036854.775808"} {
		if _, err := ParseMoney(in); err == nil {
			t.Errorf("ParseMoney(%q) unexpectedly succeeded", in)
		}
	}
}

func TestQuantizeFloat64HalfAway(t *testing.T) {
	t.Parallel()
	got, err := QuantizeFloat64(1.2345675)
	if err != nil || got != 1_234_568 {
		t.Fatalf("got %d, %v", got, err)
	}
	for _, in := range []float64{-1, math.NaN(), math.Inf(1)} {
		if _, err := QuantizeFloat64(in); err == nil {
			t.Errorf("QuantizeFloat64(%v) unexpectedly succeeded", in)
		}
	}
}

func TestCheckedMoneyArithmetic(t *testing.T) {
	t.Parallel()
	if got, err := AddMoney(10, 20); err != nil || got != 30 {
		t.Fatalf("AddMoney: %d %v", got, err)
	}
	if _, err := AddMoney(MoneyMicros(math.MaxInt64), 1); err == nil {
		t.Fatal("expected overflow")
	}
	if got, err := MulDivFloor(10, 3, 4); err != nil || got != 7 {
		t.Fatalf("MulDivFloor: %d %v", got, err)
	}
	if got, err := MulDivCeil(10, 3, 4); err != nil || got != 8 {
		t.Fatalf("MulDivCeil: %d %v", got, err)
	}
}
