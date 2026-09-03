package app

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"sort"
	"strconv"
	"sync"
	"time"

	"media-planner/services/simulator/internal/config"
	"media-planner/services/simulator/internal/domain"
	"media-planner/services/simulator/internal/simulation"
)

const maxCachedSteps = 256

type SimulationState struct {
	ID                string                  `json:"simulation_id"`
	Status            domain.SimulationStatus `json:"status"`
	CurrentHour       domain.Hour             `json:"current_hour"`
	EndHourExclusive  domain.Hour             `json:"end_hour_exclusive"`
	DurationHours     int                     `json:"duration_hours"`
	RemainingHours    int                     `json:"remaining_hours"`
	TimeZone          string                  `json:"time_zone"`
	Currency          string                  `json:"currency"`
	EngineVersion     string                  `json:"engine_version"`
	WorldConfigDigest string                  `json:"world_config_digest"`
	ChannelIDs        []domain.ChannelID      `json:"channel_ids"`
}

type CurrentState struct {
	ID             string                  `json:"simulation_id"`
	Status         domain.SimulationStatus `json:"status"`
	CurrentHour    domain.Hour             `json:"current_hour"`
	RemainingHours int                     `json:"remaining_hours"`
}

type StepResult struct {
	SimulationID   string                  `json:"simulation_id"`
	StepID         string                  `json:"step_id"`
	ObservedHour   domain.Hour             `json:"observed_hour"`
	NextHour       domain.Hour             `json:"next_hour"`
	Status         domain.SimulationStatus `json:"status"`
	RemainingHours int                     `json:"remaining_hours"`
	Observations   []domain.Observation    `json:"observations"`
}

type cachedStep struct {
	hash   string
	result StepResult
	etag   string
}
type resource struct {
	id         string
	engine     *simulation.Engine
	cfg        domain.SimulationConfig
	revision   uint64
	etag       string
	status     domain.SimulationStatus
	cache      map[string]cachedStep
	cacheOrder []string
}

type Registry struct {
	mu                   sync.Mutex
	model                config.Loaded
	resource             *resource
	tombstones           map[string]time.Time
	tombstoneTTL         time.Duration
	requirePreconditions bool
}

type RegistryOption func(*Registry)

func WithoutPreconditions() RegistryOption {
	return func(registry *Registry) { registry.requirePreconditions = false }
}

func NewRegistry(model config.Loaded, options ...RegistryOption) *Registry {
	registry := &Registry{model: model, tombstones: make(map[string]time.Time), tombstoneTTL: time.Minute, requirePreconditions: true}
	for _, option := range options {
		option(registry)
	}
	return registry
}

func (r *Registry) Reset(id string, cfg domain.SimulationConfig, ifMatch string, ifNoneMatch bool) (SimulationState, string, bool, error) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.expireTombstones()
	created := r.resource == nil
	if !created {
		if r.resource.id != id {
			return SimulationState{}, "", false, domain.NewError(domain.CodeActiveLimit, "another simulation already exists")
		}
		if r.requirePreconditions && ifNoneMatch {
			return SimulationState{}, "", false, domain.NewError(domain.CodePreconditionFailed, "simulation already exists")
		}
		if r.requirePreconditions && (ifMatch == "" || ifMatch != r.resource.etag) {
			return SimulationState{}, "", false, domain.NewError(domain.CodePreconditionFailed, "stale or missing If-Match")
		}
	} else if r.requirePreconditions && !ifNoneMatch {
		return SimulationState{}, "", false, domain.NewError(domain.CodePreconditionFailed, "creation requires If-None-Match: *")
	}
	engine := simulation.New(r.model)
	if err := engine.Reset(cfg); err != nil {
		return SimulationState{}, "", false, err
	}
	revision := uint64(1)
	if r.resource != nil {
		revision = r.resource.revision + 1
	}
	res := &resource{id: id, engine: engine, cfg: cfg, revision: revision, status: domain.StatusActive, cache: make(map[string]cachedStep)}
	res.etag = makeETag(res)
	r.resource = res
	delete(r.tombstones, id)
	return r.state(res), res.etag, created, nil
}

func (r *Registry) Current(id string) (CurrentState, string, error) {
	r.mu.Lock()
	defer r.mu.Unlock()
	res, err := r.find(id)
	if err != nil {
		return CurrentState{}, "", err
	}
	return CurrentState{ID: id, Status: res.status, CurrentHour: res.engine.CurrentHour(), RemainingHours: res.cfg.DurationHours - res.steps()}, res.etag, nil
}

