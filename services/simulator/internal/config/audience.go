package config

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"math"
	"media-planner/services/simulator/internal/domain"
	"sort"
)

const SegmentedEngineVersion = "sim-v2-delivery"

func (b *BaseConfig) UnmarshalJSON(data []byte) error {
	type wire BaseConfig
	var value wire
	d := json.NewDecoder(bytes.NewReader(data))
	d.DisallowUnknownFields()
	if err := d.Decode(&value); err != nil {
		return err
	}
	var raw map[string]json.RawMessage
	if err := json.Unmarshal(data, &raw); err != nil {
		return err
	}
	for _, v := range raw {
		if bytes.Equal(bytes.TrimSpace(v), []byte("null")) {
			return fmt.Errorf("base fields must not be null")
		}
	}
	*b = BaseConfig(value)
	_, b.capacityPresent = raw["audience_capacity"]
	return nil
}

// A map preserves omission (1) versus an explicit zero multiplier.
type Multipliers map[string]float64

func (m Multipliers) Get(key string) float64 {
	if v, ok := m[key]; ok {
		return v
	}
	return 1
}
func (m *Multipliers) UnmarshalJSON(data []byte) error {
	var raw map[string]json.RawMessage
	if err := json.Unmarshal(data, &raw); err != nil {
		return err
	}
	if raw == nil {
		return fmt.Errorf("multipliers must be object")
	}
	out := Multipliers{}
	for k, v := range raw {
		if bytes.Equal(bytes.TrimSpace(v), []byte("null")) {
			return fmt.Errorf("null multiplier")
		}
		var f float64
		if err := json.Unmarshal(v, &f); err != nil {
			return err
		}
		out[k] = f
	}
	*m = out
	return nil
}

type Segment struct {
	ID              string      `json:"id"`
	Geo             string      `json:"geo"`
	Gender          string      `json:"gender"`
	AgeFrom         int         `json:"age_from"`
	AgeTo           int         `json:"age_to_exclusive"`
	WarmCapacity    int64       `json:"warm_capacity"`
	ColdCapacity    int64       `json:"cold_capacity"`
	Multipliers     Multipliers `json:"multipliers,omitempty"`
	WarmMultipliers Multipliers `json:"warm_multipliers,omitempty"`
	ColdMultipliers Multipliers `json:"cold_multipliers,omitempty"`
}

func (s Segment) Capacity() int64 { return s.WarmCapacity + s.ColdCapacity }

func (s *Segment) UnmarshalJSON(data []byte) error {
	type wire Segment
	var value wire
	d := json.NewDecoder(bytes.NewReader(data))
	d.DisallowUnknownFields()
	if err := d.Decode(&value); err != nil {
		return err
	}
	if err := d.Decode(new(any)); err != io.EOF {
		return fmt.Errorf("trailing segment JSON")
	}
	var raw map[string]json.RawMessage
	if err := json.Unmarshal(data, &raw); err != nil {
		return err
	}
	for _, key := range []string{"id", "geo", "gender", "age_from", "age_to_exclusive", "warm_capacity", "cold_capacity"} {
		if _, ok := raw[key]; !ok {
			return fmt.Errorf("segment %s required", key)
		}
	}
	for key, v := range raw {
		if bytes.Equal(bytes.TrimSpace(v), []byte("null")) {
			return fmt.Errorf("segment %s must not be null", key)
		}
	}
	*s = Segment(value)
	return nil
}

func validateSegments(model *WorldModelConfig) error {
	definitions := map[string]Segment{}
	for i := range model.Channels {
		c := &model.Channels[i]
		p := fmt.Sprintf("channels[%d].segments", i)
		if model.EngineVersion == EngineVersion {
			if c.Segments != nil {
				return invalid(p, "unsupported_for_engine_version")
			}
			continue
		}
		if len(c.Segments) < 1 || len(c.Segments) > 128 {
			return invalid(p, "must_have_1_to_128_items")
		}
		if c.Base.capacityPresent || c.Base.AudienceCapacity != (BasePositive{}) {
			return invalid(p, "capacity_must_come_from_segments")
		}
		sort.Slice(c.Segments, func(i, j int) bool { return c.Segments[i].ID < c.Segments[j].ID })
		var total int64
		for j := range c.Segments {
			s := &c.Segments[j]
			if domain.ChannelID(s.ID).Validate() != nil || (j > 0 && c.Segments[j-1].ID == s.ID) {
				return invalid(p, "invalid_or_duplicate_id")
			}
			if s.Geo == "" || len(s.Geo) > 64 || s.Gender == "" || len(s.Gender) > 64 || s.AgeFrom < 0 || s.AgeTo <= s.AgeFrom || s.AgeTo > 131 {
				return invalid(p, "invalid_dimensions")
			}
			if s.WarmCapacity < 0 || s.ColdCapacity < 0 || s.WarmCapacity > math.MaxInt64-s.ColdCapacity || total > math.MaxInt64-s.Capacity() {
				return invalid(p, "invalid_capacity")
			}
			total += s.Capacity()
			if prev, ok := definitions[s.ID]; ok && (prev.Geo != s.Geo || prev.Gender != s.Gender || prev.AgeFrom != s.AgeFrom || prev.AgeTo != s.AgeTo) {
				return invalid(p, "inconsistent_segment_id")
			}
			definitions[s.ID] = *s
			for k := 0; k < j; k++ {
				other := c.Segments[k]
				if s.Geo == other.Geo && s.Gender == other.Gender && s.AgeFrom < other.AgeTo && other.AgeFrom < s.AgeTo {
					return invalid(p, "overlapping_age_groups")
				}
			}
			for index, m := range []Multipliers{s.Multipliers, s.WarmMultipliers, s.ColdMultipliers} {
				for key, value := range m {
					if (key != "cpm" && key != "ctr" && key != "cr" && !(index == 0 && key == "supply")) || !finite(value) || value < 0 || (key == "cpm" && value == 0) {
						return invalid(p, "invalid_multiplier")
					}
					if value == 1 {
						delete(m, key)
					}
				}
			}
		}
	}
	return nil
}

// ResolveAudience returns an owned effective selection for all channels.
func ResolveAudience(model WorldModelConfig, a domain.Audience) (domain.Audience, error) {
	a, err := a.Normalize()
	if err != nil {
		return nil, err
	}
	if model.EngineVersion == EngineVersion {
		if a != nil {
			return nil, domain.NewError(domain.CodeValidation, "audience unsupported").WithField("audience", "unsupported_for_engine_version")
		}
		return nil, nil
	}
	out := domain.Audience{}
	for _, c := range model.Channels {
		ids := map[string]bool{}
		all := []string{}
		for _, s := range c.Segments {
			ids[s.ID] = true
			all = append(all, s.ID)
		}
		sort.Strings(all)
		selection, ok := a[c.ID]
		if !ok {
			selection = domain.ChannelAudience{SegmentIDs: all}
		}
		for _, id := range selection.SegmentIDs {
			if !ids[id] {
				return nil, domain.NewError(domain.CodeValidation, "unknown segment").WithField("audience."+string(c.ID)+".segment_ids", "unknown_segment")
			}
		}
		out[c.ID] = selection
	}
	for id := range a {
		if _, ok := out[id]; !ok {
			return nil, domain.NewError(domain.CodeValidation, "unknown channel").WithField("audience."+string(id), "unknown_channel")
		}
	}
	return out, nil
}
