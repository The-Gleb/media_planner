package simulation

import (
	"math"
	"media-planner/services/simulator/internal/domain"
	"testing"
)

func TestDeliveryScore(t *testing.T) {
	warm := deliveryScore(true, 100, 100, 0, 0)
	cold := deliveryScore(false, 100, 100, 0, 0)
	if warm/(warm+cold) != .8 {
		t.Fatal(warm, cold)
	}
	saturated := deliveryScore(true, 100, 100, 100, 1000)
	if saturated <= 0 || saturated >= warm {
		t.Fatal(saturated)
	}
	if deliveryScore(true, 0, 100, 0, 0) != 0 || deliveryScore(true, 100, 0, 0, 0) != 0 {
		t.Fatal("empty pool")
	}
}

func TestDeliveryImpressionShares(t *testing.T) {
	p := []poolHour{{requests: 10000, cpm: 100000000, selected: true}, {requests: 10000, cpm: 200000000, selected: true}}
	x, err := allocateDelivery(p, []int64{1, 1}, 300000000)
	if err != nil || math.Abs(float64(x[0]-x[1])) > 1 || x[0] < 999 {
		t.Fatal(x, err)
	}
	p[0].requests = 100
	x, err = allocateDelivery(p, []int64{1, 1}, 300000000)
	if err != nil || x[0] != 100 || x[1] < 1449 {
		t.Fatal(x, err)
	}
	for _, b := range []domain.MoneyMicros{0, 1, 2, 999, 300000000, 9000000000} {
		x, err = allocateDelivery(p, []int64{4, 1}, b)
		if err != nil {
			t.Fatal(err)
		}
		var spent int64
		for i, n := range x {
			if n < 0 || n > p[i].requests {
				t.Fatal(x)
			}
			cost, e := domain.MulDivCeil(n, int64(p[i].cpm), 1000)
			if e != nil {
				t.Fatal(e)
			}
			spent += cost
		}
		if spent > int64(b) {
			t.Fatal(spent, b)
		}
	}
}

func TestDeliveryTinyCostsAndEligibility(t *testing.T) {
	for _, cpm := range []int64{1, 999, 1000, 1001, math.MaxInt64} {
		p := []poolHour{{requests: 100000, cpm: domain.MoneyMicros(cpm), selected: true}, {requests: 100000, cpm: domain.MoneyMicros(cpm), selected: true}, {requests: 100000, cpm: 1, selected: false}}
		for _, budget := range []int64{0, 1, 2, 1000} {
			x, err := allocateDelivery(p, []int64{4, 1, 9}, domain.MoneyMicros(budget))
			if err != nil {
				t.Fatal(err)
			}
			var sum int64
			for i, n := range x {
				c, e := domain.MulDivCeil(n, int64(p[i].cpm), 1000)
				if e != nil {
					t.Fatal(e)
				}
				sum += c
			}
			if sum > budget || x[2] != 0 || (budget == 0 && (x[0] != 0 || x[1] != 0)) {
				t.Fatal(x, sum, budget)
			}
		}
	}
	p := []poolHour{{requests: 100, cpm: 1000, selected: true, capacity: 100, key: poolKey{Temperature: "warm"}}, {requests: 100, cpm: 2000, selected: true, capacity: 100}}
	before, err := deliveryWeights(p, nil)
	if err != nil {
		t.Fatal(err)
	}
	p[0].cpm = 500000
	p[0].ctr = .99
	p[0].cr = .01
	after, err := deliveryWeights(p, nil)
	if err != nil || before[0] != after[0] || before[1] != after[1] {
		t.Fatal("rate dependent score")
	}
}
