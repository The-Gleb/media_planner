package simulation

import (
	"math"
	"sort"
	"strconv"
	"sync"
	"time"

	"media-planner/services/simulator/internal/config"
	"media-planner/services/simulator/internal/domain"
)

type runtimeState struct{ Impressions, UniqueReach int64 }

type Engine struct {
	mu          sync.Mutex
	model       config.Loaded
	cfg         domain.SimulationConfig
	world       World
	current     domain.Hour
	steps       int
	states      map[domain.ChannelID]runtimeState
	pools       map[poolKey]runtimeState
	smsCooldown map[poolKey][]smsCohort
	events      map[domain.ChannelID][]EventSchedule
	ready       bool
}

func New(model config.Loaded) *Engine { return &Engine{model: model} }

func (e *Engine) Reset(cfg domain.SimulationConfig) error {
	audience, err := config.ResolveAudience(e.model.Model, cfg.Audience)
	if err != nil {
		return err
	}
	cfg.Audience = audience
	if err := cfg.Validate(); err != nil {
		return err
	}
	world, err := generateWorld(e.model, cfg.WorldSeed)
	if err != nil {
		return domain.NewError(domain.CodeInternal, "world generation failed")
	}
	states := make(map[domain.ChannelID]runtimeState, len(world.Channels))
	events := make(map[domain.ChannelID][]EventSchedule, len(world.Channels))
	configByID := make(map[domain.ChannelID]config.ChannelModelConfig, len(e.model.Model.Channels))
	for _, c := range e.model.Model.Channels {
		configByID[c.ID] = c
	}
	for i, event := range cfg.ScenarioEvents {
		if _, ok := configByID[event.ChannelID]; !ok {
			return domain.NewError(domain.CodeValidation, "simulation config is invalid").WithField("scenario_events["+strconv.Itoa(i)+"].channel_id", "unknown_channel")
		}
	}
	for _, c := range world.Channels {
		states[c.ID] = runtimeState{}
		schedule := []EventSchedule{}
		if !cfg.DisableRandomEvents {
			schedule = generateEvents(configByID[c.ID], cfg.CampaignSeed, cfg.DurationHours)
		}
		events[c.ID] = append(schedule, explicitEvents(c.ID, cfg.ScenarioEvents)...)
	}
	e.mu.Lock()
	defer e.mu.Unlock()
	e.cfg = cfg
	e.world = world
	e.current = cfg.StartHour
	e.steps = 0
	e.states = states
	e.pools = map[poolKey]runtimeState{}
	e.smsCooldown = map[poolKey][]smsCohort{}
	e.events = events
	e.ready = true
	return nil
}

func (e *Engine) CurrentHour() domain.Hour { e.mu.Lock(); defer e.mu.Unlock(); return e.current }
func (e *Engine) WorldFingerprint() string {
	e.mu.Lock()
	defer e.mu.Unlock()
	return e.world.Fingerprint
}
func (e *Engine) ChannelIDs() []domain.ChannelID {
	e.mu.Lock()
	defer e.mu.Unlock()
	ids := make([]domain.ChannelID, len(e.world.Channels))
	for i, c := range e.world.Channels {
		ids[i] = c.ID
	}
	return ids
}

