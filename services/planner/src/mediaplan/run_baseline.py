"""Сквозной прогон: бриф → медиаплан → Go-симулятор → заморозка против трекера → метрики.

Нужен запущенный симулятор (см. README). Пример:
    uv run python -m mediaplan.run_baseline --budget 1200000 --days 21 --shock ctr
"""

import argparse
import time

from mediaplan import catalog as catalog_module
from mediaplan import executor, metrics, planner
from mediaplan.contracts import HOURS_PER_DAY, Brief, MediaPlan, Objective
from mediaplan.simulator_client import ScenarioEvent, ScenarioMetric, SimulatorClient, resolve_simulator_url


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Бейзлайн MediaPlan Optimizer поверх Go-симулятора")
    parser.add_argument("--budget", type=float, default=1_200_000.0, help="бюджет кампании, руб.")
    parser.add_argument("--days", type=int, default=21, help="горизонт кампании, дней")
    parser.add_argument("--objective", choices=("clicks", "conversions"), default="conversions")
    parser.add_argument("--world-seed", type=int, default=42)
    parser.add_argument("--campaign-seed", type=int, default=7)
    parser.add_argument("--shock", choices=("none", "ctr", "cpm", "supply", "pause"), default="none")
    parser.add_argument("--shock-channel", default=None, help="по умолчанию — канал с наибольшим бюджетом в плане")
    parser.add_argument("--shock-day", type=int, default=None, help="по умолчанию — середина горизонта")
    parser.add_argument("--shock-strength", type=float, default=0.4, help="доля: CTR/supply × (1 − s), CPM × (1 + s)")
    parser.add_argument("--random-events", action="store_true", help="оставить случайные дрейфы и шоки мира")
    parser.add_argument("--simulator-url", default=resolve_simulator_url())
    return parser.parse_args()


def build_scenario(arguments: argparse.Namespace, plan: MediaPlan) -> tuple[ScenarioEvent, ...]:
    if arguments.shock == "none":
        return ()
    channel_id = arguments.shock_channel or max(plan.channel_forecasts, key=lambda f: f.budget_rub).channel_id
    start_day = arguments.shock_day if arguments.shock_day is not None else plan.brief.horizon_days // 2
    start_hour = start_day * HOURS_PER_DAY
    metric: ScenarioMetric = arguments.shock
    multiplier = {
        "ctr": 1 - arguments.shock_strength,
        "supply": 1 - arguments.shock_strength,
        "cpm": 1 + arguments.shock_strength,
    }.get(metric, 0.0)
    return (
        ScenarioEvent(
            channel_id=channel_id,
            metric=metric,
            start_hour=start_hour,
            duration_hours=plan.brief.horizon_hours - start_hour,
            multiplier=multiplier,
        ),
    )


def print_plan(plan: MediaPlan) -> None:
    brief = plan.brief
    print(f"\nМедиаплан: бюджет {brief.budget_rub:,.0f} ₽, {brief.horizon_days} дн., цель — {brief.objective}")
    print(f"Распределено: {plan.total_budget_rub:,.0f} ₽ ({plan.total_budget_rub / brief.budget_rub:.1%} бюджета)")
    header_left = f"{'канал':<15}{'бюджет ₽':>14}{'показы':>12}{'клики':>9}{'конв.':>8}"
    header_right = f"{'CTR':>8}{'CR':>7}{'CPM':>8}{'CPC':>8}{'CPA':>9}"
    print(header_left + header_right)
    for forecast in plan.channel_forecasts:
        if forecast.budget_rub <= 0:
            continue
        print(
            f"{forecast.channel_id:<15}{forecast.budget_rub:>14,.0f}{forecast.impressions:>12,.0f}"
            f"{forecast.clicks:>9,.0f}{forecast.conversions:>8,.0f}{forecast.ctr:>8.2%}{forecast.cr:>7.1%}"
            f"{forecast.cpm_rub:>8.0f}{forecast.cpc_rub:>8.1f}{forecast.cpa_rub:>9.0f}"
        )
    print(f"Итого прогноз KPI: {plan.cumulative_kpi[-1]:,.0f}")


def print_comparison(plan: MediaPlan, results: tuple[executor.CampaignResult, ...]) -> None:
    header_left = f"\n{'стратегия':<12}{'spend факт':>14}{'откл. spend':>12}{'MAPE spend':>12}"
    header_right = f"{'KPI факт':>10}{'откл. KPI':>11}{'MAPE KPI':>10}"
    print(header_left + header_right)
    for result in results:
        print(
            f"{result.strategy:<12}{result.cumulative_spend[-1]:>14,.0f}"
            f"{metrics.compute_end_deviation(plan.cumulative_spend, result.cumulative_spend):>+12.1%}"
            f"{metrics.compute_trajectory_mape(plan.cumulative_spend, result.cumulative_spend):>12.1%}"
            f"{result.cumulative_kpi[-1]:>10,.0f}"
            f"{metrics.compute_end_deviation(plan.cumulative_kpi, result.cumulative_kpi):>+11.1%}"
            f"{metrics.compute_trajectory_mape(plan.cumulative_kpi, result.cumulative_kpi):>10.1%}"
        )
    print("Отклонение — знаковое к концу кампании (плюс = факт выше плана); MAPE — среднее по часам траектории.")


def main() -> None:
    arguments = parse_arguments()
    objective: Objective = arguments.objective
    catalog = catalog_module.build_catalog(catalog_module.load_world_config())
    brief = Brief(budget_rub=arguments.budget, horizon_days=arguments.days, objective=objective)

    started_at = time.perf_counter()
    plan = planner.build_media_plan(brief, catalog)
    print_plan(plan)
    scenario = build_scenario(arguments, plan)
    for event in scenario:
        print(f"\nШок: {event}")

    results: list[executor.CampaignResult] = []
    with SimulatorClient(catalog.channel_ids, base_url=arguments.simulator_url) as client:
        for strategy in ("frozen", "adaptive"):
            client.reset(
                world_seed=arguments.world_seed,
                campaign_seed=arguments.campaign_seed,
                horizon_hours=brief.horizon_hours,
                events=scenario,
                disable_random_events=not arguments.random_events,
            )
            results.append(executor.run_campaign(plan, catalog, client, strategy))
    print_comparison(plan, tuple(results))
    print(f"\nПрогон {brief.horizon_hours} часов × 2 стратегии через HTTP: {time.perf_counter() - started_at:.1f} с")


if __name__ == "__main__":
    main()
