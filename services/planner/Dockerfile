FROM ghcr.io/astral-sh/uv:0.12.9 AS uv
FROM python:3.14.7-slim AS build
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY services/planner/pyproject.toml services/planner/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY services/planner/src ./src
RUN uv sync --frozen --no-dev

FROM python:3.14.7-slim
RUN groupadd --system planner && useradd --system --gid planner --home-dir /nonexistent planner
WORKDIR /app
COPY --from=build --chown=planner:planner /app/.venv /app/.venv
COPY --from=build --chown=planner:planner /app/src /app/src
ENV PATH=/app/.venv/bin:$PATH PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER planner
EXPOSE 8080
CMD ["planner"]
