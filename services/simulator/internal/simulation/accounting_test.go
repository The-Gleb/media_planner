package simulation

import (
	"math"
	"testing"

	"media-planner/services/simulator/internal/domain"
)

func TestAccountingInvariants(t *testing.T) {
	budget, _ := domain.ParseMoney("1500.000000")
	cpm, _ := domain.ParseMoney("12.345678")
	affordable, err := affordableImpressions(budget, cpm)
	if err != nil || affordable <= 0 {
		t.Fatalf("affordable=%d err=%v", affordable, err)
	}
	spend, ecpm, err := spendAndECPM(affordable, cpm)
	if err != nil || spend > budget || ecpm == nil {
		t.Fatalf("spend=%s budget=%s ecpm=%v err=%v", spend, budget, ecpm, err)
	}
	zeroSpend, zeroECPM, err := spendAndECPM(0, cpm)
	if err != nil || zeroSpend != 0 || zeroECPM != nil {
		t.Fatalf("zero=%v %v %v", zeroSpend, zeroECPM, err)
	}
	if _, err := affordableImpressions(budget, 0); err == nil {
		t.Fatal("expected zero CPM error")
	}
	if _, _, err := spendAndECPM(math.MaxInt64, domain.MoneyMicros(math.MaxInt64)); err == nil {
		t.Fatal("expected overflow")
	}
}
