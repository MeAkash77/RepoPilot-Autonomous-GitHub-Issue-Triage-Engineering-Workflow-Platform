<div align="center">

<img src="./logo.svg" width="140" height="140" alt="RepoPilot" />

# RepoPilot

### The autonomous triage engineer that never sleeps.

**Install the GitHub App. Open an issue. Watch it get classified, deduplicated, owner-routed,
and queued for approval — in under 4 seconds, for less than a tenth of a cent.**

<br/>

[![CI](https://github.com/AyushCoder9/RepoPilot/actions/workflows/ci.yml/badge.svg)](https://github.com/AyushCoder9/RepoPilot/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/AyushCoder9/RepoPilot/branch/main/graph/badge.svg)](https://codecov.io/gh/AyushCoder9/RepoPilot)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-b6ff3c?style=flat&logo=python&logoColor=black&labelColor=0a0b0a)](https://python.org)
[![Next.js 15](https://img.shields.io/badge/Next.js-15-b6ff3c?style=flat&logo=nextdotjs&logoColor=black&labelColor=0a0b0a)](https://nextjs.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2-b6ff3c?style=flat&labelColor=0a0b0a)](https://langchain-ai.github.io/langgraph/)
[![OpenTelemetry](https://img.shields.io/badge/OpenTelemetry-enabled-b6ff3c?style=flat&logo=opentelemetry&logoColor=black&labelColor=0a0b0a)](docs/OBSERVABILITY.md)
[![Fly.io](https://img.shields.io/badge/Fly.io-deployed-b6ff3c?style=flat&logo=flydotio&logoColor=black&labelColor=0a0b0a)](https://fly.io)
[![License: MIT](https://img.shields.io/badge/license-MIT-b6ff3c?style=flat&labelColor=0a0b0a)](LICENSE)

<br/>

[**Live App →**](https://repopilot.vercel.app) &nbsp;·&nbsp;
[**Install GitHub App →**](https://github.com/apps/repopilot-gh/installations/new) &nbsp;·&nbsp;
[**Architecture →**](docs/ARCHITECTURE.md) &nbsp;·&nbsp;
[**Observability →**](docs/OBSERVABILITY.md)

</div>

---

## What RepoPilot does

RepoPilot is a **production-grade, full-stack AI system** that plugs into any GitHub repository as an App and autonomously triages every new issue through an 8-stage LangGraph pipeline — with human-in-the-loop approval, cost controls, rate limiting, prompt-injection defences, and full observability.

```
issue.opened
     │
     ▼
 01  sanitize ──── injection screen · Unicode normalisation · field clamps · hidden-channel stripping
     │
     ▼
 02  retrieve ──── hybrid RAG: pgvector dense + BM25 sparse → RRF fusion → Cohere cross-encoder rerank
     │
     ▼
 03  classify ──── type (bug/feature/question/docs) · severity 1–4 · auditable rationale · structured output
     │
     ├─────────────────────────┬──────────────────────────┐
     ▼                         ▼                          ▼
 04  duplicates           05  info-gap              06  code-locator
     cited evidence            detects missing            file-path suggestions
     from issue history        reproduction steps         via retrieval + path terms
     │                         │                          │
     └─────────────────────────┴──────────────────────────┘
                               │
                               ▼
                          07  assignee ──── CODEOWNERS + commit-area history
                               │
                               ▼
                          08  compose ───── proposed actions (label / comment / assign)
                               │
                               ▼
                          guardrail ──────── output allowlist check · autonomy gate
                               │
                               ▼
                          approval queue ── human-in-the-loop: approve / edit / reject
```

Every proposed action lands in a **human review queue**. Raise the autonomy level to auto-apply low-risk actions; keep full control for high-risk ones. The approval decision is recorded as a labeled feedback event for future fine-tuning.

---

## Live numbers

| Metric | Value |
|---|---|
| End-to-end pipeline latency (mean) | **3.7 s** |
| Cost per triage run (mean) | **$0.0008** |
| Cost cap per run (hard guardrail) | $0.02 |
| Daily per-installation run cap | 500 runs |
| Pipeline stages | 8 |
| Parallel stages | 3 (nodes 04–06) |
| Embedding dimension | 1 024 |
| Test suite size | **129 unit + integration** |
| Adversarial red-team cases | **26** (100 % pass gate in CI) |
| LLM providers (with automatic fallback) | 2 (Groq + Gemini) |
| Supported issue types | 4 |
| Severity levels | 4 |

---

## Full technology stack

### Languages & Runtimes
| | |
|---|---|
| **Python 3.12** | Agent, API, worker — full async (`asyncio`, `asyncpg`, `arq`) |
| **TypeScript 5** | Next.js frontend — strict mode, full type coverage |

### AI & ML
| Library / Service | Role |
|---|---|
| **LangGraph 0.2** | Directed acyclic graph for the 8-stage triage pipeline; per-node timeouts, deterministic execution order, native SSE streaming |
| **Groq API** — Llama 3.3 70B | Primary fast LLM for classify, duplicate, info-gap, code-locator, guardrail nodes |
| **Google Gemini 1.5 Flash** | Long-context LLM for compose node; automatic fallback when Groq circuit opens |
| **Cohere Reranker** | Cross-encoder reranking of hybrid-search candidates |
| **pgvector HNSW** | 1 024-dim dense vector search, cosine similarity, ef_construction=200 |
| **BM25 full-text** | PostgreSQL `tsvector` GIN index, sparse retrieval |
| **RRF fusion** | Reciprocal Rank Fusion (k=60) combining dense + sparse scores |
| **Langfuse Cloud** | Per-node LLM trace: model, tokens, cost, latency; v2 SDK pinned `>=2.59,<3` |

### Backend
| Library / Service | Role |
|---|---|
| **FastAPI** | Async REST API; OpenAPI docs in dev |
| **arq** | Async Redis job queue; worker processes triage jobs |
| **SQLAlchemy 2 (async)** | ORM with `asyncpg` driver |
| **Alembic** | Database schema migrations |
| **Pydantic v2** | Settings, request/response models, structured LLM outputs |
| **slowapi** | Rate limiting: per-route sliding window, Redis-backed in prod |
| **structlog** | JSON-structured logging in prod/CI; ConsoleRenderer locally; `request_id` correlation across API + worker |
| **OpenTelemetry SDK** | Traces + metrics pushed to Grafana Cloud via OTLP/HTTP; no-op when endpoint unset |
| **httpx** | Async HTTP client (GitHub API, LLM providers) |
| **PyJWT** | GitHub App JWT generation for installation token exchange |

### Frontend
| Library / Service | Role |
|---|---|
| **Next.js 15** (App Router) | Server components, server actions, BFF proxy, API route handlers |
| **Auth.js v5** | GitHub OAuth, JWT sessions, middleware-guarded `/dashboard` |
| **React Three Fiber + GSAP** | WebGL hero animation on the landing page |
| **Framer Motion** | Page transitions, micro-interactions |
| **Recharts** | Latency percentile charts, run-volume bars, cost trend on Observability page |
| **Tailwind CSS v4** | Utility-first dark theme |
| **Phosphor Icons** | Icon system |
| **Playwright** | E2E test suite (landing, dashboard, auth flow) |

### Data & Storage
| Service | Role |
|---|---|
| **Neon Postgres 16** | Primary database + pgvector extension (HNSW index); pooled connection string for runtime, direct for migrations |
| **Upstash Redis 7** | Job queue (arq), rate-limit counters, circuit-breaker state, budget counters; TLS, regional |

### Infrastructure & Deployment
| Service | Role |
|---|---|
| **Fly.io** | API + worker: 2 shared-CPU 256 MB machines, `sin` (Singapore) region, rolling deploys, machine-level health checks |
| **Vercel** | Next.js hosting; zero-config, edge network, preview deployments on PR |
| **GitHub Actions** | CI pipeline (lint → typecheck → test → coverage → deploy); CodeQL SAST; Dependabot; DLQ alert cron; load-test dispatch |
| **Docker Compose** | Local dev: `pgvector/pgvector:pg16` + `redis:7-alpine` |
| **Docker multi-stage** | Build image: `uv:python3.12-bookworm-slim`; runtime: `python:3.12-slim-bookworm`; ~228 MB final image |

### Observability
| Tool | What it covers |
|---|---|
| **Grafana Cloud** | Unified metrics (Prometheus/Mimir), logs (Loki), traces (Tempo), uptime |
| **OpenTelemetry OTLP** | API + worker push spans + metrics to Grafana via OTLP/HTTP — no sidecar, no agent |
| **Langfuse Cloud** | LLM-specific traces: per-node model, tokens, cost, latency; every triage run |
| **structlog JSON** | Request-ID-correlated JSON logs; `X-Request-ID` header minted per request, propagated to worker jobs |
| **In-app `/dashboard/observability`** | Live p50/p95/p99 latency charts, run volume, cost trend, DLQ depth, component health tiles |
| **Public `/status` page** | Component health + last-checked timestamps; no auth required |
| **Grafana dashboard JSON** | Importable at `infra/grafana/repopilot-dashboard.json` — SLO tiles, latency percentiles, LLM errors, circuit breaker |

### Security
| Layer | Mechanism |
|---|---|
| Webhook authenticity | HMAC SHA-256 (`X-Hub-Signature-256`) + `hmac.compare_digest` (constant-time) + idempotent delivery ledger |
| Prompt injection | Multi-layer: sanitize node strips control chars + hidden channels (data URIs, HTML comments, tag-block chars); guardrail node checks outputs against allowlist; autonomy downgrade on detection; 26-case adversarial eval suite |
| API authentication | `X-Internal-Key` on all data endpoints; secret never reaches the browser (server-side BFF proxy in Next.js) |
| User authentication | GitHub OAuth (Auth.js v5) · JWT sessions · middleware guard on all `/dashboard` routes |
| Tenant isolation | `scoped_repo_ids()` resolves caller → installations → repos; all queries scoped; out-of-scope returns 404 |
| Rate limiting | slowapi per-route tiers: webhook 300/min, dashboard reads 120/min, mutations 30/min, SSE 10/min; `Retry-After` header; Redis-backed |
| Request hardening | Body-size caps (2 MB webhook / 256 KB dashboard); HSTS + CSP + `X-Frame-Options` + nosniff + Referrer-Policy on every response; `Server` header stripped; global opaque 500 handler |
| Abuse budget | Redis `INCR` per installation per day; over-cap webhooks ledgered `THROTTLED`, never enqueued; GitHub always receives 202 |
| Cost runaway | `MAX_COST_PER_RUN_USD` hard cap in compose node; per-run token accounting |
| SAST | GitHub CodeQL (Python + TypeScript) on every push + PR + weekly schedule |
| Dependency scanning | Dependabot weekly for pip, npm, GitHub Actions |

### Reliability
| Feature | Implementation |
|---|---|
| LLM fallback | Every route in `models.yaml` has `fallback_provider` / `fallback_model`; groq ↔ gemini |
| Circuit breaker | Redis-backed per-provider: 5 consecutive failures → open 60 s; half-open probe → auto-recover; `LLMResponse.used_fallback` flag |
| Deep health check | `GET /readyz` — real `SELECT 1` on Postgres + Redis `PING`; returns 503 if either down |
| Liveness probe | `GET /healthz` — always 200; no dependencies |
| Dead-letter queue | `WebhookDelivery.status=FAILED` ledger; exposed via `GET /api/v1/observability/dead-letter` |
| DLQ alerting | GitHub Actions cron every 30 min; fails job (triggers notification) if DLQ depth > 5 |
| Idempotency | Delivery ledger deduplicates webhooks by `X-GitHub-Delivery` |

---

## System architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  GitHub                                                                     │
│  ┌───────────────┐  issues.opened  ┌────────────────────────────────────┐  │
│  │  GitHub App   │ ──── webhook ──▶│  /webhooks/github                  │  │
│  │  (App JWT +   │  HMAC-verified  │  HMAC verify · idempotency ledger  │  │
│  │   inst token) │                 │  → enqueue arq job                 │  │
│  └───────────────┘                 └──────────────┬─────────────────────┘  │
└────────────────────────────────────────────────────│────────────────────────┘
                                                     │ Redis job queue
┌────────────────────────────────────────────────────▼────────────────────────┐
│  apps/api  ·  FastAPI (Fly.io · sin region · 2 machines)                   │
│                                                                              │
│  Middleware stack (outermost → innermost):                                  │
│  RequestContextMiddleware → SecurityMiddleware → SlowAPIMiddleware          │
│  → CORSMiddleware → TrustedHostMiddleware                                   │
│                                                                              │
│  Routes:                                                                    │
│  /healthz  /readyz  /webhooks/github  (public)                             │
│  /api/v1/{repos,runs,actions,analytics,observability,search}  (X-Internal-Key) │
└──────────────────────┬────────────────────────────▲────────────────────────┘
                       │ arq enqueue                │ X-Internal-Key (BFF)
┌──────────────────────▼──────────┐    ┌────────────┴───────────────────────┐
│  apps/worker  ·  arq (Fly.io)   │    │  apps/web  ·  Next.js 15 (Vercel) │
│                                  │    │                                    │
│  LangGraph triage pipeline:      │    │  Landing · Demo · Dashboard        │
│  sanitize → retrieve → classify  │    │  Auth.js v5 (GitHub OAuth)         │
│  → [duplicates ‖ info-gap ‖      │    │  BFF proxy → API                  │
│     code-locator] → assignee     │    │  Observability page                │
│  → compose → guardrail           │    │  Approval inbox (HITL)             │
│                                  │    │  SSE run streaming                 │
│  LLM routing (YAML-configured):  │    │  WebGL hero · Framer Motion        │
│  Groq Llama 3.3-70B (primary)    │    └────────────────────────────────────┘
│  Gemini 1.5 Flash (fallback)     │
│  Circuit breaker (Redis-backed)  │
│  Langfuse tracing per node       │
└──────────────────────┬───────────┘
                       │
┌──────────────────────▼───────────────────────────────────────────────────────┐
│  Data Layer                                                                  │
│  Neon Postgres 16 + pgvector HNSW   ·   Upstash Redis 7 (TLS)              │
└──────────────────────────────────────────────────────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────────────────────────────┐
│  Observability Layer                                                         │
│  structlog JSON → Grafana Cloud Loki                                        │
│  OpenTelemetry OTLP → Grafana Cloud Tempo (traces) + Mimir (metrics)       │
│  Langfuse Cloud → LLM-specific span tree per triage run                    │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Repository layout

```
RepoPilot/
├── apps/
│   ├── api/                      FastAPI application
│   │   ├── src/repopilot_api/
│   │   │   ├── main.py           App factory, middleware stack, router registration
│   │   │   ├── middleware.py     RequestContextMiddleware, SecurityMiddleware
│   │   │   ├── ratelimit.py      slowapi limiter, per-route tier config
│   │   │   ├── deps.py           FastAPI dependencies (DB session, caller context)
│   │   │   ├── scoping.py        scoped_repo_ids() — tenant isolation
│   │   │   └── routes/
│   │   │       ├── health.py     /healthz (liveness) + /readyz (deep check)
│   │   │       ├── webhooks.py   GitHub App webhook handler
│   │   │       ├── runs.py       Triage run list, detail, SSE stream
│   │   │       ├── actions.py    Proposed action approval/reject queue
│   │   │       ├── repos.py      Repo settings (autonomy level, indexing)
│   │   │       ├── analytics.py  Aggregate metrics for dashboard
│   │   │       ├── observability.py  /metrics /health /traces /dead-letter
│   │   │       └── search.py     Hybrid knowledge-base search endpoint
│   │   └── tests/                API unit + integration tests
│   │
│   └── web/                      Next.js 15 frontend
│       ├── src/app/
│       │   ├── page.tsx          Landing page (WebGL hero, features, stack)
│       │   ├── status/           Public status page (no auth)
│       │   └── dashboard/
│       │       ├── page.tsx      Overview (cost/latency/approval-rate)
│       │       ├── inbox/        HITL approval queue (j/k/A/R keyboard nav)
│       │       ├── runs/[id]/    Run detail + SSE-streamed node timeline
│       │       ├── repos/        Repo autonomy settings
│       │       ├── analytics/    Recharts cost + latency analytics
│       │       └── observability/ Live p50/p95/p99 charts, DLQ, health tiles
│       ├── src/components/
│       │   ├── sidebar.tsx       Dashboard nav (Overview/Inbox/Runs/Repos/Analytics/Observability)
│       │   ├── nav/              Landing navbar + section anchors
│       │   └── ui/               StatusDot, Stat, Card, command palette (⌘K)
│       ├── src/lib/api.ts        Type-safe API client (all endpoints, BFF proxy)
│       └── tests/e2e/            Playwright test suite
│
├── packages/
│   ├── agent/                    LangGraph triage pipeline
│   │   ├── src/repopilot_agent/
│   │   │   ├── graph.py          LangGraph StateGraph definition
│   │   │   ├── runner.py         Pipeline execution, cost/token accounting
│   │   │   ├── nodes/            8 individual node implementations
│   │   │   ├── tracing.py        Langfuse post-hoc span recording
│   │   │   └── config/
│   │   │       ├── models.yaml   Per-route LLM + fallback config (YAML-driven)
│   │   │       └── prompts/      Versioned prompt registry
│   │   └── tests/
│   │
│   ├── core/                     Shared DB + settings
│   │   ├── src/repopilot_core/
│   │   │   ├── db/models.py      SQLAlchemy models (Issue, TriageRun, WebhookDelivery, …)
│   │   │   ├── settings.py       Pydantic BaseSettings (all env vars)
│   │   │   ├── logging.py        configure_logging() — structlog JSON/console
│   │   │   └── telemetry.py      init_telemetry() — OTel TracerProvider + MeterProvider
│   │   └── alembic/              5 migration revisions
│   │
│   ├── llm/                      LLM router + circuit breaker
│   │   └── src/repopilot_llm/
│   │       ├── router.py         LLMRouter, RouteConfig, CircuitBreaker, LLMResponse
│   │       ├── providers/        Groq, Gemini, Anthropic adapters
│   │       └── tests/
│   │
│   ├── github/                   GitHub App client
│   │   └── src/repopilot_github/
│   │       └── client.py         App JWT, installation token cache, retrying httpx
│   │
│   └── retrieval/                Hybrid search engine
│       └── src/repopilot_retrieval/
│           ├── search.py         Dense + sparse → RRF → rerank pipeline
│           ├── chunkers.py       Issue, markdown, code chunkers
│           ├── embedder.py       Gemini embedding provider
│           └── reranker.py       Cohere cross-encoder
│
├── evals/                        Red-team evaluation suite
│   ├── src/evals/runner.py       Eval runner with baseline regression gates
│   ├── datasets/                 26 adversarial cases + 30-case classification seed
│   └── tests/                    pytest-based eval harness (CI gate: F1 budget 2 pts)
│
├── mcp-server/                   MCP server for Claude Desktop / IDEs
│   └── src/mcp_repopilot/        6 tools: pending actions, triage status, search, analytics
│
├── infra/
│   ├── docker-compose.yml        Local dev stack (pgvector:pg16, redis:7-alpine)
│   ├── Dockerfile.api            Multi-stage, uv-based, ~228 MB
│   ├── Dockerfile.worker         Same base, worker entrypoint
│   └── grafana/
│       └── repopilot-dashboard.json  Importable Grafana dashboard
│
├── scripts/
│   ├── dev-up.sh                 One-command dev stack start
│   ├── dev-down.sh               One-command dev stack stop
│   └── load-test.js              k6 load test (workflow_dispatch in CI)
│
├── docs/
│   ├── ARCHITECTURE.md           System design, data flow, ADR index
│   ├── SECURITY.md               Full threat model, defence layers
│   ├── OBSERVABILITY.md          SLOs, Grafana setup, Langfuse setup, runbook
│   ├── EVALS.md                  Red-team matrix, eval methodology
│   ├── deploy.md                 Click-by-click production deploy guide
│   ├── github-app-setup.md       GitHub App creation and webhook config
│   ├── mcp-setup.md              Claude Desktop + IDE MCP integration
│   └── ADRs/                     Architecture Decision Records (001, 002)
│
└── .github/
    ├── workflows/
    │   ├── ci.yml                Lint → typecheck → test → coverage → deploy
    │   ├── codeql.yml            CodeQL SAST (Python + TypeScript, weekly)
    │   ├── dlq-alert.yml         DLQ depth cron alert (every 30 min)
    │   └── load-test.yml         k6 load test (workflow_dispatch)
    └── dependabot.yml            Weekly updates: pip + npm + actions
```

---

## Quickstart

### Prerequisites

| Tool | Version | Install |
|---|---|---|
| Python | 3.12 | [python.org](https://python.org) |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Node.js | 20 + | [nodejs.org](https://nodejs.org) |
| pnpm | 9 | `npm install -g pnpm` |
| Docker Desktop | any | [docker.com](https://docker.com) |
| GitHub App | — | [docs/github-app-setup.md](docs/github-app-setup.md) |

### 1 · Clone and install

```bash
git clone https://github.com/AyushCoder9/RepoPilot
cd RepoPilot
uv sync --all-extras    # Python workspace (api, worker, all packages)
pnpm install            # Node workspace (web)
```

### 2 · Configure environment

```bash
cp .env.example .env
cp apps/web/.env.example apps/web/.env.local
```

Generate secrets:

```bash
openssl rand -hex 32   # → INTERNAL_API_KEY  (paste in .env AND apps/web/.env.local)
openssl rand -hex 32   # → AUTH_SECRET       (paste in apps/web/.env.local)
```

Minimum required variables in `.env`:

```env
DATABASE_URL=postgresql+asyncpg://repopilot:repopilot@localhost:5432/repopilot
REDIS_URL=redis://localhost:6379
INTERNAL_API_KEY=<generated>
GITHUB_APP_ID=<from github app>
GITHUB_APP_PRIVATE_KEY=<pem content>
GITHUB_WEBHOOK_SECRET=<from github app>
GROQ_API_KEY=<from groq.com>
GOOGLE_API_KEY=<from aistudio.google.com>
```

### 3 · Start everything

```bash
bash scripts/dev-up.sh
```

Open [**http://localhost:3000**](http://localhost:3000) after ~10 s.

```bash
bash scripts/dev-down.sh   # stop everything
```

**Verify the stack:**

```bash
curl http://localhost:8000/healthz   # → {"status":"ok"}
curl http://localhost:8000/readyz    # → {"status":"ok","checks":{"postgres":...,"redis":...}}
```

Full command-by-command breakdown → [run.md](run.md)

---

## Testing

```bash
# Full Python test suite (129 tests)
uv run pytest -q

# With coverage report
uv run pytest -q --cov --cov-report=term-missing

# Red-team adversarial evals (26 cases, 100 % pass required)
uv run pytest evals/ -v

# Playwright E2E (frontend)
cd apps/web && pnpm exec playwright test

# Live API contract tests (needs running stack)
RUN_LIVE=1 uv run pytest apps/api/tests/test_live_deployed.py -v -m live
```

CI runs the full suite on every push to `main` and every PR: lint (ruff) → typecheck (mypy strict) → migrations → tests → coverage upload (Codecov) → Playwright E2E.

---

## Observability & Operations

RepoPilot is fully instrumented for production:

```
Fly.io machines
    │
    ├── structlog JSON logs ──────────────────────▶ Grafana Cloud Loki
    │   (request_id, method, path, status, latency)
    │
    ├── OpenTelemetry OTLP ───────────────────────▶ Grafana Cloud Tempo (traces)
    │                         ────────────────────▶ Grafana Cloud Mimir (metrics)
    │
    └── Langfuse SDK ─────────────────────────────▶ Langfuse Cloud
        (per-node: model, tokens, cost, latency)
```

**In-app observability** (no external dependency required):
- `/dashboard/observability` — live p50/p95/p99 latency bar chart, run volume, cost trend, DLQ count, component health tiles
- `/status` — public status page, component health, last-checked timestamps

**SLOs:**

| Signal | Target |
|---|---|
| Triage success rate | ≥ 99 % |
| p95 pipeline latency | < 8 s |
| Mean cost per run | < $0.002 |
| API p95 HTTP latency | < 500 ms |
| DLQ depth | < 5 items / hour |

Setup guide → [docs/OBSERVABILITY.md](docs/OBSERVABILITY.md)
Grafana dashboard → [infra/grafana/repopilot-dashboard.json](infra/grafana/repopilot-dashboard.json)

---

## Security model

RepoPilot is hardened at every layer. Full threat model → [docs/SECURITY.md](docs/SECURITY.md)

**Highlights:**
- **Zero-trust webhook ingestion** — every delivery HMAC-verified before any processing; duplicate deliveries silently dropped via idempotency ledger.
- **Multi-layer prompt injection defence** — sanitize node + guardrail node + 26-case red-team eval suite as a hard CI gate.
- **Strict tenant isolation** — `scoped_repo_ids()` scopes every DB query to the signed-in user's GitHub installations. Out-of-scope access returns 404 (no existence disclosure).
- **API key never hits the browser** — Next.js BFF proxy intercepts all data requests; `INTERNAL_API_KEY` is a server-only environment variable.
- **Per-installation abuse budget** — Redis counter gates daily run volume per installation; over-cap webhooks are ledgered `THROTTLED`, GitHub always receives 202.
- **Automated scanning** — CodeQL SAST weekly + on every PR; Dependabot for pip, npm, and Actions.

---

## Evaluations

26 adversarial red-team cases, run as a hard gate in CI:

| Category | Cases |
|---|---|
| Direct prompt injection (issue body) | 8 |
| Indirect injection (Unicode / hidden channels) | 5 |
| Oversized payloads | 3 |
| Malformed / replayed webhooks | 4 |
| Pipeline timeout behaviour | 2 |
| Cost guardrail enforcement | 2 |
| Output allowlist evasion | 2 |

All 26 must pass. Macro-F1 budget: max 2-point regression from baseline before CI fails.

```bash
uv run pytest evals/ -v
```

Full matrix → [docs/EVALS.md](docs/EVALS.md)

---

## MCP server

RepoPilot ships a Model Context Protocol server with 6 tools, usable from Claude Desktop, Claude Code, or any MCP-compatible IDE:

| Tool | Description |
|---|---|
| `list_pending_actions` | All proposed actions awaiting human approval |
| `approve_action` | Approve a proposed action with optional edit |
| `reject_action` | Reject a proposed action with reason |
| `get_triage_status` | Triage run status for a given issue |
| `search_knowledge` | Hybrid search over the indexed knowledge base |
| `get_analytics` | Aggregate cost / latency / approval-rate metrics |

```bash
# stdio transport (Claude Desktop)
uv run repopilot-mcp

# HTTP transport (remote MCP clients)
REPOPILOT_MCP_TRANSPORT=http uv run repopilot-mcp
```

Setup → [docs/mcp-setup.md](docs/mcp-setup.md)

---

## Architecture decisions

| ADR | Decision | Rationale |
|---|---|---|
| [ADR-001](docs/ADRs/001-pgvector-over-dedicated-vector-db.md) | pgvector over Pinecone / Weaviate | One less dependency; 97 % of Pinecone recall on this workload; joins with relational data |
| [ADR-002](docs/ADRs/002-langgraph-over-crewai-or-raw-loop.md) | LangGraph over CrewAI / raw loop | Deterministic graph execution; per-node timeouts; native SSE streaming; typed state |

---

## Production deployment

All managed cloud — nothing runs on your laptop.

| Service | What runs there |
|---|---|
| **Fly.io** `sin` region | API (2 × shared-CPU 256 MB) + Worker (1 × shared-CPU 256 MB) |
| **Vercel** | Next.js web app, edge network, preview deploys per PR |
| **Neon** | Postgres 16 + pgvector; pooled connection for runtime, direct for migrations |
| **Upstash** | Redis 7, regional, TLS; job queue + rate limiter + circuit breaker |
| **Grafana Cloud** | Logs (Loki) + metrics (Mimir) + traces (Tempo); free tier |
| **Langfuse Cloud** | LLM-specific tracing; free tier |
| **GitHub Actions** | CI + CD + CodeQL + Dependabot + DLQ alerts |

Click-by-click deploy guide → [docs/deploy.md](docs/deploy.md)

---

## CI/CD pipeline

```
push to main
     │
     ├── CI ──────────────────────────────────────────────────────┐
     │   ├── python job                                           │
     │   │   ├── ruff lint + format check                        │
     │   │   ├── mypy --strict (all packages)                    │
     │   │   ├── alembic upgrade head (Postgres service)         │
     │   │   ├── pytest -q --cov (129 tests, Redis + Postgres)   │
     │   │   └── codecov/codecov-action@v4 (coverage upload)     │
     │   ├── web job                                              │
     │   │   ├── pnpm lint (ESLint)                              │
     │   │   ├── pnpm typecheck (tsc)                            │
     │   │   └── pnpm build (Next.js production build)           │
     │   └── e2e job                                              │
     │       └── Playwright (chromium, live API)                  │
     │                                                            │
     ├── Deploy ──────────────────────────────────────────────────┤
     │   ├── flyctl deploy repopilot-api (rolling)               │
     │   └── flyctl deploy repopilot-worker (rolling)            │
     │                                                            │
     └── CodeQL ─────────────────────────────────────────────────┘
         └── Python + TypeScript SAST
```

---

## License

MIT — see [LICENSE](LICENSE)

---

<div align="center">

Built with [LangGraph](https://langchain-ai.github.io/langgraph/) · [FastAPI](https://fastapi.tiangolo.com) · [Next.js](https://nextjs.org) · [Fly.io](https://fly.io) · [Grafana Cloud](https://grafana.com/products/cloud/)

</div>
