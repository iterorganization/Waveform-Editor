#!/usr/bin/env bash
# Start the Waveform Editor web service.
# Usage:
#   ./start-web.sh           # starts backend only (serves frontend from dist/ if built)
#   ./start-web.sh --dev     # starts backend + Vite dev server concurrently

set -e
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ "$1" == "--dev" ]]; then
    echo "Starting in development mode (backend + Vite dev server)..."
    # Start Vite dev server in background
    (cd "$REPO_DIR/frontend" && npm run dev) &
    VITE_PID=$!
    trap "kill $VITE_PID 2>/dev/null" EXIT
    echo "Vite dev server starting on http://localhost:5173"
fi

echo "Starting FastAPI backend on http://localhost:8000"
cd "$REPO_DIR"
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
