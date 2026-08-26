# Security model

RepoPilot's core security premise: **issue bodies are attacker-controlled input feeding an agent that holds GitHub write permissions.** Every design choice below follows from that.

## 1. Webhook boundary

- HMAC SHA-256 signature (`X-Hub-Signature-256`) verified with a constant-time compare (`hmac.compare_digest`) over the raw body. No signature, wrong prefix, or empty secret ⇒ 401.
- Idempotency: every delivery is ledgered by `X-GitHub-Delivery` ID with a unique constraint; redeliveries are acknowledged but never re-enqueued.
- The webhook handler does no work: verify → ledger → enqueue → 202.

## 2. Prompt injection (the centerpiece)

Layered, with the assumption that any single layer can fail:

**Layer 1 — input sanitization** (`packages/agent/guardrails/sanitize.py`)
- Strips channels invisible to a human reading the issue on GitHub: HTML comments, markdown image alt-text/URLs, zero-width and Unicode tags-block characters (U+E0000–U+E007F), long data URIs.
- Detects instruction-like patterns (ignore-previous, role reassignment, system-prompt probes, agent addressing, close/delete-all commands, exfiltration asks) on both the sanitized and the original text — an instruction visible only pre-sanitization is the highest-signal attack.
- Detection never blocks triage; it sets `injection_risk=high`, which **forces autonomy down to suggest-only for that run** and flags it in the UI.

**Layer 2 — prompt structure**
- User content appears only inside fenced data blocks (`<issue_data>`); every prompt states that fenced content is data, never instructions.

**Layer 3 — output allowlist** (`packages/agent/guardrails/output.py`)
- The agent can only emit the five allowlisted action types; anything else is stripped, never "repaired".
- Comments: blocked on external URLs (only `github.com/<this repo>` allowed), secret patterns (GitHub/AWS/Slack/OpenAI token shapes), hidden-channel artifacts; @-mentions stripped; 1500-char cap.
- Labels: charset allowlist, ≤50 chars, ≤5 labels. Assignees must come from the deterministic CODEOWNERS/commit-frequency suggester. `close_duplicate` is always HIGH risk.
- On `injection_risk=high`, comment actions are dropped entirely — attacker-influenced text is never posted.

**Layer 4 — execution gate** (`packages/github/executor.py`)
- `decide_gate(autonomy, risk)`: HIGH never auto-executes, at any autonomy level. The executor is the single code path that writes to GitHub.

**Verification**: 25 adversarial cases + 1 benign control in `evals/datasets/redteam.jsonl`, run by CI and by pytest; 100% pass is a hard gate. See [EVALS.md](EVALS.md).

## 3. Least privilege

GitHub App permissions: issues read/write, contents read-only, metadata read-only. No code write access, ever. Installation tokens are short-lived (1h), cached with a refresh margin, never persisted.

## 4. Secrets

Env-only via pydantic `SecretStr` (excluded from repr/logs). Pre-commit runs `detect-private-key`. Langfuse traces record token *counts*, not prompt secrets; the GitHub App PEM never leaves settings.

## 5. LLM cost ceiling

- Per-run cost cap (default $0.02) bounds blast radius of any prompt-injected "do more work" attack; max one strong-model escalation per run.

## 6. HTTP rate limiting

Implemented via `slowapi` (Starlette-native, `limits` library), backed by Redis in production and in-memory in local dev. Key function prefers `X-User-Login` (dashboard routes) then client IP (webhooks).

| Route group | Limit | Key |
|---|---|---|
| `POST /webhooks/github` | 300 / minute | client IP |
| Dashboard reads (runs, repos, analytics, actions list/detail) | 120 / minute | user login |
| Mutations (approve, reject, settings PATCH) | 30 / minute | user login |
| `GET /runs/{id}/stream` | 10 / minute | user login |

Over-limit requests receive **429** with a `Retry-After` header. The middleware is registered in `create_app()` alongside a custom `RateLimitExceeded` handler; `SlowAPIMiddleware` wires into the ASGI stack before routing.

## 7. Tenant isolation (IDOR prevention)

`X-User-Login` (the signed-in GitHub login forwarded by the BFF) is resolved to a `frozenset` of repo IDs via `scoped_repo_ids(db, caller)`:

```
Installation(account_login == caller.login) → Repo.id set
```

Every gated route — `list_runs`, `get_run`, `stream_run`, `list_repos`, `update_settings`, `list_pending`, `approve_action`, `reject_action`, and all analytics aggregates — applies this filter before returning or mutating any data.

Out-of-scope resource access returns **404** (not 403) to avoid existence disclosure. When no `X-User-Login` is present (local dev with the internal-key gate open), `scoped_repo_ids` returns `None`, which bypasses all filtering and preserves the no-auth local UX.

## 8. Request hardening

**Body-size cap** (`SecurityMiddleware`):
- `Content-Length` checked on every request before the body is read.
- Webhook path: 2 MB ceiling. All other paths: 256 KB ceiling.
- Chunked bodies without `Content-Length` are rejected after `await request.body()` by an explicit byte-length guard inside the webhook handler.
- Oversized requests → **413 Request Entity Too Large**.

**Timing-safe key compare**: `require_internal` uses `hmac.compare_digest` instead of `!=`, preventing timing-oracle attacks on the internal API key.

**CORS**: `CORSMiddleware` locked to `settings.web_origin`; only `GET`, `POST`, `PATCH` allowed; exposed headers limited to `X-Internal-Key`, `X-User-Login`, `Content-Type`.

**Trusted host**: `TrustedHostMiddleware` active in production only (`*.fly.dev`).

**Security response headers** (set on every API response):

| Header | Value |
|---|---|
| `Strict-Transport-Security` | `max-age=63072000; includeSubDomains; preload` |
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `Referrer-Policy` | `no-referrer` |
| `Permissions-Policy` | `geolocation=(), microphone=(), camera=()` |
| `X-Robots-Tag` | `noindex, nofollow` |
| `Server` | *(removed)* |

**Next.js security headers** (all routes via `next.config.ts`): HSTS, nosniff, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, and a full Content Security Policy tuned for WebGL, Fontshare CDN, GitHub avatar CDN, and the SSE stream endpoint.

**Global exception handler**: unhandled exceptions return opaque `{"detail": "internal server error"}` (500) to clients; full traceback logged via structlog.

**API docs**: `/docs` and `/redoc` are disabled in production.

## 9. Per-installation abuse budget

Prevents a compromised or malicious installation from driving unbounded LLM spend by mass-opening issues.

- Budget key: `budget:{installation_id}:{YYYYMMDD}` in Redis (same arq pool reused).
- On each `issues` webhook: atomic `INCR` on the budget key; TTL set to 26 h on first write (covers timezone skew at day boundary).
- If the counter exceeds `settings.max_runs_per_install_per_day` (default 500):
  - Delivery status set to `THROTTLED` and persisted to the ledger.
  - Job **not** enqueued — zero LLM spend.
  - GitHub receives **202 Accepted** (prevents exponential retry backoff from GitHub's delivery system).
  - Warning logged via structlog with `installation_id` and `date_key`.
- Budget resets automatically at day rollover (key expiry + new key).
- Cap is env-configurable (`MAX_RUNS_PER_INSTALL_PER_DAY`).

## Reporting

Found something? Open a private security advisory on the repo or email the maintainer. Please do not open public issues for vulnerabilities — ironic as that would be for this project.
