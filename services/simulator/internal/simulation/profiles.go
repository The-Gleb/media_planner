package simulation

import (
	"math"
	"math/rand/v2"
	"time"

	"media-planner/services/simulator/internal/config"
	"media-planner/services/simulator/internal/domain"
)

func generateHourly(cfg config.HourlyPattern, r *rand.Rand) [24]float64 {
	type peak struct{ center, width, amplitude float64 }
	peaks := make([]peak, rangeInt(r, cfg.PeaksCount.Min, cfg.PeaksCount.Max))
	for i := range peaks {
		peaks[i] = peak{rangeFloat(r, cfg.PeakCenterHour.Min, cfg.PeakCenterHour.Max), rangeFloat(r, cfg.PeakWidthHours.Min, cfg.PeakWidthHours.Max), rangeFloat(r, cfg.PeakAmplitude.Min, cfg.PeakAmplitude.Max)}
	}
	var result [24]float64
	mean := 0.0
	for hour := range result {
		value := 1.0
		for _, peak := range peaks {
			distance := math.Abs(float64(hour) - peak.center)
			distance = math.Min(distance, 24-distance)
			value += peak.amplitude * math.Exp(-(distance*distance)/(2*peak.width*peak.width))
		}
		result[hour] = value
		mean += value
	}
	mean /= 24
	for i := range result {
		result[i] /= mean
	}
	return result
}

func generateWeekday(cfg config.WeekdayPattern, r *rand.Rand) [7]float64 {
	variation := rangeFloat(r, cfg.Variation.Min, cfg.Variation.Max)
	weekend := rangeFloat(r, cfg.WeekendModifier.Min, cfg.WeekendModifier.Max)
	phase := r.Float64() * 2 * math.Pi
	var result [7]float64
	mean := 0.0
	for day := range result {
		value := 1 + variation*math.Sin(2*math.Pi*float64(day)/7+phase)
		if day == int(time.Saturday) || day == int(time.Sunday) {
			value *= weekend
		}
		result[day] = math.Max(value, .000001)
		mean += result[day]
	}
	mean /= 7
	for i := range result {
		result[i] /= mean
	}
	return result
}

func localClock(hour domain.Hour, zone string) (int, time.Weekday, error) {
	location, err := time.LoadLocation(zone)
	if err != nil {
		return 0, 0, err
	}
	local := hour.In(location)
	return local.Hour(), local.Weekday(), nil
}
