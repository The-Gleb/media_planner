package app

import (
	"sync"
	"sync/atomic"
	"testing"

	"media-planner/services/simulator/internal/config"
	"media-planner/services/simulator/internal/domain"
)

func testRegistry(t *testing.T) (*Registry, domain.SimulationConfig) {
	t.Helper()
	model, err := config.LoadFile("../../configs/world-config.json")
	if err != nil {
		t.Fatal(err)
	}
	h, _ := domain.ParseHour("2026-09-03T06:00:00Z")
	return NewRegistry(model), domain.SimulationConfig{WorldSeed: 42, CampaignSeed: 77, StartHour: h, DurationHours: 2, TimeZone: "Europe/Moscow"}
}

func TestWorldMetadataIsSanitizedAndSorted(t *testing.T) {
	r, _ := testRegistry(t)
	metadata := r.WorldMetadata()
	if metadata.EngineVersion == "" || metadata.Currency == "" || len(metadata.WorldConfigDigest) != 64 {
		t.Fatalf("incomplete metadata: %+v", metadata)
	}
	if len(metadata.ChannelIDs) != 2 || metadata.ChannelIDs[0] != "search_1" || metadata.ChannelIDs[1] != "social_1" {
		t.Fatalf("channel IDs are not stable and sorted: %v", metadata.ChannelIDs)
	}
}

func TestRegistryConditionalStepAndRetry(t *testing.T) {
	r, cfg := testRegistry(t)
	state, etag, created, err := r.Reset("11111111-1111-4111-8111-111111111111", cfg, "", true)
	if err != nil || !created || state.RemainingHours != 2 {
		t.Fatalf("reset: %#v %q %v %v", state, etag, created, err)
	}
	actions := []domain.ChannelAction{{ChannelID: "social_1", BudgetCap: 10}}
	first, next, err := r.Step(state.ID, "a04ea33b-b91a-4faa-a0b5-f2869efbdf17", etag, actions)
	if err != nil {
		t.Fatal(err)
	}
	retry, retryETag, err := r.Step(state.ID, "a04ea33b-b91a-4faa-a0b5-f2869efbdf17", etag, actions)
	if err != nil || retryETag != next || retry.ObservedHour != first.ObservedHour {
		t.Fatalf("retry: %#v %q %v", retry, retryETag, err)
	}
	if _, _, err := r.Step(state.ID, "a04ea33b-b91a-4faa-a0b5-f2869efbdf17", etag, []domain.ChannelAction{{ChannelID: "social_1", BudgetCap: 11}}); err == nil {
		t.Fatal("expected reused ID conflict")
	}
}

func TestRegistryAllowsOneConcurrentCommit(t *testing.T) {
	r, cfg := testRegistry(t)
	state, etag, _, _ := r.Reset("11111111-1111-4111-8111-111111111111", cfg, "", true)
	var success atomic.Int32
	var wg sync.WaitGroup
	for i := 0; i < 20; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			id := "00000000-0000-4000-8000-0000000000" + string(rune('a'+i))
			if _, _, err := r.Step(state.ID, id, etag, nil); err == nil {
				success.Add(1)
			}
		}(i)
	}
	wg.Wait()
	if success.Load() != 1 {
		t.Fatalf("commits=%d", success.Load())
	}
}

func TestRegistryCanRelaxPreconditionsForDevelopment(t *testing.T) {
	strict, cfg := testRegistry(t)
	registry := NewRegistry(strict.model, WithoutPreconditions())
	state, _, created, err := registry.Reset("campaign-demo_1", cfg, "", false)
	if err != nil || !created {
		t.Fatalf("create without precondition: created=%v err=%v", created, err)
	}
	if _, _, err := registry.Step(state.ID, "a04ea33b-b91a-4faa-a0b5-f2869efbdf17", "", nil); err != nil {
		t.Fatalf("step without precondition: %v", err)
	}
	if _, _, _, err := registry.Reset(state.ID, cfg, "", false); err != nil {
		t.Fatalf("reset without precondition: %v", err)
	}
	if err := registry.Delete(state.ID, ""); err != nil {
		t.Fatalf("delete without precondition: %v", err)
	}
}
