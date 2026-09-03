"""Песочница MediaPlan Optimizer поверх Go-симулятора: бриф → план → симуляция → заморозка против трекера.

Запуск: uv run streamlit run src/mediaplan/app.py   (нужен запущенный симулятор, см. README)
"""

import dataclasses
import typing

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from mediaplan import catalog as catalog_module
from mediaplan import executor, metrics, planner
from mediaplan.contracts import HOURS_PER_DAY, Brief, MediaPlan, Objective
from mediaplan.simulator_client import (
    ScenarioEvent,
    ScenarioMetric,
    SimulatorClient,
    resolve_simulator_url,
    wait_until_ready,
)


CHANNEL_COLORS: typing.Final = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948")
COLOR_PLAN: typing.Final = "#52514e"
COLOR_FROZEN: typing.Final = "#eb6834"
COLOR_ADAPTIVE: typing.Final = "#2a78d6"
COLOR_SHOCK: typing.Final = "#d03b3b"

ShockKind = typing.Literal["нет", "падение CTR", "скачок CPM", "исчерпание ёмкости", "пауза канала"]
SHOCK_METRICS: typing.Final[dict[str, ScenarioMetric]] = {
    "падение CTR": "ctr",
    "скачок CPM": "cpm",
    "исчерпание ёмкости": "supply",
    "пауза канала": "pause",
}


@typing.final
@dataclasses.dataclass(kw_only=True, slots=True, frozen=True)
class SandboxSettings:
    budget_rub: float
    horizon_days: int
    objective: Objective
    world_seed: int
    campaign_seed: int
    random_events: bool
    shock_kind: ShockKind
    shock_channel: str
    shock_start_day: int
    shock_strength: float


@typing.final
@dataclasses.dataclass(kw_only=True, slots=True, frozen=True)
class SandboxRun:
    plan: MediaPlan
    frozen: executor.CampaignResult
    adaptive: executor.CampaignResult
    shock: ScenarioEvent | None


def build_shock(settings: SandboxSettings) -> ScenarioEvent | None:
    metric = SHOCK_METRICS.get(settings.shock_kind)
    if metric is None:
        return None
    start_hour = settings.shock_start_day * HOURS_PER_DAY
    multiplier = {
        "ctr": 1 - settings.shock_strength,
        "supply": 1 - settings.shock_strength,
        "cpm": 1 + settings.shock_strength,
    }.get(metric, 0.0)
    return ScenarioEvent(
        channel_id=settings.shock_channel,
        metric=metric,
        start_hour=start_hour,
        duration_hours=settings.horizon_days * HOURS_PER_DAY - start_hour,
        multiplier=multiplier,
    )


@st.cache_data(show_spinner="Считаю план и гоняю кампанию в двух стратегиях через симулятор…")
def run_sandbox(settings: SandboxSettings, simulator_url: str) -> SandboxRun:
    catalog = catalog_module.build_catalog(catalog_module.load_world_config())
    brief = Brief(budget_rub=settings.budget_rub, horizon_days=settings.horizon_days, objective=settings.objective)
    plan = planner.build_media_plan(brief, catalog)
    shock = build_shock(settings)
    events = (shock,) if shock is not None else ()
    results: dict[str, executor.CampaignResult] = {}
    with SimulatorClient(catalog.channel_ids, base_url=simulator_url) as client:
        for strategy in ("frozen", "adaptive"):
            client.reset(
                world_seed=settings.world_seed,
                campaign_seed=settings.campaign_seed,
                horizon_hours=brief.horizon_hours,
                events=events,
                disable_random_events=not settings.random_events,
            )
            results[strategy] = executor.run_campaign(plan, catalog, client, strategy)
    return SandboxRun(plan=plan, frozen=results["frozen"], adaptive=results["adaptive"], shock=shock)


