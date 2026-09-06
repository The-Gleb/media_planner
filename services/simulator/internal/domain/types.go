package domain

import (
	"encoding/json"
	"errors"
	"fmt"
	"math"
	"regexp"
	"strconv"
	"time"
)

const (
	MinDurationHours = 1
	MaxDurationHours = 2160
)

type ChannelID string

var channelIDPattern = regexp.MustCompile(`^[a-z][a-z0-9_-]{0,63}$`)

func (id ChannelID) Validate() error {
	if !channelIDPattern.MatchString(string(id)) {
		return NewError(CodeValidation, "invalid channel id").WithField("channel_id", "invalid_format")
	}
	return nil
}

type Hour struct{ time.Time }

func ParseHour(value string) (Hour, error) {
	t, err := time.Parse(time.RFC3339, value)
	if err != nil {
		return Hour{}, NewError(CodeValidation, "invalid hour").WithField("hour", "invalid_rfc3339")
	}
	if t.Minute() != 0 || t.Second() != 0 || t.Nanosecond() != 0 {
		return Hour{}, NewError(CodeValidation, "hour must be aligned").WithField("hour", "must_be_hour_aligned")
	}
	return Hour{Time: t.UTC()}, nil
}

func NewHour(t time.Time) (Hour, error) { return ParseHour(t.Format(time.RFC3339Nano)) }

func (h Hour) Add(d time.Duration) Hour { return Hour{Time: h.Time.Add(d).UTC()} }

func (h Hour) String() string {
	if h.Time.IsZero() {
		return ""
	}
	return h.UTC().Format(time.RFC3339)
}

func (h Hour) MarshalJSON() ([]byte, error) {
	if h.Time.IsZero() {
		return []byte("null"), nil
	}
	return json.Marshal(h.String())
}

func (h *Hour) UnmarshalJSON(data []byte) error {
	var value string
	if err := json.Unmarshal(data, &value); err != nil {
		return err
	}
	parsed, err := ParseHour(value)
	if err != nil {
		return err
	}
	*h = parsed
	return nil
}

type ScenarioEvent struct {
	ChannelID     ChannelID `json:"channel_id"`
	Metric        string    `json:"metric"`
	StartIndex    int       `json:"start_index"`
	DurationHours int       `json:"duration_hours"`
	Multiplier    float64   `json:"multiplier"`
}

var scenarioMetrics = map[string]struct{}{"supply": {}, "cpm": {}, "ctr": {}, "cr": {}, "pause": {}}

type SimulationConfig struct {
	Audience            Audience        `json:"audience,omitempty"`
	WorldSeed           int64           `json:"world_seed"`
	CampaignSeed        int64           `json:"campaign_seed"`
	StartHour           Hour            `json:"start_hour"`
	DurationHours       int             `json:"duration_hours"`
	TimeZone            string          `json:"time_zone"`
	ScenarioEvents      []ScenarioEvent `json:"scenario_events,omitempty"`
	DisableRandomEvents bool            `json:"disable_random_events,omitempty"`
}

func (c SimulationConfig) Validate() error {
	var result *Error
	add := func(field, code string) {
		if result == nil {
			result = NewError(CodeValidation, "simulation config is invalid")
		}
		result.WithField(field, code)
	}
	if c.StartHour.Time.IsZero() || c.StartHour.Minute() != 0 || c.StartHour.Second() != 0 || c.StartHour.Nanosecond() != 0 {
		add("start_hour", "must_be_hour_aligned")
	}
	if c.DurationHours < MinDurationHours || c.DurationHours > MaxDurationHours {
		add("duration_hours", "out_of_range")
	}
	if c.TimeZone == "" {
		add("time_zone", "required")
	} else if _, err := time.LoadLocation(c.TimeZone); err != nil {
		add("time_zone", "unknown_time_zone")
	}
	for i, event := range c.ScenarioEvents {
		prefix := "scenario_events[" + strconv.Itoa(i) + "]"
		if err := event.ChannelID.Validate(); err != nil {
			add(prefix+".channel_id", "invalid_format")
		}
		if _, ok := scenarioMetrics[event.Metric]; !ok {
			add(prefix+".metric", "unknown_metric")
		}
		if event.StartIndex < 0 || event.StartIndex >= c.DurationHours {
			add(prefix+".start_index", "out_of_range")
		}
		if event.DurationHours < 1 || event.StartIndex+event.DurationHours > c.DurationHours {
			add(prefix+".duration_hours", "out_of_range")
		}
		if event.Metric != "pause" && (math.IsNaN(event.Multiplier) || math.IsInf(event.Multiplier, 0) || event.Multiplier < 0) {
			add(prefix+".multiplier", "must_be_non_negative_finite")
		}
	}
	if result != nil {
		return result
	}
	return nil
}

