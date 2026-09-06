package config

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"math"
	"os"
	"regexp"
	"sort"

	"media-planner/services/simulator/internal/domain"
)

const EngineVersion = "sim-v0"

var currencyPattern = regexp.MustCompile(`^[A-Z]{3}$`)

func LoadFile(path string) (Loaded, error) {
	f, err := os.Open(path)
	if err != nil {
		return Loaded{}, fmt.Errorf("open world config: %w", err)
	}
	defer f.Close()
	return Load(f)
}

func Load(r io.Reader) (Loaded, error) {
	decoder := json.NewDecoder(io.LimitReader(r, 4<<20))
	decoder.DisallowUnknownFields()
	var model WorldModelConfig
	if err := decoder.Decode(&model); err != nil {
		return Loaded{}, fmt.Errorf("decode world config: %w", err)
	}
	var extra any
	if err := decoder.Decode(&extra); err != io.EOF {
		return Loaded{}, fmt.Errorf("decode world config: trailing JSON value")
	}
	if err := validateSegments(&model); err != nil {
		return Loaded{}, err
	}
	if err := validate(model); err != nil {
		return Loaded{}, err
	}
	sort.Slice(model.Channels, func(i, j int) bool { return model.Channels[i].ID < model.Channels[j].ID })
	normalized, err := json.Marshal(model)
	if err != nil {
		return Loaded{}, fmt.Errorf("normalize world config: %w", err)
	}
	digest := sha256.Sum256(normalized)
	return Loaded{Model: model, Digest: hex.EncodeToString(digest[:]), Normalized: normalized}, nil
}

func validate(model WorldModelConfig) error {
	if model.EngineVersion == "sim-v1-segments" {
		return invalid("engine_version", "migrate_to_sim-v2-delivery_and_reset")
	}
	if model.EngineVersion != EngineVersion && model.EngineVersion != SegmentedEngineVersion {
		return invalid("engine_version", "unsupported_engine_version")
	}
	if !currencyPattern.MatchString(model.Currency) {
		return invalid("currency", "invalid_iso4217_code")
	}
	if model.MoneyScale != 6 {
		return invalid("money_scale", "must_equal_6")
	}
	if len(model.Channels) < 1 || len(model.Channels) > 20 {
		return invalid("channels", "must_have_1_to_20_items")
	}
	seen := make(map[domain.ChannelID]struct{}, len(model.Channels))
	for i, channel := range model.Channels {
		prefix := fmt.Sprintf("channels[%d]", i)
		if err := channel.ID.Validate(); err != nil {
			return invalid(prefix+".id", "invalid_format")
		}
		if _, ok := seen[channel.ID]; ok {
			return invalid(prefix+".id", "duplicate")
		}
		seen[channel.ID] = struct{}{}
		if channel.Type == "" {
			return invalid(prefix+".type", "required")
		}
		checked := channel
		if model.EngineVersion == SegmentedEngineVersion {
			checked.Base.AudienceCapacity = BasePositive{Distribution: "log_uniform", Range: FloatRange{Min: 1, Max: 1}}
		}
		if err := validateChannel(prefix, checked); err != nil {
			return err
		}
	}
	return nil
}