def render_sidebar(channel_ids: tuple[str, ...]) -> SandboxSettings:
    st.sidebar.header("Бриф")
    budget_rub = st.sidebar.number_input(
        "Бюджет, ₽", min_value=10_000, max_value=50_000_000, value=1_200_000, step=50_000
    )
    horizon_days = st.sidebar.slider("Горизонт, дней", min_value=3, max_value=30, value=21)
    objective: Objective = st.sidebar.radio("Цель", options=("conversions", "clicks"), horizontal=True)

    st.sidebar.header("Мир (Go-симулятор)")
    world_seed = st.sidebar.number_input("Seed мира", min_value=0, max_value=1_000_000, value=42)
    campaign_seed = st.sidebar.number_input("Seed кампании", min_value=0, max_value=1_000_000, value=7)
    random_events = st.sidebar.checkbox("Случайные дрейфы и шоки мира", value=False)

    st.sidebar.header("Шок (стенд)")
    shock_options: tuple[ShockKind, ...] = ("нет", "падение CTR", "скачок CPM", "исчерпание ёмкости", "пауза канала")
    shock_kind: ShockKind = st.sidebar.selectbox("Сценарий", options=shock_options) or "нет"
    default_channel = channel_ids.index("marketplace_a") if "marketplace_a" in channel_ids else 0
    shock_channel = st.sidebar.selectbox("Канал", options=channel_ids, index=default_channel)
    shock_start_day = st.sidebar.slider(
        "Начало, день", min_value=0, max_value=horizon_days - 1, value=horizon_days // 2
    )
    shock_strength = st.sidebar.slider("Сила (доля)", min_value=0.1, max_value=0.9, value=0.4, step=0.05)
    return SandboxSettings(
        budget_rub=float(budget_rub),
        horizon_days=int(horizon_days),
        objective=objective,
        world_seed=int(world_seed),
        campaign_seed=int(campaign_seed),
        random_events=bool(random_events),
        shock_kind=shock_kind,
        shock_channel=shock_channel,
        shock_start_day=int(shock_start_day),
        shock_strength=float(shock_strength),
    )


def render_channels_tab(world_config: catalog_module.WorldConfig) -> None:
    catalog = catalog_module.build_catalog(world_config)
    st.caption(
        "Публичные диапазоны из конфига симулятора и каталог как их середины. Конкретные значения мир сэмплит по seed "
        "и держит у себя — планировщик их не видит."
    )
    by_id = {spec.id: spec.base for spec in world_config.channels}

    def span(channel_id: str, field: str, fmt: str) -> str:
        value_range = getattr(by_id[channel_id], field).range
        return f"{value_range.min:{fmt}}–{value_range.max:{fmt}}"

    rows = [
        {
            "канал": entry.channel_id,
            "тип": entry.kind,
            "CPM диапазон": span(entry.channel_id, "cpm", ".0f"),
            "CPM каталог": entry.cpm_rub,
            "CTR диапазон": span(entry.channel_id, "ctr", ".2%"),
            "CTR каталог": entry.ctr,
            "CR диапазон": span(entry.channel_id, "cr", ".1%"),
            "CR каталог": entry.cr,
            "спрос/день": entry.daily_capacity,
            "конв. на 1000 ₽": 1000 / entry.cpm_rub * 1000 * entry.ctr * entry.cr,
        }
        for entry in catalog.channels
    ]
    frame = pd.DataFrame(rows).set_index("канал")
    st.dataframe(
        frame.style.format(
            {
                "CPM каталог": "{:.0f}",
                "CTR каталог": "{:.2%}",
                "CR каталог": "{:.1%}",
                "спрос/день": "{:,.0f}",
                "конв. на 1000 ₽": "{:.2f}",
            }
        ),
        width="stretch",
    )
    figure = go.Figure()
    figure.add_scatter(
        x=np.arange(HOURS_PER_DAY),
        y=catalog.hourly_profile * 100,
        name="ожидаемый профиль спроса",
        line={"color": COLOR_PLAN, "width": 2},
    )
    figure.update_layout(title="Каталог: доля дневного спроса по часам, %", xaxis_title="час суток", height=320)
    st.plotly_chart(figure, width="stretch")


