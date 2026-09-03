import numpy as np

from mediaplan import planner
from mediaplan.contracts import Brief, Catalog


def test_plan_spends_at_most_budget(short_brief: Brief, catalog: Catalog) -> None:
    plan = planner.build_media_plan(short_brief, catalog)

    assert plan.total_budget_rub <= short_brief.budget_rub * (1 + 1e-9)
    assert plan.total_budget_rub > 0.9 * short_brief.budget_rub
    assert (plan.hourly_budget >= 0).all()
    assert plan.hourly_budget.shape == (short_brief.horizon_hours, len(catalog.channels))


def test_plan_prefers_channels_with_higher_kpi_per_rub(short_brief: Brief, catalog: Catalog) -> None:
    plan = planner.build_media_plan(short_brief, catalog)
    budget_by_channel = {forecast.channel_id: forecast.budget_rub for forecast in plan.channel_forecasts}

    assert budget_by_channel["marketplace_a"] > budget_by_channel["programmatic"]


def test_trajectories_are_monotonic(short_brief: Brief, catalog: Catalog) -> None:
    plan = planner.build_media_plan(short_brief, catalog)

    assert (np.diff(plan.cumulative_spend) >= 0).all()
    assert (np.diff(plan.cumulative_kpi) >= 0).all()
