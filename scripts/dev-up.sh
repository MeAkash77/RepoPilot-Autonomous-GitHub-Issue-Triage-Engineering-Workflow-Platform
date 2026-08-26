#!/usr/bin/env bash
# Start the full RepoPilot dev stack in the background.
# Logs go to /tmp/repopilot-{api,worker,web}.log
set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "==> Starting infrastructure..."
docker compose -f infra/docker-compose.yml up -d postgres redis

echo "==> Waiting for Postgres to be healthy..."
until docker exec repopilot-postgres-1 pg_isready -U repopilot -q 2>/dev/null; do
  sleep 1
done

echo "==> Running migrations..."
(cd packages/core && uv run alembic upgrade head)

echo "==> Starting API (port 8000)..."
uv run uvicorn repopilot_api.main:app --reload --port 8000 \
  > /tmp/repopilot-api.log 2>&1 &
echo $! > /tmp/repopilot-api.pid

echo "==> Starting worker..."
uv run arq repopilot_worker.main.WorkerSettings \
  > /tmp/repopilot-worker.log 2>&1 &
echo $! > /tmp/repopilot-worker.pid

echo "==> Starting web (port 3000)..."
cd "$REPO_ROOT/apps/web"
pnpm dev > /tmp/repopilot-web.log 2>&1 &
echo $! > /tmp/repopilot-web.pid
cd "$REPO_ROOT"

echo ""
echo "Stack is starting. Check logs:"
echo "  API:    tail -f /tmp/repopilot-api.log"
echo "  Worker: tail -f /tmp/repopilot-worker.log"
echo "  Web:    tail -f /tmp/repopilot-web.log"
echo ""
echo "Wait ~10s then open http://localhost:3000"
echo "API health: http://localhost:8000/healthz"
echo ""
echo "To stop: bash scripts/dev-down.sh"