def figure_cumulative(
    plan: MediaPlan, run: SandboxRun, attribute: str, title: str, unit_scale: float, unit_label: str
) -> go.Figure:
    days = np.arange(1, plan.brief.horizon_hours + 1) / HOURS_PER_DAY
    figure = go.Figure()
    figure.add_scatter(
        x=days,
        y=getattr(plan, attribute) / unit_scale,
        name="план",
        line={"color": COLOR_PLAN, "dash": "dash", "width": 2},
    )
    for result, color in ((run.frozen, COLOR_FROZEN), (run.adaptive, COLOR_ADAPTIVE)):
        figure.add_scatter(
            x=days, y=getattr(result, attribute) / unit_scale, name=result.strategy, line={"color": color, "width": 2}
        )
    if run.shock is not None:
        figure.add_vline(x=run.shock.start_hour / HOURS_PER_DAY, line={"color": COLOR_SHOCK, "dash": "dot"})
    figure.update_layout(title=title, xaxis_title="день", yaxis_title=unit_label, hovermode="x unified", height=380)
    return figure


def figure_gap_from_plan(plan: MediaPlan, run: SandboxRun) -> go.Figure:
    days = np.arange(1, plan.brief.horizon_hours + 1) / HOURS_PER_DAY
    safe_plan = np.where(plan.cumulative_kpi > 0, plan.cumulative_kpi, np.nan)
    figure = go.Figure()
    figure.add_hline(y=0, line={"color": COLOR_PLAN, "dash": "dash"})
    for result, color in ((run.frozen, COLOR_FROZEN), (run.adaptive, COLOR_ADAPTIVE)):
        figure.add_scatter(
            x=days,
            y=(result.cumulative_kpi / safe_plan - 1) * 100,
            name=result.strategy,
            line={"color": color, "width": 2},
        )
    if run.shock is not None:
        figure.add_vline(x=run.shock.start_hour / HOURS_PER_DAY, line={"color": COLOR_SHOCK, "dash": "dot"})
    figure.update_layout(
        title="Отклонение накопленного KPI от плана, %",
        xaxis_title="день",
        yaxis_title="%",
        hovermode="x unified",
        height=340,
    )
    return figure


def packets_frame(result: executor.CampaignResult) -> pd.DataFrame:
    frame = pd.DataFrame([dataclasses.asdict(packet) for packet in result.packets])
    frame["day"] = frame["hour"] // HOURS_PER_DAY + 1
    return frame


def figure_daily_kpi(plan: MediaPlan, run: SandboxRun) -> go.Figure:
    kpi_label = "конверсий" if plan.brief.objective == "conversions" else "кликов"
    column = "conversions" if plan.brief.objective == "conversions" else "clicks"
    plan_daily = (
        np.diff(np.concatenate([[0.0], plan.cumulative_kpi]))
        .reshape(plan.brief.horizon_days, HOURS_PER_DAY)
        .sum(axis=1)
    )
    days = np.arange(1, plan.brief.horizon_days + 1)
    figure = go.Figure()
    figure.add_scatter(x=days, y=plan_daily, name="план", line={"color": COLOR_PLAN, "dash": "dash", "width": 2})
    for result, color in ((run.frozen, COLOR_FROZEN), (run.adaptive, COLOR_ADAPTIVE)):
        series = packets_frame(result).groupby("day")[column].sum()
        figure.add_scatter(x=series.index, y=series.to_numpy(), name=result.strategy, line={"color": color, "width": 2})
    if run.shock is not None:
        figure.add_vline(x=run.shock.start_hour / HOURS_PER_DAY, line={"color": COLOR_SHOCK, "dash": "dot"})
    figure.update_layout(
        title=f"{kpi_label.capitalize()} по дням",
        xaxis_title="день",
        yaxis_title=kpi_label,
        hovermode="x unified",
        height=340,
    )
    return figure


def figure_observed_ctr(run: SandboxRun, channel_ids: tuple[str, ...]) -> go.Figure:
    packets = packets_frame(run.adaptive)
    clicks_by_day = packets.pivot_table(index="day", columns="channel_id", values="clicks", aggfunc="sum")
    impressions_by_day = packets.pivot_table(index="day", columns="channel_id", values="impressions", aggfunc="sum")
    ctr_by_day = clicks_by_day / impressions_by_day.replace(0, np.nan)
    figure = go.Figure()
    for channel_index, channel_id in enumerate(channel_ids):
        if channel_id not in ctr_by_day or ctr_by_day[channel_id].isna().all():
            continue
        figure.add_scatter(
            x=ctr_by_day.index,
            y=ctr_by_day[channel_id] * 100,
            name=channel_id,
            line={"color": CHANNEL_COLORS[channel_index], "width": 2},
        )
    if run.shock is not None:
        figure.add_vline(x=run.shock.start_hour / HOURS_PER_DAY, line={"color": COLOR_SHOCK, "dash": "dot"})
    figure.update_layout(
        title="Наблюдаемый CTR по дням (adaptive), %",
        xaxis_title="день",
        yaxis_title="CTR, %",
        hovermode="x unified",
        height=340,
    )
    return figure


