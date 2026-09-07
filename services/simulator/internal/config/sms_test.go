package config

import "testing"

func TestSMSConfigValidation(t *testing.T) {
	for _, tc := range []struct {
		name   string
		mutate func(*WorldModelConfig, *ChannelModelConfig)
	}{
		{"price", func(_ *WorldModelConfig, c *ChannelModelConfig) { c.SMS.SegmentPrice = -1 }},
		{"segments", func(_ *WorldModelConfig, c *ChannelModelConfig) { c.SMS.SegmentsPerMessage = 0 }},
		{"interval", func(_ *WorldModelConfig, c *ChannelModelConfig) { c.SMS.MinIntervalHours = 0 }},
		{"type", func(_ *WorldModelConfig, c *ChannelModelConfig) { c.Type = "social" }},
		{"legacy", func(m *WorldModelConfig, _ *ChannelModelConfig) { m.EngineVersion = EngineVersion }},
	} {
		t.Run(tc.name, func(t *testing.T) {
			m, err := LoadFile("../../configs/world-config.audience.json")
			if err != nil {
				t.Fatal(err)
			}
			for i := range m.Model.Channels {
				c := &m.Model.Channels[i]
				if c.ID == "sms" {
					tc.mutate(&m.Model, c)
					break
				}
			}
			if validate(m.Model) == nil {
				t.Fatal("invalid SMS config accepted")
			}
		})
	}
}
