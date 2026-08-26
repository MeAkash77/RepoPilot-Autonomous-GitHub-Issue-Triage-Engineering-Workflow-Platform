#!/usr/bin/env bash
# Live end-to-end test runner.
# Tests the real deployed stack: Fly.io API + Vercel web.
#
# Usage:
#   bash scripts/e2e-live.sh
#
# Reads from .env in repo root for secrets (or set env vars directly).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# Load .env if present
if [ -f .env ]; then
  set -a; source .env; set +a
fi

LIVE_API_URL="${LIVE_API_URL:-https://repopilot-api.fly.dev}"
LIVE_WEB_URL="${LIVE_WEB_URL:-https://repopilot-steel.vercel.app}"
# Vercel INTERNAL_API_KEY (6b86c2...) — must match what Fly.io has set
INTERNAL_API_KEY="${INTERNAL_API_KEY:-6b86c2cdbf6b18ff6e4127629925f2ebf72fcb7f9d7236e9e7e2a965cb4db670}"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
BOLD='\033[1m'
NC='\033[0m'

PASS=0
FAIL=0

step()  { echo -e "\n${BOLD}── $1 ──${NC}"; }
ok()    { echo -e "  ${GREEN}✓${NC}  $1"; PASS=$((PASS+1)); }
fail()  { echo -e "  ${RED}✗${NC}  $1"; FAIL=$((FAIL+1)); }
warn()  { echo -e "  ${YELLOW}~${NC}  $1"; }

# curl wrapper: -s only, no -f, so HTTP 4xx/5xx don't kill the script.
_curl() { /usr/bin/curl -s "$@"; }
_code() { /usr/bin/curl -s -o /dev/null -w "%{http_code}" "$@"; }

# ─────────────────────────────────────────────────────────────────────────────
step "Smoke: services reachable"