def figure_daily_allocation(result: executor.CampaignResult, channel_ids: tuple[str, ...], title: str) -> go.Figure:
    daily = pd.DataFrame(result.hourly_budget, columns=channel_ids)
    daily["day"] = np.arange(len(daily)) // HOURS_PER_DAY + 1
    by_day = daily.groupby("day").sum() / 1000
    figure = go.Figure()
    for channel_index, channel_id in enumerate(channel_ids):
        if by_day[channel_id].sum() <= 0:
            continue
        figure.add_scatter(
            x=by_day.index,
            y=by_day[channel_id],
            name=channel_id,
            stackgroup="one",
            line={"color": CHANNEL_COLORS[channel_index], "width": 0.5},
        )
    figure.update_layout(
        title=title, xaxis_title="день", yaxis_title="тыс. ₽ в день", hovermode="x unified", height=360
    )
    return figure


def metrics_frame(plan: MediaPlan, run: SandboxRun) -> pd.DataFrame:
    rows = [
        {
            "стратегия": result.strategy,
            "spend факт, ₽": result.cumulative_spend[-1],
            "откл. spend": metrics.compute_end_deviation(plan.cumulative_spend, result.cumulative_spend),
            "MAPE spend": metrics.compute_trajectory_mape(plan.cumulative_spend, result.cumulative_spend),
            "KPI факт": result.cumulative_kpi[-1],
            "откл. KPI": metrics.compute_end_deviation(plan.cumulative_kpi, result.cumulative_kpi),
            "MAPE KPI": metrics.compute_trajectory_mape(plan.cumulative_kpi, result.cumulative_kpi),
        }
        for result in (run.frozen, run.adaptive)
    ]
    return pd.DataFrame(rows).set_index("стратегия")


def render_plan_tab(plan: MediaPlan) -> None:
    kpi_label = "конверсий" if plan.brief.objective == "conversions" else "кликов"
    columns = st.columns(4)
    columns[0].metric("Распределено", f"{plan.total_budget_rub:,.0f} ₽")
    columns[1].metric("Доля бюджета", f"{plan.total_budget_rub / plan.brief.budget_rub:.1%}")
    columns[2].metric(f"Прогноз, {kpi_label}", f"{plan.cumulative_kpi[-1]:,.0f}")
    cost_per_kpi = plan.total_budget_rub / plan.cumulative_kpi[-1] if plan.cumulative_kpi[-1] > 0 else 0.0
    columns[3].metric("CPA" if plan.brief.objective == "conversions" else "CPC", f"{cost_per_kpi:,.0f} ₽")
    if plan.total_budget_rub < plan.brief.budget_rub * 0.999:
        st.warning(
            "Бюджет распределён не полностью: каналы упёрлись в дневной спрос. Увеличьте горизонт или снизьте бюджет."
        )

    forecast_frame = pd.DataFrame(
        [
            {
                "канал": forecast.channel_id,
                "бюджет, ₽": forecast.budget_rub,
                "показы": forecast.impressions,
                "клики": forecast.clicks,
                "конверсии": forecast.conversions,
                "CTR": forecast.ctr,
                "CR": forecast.cr,
                "CPM": forecast.cpm_rub,
                "CPC": forecast.cpc_rub,
                "CPA": forecast.cpa_rub,
            }
            for forecast in plan.channel_forecasts
        ]
    ).set_index("канал")
    st.dataframe(
        forecast_frame.style.format(
            {
                "бюджет, ₽": "{:,.0f}",
                "показы": "{:,.0f}",
                "клики": "{:,.0f}",
                "конверсии": "{:,.0f}",
                "CTR": "{:.2%}",
                "CR": "{:.1%}",
                "CPM": "{:.0f}",
                "CPC": "{:.1f}",
                "CPA": "{:.0f}",
            }
        ),
        width="stretch",
    )
    budget_figure = go.Figure()
    budget_figure.add_bar(
        x=[forecast.budget_rub / 1000 for forecast in plan.channel_forecasts],
        y=[forecast.channel_id for forecast in plan.channel_forecasts],
        orientation="h",
        marker={"color": list(CHANNEL_COLORS)},
    )
    budget_figure.update_layout(title="Бюджет по каналам, тыс. ₽", height=340, yaxis={"autorange": "reversed"})
    st.plotly_chart(budget_figure, width="stretch")

    calendar = pd.DataFrame(plan.hourly_budget, columns=plan.channel_ids)
    calendar["день"] = np.arange(len(calendar)) // HOURS_PER_DAY + 1
    st.caption("Календарь расходов по дням, ₽")
    st.dataframe(calendar.groupby("день").sum().style.format("{:,.0f}"), width="stretch", height=260)


