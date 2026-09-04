package simulation

import (
	"math"

	"media-planner/services/simulator/internal/config"
	"media-planner/services/simulator/internal/domain"
)

type eventKind string
type metric string

const (
	eventDrift   eventKind = "drift"
	eventShock   eventKind = "shock"
	metricSupply metric    = "supply"
	metricCPM    metric    = "cpm"
	metricCTR    metric    = "ctr"
	metricCR     metric    = "cr"
	metricPause  metric    = "pause"
)

type EventSchedule struct {
	ChannelID                 domain.ChannelID
	Kind                      eventKind
	Metric                    metric
	StartIndex, DurationHours int
	Direction                 int
	LogStrength, Multiplier   float64
}

type eventFactors struct {
	Supply, CPM, CTR, CR float64
	Paused               bool
}

func generateEvents(channel config.ChannelModelConfig, campaignSeed int64, duration int) []EventSchedule {
	result := make([]EventSchedule, 0, 9)
	drifts := []struct {
		name   string
		metric metric
		cfg    config.DriftConfig
	}{{"supply", metricSupply, channel.Drift.Supply}, {"cpm", metricCPM, channel.Drift.CPM}, {"ctr", metricCTR, channel.Drift.CTR}, {"cr", metricCR, channel.Drift.CR}}
	for _, item := range drifts {
		r := newStream(campaignSeed, config.EngineVersion, string(channel.ID), "drift/"+item.name, 0)
		if r.Float64() >= item.cfg.Probability {
			continue
		}
		direction := 1
		if r.IntN(2) == 0 {
			direction = -1
		}
		result = append(result, EventSchedule{ChannelID: channel.ID, Kind: eventDrift, Metric: item.metric, StartIndex: r.IntN(duration), DurationHours: rangeInt(r, item.cfg.DurationHours.Min, item.cfg.DurationHours.Max), Direction: direction, LogStrength: rangeFloat(r, item.cfg.LogStrength.Min, item.cfg.LogStrength.Max), Multiplier: 1})
	}
	shocks := []struct {
		name   string
		metric metric
		cfg    config.ShockConfig
	}{{"supply", metricSupply, channel.Shocks.Supply}, {"cpm", metricCPM, channel.Shocks.CPM}, {"ctr", metricCTR, channel.Shocks.CTR}, {"cr", metricCR, channel.Shocks.CR}}
	for _, item := range shocks {
		r := newStream(campaignSeed, config.EngineVersion, string(channel.ID), "shock/"+item.name, 0)
		if r.Float64() >= item.cfg.Probability {
			continue
		}
		result = append(result, EventSchedule{ChannelID: channel.ID, Kind: eventShock, Metric: item.metric, StartIndex: r.IntN(duration), DurationHours: rangeInt(r, item.cfg.DurationHours.Min, item.cfg.DurationHours.Max), Multiplier: rangeFloat(r, item.cfg.Multiplier.Min, item.cfg.Multiplier.Max)})
	}
	r := newStream(campaignSeed, config.EngineVersion, string(channel.ID), "shock/pause", 0)
	if r.Float64() < channel.Shocks.Pause.Probability {
		result = append(result, EventSchedule{ChannelID: channel.ID, Kind: eventShock, Metric: metricPause, StartIndex: r.IntN(duration), DurationHours: rangeInt(r, channel.Shocks.Pause.DurationHours.Min, channel.Shocks.Pause.DurationHours.Max), Multiplier: 0})
	}
	return result
}

func explicitEvents(channelID domain.ChannelID, events []domain.ScenarioEvent) []EventSchedule {
	result := make([]EventSchedule, 0, len(events))
	for _, event := range events {
		if event.ChannelID != channelID {
			continue
		}
		schedule := EventSchedule{ChannelID: channelID, Kind: eventShock, Metric: metric(event.Metric), StartIndex: event.StartIndex, DurationHours: event.DurationHours, Multiplier: event.Multiplier}
		if schedule.Metric == metricPause {
			schedule.Multiplier = 0
		}
		result = append(result, schedule)
	}
	return result
}

func evaluateEvents(events []EventSchedule, index int) eventFactors {
	f := eventFactors{Supply: 1, CPM: 1, CTR: 1, CR: 1}
	for _, event := range events {
		factor := 1.0
		if event.Kind == eventDrift {
			if index < event.StartIndex {
				continue
			}
			progress := math.Min(1, float64(index-event.StartIndex+1)/float64(event.DurationHours))
			factor = math.Exp(float64(event.Direction) * event.LogStrength * progress)
		} else {
			if index < event.StartIndex || index >= event.StartIndex+event.DurationHours {
				continue
			}
			factor = event.Multiplier
		}
		switch event.Metric {
		case metricSupply:
			f.Supply *= factor
		case metricCPM:
			f.CPM *= factor
		case metricCTR:
			f.CTR *= factor
		case metricCR:
			f.CR *= factor
		case metricPause:
			f.Paused = true
		}
	}
	return f
}
