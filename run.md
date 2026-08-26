# Running RepoPilot locally

## TL;DR — start everything in one command

After the one-time setup below, this is all you need:

```bash
bash scripts/dev-up.sh       # starts Postgres, Redis, API, worker, web
```

```bash
bash scripts/dev-down.sh     # stops everything
```

Open [http://localhost:3000](http://localhost:3000) after about 10 seconds.
API health check: [http://localhost:8000/healthz](http://localhost:8000/healthz)

---

Run every command from the **repo root** unless stated otherwise.

---

## Prerequisites (one-time)

```bash
# Install uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install pnpm (Node package manager)
npm install -g pnpm

# Install Python + Node dependencies
uv sync --all-extras
pnpm install
```

---

## Step 1 — Environment files (one-time)

```bash
# Copy and fill in the root env (database, GitHub App, LLM keys, INTERNAL_API_KEY)
cp .env.example .env

# Copy and fill in the web env (GitHub OAuth, AUTH_SECRET, INTERNAL_API_KEY must match .env)
cp apps/web/.env.example apps/web/.env.local
```

Generate the two shared secrets (use the same INTERNAL_API_KEY in both files):

```bash
openssl rand -hex 32   # → INTERNAL_API_KEY  (paste in .env  AND  apps/web/.env.local)
openssl rand -hex 32   # → AUTH_SECRET       (paste in apps/web/.env.local)
```

---

## Step 2 — Infrastructure (Postgres + Redis)

```bash
docker compose -f infra/docker-compose.yml up -d postgres redis
```

**Kill:**
```bash
docker compose -f infra/docker-compose.yml stop postgres redis
```

---

## Step 3 — Database migrations

```bash
cd packages/core && uv run alembic upgrade head && cd -
```

*(No kill needed — this is a one-shot command that exits when done.)*

---

## Step 4 — FastAPI (port 8000)

```bash
uv run uvicorn repopilot_api.main:app --reload --port 8000
```

**Verify:**
```bash
curl http://localhost:8000/healthz
# → {"status":"ok"}
```

**Kill:**
```bash
# Ctrl-C in the terminal, or:
pkill -f "uvicorn repopilot_api.main:app"
```

---

## Step 5 — arq worker

```bash
uv run arq repopilot_worker.main.WorkerSettings
```

**Kill:**
```bash
pkill -f "arq repopilot_worker"
```

---

## Step 6 — Next.js web app (port 3000)

```bash
cd apps/web && pnpm dev
```

Open [http://localhost:3000](http://localhost:3000).

**Kill:**
```bash
# Ctrl-C in the terminal, or:
pkill -f "next dev"
```

---

## Step 7 — MCP server (optional, for Claude Desktop)

```bash
uv run repopilot-mcp
```

For HTTP transport instead of stdio:
```bash
REPOPILOT_MCP_TRANSPORT=http uv run repopilot-mcp
```

**Kill:**
```bash
pkill -f "repopilot-mcp"
```

---

## One-shot: start everything

Run each line in a **separate terminal tab** (they are blocking processes):

```bash
# Tab 1 — infrastructure (detached, no blocking)
docker compose -f infra/docker-compose.yml up -d postgres redis
cd packages/core && uv run alembic upgrade head && cd -

# Tab 2 — API
uv run uvicorn repopilot_api.main:app --reload --port 8000

# Tab 3 — worker
uv run arq repopilot_worker.main.WorkerSettings

# Tab 4 — web
cd apps/web && pnpm dev
```

Or use the helper script to launch all three background processes in one shot:

```bash
bash scripts/dev-up.sh
```

---

## One-shot: kill everything

```bash
bash scripts/dev-down.sh
```

Or manually:

```bash
pkill -f "uvicorn repopilot_api.main:app"
pkill -f "arq repopilot_worker"
pkill -f "next dev"
docker compose -f infra/docker-compose.yml stop postgres redis
```

---

## Verify the stack is healthy

```bash
# Liveness (no dependencies)
curl http://localhost:8000/healthz
# → {"status":"ok"}

# Deep readiness — real DB SELECT 1 + Redis PING
curl http://localhost:8000/readyz
# → {"status":"ok","postgres":{"ok":true,"latency_ms":2.1},"redis":{"ok":true,"latency_ms":0.8}}

# Web
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/
# → 200

# Redis
docker exec repopilot-redis-1 redis-cli ping
# → PONG
```

---

## Observability commands

```bash
# Component health (DB + Redis + LLM) — requires API key
curl -H "X-Internal-Key: $INTERNAL_API_KEY" http://localhost:8000/api/v1/observability/health

# Live metrics (last 24h)
curl -H "X-Internal-Key: $INTERNAL_API_KEY" "http://localhost:8000/api/v1/observability/metrics?window=24h"

# Dead-letter queue (failed webhooks)
curl -H "X-Internal-Key: $INTERNAL_API_KEY" http://localhost:8000/api/v1/observability/dead-letter

# Trace waterfall for a run
curl -H "X-Internal-Key: $INTERNAL_API_KEY" http://localhost:8000/api/v1/observability/traces/1

# Watch API logs in dev
tail -f /tmp/repopilot-api.log

# Watch worker logs in dev
tail -f /tmp/repopilot-worker.log
```

In-app observability dashboard (when web is running): http://localhost:3000/dashboard/observability
Public status page (no auth): http://localhost:3000/status

---

## Running tests

```bash
# Full suite (129 tests)
uv run pytest -q

# With coverage
uv run pytest -q --cov --cov-report=term-missing

# Red-team adversarial evals (26 cases)
uv run pytest evals/ -v

# Playwright E2E
cd apps/web && pnpm exec playwright test
```

---

## Ports at a glance

| Service   | Port  | Notes |
|-----------|-------|-------|
| Next.js   | 3000  | Web dashboard + landing |
| FastAPI   | 8000  | REST API + webhooks |
| Postgres  | 5432  | pgvector + tsvector |
| Redis     | 6379  | arq queue + rate limiter + circuit breaker |