def render_simulation_tab(run: SandboxRun) -> None:
    plan = run.plan
    st.dataframe(
        metrics_frame(plan, run).style.format(
            {
                "spend факт, ₽": "{:,.0f}",
                "откл. spend": "{:+.1%}",
                "MAPE spend": "{:.1%}",
                "KPI факт": "{:,.0f}",
                "откл. KPI": "{:+.1%}",
                "MAPE KPI": "{:.1%}",
            }
        ),
        width="stretch",
    )
    st.caption("Отклонение — знаковое к концу кампании (плюс = факт выше плана). MAPE — среднее по часам траектории.")
    if run.shock is not None:
        st.info(f"Шок: {run.shock}")

    kpi_label = "конверсий" if plan.brief.objective == "conversions" else "кликов"
    left, right = st.columns(2)
    left.plotly_chart(
        figure_cumulative(plan, run, "cumulative_spend", "Накопленный расход", 1e6, "млн ₽"), width="stretch"
    )
    right.plotly_chart(
        figure_cumulative(plan, run, "cumulative_kpi", f"Накопленные {kpi_label}", 1.0, kpi_label), width="stretch"
    )

    st.subheader("Где виден шок")
    left, right = st.columns(2)
    left.plotly_chart(figure_gap_from_plan(plan, run), width="stretch")
    right.plotly_chart(figure_daily_kpi(plan, run), width="stretch")
    st.plotly_chart(figure_observed_ctr(run, plan.channel_ids), width="stretch")

    st.subheader("Перераспределение бюджета")
    left, right = st.columns(2)
    left.plotly_chart(
        figure_daily_allocation(run.frozen, plan.channel_ids, "frozen: дневной расход по каналам"), width="stretch"
    )
    right.plotly_chart(
        figure_daily_allocation(run.adaptive, plan.channel_ids, "adaptive: дневной расход по каналам"), width="stretch"
    )

    with st.expander("Почасовые пакеты факта (adaptive)"):
        packets = packets_frame(run.adaptive)
        st.dataframe(packets, width="stretch", height=320)
        st.download_button("Скачать CSV", packets.to_csv(index=False).encode("utf-8"), "hourly_packets.csv", "text/csv")


def main() -> None:
    st.set_page_config(page_title="MediaPlan Optimizer", layout="wide")
    st.title("MediaPlan Optimizer — песочница")
    st.caption(
        "Каналы абстрактные, данные синтетические. Прототип планирования и управления темпом, не система закупок."
    )

    simulator_url = resolve_simulator_url()
    if not wait_until_ready(simulator_url, attempts=3, delay_seconds=0.3):
        st.error(f"Симулятор недоступен по {simulator_url}. Запустите services/simulator и укажите SIMULATOR_URL.")
        st.stop()

    world_config = catalog_module.load_world_config()
    channel_ids = catalog_module.build_catalog(world_config).channel_ids
    settings = render_sidebar(channel_ids)

    channels_tab, plan_tab, simulation_tab = st.tabs(["Каналы", "План", "Симуляция"])
    run = run_sandbox(settings, simulator_url)
    with channels_tab:
        render_channels_tab(world_config)
    with plan_tab:
        render_plan_tab(run.plan)
    with simulation_tab:
        render_simulation_tab(run)


if __name__ == "__main__":
    main()