func (r *Registry) Step(id, stepID, ifMatch string, actions []domain.ChannelAction) (StepResult, string, error) {
	r.mu.Lock()
	defer r.mu.Unlock()
	res, err := r.find(id)
	if err != nil {
		return StepResult{}, "", err
	}
	hash, err := hashActions(actions)
	if err != nil {
		return StepResult{}, "", err
	}
	if cached, ok := res.cache[stepID]; ok {
		if cached.hash != hash {
			return StepResult{}, "", domain.NewError(domain.CodeStepIDReused, "step_id was used with different actions")
		}
		return cached.result, cached.etag, nil
	}
	if stepID == "" {
		return StepResult{}, "", domain.NewError(domain.CodeValidation, "step_id is required").WithField("step_id", "required")
	}
	if r.requirePreconditions && (ifMatch == "" || ifMatch != res.etag) {
		return StepResult{}, "", domain.NewError(domain.CodePreconditionFailed, "stale or missing If-Match")
	}
	observed := res.engine.CurrentHour()
	observations, err := res.engine.Step(actions)
	if err != nil {
		return StepResult{}, "", err
	}
	res.revision++
	remaining := res.cfg.DurationHours - res.steps()
	if remaining == 0 {
		res.status = domain.StatusFinished
	}
	res.etag = makeETag(res)
	result := StepResult{SimulationID: id, StepID: stepID, ObservedHour: observed, NextHour: res.engine.CurrentHour(), Status: res.status, RemainingHours: remaining, Observations: observations}
	res.cache[stepID] = cachedStep{hash: hash, result: result, etag: res.etag}
	res.cacheOrder = append(res.cacheOrder, stepID)
	if len(res.cacheOrder) > maxCachedSteps {
		old := res.cacheOrder[0]
		res.cacheOrder = res.cacheOrder[1:]
		delete(res.cache, old)
	}
	return result, res.etag, nil
}

func (r *Registry) Delete(id, ifMatch string) error {
	r.mu.Lock()
	defer r.mu.Unlock()
	res, err := r.find(id)
	if err != nil {
		return err
	}
	if r.requirePreconditions && (ifMatch == "" || ifMatch != res.etag) {
		return domain.NewError(domain.CodePreconditionFailed, "stale or missing If-Match")
	}
	r.resource = nil
	r.tombstones[id] = time.Now()
	return nil
}

func (r *Registry) Model() config.Loaded { return r.model }
func (r *Registry) find(id string) (*resource, error) {
	r.expireTombstones()
	if r.resource != nil && r.resource.id == id {
		return r.resource, nil
	}
	if _, ok := r.tombstones[id]; ok {
		return nil, domain.NewError(domain.CodeGone, "simulation was deleted")
	}
	return nil, domain.NewError(domain.CodeNotFound, "simulation does not exist")
}
func (r *Registry) expireTombstones() {
	now := time.Now()
	for id, at := range r.tombstones {
		if now.Sub(at) >= r.tombstoneTTL {
			delete(r.tombstones, id)
		}
	}
}
func (r *Registry) state(res *resource) SimulationState {
	ids := res.engine.ChannelIDs()
	return SimulationState{ID: res.id, Status: res.status, CurrentHour: res.engine.CurrentHour(), EndHourExclusive: res.cfg.StartHour.Add(time.Duration(res.cfg.DurationHours) * time.Hour), DurationHours: res.cfg.DurationHours, RemainingHours: res.cfg.DurationHours - res.steps(), TimeZone: res.cfg.TimeZone, Currency: r.model.Model.Currency, EngineVersion: r.model.Model.EngineVersion, WorldConfigDigest: r.model.Digest, ChannelIDs: ids}
}
func (res *resource) steps() int {
	return int(res.engine.CurrentHour().Sub(res.cfg.StartHour.Time) / time.Hour)
}
func makeETag(res *resource) string {
	payload := res.id + res.engine.CurrentHour().String() + strconv.FormatUint(res.revision, 10)
	sum := sha256.Sum256([]byte(payload))
	return `"` + strconv.FormatUint(res.revision, 10) + `-` + hex.EncodeToString(sum[:8]) + `"`
}
func hashActions(actions []domain.ChannelAction) (string, error) {
	type item struct {
		ID     domain.ChannelID `json:"channel_id"`
		Budget string           `json:"budget_cap"`
	}
	items := make([]item, 0, len(actions))
	seen := map[domain.ChannelID]bool{}
	for i, a := range actions {
		if seen[a.ChannelID] {
			return "", domain.NewError(domain.CodeValidation, "duplicate action").WithField("actions["+strconv.Itoa(i)+"].channel_id", "duplicate")
		}
		seen[a.ChannelID] = true
		m, err := domain.QuantizeFloat64(a.BudgetCap)
		if err != nil {
			return "", domain.NewError(domain.CodeValidation, "invalid budget")
		}
		items = append(items, item{a.ChannelID, m.String()})
	}
	sort.Slice(items, func(i, j int) bool { return items[i].ID < items[j].ID })
	b, _ := json.Marshal(items)
	sum := sha256.Sum256(b)
	return hex.EncodeToString(sum[:]), nil
}
