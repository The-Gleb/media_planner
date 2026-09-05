import math
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from typing import Any
from uuid import UUID, uuid4

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response

from planner.application.planning import create_fixed_budget_plan, create_target_kpi_plan
from planner.config import Settings
from planner.domain.history import HourBin, PastCampaign, PastCampaignChannel
from planner.domain.models import Forecast, Horizon, MediaPlan, Strategy
from planner.domain.values import count_to_int, micros_to_money, money_to_micros
from planner.transport.http.dto import (
    AllocationDTO,
    ExpectedOutcomeDTO,
    FixedBudgetPlanRequestDTO,
    HealthDTO,
    HourlyExpectedDTO,
    InfeasibilityReasonDTO,
    InfeasibleTargetKPIPlanDTO,
    MediaPlanDTO,
    PastCampaignDTO,
    PlanRequestDTO,
    PlanResultDTO,
    TargetKPIPlanDTO,
    TargetKPIPlanRequestDTO,
)
from planner.transport.http.problem import FieldError, problem

trace_context: ContextVar[str] = ContextVar("trace_id", default="")
settings = Settings.from_env()
app = FastAPI(
    title="Media Planner Planning API",
    version=settings.service_version,
    description=(
        "Stateless deterministic planning boundary. Money and counts are decimal strings. "
        "Planner does not call Simulator or store campaign state. Target plans expose a "
        "public-catalog benchmark forecast."
    ),
    servers=[
        {"url": "http://127.0.0.1:8082", "description": "Local Docker Compose host port"},
        {"url": "http://planner:8080", "description": "Docker Compose service network"},
    ],
    openapi_tags=[{"name": "Plans"}, {"name": "Health"}],
)
app.openapi_version = "3.1.2"
app.state.ready = True


def _replace_schema_refs(value: object, names: dict[str, str]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "$ref" and isinstance(item, str):
                for old, new in names.items():
                    item = item.replace(f"/schemas/{old}", f"/schemas/{new}")
                value[key] = item
            else:
                _replace_schema_refs(item, names)
    elif isinstance(value, list):
        for item in value:
            _replace_schema_refs(item, names)


def build_openapi() -> dict[str, Any]:
    if app.openapi_schema is not None:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        description=app.description,
        routes=app.routes,
        tags=app.openapi_tags,
        servers=app.servers,
    )
    names = {
        "AllocationDTO": "Allocation",
        "CampaignStateDTO": "CampaignState",
        "ChannelStateDTO": "ChannelState",
        "FixedBudgetPlanRequestDTO": "FixedBudgetPlanRequest",
        "HealthDTO": "Health",
        "HorizonDTO": "Horizon",
        "MarketForecastDTO": "MarketForecast",
        "HourBinDTO": "HourBin",
        "PastCampaignChannelDTO": "PastCampaignChannel",
        "PastCampaignDTO": "PastCampaign",
        "MediaPlanDTO": "MediaPlan",
        "ExpectedOutcomeDTO": "ExpectedOutcome",
        "HourlyExpectedDTO": "HourlyExpected",
        "InfeasibilityReasonDTO": "InfeasibilityReason",
        "InfeasibleTargetKPIPlanDTO": "InfeasibleTargetKPIPlan",
        "SimulationContextDTO": "SimulationContext",
        "TargetKPIDTO": "TargetKPI",
        "TargetKPIPlanDTO": "TargetKPIPlan",
        "TargetKPIPlanRequestDTO": "TargetKPIPlanRequest",
    }
    components = schema["components"]["schemas"]
    for old, new in names.items():
        components[new] = components.pop(old)
        components[new]["title"] = new
    _replace_schema_refs(schema, names)

    operation = schema["paths"]["/v1/plans"]["post"]
    request_schema = operation["requestBody"]["content"]["application/json"]["schema"]
    components["PlanRequest"] = request_schema
    operation["requestBody"]["content"]["application/json"]["schema"] = {
        "$ref": "#/components/schemas/PlanRequest"
    }
    components["FieldError"] = {
        "type": "object",
        "additionalProperties": False,
        "required": ["field", "code"],
        "properties": {
            "field": {"type": "string"},
            "code": {"type": "string"},
            "detail": {"type": "string"},
        },
    }
    components["Problem"] = {
        "type": "object",
        "additionalProperties": True,
        "required": ["type", "title", "status", "code"],
        "properties": {
            "type": {"type": "string", "format": "uri"},
            "title": {"type": "string"},
            "status": {"type": "integer", "minimum": 400, "maximum": 599},
            "detail": {"type": "string"},
            "instance": {"type": "string"},
            "code": {
                "type": "string",
                "enum": [
                    "invalid_json",
                    "unsupported_media_type",
                    "validation_failed",
                    "unsupported_plan_type",
                    "internal_error",
                    "not_ready",
                ],
            },
            "trace_id": {"type": "string"},
            "errors": {
                "type": "array",
                "items": {"$ref": "#/components/schemas/FieldError"},
            },
        },
    }
    request_header = {
        "description": "Request identifier supplied by the client or generated at the boundary.",
        "required": True,
        "schema": {"type": "string", "format": "uuid"},
    }
    operation["responses"]["200"]["headers"] = {"X-Request-ID": request_header}
    for status in ("400", "415", "422", "500"):
        operation["responses"][status]["content"] = {
            "application/problem+json": {"schema": {"$ref": "#/components/schemas/Problem"}}
        }
    schema["paths"]["/health/ready"]["get"]["responses"]["503"]["content"] = {
        "application/problem+json": {"schema": {"$ref": "#/components/schemas/Problem"}}
    }
    components.update(
        {
            "Money": {
                "type": "string",
                "pattern": r"^(0|[1-9][0-9]*)(?:\.[0-9]{1,6})?$",
            },
            "Count": {"type": "string", "pattern": r"^(0|[1-9][0-9]*)$"},
            "PositiveCount": {"type": "string", "pattern": r"^[1-9][0-9]*$"},
            "Int64Text": {
                "type": "string",
                "pattern": r"^-?(0|[1-9][0-9]*)$",
            },
            "ChannelID": {
                "type": "string",
                "pattern": r"^[a-z][a-z0-9_-]{0,63}$",
            },
            "Channels": {
                "type": "array",
                "minItems": 1,
                "maxItems": 20,
                "uniqueItems": True,
                "items": {"$ref": "#/components/schemas/ChannelID"},
            },
        }
    )
    app.openapi_schema = schema
    return schema