type ChannelAction struct {
	ChannelID ChannelID `json:"channel_id"`
	BudgetCap float64   `json:"-"`
}

type Observation struct {
	ChannelID   ChannelID     `json:"channel_id"`
	Hour        Hour          `json:"hour"`
	Requests    int64         `json:"requests"`
	Impressions int64         `json:"impressions"`
	UniqueReach int64         `json:"unique_reach"`
	Clicks      int64         `json:"clicks"`
	Conversions int64         `json:"conversions"`
	Spend       MoneyMicros   `json:"spend"`
	ECPM        *DecimalMoney `json:"ecpm"`
}

type Simulator interface {
	Reset(cfg SimulationConfig) error
	Step(actions []ChannelAction) ([]Observation, error)
	CurrentHour() Hour
}

type SimulationStatus string

const (
	StatusActive   SimulationStatus = "active"
	StatusFinished SimulationStatus = "finished"
	StatusDeleted  SimulationStatus = "deleted"
)

type Code string

const (
	CodeValidation           Code = "validation_error"
	CodeInvalidConfig        Code = "invalid_config"
	CodeMalformedJSON        Code = "malformed_json"
	CodeUnsupportedMediaType Code = "unsupported_media_type"
	CodeNotFound             Code = "not_found"
	CodeGone                 Code = "gone"
	CodeConflict             Code = "conflict"
	CodeActiveLimit          Code = "active_limit"
	CodePreconditionFailed   Code = "precondition_failed"
	CodeSimulationFinished   Code = "simulation_finished"
	CodeStepIDReused         Code = "step_id_reused"
	CodeNotReady             Code = "not_ready"
	CodeInternal             Code = "internal_error"
)

var (
	ErrValidation         = errors.New("validation error")
	ErrInvalidConfig      = errors.New("invalid config")
	ErrNotFound           = errors.New("not found")
	ErrGone               = errors.New("gone")
	ErrConflict           = errors.New("conflict")
	ErrPreconditionFailed = errors.New("precondition failed")
	ErrSimulationFinished = errors.New("simulation finished")
)

type FieldError struct {
	Field  string `json:"field"`
	Code   string `json:"code"`
	Detail string `json:"detail,omitempty"`
}

type Error struct {
	Code    Code
	Message string
	Fields  []FieldError
}

func NewError(code Code, message string) *Error { return &Error{Code: code, Message: message} }

func (e *Error) WithField(field, code string) *Error {
	e.Fields = append(e.Fields, FieldError{Field: field, Code: code})
	return e
}

func (e *Error) Error() string {
	if e.Message == "" {
		return string(e.Code)
	}
	return fmt.Sprintf("%s: %s", e.Code, e.Message)
}

func (e *Error) Unwrap() error {
	switch e.Code {
	case CodeValidation, CodeMalformedJSON, CodeUnsupportedMediaType:
		return ErrValidation
	case CodeInvalidConfig:
		return ErrInvalidConfig
	case CodeNotFound:
		return ErrNotFound
	case CodeGone:
		return ErrGone
	case CodeConflict, CodeActiveLimit, CodeStepIDReused:
		return ErrConflict
	case CodePreconditionFailed:
		return ErrPreconditionFailed
	case CodeSimulationFinished:
		return ErrSimulationFinished
	default:
		return nil
	}
}