func validateChannel(p string, c ChannelModelConfig) error {
	for name, base := range map[string]BasePositive{
		"cpm": c.Base.CPM, "requests_per_day": c.Base.RequestsPerDay, "audience_capacity": c.Base.AudienceCapacity,
	} {
		if base.Distribution != "log_uniform" {
			return invalid(p+".base."+name+".distribution", "must_equal_log_uniform")
		}
		if err := positiveRange(p+".base."+name+".range", base.Range); err != nil {
			return err
		}
	}
	for name, base := range map[string]BaseProbability{"ctr": c.Base.CTR, "cr": c.Base.CR} {
		if base.Distribution != "logit_uniform" {
			return invalid(p+".base."+name+".distribution", "must_equal_logit_uniform")
		}
		if err := probabilityRange(p+".base."+name+".range", base.Range, true); err != nil {
			return err
		}
	}
	for name, pattern := range map[string]HourlyPattern{"supply": c.HourlyPatterns.Supply, "cpm": c.HourlyPatterns.CPM, "ctr": c.HourlyPatterns.CTR, "cr": c.HourlyPatterns.CR} {
		base := p + ".hourly_patterns." + name
		if err := positiveIntRange(base+".peaks_count", pattern.PeaksCount); err != nil {
			return err
		}
		if err := finiteRange(base+".peak_center_hour", pattern.PeakCenterHour); err != nil || pattern.PeakCenterHour.Min < 0 || pattern.PeakCenterHour.Max > 24 {
			return invalid(base+".peak_center_hour", "out_of_range")
		}
		if err := positiveRange(base+".peak_width_hours", pattern.PeakWidthHours); err != nil {
			return err
		}
		if err := nonNegativeRange(base+".peak_amplitude", pattern.PeakAmplitude); err != nil {
			return err
		}
	}
	for name, pattern := range map[string]WeekdayPattern{"supply": c.WeekdayPatterns.Supply, "cpm": c.WeekdayPatterns.CPM, "ctr": c.WeekdayPatterns.CTR, "cr": c.WeekdayPatterns.CR} {
		base := p + ".weekday_patterns." + name
		if err := probabilityRange(base+".variation", pattern.Variation, false); err != nil {
			return err
		}
		if err := positiveRange(base+".weekend_modifier", pattern.WeekendModifier); err != nil {
			return err
		}
	}
	if err := probabilityRange(p+".saturation.start_threshold", c.Saturation.StartThreshold, false); err != nil || c.Saturation.StartThreshold.Max >= 1 {
		return invalid(p+".saturation.start_threshold", "must_be_below_1")
	}
	for name, value := range map[string]FloatRange{
		"price_growth_strength":          c.Saturation.PriceGrowthStrength,
		"reach_decay_strength":           c.Saturation.ReachDecayStrength,
		"frequency_reach_decay_strength": c.Saturation.FrequencyReachDecayStrength,
		"ctr_fatigue_strength":           c.Saturation.CTRFatigueStrength,
		"frequency_fatigue_strength":     c.Saturation.FrequencyFatigueStrength,
		"requests_sigma":                 c.Volatility.RequestsSigma,
		"cpm_sigma":                      c.Volatility.CPMSigma,
	} {
		if err := nonNegativeRange(p+"."+name, value); err != nil {
			return err
		}
	}
	for name, drift := range map[string]DriftConfig{"supply": c.Drift.Supply, "cpm": c.Drift.CPM, "ctr": c.Drift.CTR, "cr": c.Drift.CR} {
		base := p + ".drift." + name
		if !probability(drift.Probability) {
			return invalid(base+".probability", "out_of_range")
		}
		if err := nonNegativeRange(base+".log_strength", drift.LogStrength); err != nil {
			return err
		}
		if err := positiveIntRange(base+".duration_hours", drift.DurationHours); err != nil {
			return err
		}
	}
	for name, shock := range map[string]ShockConfig{"supply": c.Shocks.Supply, "cpm": c.Shocks.CPM, "ctr": c.Shocks.CTR, "cr": c.Shocks.CR} {
		base := p + ".shocks." + name
		if !probability(shock.Probability) {
			return invalid(base+".probability", "out_of_range")
		}
		if err := nonNegativeRange(base+".multiplier", shock.Multiplier); err != nil {
			return err
		}
		if err := positiveIntRange(base+".duration_hours", shock.DurationHours); err != nil {
			return err
		}
	}
	if !probability(c.Shocks.Pause.Probability) {
		return invalid(p+".shocks.pause.probability", "out_of_range")
	}
	return positiveIntRange(p+".shocks.pause.duration_hours", c.Shocks.Pause.DurationHours)
}

func invalid(field, code string) error {
	return domain.NewError(domain.CodeInvalidConfig, "world config is invalid").WithField(field, code)
}
func finite(v float64) bool      { return !math.IsNaN(v) && !math.IsInf(v, 0) }
func probability(v float64) bool { return finite(v) && v >= 0 && v <= 1 }

func finiteRange(path string, r FloatRange) error {
	if !finite(r.Min) || !finite(r.Max) || r.Min > r.Max {
		return invalid(path, "invalid_range")
	}
	return nil
}
func positiveRange(path string, r FloatRange) error {
	if err := finiteRange(path, r); err != nil || r.Min <= 0 {
		return invalid(path, "must_be_positive_range")
	}
	return nil
}
func nonNegativeRange(path string, r FloatRange) error {
	if err := finiteRange(path, r); err != nil || r.Min < 0 {
		return invalid(path, "must_be_non_negative_range")
	}
	return nil
}
func probabilityRange(path string, r FloatRange, interior bool) error {
	if err := finiteRange(path, r); err != nil || r.Min < 0 || r.Max > 1 || (interior && (r.Min <= 0 || r.Max >= 1)) {
		return invalid(path, "must_be_probability_range")
	}
	return nil
}
func positiveIntRange(path string, r IntRange) error {
	if r.Min <= 0 || r.Max < r.Min {
		return invalid(path, "must_be_positive_range")
	}
	return nil
}
