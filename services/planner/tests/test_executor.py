from mediaplan import executor, metrics, planner
from mediaplan.contracts import Brief, Catalog
from mediaplan.simulator_client import ScenarioEvent, SimulatorClient


BEHIND_PLAN_WORLD_SEED = 42
AHEAD_OF_PLAN_WORLD_SEED = 1
CAMPAIGN_SEED = 9


def _shock_on_best_channel(brief: Brief, catalog: Catalog) -> ScenarioEvent:
    plan = planner.build_media_plan(brief, catalog)
    best_channel = max(plan.channel_forecasts, key=lambda forecast: forecast.budget_rub).channel_id
    start_hour = brief.horizon_hours // 2
    return ScenarioEvent(
        channel_id=best_channel,
        metric="ctr",
        start_hour=start_hour,
        duration_hours=brief.horizon_hours - start_hour,
        multiplier=0.6,
    )


def _run_both_strategies(
    brief: Brief, catalog: Catalog, client: SimulatorClient, world_seed: int, events: tuple[ScenarioEvent, ...] = ()
) -> tuple[executor.CampaignResult, executor.CampaignResult]:
    plan = planner.build_media_plan(brief, catalog)
    results = []
    for strategy in ("frozen", "adaptive"):
        client.reset(
            world_seed=world_seed, campaign_seed=CAMPAIGN_SEED, horizon_hours=brief.horizon_hours, events=events
        )
        results.append(executor.run_campaign(plan, catalog, client, strategy))
    return results[0], results[1]


def test_campaign_is_reproducible_by_seeds(short_brief: Brief, catalog: Catalog, client: SimulatorClient) -> None:
    plan = planner.build_media_plan(short_brief, catalog)
    client.reset(world_seed=1, campaign_seed=CAMPAIGN_SEED, horizon_hours=short_brief.horizon_hours)
    first_result = executor.run_campaign(plan, catalog, client, "frozen")
    client.reset(world_seed=1, campaign_seed=CAMPAIGN_SEED, horizon_hours=short_brief.horizon_hours)
    second_result = executor.run_campaign(plan, catalog, client, "frozen")

    assert first_result.packets == second_result.packets


def test_both_strategies_spend_close_to_plan(short_brief: Brief, catalog: Catalog, client: SimulatorClient) -> None:
    plan = planner.build_media_plan(short_brief, catalog)
    for result in _run_both_strategies(short_brief, catalog, client, BEHIND_PLAN_WORLD_SEED):
        assert metrics.compute_end_ape(plan.cumulative_spend, result.cumulative_spend) < 0.05


def test_adaptive_tracks_kpi_closer_than_frozen_when_behind_plan_under_shock(
    short_brief: Brief, catalog: Catalog, client: SimulatorClient
) -> None:
    plan = planner.build_media_plan(short_brief, catalog)
    shock = _shock_on_best_channel(short_brief, catalog)
    frozen_result, adaptive_result = _run_both_strategies(
        short_brief, catalog, client, BEHIND_PLAN_WORLD_SEED, (shock,)
    )

    assert metrics.compute_end_deviation(plan.cumulative_kpi, frozen_result.cumulative_kpi) < 0
    frozen_kpi_ape = metrics.compute_end_ape(plan.cumulative_kpi, frozen_result.cumulative_kpi)
    adaptive_kpi_ape = metrics.compute_end_ape(plan.cumulative_kpi, adaptive_result.cumulative_kpi)
    assert adaptive_kpi_ape < frozen_kpi_ape


def test_adaptive_does_not_overshoot_more_than_frozen_when_ahead_of_plan(
    short_brief: Brief, catalog: Catalog, client: SimulatorClient
) -> None:
    plan = planner.build_media_plan(short_brief, catalog)
    frozen_result, adaptive_result = _run_both_strategies(short_brief, catalog, client, AHEAD_OF_PLAN_WORLD_SEED)

    assert metrics.compute_end_deviation(plan.cumulative_kpi, frozen_result.cumulative_kpi) > 0
    frozen_kpi_ape = metrics.compute_end_ape(plan.cumulative_kpi, frozen_result.cumulative_kpi)
    adaptive_kpi_ape = metrics.compute_end_ape(plan.cumulative_kpi, adaptive_result.cumulative_kpi)
    assert adaptive_kpi_ape <= frozen_kpi_ape + 0.01
