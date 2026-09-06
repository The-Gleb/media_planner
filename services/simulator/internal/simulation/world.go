package simulation

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"math"
	"math/rand/v2"

	"media-planner/services/simulator/internal/config"
	"media-planner/services/simulator/internal/domain"
)

type HiddenChannel struct {
	Segments                                         []config.Segment   `json:"segments,omitempty"`
	ID                                               domain.ChannelID   `json:"id"`
	BaseCPM                                          domain.MoneyMicros `json:"base_cpm_micros"`
	BaseCTR, BaseCR                                  float64
	BaseRequestsPerDay, AudienceCapacity             int64
	HourlySupply, HourlyCPM, HourlyCTR, HourlyCR     [24]float64
	WeekdaySupply, WeekdayCPM, WeekdayCTR, WeekdayCR [7]float64
	Dynamics                                         DynamicsParams
	RequestsSigma, CPMSigma                          float64
}
type World struct {
	Channels    []HiddenChannel `json:"channels"`
	Fingerprint string          `json:"-"`
}

func generateWorld(loaded config.Loaded, seed int64) (World, error) {
	w := World{Channels: make([]HiddenChannel, 0, len(loaded.Model.Channels))}
	for _, c := range loaded.Model.Channels {
		stream := func(tag string) *rand.Rand { return newStream(seed, loaded.Model.EngineVersion, string(c.ID), tag, 0) }
		baseCPM, err := domain.QuantizeFloat64(logUniform(stream("base/cpm"), c.Base.CPM.Range.Min, c.Base.CPM.Range.Max))
		if err != nil {
			return World{}, err
		}
		requests := int64(math.Round(logUniform(stream("base/requests"), c.Base.RequestsPerDay.Range.Min, c.Base.RequestsPerDay.Range.Max)))
		var capacity int64
		if loaded.Model.EngineVersion == config.SegmentedEngineVersion {
			for _, s := range c.Segments {
				capacity += s.Capacity()
			}
		} else {
			capacity = int64(math.Round(logUniform(stream("base/capacity"), c.Base.AudienceCapacity.Range.Min, c.Base.AudienceCapacity.Range.Max)))
		}
		h := HiddenChannel{ID: c.ID, BaseCPM: baseCPM, BaseCTR: logitUniform(stream("base/ctr"), c.Base.CTR.Range.Min, c.Base.CTR.Range.Max), BaseCR: logitUniform(stream("base/cr"), c.Base.CR.Range.Min, c.Base.CR.Range.Max), BaseRequestsPerDay: requests, AudienceCapacity: capacity}
		h.HourlySupply = generateHourly(c.HourlyPatterns.Supply, stream("hourly/supply"))
		h.Segments = c.Segments
		h.HourlyCPM = generateHourly(c.HourlyPatterns.CPM, stream("hourly/cpm"))
		h.HourlyCTR = generateHourly(c.HourlyPatterns.CTR, stream("hourly/ctr"))
		h.HourlyCR = generateHourly(c.HourlyPatterns.CR, stream("hourly/cr"))
		h.WeekdaySupply = generateWeekday(c.WeekdayPatterns.Supply, stream("weekday/supply"))
		h.WeekdayCPM = generateWeekday(c.WeekdayPatterns.CPM, stream("weekday/cpm"))
		h.WeekdayCTR = generateWeekday(c.WeekdayPatterns.CTR, stream("weekday/ctr"))
		h.WeekdayCR = generateWeekday(c.WeekdayPatterns.CR, stream("weekday/cr"))
		h.Dynamics = DynamicsParams{rangeFloat(stream("saturation/threshold"), c.Saturation.StartThreshold.Min, c.Saturation.StartThreshold.Max), rangeFloat(stream("saturation/price"), c.Saturation.PriceGrowthStrength.Min, c.Saturation.PriceGrowthStrength.Max), rangeFloat(stream("saturation/reach"), c.Saturation.ReachDecayStrength.Min, c.Saturation.ReachDecayStrength.Max), rangeFloat(stream("saturation/frequency_reach"), c.Saturation.FrequencyReachDecayStrength.Min, c.Saturation.FrequencyReachDecayStrength.Max), rangeFloat(stream("saturation/ctr"), c.Saturation.CTRFatigueStrength.Min, c.Saturation.CTRFatigueStrength.Max), rangeFloat(stream("saturation/frequency"), c.Saturation.FrequencyFatigueStrength.Min, c.Saturation.FrequencyFatigueStrength.Max)}
		h.RequestsSigma = rangeFloat(stream("volatility/requests"), c.Volatility.RequestsSigma.Min, c.Volatility.RequestsSigma.Max)
		h.CPMSigma = rangeFloat(stream("volatility/cpm"), c.Volatility.CPMSigma.Min, c.Volatility.CPMSigma.Max)
		if h.BaseCPM <= 0 || h.BaseRequestsPerDay <= 0 || (h.AudienceCapacity <= 0 && loaded.Model.EngineVersion == config.EngineVersion) {
			return World{}, fmt.Errorf("generated invalid channel %s", c.ID)
		}
		w.Channels = append(w.Channels, h)
	}
	b, _ := json.Marshal(w)
	sum := sha256.Sum256(b)
	w.Fingerprint = hex.EncodeToString(sum[:])
	return w, nil
}