app.openapi = build_openapi  # type: ignore[method-assign]

CallNext = Callable[[Request], Awaitable[Response]]


def _request_trace_id(request: Request) -> str:
    value = getattr(request.state, "trace_id", None)
    return value if isinstance(value, str) and value else trace_context.get() or str(uuid4())


@app.middleware("http")
async def request_id_middleware(request: Request, call_next: CallNext) -> Response:
    supplied = request.headers.get("X-Request-ID", "")
    try:
        trace_id = str(UUID(supplied)) if supplied else str(uuid4())
    except ValueError:
        trace_id = str(uuid4())
    request.state.trace_id = trace_id
    token = trace_context.set(trace_id)
    try:
        if request.method == "POST" and request.url.path == "/v1/plans":
            content_type = request.headers.get("content-type", "").partition(";")[0].strip().lower()
            if content_type != "application/json":
                return problem(
                    status=415,
                    code="unsupported_media_type",
                    title="Unsupported media type",
                    detail="The planning request body must use application/json.",
                    trace_id=trace_id,
                    instance=request.url.path,
                )
        response = await call_next(request)
        response.headers["X-Request-ID"] = trace_id
        return response
    finally:
        trace_context.reset(token)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    malformed = any(item["type"] == "json_invalid" for item in exc.errors())
    if malformed:
        return problem(
            status=400,
            code="invalid_json",
            title="Malformed JSON",
            detail="The request body is not valid JSON.",
            trace_id=_request_trace_id(request),
            instance=request.url.path,
        )
    errors: list[FieldError] = [
        {
            "field": ".".join(str(part) for part in item["loc"] if part != "body"),
            "code": str(item["type"]),
            "detail": str(item["msg"]),
        }
        for item in exc.errors()
    ]
    return problem(
        status=422,
        code="validation_failed",
        title="Request validation failed",
        detail="The planning request is invalid.",
        trace_id=_request_trace_id(request),
        instance=request.url.path,
        errors=errors,
    )


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return problem(
        status=exc.status_code,
        code="validation_failed",
        title="HTTP request error",
        detail=str(exc.detail),
        trace_id=_request_trace_id(request),
        instance=request.url.path,
    )


