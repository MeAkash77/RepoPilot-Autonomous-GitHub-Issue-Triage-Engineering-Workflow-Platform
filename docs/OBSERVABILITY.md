# Observability & Operations

RepoPilot ships a two-layer observability stack:

- **In-app layer** — `/dashboard/observability` and `/status` pages built from Neon Postgres data. Always works; zero external dependency.
- **Cloud ops layer** — structured JSON logs + OpenTelemetry traces/metrics pushed to Grafana Cloud; Langfuse for LLM-specific spans.

---

## SLOs

| Signal | Target | Source |
|---|---|---|
| Triage success rate | ≥ 99 % | `TriageRun.status` |
| p95 pipeline latency | < 8 s | `TriageRun.latency_ms` |
| Mean cost per run | < $0.002 | `TriageRun.total_cost_usd` |
| API p95 HTTP latency | < 500 ms | OTel request histogram |
| DLQ depth | < 5 items in 1 h window | `WebhookDelivery.status=FAILED` |

---

## In-app endpoints

| Endpoint | Auth | Description |
|---|---|---|
| `GET /api/v1/observability/metrics?window=24h` | Internal key | p50/p95/p99 latency, run volume, cost |
| `GET /api/v1/observability/health` | Internal key | Live DB + Redis + LLM checks |
| `GET /api/v1/observability/traces/{run_id}` | Internal key | Per-node waterfall from `model_routing` JSON |
| `GET /api/v1/observability/dead-letter` | Internal key | FAILED deliveries last 24 h |
| `GET /readyz` | Public | Deep health: returns 503 when DB/Redis down |
| `GET /healthz` | Public | Liveness: always 200 (no deps) |

Window values: `1h`, `6h`, `24h`, `7d`.

---

## Grafana Cloud setup

### 1 · Create account

Go to <https://grafana.com/auth/sign-up/create-user> → Free plan → choose a stack region close to your Fly.io region (`sin` → Singapore or AP region).

### 2 · Get OTLP credentials

1. In Grafana Cloud portal → **My Account** → **Stacks** → click your stack.
2. **OpenTelemetry** section → **Configure** → copy:
   - **OTLP endpoint**: `https://otlp-gateway-<region>.grafana.net/otlp`
   - **Instance ID** + **API token** (create a token with `MetricsPublisher` + `LogsPublisher` + `TracesPublisher` scopes).
3. The header value is: `Authorization=Basic <base64(instanceId:token)>`

### 3 · Set Fly secrets

```bash
flyctl secrets set \
  OTEL_EXPORTER_OTLP_ENDPOINT="https://otlp-gateway-prod-us-east-0.grafana.net/otlp" \
  OTEL_EXPORTER_OTLP_HEADERS="Authorization=Basic <base64string>" \
  --app repopilot-api

flyctl secrets set \
  OTEL_EXPORTER_OTLP_ENDPOINT="https://otlp-gateway-prod-us-east-0.grafana.net/otlp" \
  OTEL_EXPORTER_OTLP_HEADERS="Authorization=Basic <base64string>" \
  --app repopilot-worker
```

Both services auto-redeploy after secrets are set. Traces and metrics appear in Grafana within ~30 s of the first request.

### 4 · Import the dashboard

1. Grafana UI → **Dashboards** → **Import**.
2. Upload `infra/grafana/repopilot-dashboard.json` from this repo.
3. Select your Prometheus and Loki data sources.

---

## Langfuse setup

Langfuse traces every LLM span (node, model, tokens, cost, latency).

1. Sign up at <https://cloud.langfuse.com>.
2. Create a project → copy **Public Key** + **Secret Key** + **Host**.
3. Set as Fly secrets on the worker:

```bash
flyctl secrets set \
  LANGFUSE_PUBLIC_KEY="pk-lf-..." \
  LANGFUSE_SECRET_KEY="sk-lf-..." \
  LANGFUSE_HOST="https://cloud.langfuse.com" \
  --app repopilot-worker
```

Each triage run produces one Langfuse trace with child spans per LangGraph node. View at `cloud.langfuse.com` → your project → Traces.

**Version pin**: `langfuse>=2.59,<3`. The agent uses the v2 SDK API (`client.trace()` / `trace.span()`); v3+ removed these. Pin is in `packages/agent/pyproject.toml`.

---

## LLM fallback & circuit breaker

Each route in `packages/agent/src/repopilot_agent/config/models.yaml` has a `fallback_provider` / `fallback_model`. The circuit breaker is Redis-backed:

- 5 consecutive failures on a provider → circuit opens for 60 s.
- Open circuit → requests route directly to fallback; primary not called.
- After 60 s cooldown → half-open probe; success closes the circuit.

Log events to watch: `llm.fallback`, `llm.circuit_open`, `llm.circuit_closed`.

---

## DLQ alerting

`.github/workflows/dlq-alert.yml` runs every 30 minutes. It calls `GET /api/v1/observability/dead-letter` and fails the CI job if DLQ count > 5, which triggers a GitHub Actions notification email.

To add a webhook alert, set `DLQ_ALERT_WEBHOOK_URL` as a GitHub Actions secret — the workflow will `curl` it on failure.

---

## Structured logs

All services emit JSON logs in production (`ENVIRONMENT=production`). Every API request is tagged with `request_id` (from `X-Request-ID` header or auto-minted UUID). Worker jobs inherit the same `request_id` passed through the arq job kwargs.

Useful Grafana Loki queries:

```logql
# All logs for a request
{service="repopilot-api"} | json | request_id="<id>"

# Errors last hour
{service_name=~"repopilot.*"} | json | level="error"

# LLM fallback events
{service_name="repopilot-worker"} | json | event="llm.fallback"

# DLQ events
{service_name="repopilot-worker"} | json | event="webhook.processing_failed"
```

---

## Alerting runbook

| Alert | Condition | Action |
|---|---|---|
| DLQ spike | > 5 FAILED deliveries / h | Check worker logs, GitHub App connectivity |
| LLM circuit open | `llm.circuit_open` appears | Check Groq/Gemini status pages, fallback active |
| API p95 > 8 s | Grafana alert | Check Neon cold-start, connection pool |
| `/readyz` 503 | Fly health check fails | Check `DATABASE_URL` secret, Redis connectivity |
| Worker silent | No `job.completed` log in 10 min | Check `flyctl status --app repopilot-worker` |

---

## Uptime monitoring

Configure **Grafana Synthetic Monitoring** (free) to probe:

- `https://repopilot-api.fly.dev/healthz` every 60 s from multiple regions
- `https://repopilot.vercel.app` (or custom domain) every 60 s

Alert on failure → Grafana notification channel (email, PagerDuty, Slack).
