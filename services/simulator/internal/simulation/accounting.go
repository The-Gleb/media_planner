package simulation

import (
	"errors"

	"media-planner/services/simulator/internal/domain"
)

func affordableImpressions(budget, cpm domain.MoneyMicros) (int64, error) {
	if budget < 0 || cpm <= 0 {
		return 0, errors.New("invalid budget or CPM")
	}
	return domain.MulDivFloor(int64(budget), 1000, int64(cpm))
}
func spendAndECPM(impressions int64, cpm domain.MoneyMicros) (domain.MoneyMicros, *domain.DecimalMoney, error) {
	if impressions < 0 || cpm <= 0 {
		return 0, nil, errors.New("invalid impressions or CPM")
	}
	if impressions == 0 {
		return 0, nil, nil
	}
	spend, err := domain.MulDivCeil(impressions, int64(cpm), 1000)
	if err != nil {
		return 0, nil, err
	}
	e, err := domain.MulDivCeil(spend, 1000, impressions)
	if err != nil {
		return 0, nil, err
	}
	ecpm := domain.DecimalMoney(e)
	return domain.MoneyMicros(spend), &ecpm, nil
}
