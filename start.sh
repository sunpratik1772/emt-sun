#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
RUN_DIR="$ROOT_DIR/.run"
LOG_DIR="$RUN_DIR/logs"

BACKEND_PORT=8001
FRONTEND_PORT=3000
FRONTEND_URL="http://localhost:${FRONTEND_PORT}"

if ! command -v lsof >/dev/null 2>&1; then
  echo "Error: lsof is required but not installed."
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 is required but not installed."
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "Error: npm is required but not installed."
  exit 1
fi

mkdir -p "$LOG_DIR"

echo "Stopping all processes on ports ${BACKEND_PORT} and ${FRONTEND_PORT}..."

# ── 1. Kill tracked PIDs from previous run ──
for pidfile in "$RUN_DIR/backend.pid" "$RUN_DIR/frontend.pid"; do
  if [ -f "$pidfile" ]; then
    pid="$(cat "$pidfile" 2>/dev/null || true)"
    if [ -n "${pid:-}" ] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
    rm -f "$pidfile"
  fi
done

# ── 2. Kill anything listening on our ports (SIGTERM) ──
for port in "$BACKEND_PORT" "$FRONTEND_PORT"; do
  pids="$(lsof -ti :"$port" 2>/dev/null || true)"
  if [ -n "${pids}" ]; then
    echo "  Sending SIGTERM to PIDs on port ${port}: $(echo $pids | tr '\n' ' ')"
    echo "$pids" | xargs kill 2>/dev/null || true
  fi
done

# ── 3. Also kill known process patterns from this repo ──
pkill -f "uvicorn server:app.*${BACKEND_PORT}" 2>/dev/null || true
pkill -f "vite.*${FRONTEND_PORT}" 2>/dev/null || true
pkill -f "node.*${FRONTEND_PORT}" 2>/dev/null || true

# Give processes time to exit gracefully.
sleep 2

# ── 4. Force-kill anything still clinging to our ports ──
for port in "$BACKEND_PORT" "$FRONTEND_PORT"; do
  pids="$(lsof -ti :"$port" 2>/dev/null || true)"
  if [ -n "${pids}" ]; then
    echo "  Force-killing stubborn PIDs on port ${port}: $(echo $pids | tr '\n' ' ')"
    echo "$pids" | xargs kill -9 2>/dev/null || true
  fi
done

sleep 1

# ── 5. Verify ports are actually free ──
for port in "$BACKEND_PORT" "$FRONTEND_PORT"; do
  if lsof -ti :"$port" >/dev/null 2>&1; then
    echo "ERROR: Port ${port} is still in use after cleanup. Aborting."
    echo "  Run: lsof -i :${port}   to see what's holding it."
    exit 1
  fi
done

echo "Ports ${BACKEND_PORT} and ${FRONTEND_PORT} are free."

wait_for_port() {
  local port="$1"
  local name="$2"
  local attempts=20
  local i

  for ((i=1; i<=attempts; i++)); do
    if lsof -ti :"${port}" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done

  echo "${name} failed to start on port ${port} after ${attempts}s."
  return 1
}

BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"

echo "Starting backend on port ${BACKEND_PORT}..."
(
  cd "$BACKEND_DIR"
  nohup python3 -m uvicorn server:app --host 0.0.0.0 --port "${BACKEND_PORT}" >"$BACKEND_LOG" 2>&1 &
  echo $! > "$RUN_DIR/backend.pid"
)

sleep 2
if ! wait_for_port "${BACKEND_PORT}" "Backend"; then
  echo "Backend failed to start. Check: $BACKEND_LOG"
  exit 1
fi

echo "Starting frontend on port ${FRONTEND_PORT}..."
(
  cd "$FRONTEND_DIR"
  nohup npm start >"$FRONTEND_LOG" 2>&1 &
  echo $! > "$RUN_DIR/frontend.pid"
)

sleep 2
if ! wait_for_port "${FRONTEND_PORT}" "Frontend"; then
  echo "Frontend failed to start. Check: $FRONTEND_LOG"
  exit 1
fi

echo ""
echo "Services are up:"
echo "Frontend: ${FRONTEND_URL}"
echo "Backend : http://localhost:${BACKEND_PORT}/api/health"
echo ""
echo "PID files:"
echo "  $RUN_DIR/backend.pid"
echo "  $RUN_DIR/frontend.pid"
echo "Logs:"
echo "  $BACKEND_LOG"
echo "  $FRONTEND_LOG"

if command -v open >/dev/null 2>&1; then
  echo ""
  echo "Opening UI: ${FRONTEND_URL}"
  open "${FRONTEND_URL}" >/dev/null 2>&1 || true
fi
