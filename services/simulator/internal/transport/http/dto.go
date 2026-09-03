package httptransport

import (
	"regexp"
	"strconv"

	"media-planner/services/simulator/internal/domain"
)

type simulationConfigDTO struct {
	WorldSeed     string      `json:"world_seed"`
	CampaignSeed  string      `json:"campaign_seed"`
	StartHour     domain.Hour `json:"start_hour"`
	DurationHours int         `json:"duration_hours"`
	TimeZone      string      `json:"time_zone"`
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
	cfg := domain.SimulationConfig{WorldSeed: world, CampaignSeed: campaign, StartHour: d.StartHour, DurationHours: d.DurationHours, TimeZone: d.TimeZone}
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
	if !uuidPattern.MatchString(d.StepID) {
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

var uuidPattern = regexp.MustCompile(`^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$`)
