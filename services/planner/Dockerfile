FROM python:3.12-slim AS runtime

COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /usr/local/bin/uv

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN uv sync --frozen --no-dev

EXPOSE 8501
CMD ["uv", "run", "--no-sync", "streamlit", "run", "src/mediaplan/app.py", \
     "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
