from typing import Literal, TypedDict

from fastapi.responses import JSONResponse

ProblemCode = Literal[
    "invalid_json",
    "unsupported_media_type",
    "validation_failed",
    "unsupported_plan_type",
    "internal_error",
    "not_ready",
]


class FieldError(TypedDict):
    field: str
    code: str
    detail: str


def problem(
    *,
    status: int,
    code: ProblemCode,
    title: str,
    detail: str,
    trace_id: str,
    instance: str | None = None,
    errors: list[FieldError] | None = None,
) -> JSONResponse:
    body: dict[str, object] = {
        "type": f"https://media-planner.local/problems/{code}",
        "title": title,
        "status": status,
        "detail": detail,
        "code": code,
        "trace_id": trace_id,
    }
    if instance is not None:
        body["instance"] = instance
    if errors:
        body["errors"] = errors
    return JSONResponse(
        body,
        status_code=status,
        media_type="application/problem+json",
        headers={"X-Request-ID": trace_id},
    )
