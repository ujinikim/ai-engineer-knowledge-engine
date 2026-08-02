# syntax=docker/dockerfile:1

FROM ghcr.io/astral-sh/uv:0.11.32 AS uv

FROM python:3.12-alpine AS builder

COPY --from=uv /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

FROM python:3.12-alpine AS runtime

ARG VCS_REF=unknown

LABEL org.opencontainers.image.source="https://github.com/ujinikim/ai-engineer-knowledge-engine" \
      org.opencontainers.image.revision="${VCS_REF}"

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY app ./app
COPY alembic.ini ./alembic.ini
COPY migrations ./migrations
COPY scripts ./scripts
COPY data/sources.yml data/update_sources.yml ./data/

RUN addgroup -S app \
    && adduser -S -G app -h /app app \
    && mkdir -p /app/data/raw \
    && chown -R app:app /app

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
