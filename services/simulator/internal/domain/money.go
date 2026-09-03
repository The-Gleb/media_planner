package domain

import (
	"encoding/json"
	"errors"
	"fmt"
	"math"
	"math/big"
	"strconv"
	"strings"
)

const MoneyScale int64 = 1_000_000

type MoneyMicros int64
type DecimalMoney = MoneyMicros

func ParseMoney(value string) (MoneyMicros, error) {
	if value == "" || strings.TrimSpace(value) != value || strings.HasPrefix(value, "+") || strings.HasPrefix(value, "-") {
		return 0, errors.New("money must be a non-negative decimal")
	}
	parts := strings.Split(value, ".")
	if len(parts) > 2 || parts[0] == "" || (len(parts) == 2 && (parts[1] == "" || len(parts[1]) > 6)) {
		return 0, errors.New("money must have at most six decimals")
	}
	for _, part := range parts {
		for _, r := range part {
			if r < '0' || r > '9' {
				return 0, errors.New("money contains a non-digit")
			}
		}
	}
	whole, err := strconv.ParseUint(parts[0], 10, 63)
	if err != nil || whole > uint64(math.MaxInt64/MoneyScale) {
		return 0, errors.New("money overflows int64 micros")
	}
	frac := uint64(0)
	if len(parts) == 2 {
		padded := parts[1] + strings.Repeat("0", 6-len(parts[1]))
		frac, err = strconv.ParseUint(padded, 10, 20)
		if err != nil {
			return 0, errors.New("invalid money fraction")
		}
	}
	micros := whole*uint64(MoneyScale) + frac
	if micros > uint64(math.MaxInt64) {
		return 0, errors.New("money overflows int64 micros")
	}
	return MoneyMicros(micros), nil
}

func QuantizeFloat64(value float64) (MoneyMicros, error) {
	if math.IsNaN(value) || math.IsInf(value, 0) || value < 0 || value > float64(math.MaxInt64)/float64(MoneyScale) {
		return 0, errors.New("money float is invalid")
	}
	return MoneyMicros(math.Round(value * float64(MoneyScale))), nil
}

func (m MoneyMicros) String() string {
	if m < 0 {
		return "-" + MoneyMicros(-m).String()
	}
	return fmt.Sprintf("%d.%06d", int64(m)/MoneyScale, int64(m)%MoneyScale)
}

func (m MoneyMicros) Float64() float64 { return float64(m) / float64(MoneyScale) }

func (m MoneyMicros) MarshalJSON() ([]byte, error) { return json.Marshal(m.String()) }

func (m *MoneyMicros) UnmarshalJSON(data []byte) error {
	var value string
	if err := json.Unmarshal(data, &value); err != nil {
		return errors.New("money must be encoded as a decimal string")
	}
	parsed, err := ParseMoney(value)
	if err != nil {
		return err
	}
	*m = parsed
	return nil
}

func AddMoney(a, b MoneyMicros) (MoneyMicros, error) {
	if a < 0 || b < 0 || int64(a) > math.MaxInt64-int64(b) {
		return 0, errors.New("money addition overflow")
	}
	return a + b, nil
}

func MulDivFloor(a, b, divisor int64) (int64, error) { return mulDiv(a, b, divisor, false) }
func MulDivCeil(a, b, divisor int64) (int64, error)  { return mulDiv(a, b, divisor, true) }

func mulDiv(a, b, divisor int64, ceil bool) (int64, error) {
	if a < 0 || b < 0 || divisor <= 0 {
		return 0, errors.New("mul-div requires non-negative values and positive divisor")
	}
	product := new(big.Int).Mul(big.NewInt(a), big.NewInt(b))
	quotient, remainder := new(big.Int), new(big.Int)
	quotient.QuoRem(product, big.NewInt(divisor), remainder)
	if ceil && remainder.Sign() != 0 {
		quotient.Add(quotient, big.NewInt(1))
	}
	if !quotient.IsInt64() {
		return 0, errors.New("mul-div overflow")
	}
	return quotient.Int64(), nil
}
