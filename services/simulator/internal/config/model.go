package config

import "media-planner/services/simulator/internal/domain"

type FloatRange struct {
	Min float64 `json:"min"`
	Max float64 `json:"max"`
}

type IntRange struct {
	Min int `json:"min"`
	Max int `json:"max"`
}

type BasePositive struct {
	Distribution string     `json:"distribution"`
	Range        FloatRange `json:"range"`
}

type BaseProbability struct {
	Distribution string     `json:"distribution"`
	Range        FloatRange `json:"range"`
}

type BaseConfig struct {
	CPM              BasePositive    `json:"cpm"`
	CTR              BaseProbability `json:"ctr"`
	CR               BaseProbability `json:"cr"`
	RequestsPerDay   BasePositive    `json:"requests_per_day"`
	AudienceCapacity BasePositive    `json:"audience_capacity"`
}

type HourlyPattern struct {
	PeaksCount     IntRange   `json:"peaks_count"`
	PeakCenterHour FloatRange `json:"peak_center_hour"`
	PeakWidthHours FloatRange `json:"peak_width_hours"`
	PeakAmplitude  FloatRange `json:"peak_amplitude"`
}

type HourlyPatterns struct {
	Supply HourlyPattern `json:"supply"`
	CPM    HourlyPattern `json:"cpm"`
	CTR    HourlyPattern `json:"ctr"`
	CR     HourlyPattern `json:"cr"`
}

type WeekdayPattern struct {
	Variation       FloatRange `json:"variation"`
	WeekendModifier FloatRange `json:"weekend_modifier"`
}

type WeekdayPatterns struct {
	Supply WeekdayPattern `json:"supply"`
	CPM    WeekdayPattern `json:"cpm"`
	CTR    WeekdayPattern `json:"ctr"`
	CR     WeekdayPattern `json:"cr"`
}

type SaturationConfig struct {
	StartThreshold              FloatRange `json:"start_threshold"`
	PriceGrowthStrength         FloatRange `json:"price_growth_strength"`
	ReachDecayStrength          FloatRange `json:"reach_decay_strength"`
	FrequencyReachDecayStrength FloatRange `json:"frequency_reach_decay_strength"`
	CTRFatigueStrength          FloatRange `json:"ctr_fatigue_strength"`
	FrequencyFatigueStrength    FloatRange `json:"frequency_fatigue_strength"`
}

type VolatilityConfig struct {
	RequestsSigma FloatRange `json:"requests_sigma"`
	CPMSigma      FloatRange `json:"cpm_sigma"`
}

type DriftConfig struct {
	Probability   float64    `json:"probability"`
	LogStrength   FloatRange `json:"log_strength"`
	DurationHours IntRange   `json:"duration_hours"`
}

type DriftPatterns struct {
	Supply DriftConfig `json:"supply"`
	CPM    DriftConfig `json:"cpm"`
	CTR    DriftConfig `json:"ctr"`
	CR     DriftConfig `json:"cr"`
}

type ShockConfig struct {
	Probability   float64    `json:"probability"`
	Multiplier    FloatRange `json:"multiplier"`
	DurationHours IntRange   `json:"duration_hours"`
}

type PauseConfig struct {
	Probability   float64  `json:"probability"`
	DurationHours IntRange `json:"duration_hours"`
}

type ShockPatterns struct {
	Supply ShockConfig `json:"supply"`
	CPM    ShockConfig `json:"cpm"`
	CTR    ShockConfig `json:"ctr"`
	CR     ShockConfig `json:"cr"`
	Pause  PauseConfig `json:"pause"`
}

type ChannelModelConfig struct {
	ID              domain.ChannelID `json:"id"`
	Type            string           `json:"type"`
	Base            BaseConfig       `json:"base"`
	HourlyPatterns  HourlyPatterns   `json:"hourly_patterns"`
	WeekdayPatterns WeekdayPatterns  `json:"weekday_patterns"`
	Saturation      SaturationConfig `json:"saturation"`
	Volatility      VolatilityConfig `json:"volatility"`
	Drift           DriftPatterns    `json:"drift"`
	Shocks          ShockPatterns    `json:"shocks"`
}

type WorldModelConfig struct {
	EngineVersion string               `json:"engine_version"`
	Currency      string               `json:"currency"`
	MoneyScale    int                  `json:"money_scale"`
	Channels      []ChannelModelConfig `json:"channels"`
}

type Loaded struct {
	Model      WorldModelConfig
	Digest     string
	Normalized []byte
}