func (e *Engine) Step(actions []domain.ChannelAction) ([]domain.Observation, error) {
	e.mu.Lock()
	defer e.mu.Unlock()
	if !e.ready {
		return nil, domain.NewError(domain.CodeConflict, "simulation is not reset")
	}
	if e.steps >= e.cfg.DurationHours {
		return nil, domain.NewError(domain.CodeSimulationFinished, "simulation horizon is exhausted")
	}
	known := make(map[domain.ChannelID]struct{}, len(e.world.Channels))
	for _, c := range e.world.Channels {
		known[c.ID] = struct{}{}
	}
	budgets := make(map[domain.ChannelID]domain.MoneyMicros, len(actions))
	for i, a := range actions {
		if err := a.ChannelID.Validate(); err != nil {
			return nil, domain.NewError(domain.CodeValidation, "actions are invalid").WithField("actions["+strconv.Itoa(i)+"].channel_id", "invalid_format")
		}
		if _, ok := known[a.ChannelID]; !ok {
			return nil, domain.NewError(domain.CodeValidation, "actions are invalid").WithField("actions["+strconv.Itoa(i)+"].channel_id", "unknown_channel")
		}
		if _, ok := budgets[a.ChannelID]; ok {
			return nil, domain.NewError(domain.CodeValidation, "actions are invalid").WithField("actions["+strconv.Itoa(i)+"].channel_id", "duplicate")
		}
		budget, err := domain.QuantizeFloat64(a.BudgetCap)
		if err != nil {
			return nil, domain.NewError(domain.CodeValidation, "actions are invalid").WithField("actions["+strconv.Itoa(i)+"].budget_cap", "must_be_non_negative_finite")
		}
		budgets[a.ChannelID] = budget
	}
	if e.model.Model.EngineVersion == config.SegmentedEngineVersion {
		return e.stepAudience(budgets)
	}
	newStates := make(map[domain.ChannelID]runtimeState, len(e.states))
	for id, s := range e.states {
		newStates[id] = s
	}
	observations := make([]domain.Observation, 0, len(e.world.Channels))
	index := e.steps
	for _, channel := range e.world.Channels {
		state := e.states[channel.ID]
		hourOfDay, weekday, err := localClock(e.current, e.cfg.TimeZone)
		if err != nil {
			return nil, domain.NewError(domain.CodeInternal, "timezone lookup failed")
		}
		dyn := dynamics(state.Impressions, state.UniqueReach, channel.AudienceCapacity, channel.Dynamics)
		factors := evaluateEvents(e.events[channel.ID], index)
		requestNoise := lognormalMeanOne(newStream(e.cfg.CampaignSeed, e.model.Model.EngineVersion, string(channel.ID), "noise/requests", index), channel.RequestsSigma)
		cpmNoise := lognormalMeanOne(newStream(e.cfg.CampaignSeed, e.model.Model.EngineVersion, string(channel.ID), "noise/cpm", index), channel.CPMSigma)
		requestRaw := float64(channel.BaseRequestsPerDay) / 24 * channel.HourlySupply[hourOfDay] * channel.WeekdaySupply[int(weekday)] * factors.Supply * requestNoise
		if factors.Paused {
			requestRaw = 0
		}
		if math.IsNaN(requestRaw) || math.IsInf(requestRaw, 0) || requestRaw < 0 || requestRaw > float64(math.MaxInt64) {
			return nil, domain.NewError(domain.CodeInternal, "invalid generated requests")
		}
		requests := int64(math.Round(requestRaw))
		cpmFloat := channel.BaseCPM.Float64() * channel.HourlyCPM[hourOfDay] * channel.WeekdayCPM[int(weekday)] * dyn.PriceFactor * factors.CPM * cpmNoise
		cpm, err := domain.QuantizeFloat64(cpmFloat)
		if err != nil || cpm <= 0 {
			return nil, domain.NewError(domain.CodeInternal, "invalid generated CPM")
		}
		ctr := clamp(channel.BaseCTR*channel.HourlyCTR[hourOfDay]*channel.WeekdayCTR[int(weekday)]*dyn.FatigueFactor*factors.CTR, 0, 1)
		cr := clamp(channel.BaseCR*channel.HourlyCR[hourOfDay]*channel.WeekdayCR[int(weekday)]*factors.CR, 0, 1)
		affordable, err := affordableImpressions(budgets[channel.ID], cpm)
		if err != nil {
			return nil, domain.NewError(domain.CodeInternal, "affordability failed")
		}
		impressions := min64(requests, affordable)
		unique, err := sampleBinomial(newStream(e.cfg.CampaignSeed, e.model.Model.EngineVersion, string(channel.ID), "reach", index), impressions, dyn.NewUserProbability)
		if err != nil {
			return nil, domain.NewError(domain.CodeInternal, "reach sampling failed")
		}
		remaining := channel.AudienceCapacity - state.UniqueReach
		if unique > remaining {
			unique = remaining
		}
		clicks, err := sampleBinomial(newStream(e.cfg.CampaignSeed, e.model.Model.EngineVersion, string(channel.ID), "clicks", index), impressions, ctr)
		if err != nil {
			return nil, domain.NewError(domain.CodeInternal, "click sampling failed")
		}
		conversions, err := sampleBinomial(newStream(e.cfg.CampaignSeed, e.model.Model.EngineVersion, string(channel.ID), "conversions", index), clicks, cr)
		if err != nil {
			return nil, domain.NewError(domain.CodeInternal, "conversion sampling failed")
		}
		spend, ecpm, err := spendAndECPM(impressions, cpm)
		if err != nil || spend > budgets[channel.ID] {
			return nil, domain.NewError(domain.CodeInternal, "accounting invariant failed")
		}
		if state.Impressions > math.MaxInt64-impressions || state.UniqueReach > math.MaxInt64-unique {
			return nil, domain.NewError(domain.CodeInternal, "cumulative count overflow")
		}
		newStates[channel.ID] = runtimeState{state.Impressions + impressions, state.UniqueReach + unique}
		observations = append(observations, domain.Observation{ChannelID: channel.ID, Hour: e.current, Requests: requests, Impressions: impressions, UniqueReach: unique, Clicks: clicks, Conversions: conversions, Spend: spend, ECPM: ecpm})
	}
	sort.Slice(observations, func(i, j int) bool { return observations[i].ChannelID < observations[j].ChannelID })
	e.states = newStates
	e.steps++
	e.current = e.current.Add(time.Hour)
	return observations, nil
}

func min64(a, b int64) int64 {
	if a < b {
		return a
	}
	return b
}
