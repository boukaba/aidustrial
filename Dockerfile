# --- web build -------------------------------------------------------------
FROM node:22-slim AS web
WORKDIR /web
RUN npm install -g pnpm@10
COPY dashboard/package.json dashboard/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY dashboard/ ./
RUN pnpm build

# --- runtime ---------------------------------------------------------------
FROM python:3.12-slim
WORKDIR /app

RUN pip install --no-cache-dir uv==0.11.7
COPY agent/pyproject.toml agent/uv.lock ./
COPY agent/src ./src
RUN uv sync --frozen --no-dev

# The Next.js static export, served by FastAPI on the same origin as the
# WebSocket. One URL, no CORS or mixed-content surprises.
COPY --from=web /web/out ./static

ENV PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    AIDUSTRIAL_STATIC_DIR=/app/static \
    AIDUSTRIAL_LLM=off \
    AIDUSTRIAL_JEV=off

EXPOSE 8080
CMD ["sh", "-c", "uv run uvicorn aidustrial.server.app:app --host 0.0.0.0 --port ${PORT:-8080}"]
