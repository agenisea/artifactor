#!/usr/bin/env bash
# dev.sh — Start Artifactor backend + frontend for local development.
# Usage: ./dev.sh
# Stop:  Ctrl-C (kills both processes)

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

PIDS=()

cleanup() {
  echo ""
  echo "Shutting down..."
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  for pid in "${PIDS[@]}"; do
    wait "$pid" 2>/dev/null || true
  done
  echo "Done."
}
trap cleanup EXIT INT TERM

# --- Preflight checks ---

if ! command -v uv &>/dev/null; then
  echo "ERROR: uv is not installed. Install it: https://docs.astral.sh/uv/getting-started/"
  exit 1
fi

if ! command -v pnpm &>/dev/null; then
  echo "ERROR: pnpm is not installed. Install it: npm i -g pnpm"
  exit 1
fi

# --- Install dependencies (idempotent, fast if already installed) ---

echo "==> Installing Python dependencies..."
uv sync --extra dev --quiet

echo "==> Installing frontend dependencies..."
(cd "$ROOT/frontend" && pnpm install --silent)

# --- Create data directories ---

mkdir -p "$ROOT/data" "$ROOT/logs"

# --- Free ports if occupied by stale processes ---

for port in "$BACKEND_PORT" "$FRONTEND_PORT"; do
  stale_pids=$(lsof -ti :"$port" 2>/dev/null || true)
  if [[ -n "$stale_pids" ]]; then
    echo "==> Killing stale process on port $port"
    echo "$stale_pids" | xargs kill 2>/dev/null || true
    sleep 0.5
  fi
done

# --- Start backend ---

echo "==> Starting backend on http://localhost:$BACKEND_PORT"
uv run uvicorn artifactor.main:app \
  --reload \
  --host 0.0.0.0 \
  --port "$BACKEND_PORT" &
PIDS+=($!)

# --- Start frontend ---

echo "==> Starting frontend on http://localhost:$FRONTEND_PORT"
BACKEND_URL="http://localhost:$BACKEND_PORT" \
  pnpm --dir "$ROOT/frontend" dev --port "$FRONTEND_PORT" &
PIDS+=($!)

echo ""
echo "========================================="
echo "  Backend:  http://localhost:$BACKEND_PORT"
echo "  Frontend: http://localhost:$FRONTEND_PORT"
echo "  Press Ctrl-C to stop both."
echo "========================================="
echo ""

# Wait forever until Ctrl-C
wait
