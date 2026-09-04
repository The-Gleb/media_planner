package httptransport

import (
	"regexp"
	"strconv"

	"media-planner/services/simulator/internal/domain"
)

type scenarioEventDTO struct {
	ChannelID     domain.ChannelID `json:"channel_id"`
	Metric        string           `json:"metric"`
	StartIndex    int              `json:"start_index"`
	DurationHours int              `json:"duration_hours"`
	Multiplier    float64          `json:"multiplier"`
}

type simulationConfigDTO struct {
	WorldSeed           string             `json:"world_seed"`
	CampaignSeed        string             `json:"campaign_seed"`
	StartHour           domain.Hour        `json:"start_hour"`
	DurationHours       int                `json:"duration_hours"`
	TimeZone            string             `json:"time_zone"`
	ScenarioEvents      []scenarioEventDTO `json:"scenario_events,omitempty"`
	DisableRandomEvents bool               `json:"disable_random_events,omitempty"`
}

func (d simulationConfigDTO) domain() (domain.SimulationConfig, error) {
	world, err := strconv.ParseInt(d.WorldSeed, 10, 64)
	if err != nil {
		return domain.SimulationConfig{}, domain.NewError(domain.CodeValidation, "invalid world_seed").WithField("world_seed", "invalid_int64")
	}
	campaign, err := strconv.ParseInt(d.CampaignSeed, 10, 64)
	if err != nil {
		return domain.SimulationConfig{}, domain.NewError(domain.CodeValidation, "invalid campaign_seed").WithField("campaign_seed", "invalid_int64")
	}
	events := make([]domain.ScenarioEvent, 0, len(d.ScenarioEvents))
	for _, event := range d.ScenarioEvents {
		events = append(events, domain.ScenarioEvent{ChannelID: event.ChannelID, Metric: event.Metric, StartIndex: event.StartIndex, DurationHours: event.DurationHours, Multiplier: event.Multiplier})
	}
	cfg := domain.SimulationConfig{WorldSeed: world, CampaignSeed: campaign, StartHour: d.StartHour, DurationHours: d.DurationHours, TimeZone: d.TimeZone, ScenarioEvents: events, DisableRandomEvents: d.DisableRandomEvents}
	if err := cfg.Validate(); err != nil {
		return domain.SimulationConfig{}, err
	}
	return cfg, nil
}

type channelActionDTO struct {
	ChannelID domain.ChannelID `json:"channel_id"`
	BudgetCap string           `json:"budget_cap"`
}
type stepRequestDTO struct {
	StepID  string             `json:"step_id"`
	Actions []channelActionDTO `json:"actions"`
}

func (d stepRequestDTO) domainActions() ([]domain.ChannelAction, error) {
	if !stepIDPattern.MatchString(d.StepID) {
		return nil, domain.NewError(domain.CodeValidation, "invalid step_id").WithField("step_id", "invalid_uuid")
	}
	actions := make([]domain.ChannelAction, 0, len(d.Actions))
	for i, a := range d.Actions {
		money, err := domain.ParseMoney(a.BudgetCap)
		if err != nil {
			return nil, domain.NewError(domain.CodeValidation, "invalid action").WithField("actions["+strconv.Itoa(i)+"].budget_cap", "invalid_money")
		}
		actions = append(actions, domain.ChannelAction{ChannelID: a.ChannelID, BudgetCap: money.Float64()})
	}
	return actions, nil
}

func parseSimulationID(value string) (string, error) {
	if !simulationIDPattern.MatchString(value) {
		return "", domain.NewError(domain.CodeValidation, "invalid simulation_id").WithField("simulation_id", "invalid_format")
	}
	return value, nil
}

var (
	simulationIDPattern = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$`)
	stepIDPattern       = regexp.MustCompile(`^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$`)
)
