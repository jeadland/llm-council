#!/bin/bash

# LLM Council - Start script
# On OpenClaw installs: no API key needed — routes through local gateway automatically.

echo "Starting LLM Council..."
echo ""

# Check for OpenClaw gateway (local-first mode)
if curl -sf --max-time 2 -X POST http://127.0.0.1:18789/v1/chat/completions -o /dev/null 2>/dev/null; then
    echo "✓ OpenClaw gateway detected — using local proxy (no API key needed)"
elif [ -n "$OPENROUTER_API_KEY" ] || [ -f ".env" ]; then
    echo "ℹ  OpenClaw gateway not found — using OpenRouter direct API"
else
    echo "⚠  No OpenClaw gateway and no OPENROUTER_API_KEY — queries may fail"
    echo "   Start the OpenClaw gateway:  openclaw gateway start"
    echo "   Or set OPENROUTER_API_KEY in .env"
fi
echo ""

# Start backend
echo "Starting backend on http://localhost:8001..."
uv run python -m backend.main &
BACKEND_PID=$!

# Wait a bit for backend to start
sleep 2

# Start frontend
echo "Starting frontend on http://localhost:5173..."
cd frontend
npm run dev -- --host 0.0.0.0 &
FRONTEND_PID=$!

echo ""
echo "✓ LLM Council is running!"
echo "  Backend:  http://localhost:8001"
echo "  Frontend: http://localhost:5173"
echo ""
echo "Press Ctrl+C to stop both servers"

# Wait for Ctrl+C
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" SIGINT SIGTERM
wait
