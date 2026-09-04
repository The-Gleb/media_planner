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

from planner.application.planning import create_fixed_budget_plan
from planner.config import Settings
from planner.domain.models import Horizon
from planner.domain.values import micros_to_money, money_to_micros
from planner.transport.http.dto import (
    AllocationDTO,
    FixedBudgetPlanRequestDTO,
    HealthDTO,
    MediaPlanDTO,
    PlanRequestDTO,
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
        "Planner does not call Simulator, store campaign state, or produce forecasts in v0."
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
        "MediaPlanDTO": "MediaPlan",
        "SimulationContextDTO": "SimulationContext",
        "TargetKPIDTO": "TargetKPI",
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
    response_model=MediaPlanDTO,
    operation_id="createMediaPlan",
    tags=["Plans"],
    responses=_PROBLEM_RESPONSES,
)
async def create_plan(request: PlanRequestDTO) -> MediaPlanDTO | JSONResponse:
    if isinstance(request, TargetKPIPlanRequestDTO):
        return problem(
            status=422,
            code="unsupported_plan_type",
            title="Plan type is not supported",
            detail="Target KPI planning is visible for future use but is not implemented in v0.",
            trace_id=trace_context.get(),
            instance="/v1/plans",
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
        horizon=request.horizon,
        expected=None,
        allocations=[
            AllocationDTO(
                channel_id=allocation.channel_id,
                hour=allocation.hour,
                budget_cap=micros_to_money(allocation.budget_micros),
                expected=None,
            )
            for allocation in plan.allocations
        ],
        required_budget=None,
        reason=None,
    )


def run() -> None:
    uvicorn.run(app, host=settings.address, port=settings.port, log_level=settings.log_level)