@app.exception_handler(Exception)
async def unexpected_error(request: Request, _exc: Exception) -> JSONResponse:
    return problem(
        status=500,
        code="internal_error",
        title="Internal server error",
        detail="An unexpected error occurred.",
        trace_id=_request_trace_id(request),
        instance=request.url.path,
    )


@app.get(
    "/health/live",
    response_model=HealthDTO,
    operation_id="getPlannerLiveness",
    tags=["Health"],
)
async def liveness() -> HealthDTO:
    return HealthDTO(status="ok")


@app.get(
    "/health/ready",
    response_model=HealthDTO,
    operation_id="getPlannerReadiness",
    tags=["Health"],
    responses={503: {"description": "Planner is not ready"}},
)
async def readiness(request: Request) -> HealthDTO | JSONResponse:
    if not bool(request.app.state.ready):
        return problem(
            status=503,
            code="not_ready",
            title="Planner is not ready",
            detail="Planner initialization has not completed.",
            trace_id=_request_trace_id(request),
            instance=request.url.path,
        )
    return HealthDTO(status="ok")


_PROBLEM_RESPONSES: dict[int | str, dict[str, object]] = {
    400: {"description": "Malformed JSON or request framing"},
    415: {"description": "Request body is not JSON"},
    422: {"description": "Invalid request or unsupported plan type"},
    500: {"description": "Unexpected internal failure"},
}


@app.post(
    "/v1/plans",
    response_model=PlanResultDTO,
    operation_id="createMediaPlan",
    tags=["Plans"],
    responses=_PROBLEM_RESPONSES,
)
async def create_plan(
    request: PlanRequestDTO,
) -> MediaPlanDTO | TargetKPIPlanDTO | InfeasibleTargetKPIPlanDTO | JSONResponse:
    if isinstance(request, TargetKPIPlanRequestDTO):
        if (
            request.current.state_revision != 0
            or request.current.current_hour != request.horizon.from_hour
        ):
            return problem(
                status=422,
                code="validation_failed",
                title="Request validation failed",
                detail="Target KPI planning is available only before campaign execution.",
                trace_id=trace_context.get(),
                instance="/v1/plans",
                errors=[
                    {
                        "field": "current.state_revision",
                        "code": "initial_state_required",
                        "detail": "Target planning requires revision zero.",
                    }
                ],
            )
        if request.strategy is not Strategy.OPTIMIZED:
            return problem(
                status=422,
                code="validation_failed",
                title="Request validation failed",
                detail="Target KPI planning requires the optimized strategy.",
                trace_id=trace_context.get(),
                instance="/v1/plans",
                errors=[
                    {
                        "field": "strategy",
                        "code": "optimized_required",
                        "detail": "Select the optimized strategy.",
                    }
                ],
            )
        try:
            plan, solution = create_target_kpi_plan(
                target_value=count_to_int(request.target.value, positive=True),
                target_metric=request.target.metric.value,
                horizon=Horizon(request.horizon.from_hour, request.horizon.to_hour),
                channels=request.channels,
                simulation=request.simulation.model_dump(mode="json"),
                strategy=request.strategy.value,
                history=_history(request.history),
            )
        except ValueError as exc:
            return problem(
                status=422,
                code="validation_failed",
                title="Request validation failed",
                detail=str(exc),
                trace_id=trace_context.get(),
                instance="/v1/plans",
            )
        expected = _expected_outcome(solution.expected)
        if plan is None or solution.required_budget_micros is None:
            maximum = str(solution.max_achievable)
            return InfeasibleTargetKPIPlanDTO(
                request_id=request.request_id,
                state_revision=0,
                plan_id=None,
                feasible=False,
                type="target_kpi",
                strategy=Strategy.OPTIMIZED,
                optimize=request.target.metric,
                currency=request.simulation.currency,
                budget=None,
                unallocated_budget=None,
                horizon=request.horizon,
                expected=expected,
                allocations=[],
                required_budget=None,
                reason=InfeasibilityReasonDTO(
                    code="target_exceeds_capacity",
                    detail="The target exceeds benchmark capacity for the selected horizon and channels.",
                    max_achievable=maximum,
                    recommended_target=maximum,
                ),
                target=request.target,
            )
        budget = micros_to_money(solution.required_budget_micros)
        return TargetKPIPlanDTO(
            request_id=request.request_id,
            state_revision=0,
            plan_id=plan.plan_id,
            feasible=True,
            type="target_kpi",
            strategy=Strategy.OPTIMIZED,
            optimize=request.target.metric,
            currency=request.simulation.currency,
            budget=budget,
            unallocated_budget=micros_to_money(plan.unallocated_budget_micros),
            horizon=request.horizon,
            expected=expected,
            allocations=_allocations(plan),
            required_budget=budget,
            reason=None,
            target=request.target,
        )
    if not isinstance(request, FixedBudgetPlanRequestDTO):
        raise TypeError("validated request has an unknown plan type")

    budget_micros = money_to_micros(request.budget)
    plan = create_fixed_budget_plan(
        budget_micros=budget_micros,
        horizon=Horizon(request.horizon.from_hour, request.horizon.to_hour),
        channels=request.channels,
        simulation=request.simulation.model_dump(mode="json"),
        current=request.current.model_dump(mode="json"),
        optimize=request.optimize.value,
        strategy=request.strategy.value,
        history=_history(request.history),
    )
    return MediaPlanDTO(
        request_id=request.request_id,
        state_revision=request.current.state_revision,
        plan_id=plan.plan_id,
        feasible=True,
        type="fixed_budget",
        strategy=request.strategy,
        optimize=request.optimize,
        currency=request.simulation.currency,
        budget=micros_to_money(budget_micros),
        unallocated_budget=micros_to_money(plan.unallocated_budget_micros),
        horizon=request.horizon,
        expected=_expected_outcome(plan.forecast.total) if plan.forecast else None,
        allocations=_allocations(plan),
        required_budget=None,
        reason=None,
        target=None,
    )


