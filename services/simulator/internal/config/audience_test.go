package config

import (
	"bytes"
	"encoding/json"
	"fmt"
	"testing"
)

func TestSegmentConfig(t *testing.T) {
	model, err := LoadFile("../../configs/world-config.audience.json")
	if err != nil {
		t.Fatal(err)
	}
	if model.Model.EngineVersion != "sim-v2-delivery" {
		t.Fatal("expected delivery model")
	}
	reload, err := Load(bytes.NewReader(model.Normalized))
	if err != nil || reload.Digest != model.Digest {
		t.Fatal("unstable normalization", err)
	}
	for _, mutate := range []func(*WorldModelConfig){
		func(m *WorldModelConfig) { m.EngineVersion = "sim-v1-segments" },
		func(m *WorldModelConfig) { m.EngineVersion = "unknown" },
		func(m *WorldModelConfig) { m.Channels[0].Segments[0].WarmCapacity = -1 },
		func(m *WorldModelConfig) { m.Channels[0].Segments[0].WarmCapacity = 9223372036854775807 },
		func(m *WorldModelConfig) { m.Channels[0].Segments[0].AgeTo = 0 },
		func(m *WorldModelConfig) { m.Channels[0].Segments[0].Multipliers["bogus"] = 1 },
		func(m *WorldModelConfig) { m.EngineVersion = "sim-v0" },
		func(m *WorldModelConfig) { m.Channels[0].Segments[0].Multipliers["cpm"] = 0 },
		func(m *WorldModelConfig) {
			m.Channels[0].Segments = append(m.Channels[0].Segments, m.Channels[0].Segments[0])
		},
		func(m *WorldModelConfig) {
			m.Channels[0].Base.AudienceCapacity = BasePositive{Distribution: "log_uniform", Range: FloatRange{1, 2}}
		},
	} {
		fresh, _ := Load(bytes.NewReader(model.Normalized))
		mutate(&fresh.Model)
		raw, _ := json.Marshal(fresh.Model)
		if _, err := Load(bytes.NewReader(raw)); err == nil {
			t.Fatal("accepted invalid model")
		}
	}
}

func TestAudienceBoundariesAndOrdering(t *testing.T) {
	m, err := LoadFile("../../configs/world-config.audience.json")
	if err != nil {
		t.Fatal(err)
	}
	for _, c := range m.Model.Channels {
		for i, j := 0, len(c.Segments)-1; i < j; i, j = i+1, j-1 {
			c.Segments[i], c.Segments[j] = c.Segments[j], c.Segments[i]
		}
	}
	raw, _ := json.Marshal(m.Model)
	reordered, err := Load(bytes.NewReader(raw))
	if err != nil || reordered.Digest != m.Digest {
		t.Fatal("ordering changes digest", err)
	}
	for _, mutate := range []func(*WorldModelConfig){
		func(m *WorldModelConfig) { m.Channels[0].Segments[0].AgeTo = 45 },
		func(m *WorldModelConfig) { m.Channels[0].Segments[0].Geo = "different" },
	} {
		fresh, _ := Load(bytes.NewReader(m.Normalized))
		mutate(&fresh.Model)
		raw, _ := json.Marshal(fresh.Model)
		if _, err := Load(bytes.NewReader(raw)); err == nil {
			t.Fatal("accepted inconsistent/overlapping dimensions")
		}
	}
	m.Model.Channels = m.Model.Channels[:1]
	c := &m.Model.Channels[0]
	c.Segments = nil
	for i := 0; i < 129; i++ {
		c.Segments = append(c.Segments, Segment{ID: fmt.Sprintf("segment_%03d", i), Geo: fmt.Sprintf("geo_%03d", i), Gender: "female", AgeFrom: 25, AgeTo: 35})
		if i == 127 || i == 128 {
			raw, _ := json.Marshal(m.Model)
			_, err := Load(bytes.NewReader(raw))
			if (err == nil) != (i == 127) {
				t.Fatalf("segment count %d: %v", i+1, err)
			}
		}
	}
}

func TestAudienceRequiredAndNeutralFields(t *testing.T) {
	m, err := LoadFile("../../configs/world-config.audience.json")
	if err != nil {
		t.Fatal(err)
	}
	for _, bad := range [][]byte{
		bytes.Replace(m.Normalized, []byte(`"warm_capacity":`), []byte(`"unknown_capacity":`), 1),
		bytes.Replace(m.Normalized, []byte(`"age_from":25`), []byte(`"age_from":null`), 1),
		bytes.Replace(m.Normalized, []byte(`"cpm":1.2`), []byte(`"cpm":null`), 1),
	} {
		if _, err := Load(bytes.NewReader(bad)); err == nil {
			t.Fatal("accepted null/missing field")
		}
	}
	before := m.Digest
	m.Model.Channels[0].Segments[0].Multipliers["ctr"] = 1
	raw, _ := json.Marshal(m.Model)
	same, err := Load(bytes.NewReader(raw))
	if err != nil || same.Digest != before {
		t.Fatal("neutral defaults differ", err)
	}
}
