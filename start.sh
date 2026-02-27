#!/bin/bash
set -euo pipefail

# LLM Council start script
# Modes:
#   auto    -> preview if Caddy is detected on :5173, else dev
#   preview -> npm run build + npm run preview (default port 4173)
#   dev     -> npm run dev (default port 5173)

MODE="auto"
BACKEND_PORT="${BACKEND_PORT:-8001}"
DEV_PORT="${DEV_PORT:-5173}"
PREVIEW_PORT="${PREVIEW_PORT:-4173}"
HOST_DEV="0.0.0.0"
HOST_PREVIEW="127.0.0.1"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      MODE="${2:-auto}"
      shift 2
      ;;
    --backend-port)
      BACKEND_PORT="${2:-8001}"
      shift 2
      ;;
    --dev-port)
      DEV_PORT="${2:-5173}"
      shift 2
      ;;
    --preview-port)
      PREVIEW_PORT="${2:-4173}"
      shift 2
      ;;
    *)
      echo "Unknown arg: $1"
      echo "Usage: $0 [--mode auto|preview|dev] [--backend-port N] [--dev-port N] [--preview-port N]"
      exit 1
      ;;
  esac
done

is_listening() {
  local port="$1"
  ss -ltn "( sport = :$port )" 2>/dev/null | tail -n +2 | grep -q .
}

first_free_port() {
  local start="$1"
  local end=$((start + 20))
  local p
  for ((p=start; p<=end; p++)); do
    if ! is_listening "$p"; then
      echo "$p"
      return 0
    fi
  done
  return 1
}

wait_http() {
  local url="$1"
  local tries=30
  local i
  for ((i=1; i<=tries; i++)); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.5
  done
  return 1
}

echo "Starting LLM Council..."

# Auto mode picks preview when Caddy is serving on :5173
if [[ "$MODE" == "auto" ]]; then
  if ss -ltnp 2>/dev/null | grep -qE ':5173\s' && ss -ltnp 2>/dev/null | grep -q 'caddy'; then
    MODE="preview"
  else
    MODE="dev"
  fi
fi

# Check for OpenClaw gateway (local-first mode)
if curl -sf --max-time 2 -X POST http://127.0.0.1:18789/v1/chat/completions -o /dev/null 2>/dev/null; then
  echo "✓ OpenClaw gateway detected — using local proxy (no API key needed)"
elif [[ -n "${OPENROUTER_API_KEY:-}" ]] || [[ -f ".env" ]]; then
  echo "ℹ  OpenClaw gateway not found — using OpenRouter direct API"
else
  echo "⚠  No OpenClaw gateway and no OPENROUTER_API_KEY — queries may fail"
  echo "   Start the OpenClaw gateway: openclaw gateway start"
  echo "   Or set OPENROUTER_API_KEY in .env"
fi

# Backend port check
if is_listening "$BACKEND_PORT"; then
  echo "⚠  Backend port :$BACKEND_PORT already in use; trying next free port"
  BACKEND_PORT="$(first_free_port "$BACKEND_PORT")"
fi

echo "Starting backend on http://127.0.0.1:${BACKEND_PORT}..."
BACKEND_PORT="$BACKEND_PORT" BACKEND_HOST="127.0.0.1" uv run python -m backend.main &
BACKEND_PID=$!

# Start frontend according to mode
cd frontend
if [[ "$MODE" == "preview" ]]; then
  FRONTEND_PORT="$PREVIEW_PORT"
  if is_listening "$FRONTEND_PORT"; then
    echo "⚠  Preview port :$FRONTEND_PORT is busy; selecting next free port"
    FRONTEND_PORT="$(first_free_port "$FRONTEND_PORT")"
  fi
  echo "Building frontend for preview..."
  npm run build >/dev/null
  echo "Starting preview frontend on http://${HOST_PREVIEW}:${FRONTEND_PORT}..."
  npm run preview -- --host "$HOST_PREVIEW" --port "$FRONTEND_PORT" --strictPort &
else
  FRONTEND_PORT="$DEV_PORT"
  if is_listening "$FRONTEND_PORT"; then
    echo "⚠  Dev port :$FRONTEND_PORT is busy; selecting next free port"
    FRONTEND_PORT="$(first_free_port "$FRONTEND_PORT")"
  fi
  echo "Starting dev frontend on http://${HOST_DEV}:${FRONTEND_PORT}..."
  npm run dev -- --host "$HOST_DEV" --port "$FRONTEND_PORT" --strictPort &
fi
FRONTEND_PID=$!

cleanup() {
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup SIGINT SIGTERM EXIT

BACKEND_URL="http://127.0.0.1:${BACKEND_PORT}/"
FRONTEND_URL="http://127.0.0.1:${FRONTEND_PORT}/"

if ! wait_http "$BACKEND_URL"; then
  echo "✗ Backend failed health check at $BACKEND_URL"
  exit 1
fi
if ! wait_http "$FRONTEND_URL"; then
  echo "✗ Frontend failed health check at $FRONTEND_URL"
  exit 1
fi

echo ""
echo "✓ LLM Council is running"
echo "  Mode:     $MODE"
echo "  Backend:  http://127.0.0.1:${BACKEND_PORT}"
echo "  Frontend: http://127.0.0.1:${FRONTEND_PORT}"
if ss -ltnp 2>/dev/null | grep -qE ':5173\s' && ss -ltnp 2>/dev/null | grep -q 'caddy'; then
  echo "  Caddy:    http://<host>:5173"
  if [[ "$MODE" == "preview" && "$FRONTEND_PORT" != "4173" ]]; then
    echo "  ⚠  Caddy may still point to :4173. Update Caddyfile if needed."
  fi
fi

echo ""
echo "Press Ctrl+C to stop both services"
wait