def _history(history: list[PastCampaignDTO]) -> tuple[PastCampaign, ...]:
    return tuple(
        PastCampaign(
            horizon_hours=campaign.horizon_hours,
            channels={
                channel_id: PastCampaignChannel(
                    bins=tuple(
                        HourBin(
                            hours=item.hours,
                            requests=count_to_int(item.requests),
                            impressions=count_to_int(item.impressions),
                            unique_reach=count_to_int(item.unique_reach),
                            clicks=count_to_int(item.clicks),
                            conversions=count_to_int(item.conversions),
                            spent_micros=money_to_micros(item.spent),
                        )
                        for item in channel.bins
                    )
                )
                for channel_id, channel in campaign.channels.items()
            },
        )
        for campaign in history
    )


def _decimal_text(value: float) -> str:
    return f"{max(value, 0.0):.6f}"


def _allocations(plan: MediaPlan) -> list[AllocationDTO]:
    hourly = plan.forecast.hourly if plan.forecast is not None else {}
    result: list[AllocationDTO] = []
    for allocation in plan.allocations:
        forecast = hourly.get((allocation.channel_id, allocation.hour))
        result.append(
            AllocationDTO(
                channel_id=allocation.channel_id,
                hour=allocation.hour,
                budget_cap=micros_to_money(allocation.budget_micros),
                expected=None
                if forecast is None
                else HourlyExpectedDTO(
                    spend=micros_to_money(forecast.spend_micros),
                    impressions=_decimal_text(forecast.impressions),
                    unique_reach=_decimal_text(forecast.unique_reach),
                    clicks=_decimal_text(forecast.clicks),
                    conversions=_decimal_text(forecast.conversions),
                ),
            )
        )
    return result


def _expected_outcome(forecast: Forecast) -> ExpectedOutcomeDTO:
    return ExpectedOutcomeDTO(
        spend=micros_to_money(forecast.spend_micros),
        impressions=str(max(0, math.floor(forecast.impressions))),
        unique_reach=str(max(0, math.floor(forecast.unique_reach))),
        clicks=str(max(0, math.floor(forecast.clicks))),
        conversions=str(max(0, math.floor(forecast.conversions))),
    )


def run() -> None:
    uvicorn.run(app, host=settings.address, port=settings.port, log_level=settings.log_level)
