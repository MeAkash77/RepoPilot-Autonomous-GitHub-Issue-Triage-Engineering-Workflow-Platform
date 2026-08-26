#!/usr/bin/env bash
# Stop the full RepoPilot dev stack.
set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

stop_pid() {
  local name="$1"
  local pidfile="/tmp/repopilot-${name}.pid"
  if [ -f "$pidfile" ]; then
    local pid
    pid=$(cat "$pidfile")
    if kill -0 "$pid" 2>/dev/null; then
      echo "==> Stopping $name (PID $pid)..."
      kill "$pid"
    fi
    rm -f "$pidfile"
  fi
}

stop_pid api
stop_pid worker
stop_pid web

# Fallback: pkill anything that might still be running
pkill -f "uvicorn repopilot_api.main:app" 2>/dev/null || true
pkill -f "arq repopilot_worker" 2>/dev/null || true
pkill -f "next dev" 2>/dev/null || true

echo "==> Stopping infrastructure..."
docker compose -f infra/docker-compose.yml stop postgres redis

echo "Done. All RepoPilot services stopped."