STATUS=$(_curl "$LIVE_API_URL/healthz" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','?'))" 2>/dev/null)
[ "$STATUS" = "ok" ] && ok "API health: $STATUS" || fail "API health: got '$STATUS'"

READY_CODE=$(_code "$LIVE_API_URL/readyz")
[ "$READY_CODE" = "200" ] && ok "API readyz: HTTP $READY_CODE" || fail "API readyz: HTTP $READY_CODE"

WEB_CODE=$(_code "$LIVE_WEB_URL/")
[ "$WEB_CODE" = "200" ] && ok "Web app: HTTP $WEB_CODE" || fail "Web app: HTTP $WEB_CODE"

REDIR_CODE=$(_code "$LIVE_WEB_URL/dashboard")
[ "$REDIR_CODE" = "302" ] && ok "Dashboard auth-guard: HTTP $REDIR_CODE (redirects to sign-in)" || fail "Dashboard auth-guard: expected 302, got $REDIR_CODE"

REDIR_DEST=$(/usr/bin/curl -s -o /dev/null -w "%{redirect_url}" "$LIVE_WEB_URL/dashboard")
echo "$REDIR_DEST" | grep -q "signin" && ok "Redirect target contains 'signin': $REDIR_DEST" || fail "Redirect target: $REDIR_DEST"

# ─────────────────────────────────────────────────────────────────────────────
step "Security headers (API)"

check_header() {
  local hdr="$1" expected="$2"
  local value
  value=$(/usr/bin/curl -sI "$LIVE_API_URL/healthz" | grep -i "^$hdr:" | head -1 | sed 's/^[^:]*: //' | tr -d '\r')
  if echo "$value" | grep -qi "$expected"; then
    ok "$hdr: $value"
  else
    fail "$hdr: expected '$expected', got '$value'"
  fi
}

check_header "strict-transport-security" "max-age="
check_header "x-content-type-options" "nosniff"
check_header "x-frame-options" "DENY"
check_header "referrer-policy" "no-referrer"

# ─────────────────────────────────────────────────────────────────────────────
step "Webhook auth"

# No required header → 422 (FastAPI field validation)
CODE=$(_code -X POST "$LIVE_API_URL/webhooks/github" \
  -H "Content-Type: application/json" -d '{"action":"opened"}')
{ [ "$CODE" = "422" ] || [ "$CODE" = "400" ]; } && ok "No X-GitHub-Delivery → HTTP $CODE (rejected)" || fail "No X-GitHub-Delivery → HTTP $CODE (expected 400/422)"

# Wrong HMAC signature → 401 (verify_signature fails)
CODE=$(_code -X POST "$LIVE_API_URL/webhooks/github" \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: issues" \
  -H "X-GitHub-Delivery: test-$(date +%s)" \
  -H "X-Hub-Signature-256: sha256=deadbeef" \
  -d '{"action":"opened"}')
[ "$CODE" = "401" ] && ok "Bad HMAC → HTTP $CODE (invalid signature)" || fail "Bad HMAC → HTTP $CODE (expected 401)"

BODY=$(_curl -X POST "$LIVE_API_URL/webhooks/github" \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: issues" \
  -H "X-GitHub-Delivery: test-detail-$(date +%s)" \
  -H "X-Hub-Signature-256: sha256=deadbeef" \
  -d '{"action":"opened"}')
echo "$BODY" | grep -q "signature" && ok "Bad HMAC body: $BODY" || fail "Bad HMAC body missing 'signature': $BODY"

# Valid HMAC → 202 accepted
if [ -n "${GITHUB_WEBHOOK_SECRET:-}" ]; then
  DELIVERY="live-e2e-$(date +%s)-$$"
  PAYLOAD="{\"action\":\"opened\",\"installation\":{\"id\":1},\"issue\":{\"number\":9001,\"title\":\"[live-e2e] smoke\",\"body\":\"automated test\",\"user\":{\"login\":\"bot\"},\"state\":\"open\",\"labels\":[],\"created_at\":\"2026-01-01T00:00:00Z\"},\"repository\":{\"id\":1,\"full_name\":\"AyushCoder9/repopilot-sandbox\",\"private\":false},\"sender\":{\"login\":\"bot\"}}"
  SIG="sha256=$(printf '%s' "$PAYLOAD" | openssl dgst -sha256 -hmac "$GITHUB_WEBHOOK_SECRET" | awk '{print $2}')"
  CODE=$(_code -X POST "$LIVE_API_URL/webhooks/github" \
    -H "Content-Type: application/json" \
    -H "X-GitHub-Event: issues" \
    -H "X-GitHub-Delivery: $DELIVERY" \
    -H "X-Hub-Signature-256: $SIG" \
    -d "$PAYLOAD")
  { [ "$CODE" = "202" ] || [ "$CODE" = "200" ]; } && ok "Valid HMAC → HTTP $CODE (accepted + queued)" || fail "Valid HMAC → HTTP $CODE (expected 202)"

  # Idempotency: resend same delivery → still 202 (duplicate acknowledged)
  CODE2=$(_code -X POST "$LIVE_API_URL/webhooks/github" \
    -H "Content-Type: application/json" \
    -H "X-GitHub-Event: issues" \
    -H "X-GitHub-Delivery: $DELIVERY" \
    -H "X-Hub-Signature-256: $SIG" \
    -d "$PAYLOAD")
  { [ "$CODE2" = "202" ] || [ "$CODE2" = "409" ]; } && ok "Duplicate delivery → HTTP $CODE2 (idempotent)" || fail "Duplicate delivery → HTTP $CODE2 (expected 202 or 409)"
else
  warn "GITHUB_WEBHOOK_SECRET not set — skipping HMAC tests"
fi

# ─────────────────────────────────────────────────────────────────────────────
step "Internal API auth gate"

CODE=$(_code "$LIVE_API_URL/api/v1/repos")
[ "$CODE" = "401" ] && ok "No key → HTTP $CODE" || fail "No key → HTTP $CODE (expected 401)"

CODE=$(_code "$LIVE_API_URL/api/v1/repos" -H "X-Internal-Key: wrong-key")
[ "$CODE" = "401" ] && ok "Wrong key → HTTP $CODE" || fail "Wrong key → HTTP $CODE (expected 401)"

CODE=$(_code "$LIVE_API_URL/api/v1/repos" -H "X-Internal-Key: $INTERNAL_API_KEY")
[ "$CODE" = "200" ] && ok "Valid key /api/v1/repos → HTTP $CODE" || fail "Valid key /api/v1/repos → HTTP $CODE (expected 200)"

CODE=$(_code "$LIVE_API_URL/api/v1/runs" -H "X-Internal-Key: $INTERNAL_API_KEY")
[ "$CODE" = "200" ] && ok "Valid key /api/v1/runs → HTTP $CODE" || fail "Valid key /api/v1/runs → HTTP $CODE"

CODE=$(_code "$LIVE_API_URL/api/v1/actions/pending" -H "X-Internal-Key: $INTERNAL_API_KEY")
[ "$CODE" = "200" ] && ok "Valid key /api/v1/actions/pending → HTTP $CODE" || fail "Valid key /api/v1/actions/pending → HTTP $CODE"

CODE=$(_code "$LIVE_API_URL/api/v1/analytics/overview" -H "X-Internal-Key: $INTERNAL_API_KEY")
[ "$CODE" = "200" ] && ok "Valid key /api/v1/analytics/overview → HTTP $CODE" || fail "Valid key /api/v1/analytics/overview → HTTP $CODE"

# ─────────────────────────────────────────────────────────────────────────────
step "Response shapes (API contract)"

REPOS=$(_curl "$LIVE_API_URL/api/v1/repos" -H "X-Internal-Key: $INTERNAL_API_KEY")
echo "$REPOS" | python3 -c "import sys,json; d=json.load(sys.stdin); assert isinstance(d, list)" 2>/dev/null \
  && ok "GET /api/v1/repos → JSON array" || fail "GET /api/v1/repos → unexpected shape: $REPOS"

RUNS=$(_curl "$LIVE_API_URL/api/v1/runs" -H "X-Internal-Key: $INTERNAL_API_KEY")
# /api/v1/runs returns paginated {items: [], next_cursor: null}
echo "$RUNS" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'items' in d or isinstance(d, list)" 2>/dev/null \
  && ok "GET /api/v1/runs → paginated JSON response" || fail "GET /api/v1/runs → unexpected shape: $RUNS"

ANALYTICS=$(_curl "$LIVE_API_URL/api/v1/analytics/overview" -H "X-Internal-Key: $INTERNAL_API_KEY")
echo "$ANALYTICS" | python3 -c "import sys,json; d=json.load(sys.stdin); assert isinstance(d, dict)" 2>/dev/null \
  && ok "GET /api/v1/analytics/overview → JSON object" || fail "GET /api/v1/analytics/overview → unexpected shape: $ANALYTICS"

# ─────────────────────────────────────────────────────────────────────────────
step "Playwright — live Vercel site (unauthenticated pages)"

cd apps/web
PW_OUT=$(LIVE_URL="$LIVE_WEB_URL" pnpm exec playwright test \
  --config playwright.live.config.ts \
  --project=live 2>&1)
PW_EXIT=$?
echo "$PW_OUT" | grep -E "✓|✗|passed|failed" | tail -15
if [ $PW_EXIT -eq 0 ]; then
  PW_PASS=$(echo "$PW_OUT" | grep -oE "[0-9]+ passed" | grep -oE "[0-9]+" || echo 0)
  ok "Playwright $PW_PASS tests passed on live Vercel"
else
  fail "Playwright failed — see output above"
fi
cd "$REPO_ROOT"

# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}══════════════════════════════════════${NC}"
echo -e "${BOLD}  Results: ${GREEN}${PASS} passed${NC}  ${RED}${FAIL} failed${NC}"
echo -e "${BOLD}══════════════════════════════════════${NC}"
echo ""

[ "$FAIL" -eq 0 ] && exit 0 || exit 1
