#!/usr/bin/env bash
# Start the Waveform Editor web service.
# Usage:
#   ./start-web.sh              # starts backend only on port 12345
#   ./start-web.sh <port>       # starts backend on specified port
#   ./start-web.sh --dev        # starts backend + Vite dev server on port 12345
#   ./start-web.sh --dev <port> # starts backend + Vite dev server on specified port

set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Parse arguments
DEV_MODE=false
PORT=12345

if [[ "$1" == "--dev" ]]; then
    DEV_MODE=true
    PORT="${2:-12345}"
elif [[ -n "$1" ]]; then
    PORT="$1"
fi

# On HPC systems, environment modules (EasyBuild etc.) put their site-packages
# on PYTHONPATH, which shadows the venv's packages (PYTHONPATH outranks a
# venv in sys.path). Prepend the venv's site-packages so its versions win
# while module-provided packages (imas_core, muscle3) stay importable.
if [[ -n "$VIRTUAL_ENV" && -n "$PYTHONPATH" ]]; then
    VENV_SITE="$(python -c 'import sysconfig; print(sysconfig.get_path("purelib"))')"
    export PYTHONPATH="$VENV_SITE:$PYTHONPATH"
fi

# Friendly check for a fresh clone / wrong environment
if ! python -c "import uvicorn" 2>/dev/null; then
    echo "uvicorn is not importable — activate a virtualenv and install the package first:" >&2
    echo "  uv venv && source .venv/bin/activate && uv pip install -e .[all]" >&2
    exit 1
fi

if $DEV_MODE; then
    echo "Starting in development mode (backend + Vite dev server)..."

    if [ ! -d "$REPO_DIR/frontend/node_modules" ]; then
        echo "frontend/node_modules missing — running npm install (first run)..."
        (cd "$REPO_DIR/frontend" && npm install)
    fi

    # Start Vite dev server in background
    (cd "$REPO_DIR/frontend" && npm run dev) &
    VITE_PID=$!

    trap "kill $VITE_PID 2>/dev/null" EXIT

    echo "Vite dev server starting on http://localhost:5173"
else
    if [ ! -d "$REPO_DIR/frontend/dist" ]; then
        echo "frontend/dist missing — building the frontend (first run)..."

        if [ ! -d "$REPO_DIR/frontend/node_modules" ]; then
            (cd "$REPO_DIR/frontend" && npm install)
        fi

        (cd "$REPO_DIR/frontend" && npm run build)
    fi
fi

echo "Starting FastAPI backend on http://localhost:${PORT}"

cd "$REPO_DIR"

# Bind to all interfaces so SSH port forwarding from an HPC login node can
# reach the service on the compute node.
#
# --reload-dir: only watch source code. NICE/MUSCLE runs write files (logs,
# profiling DBs, etc.) that would otherwise trigger server restarts.
python -m uvicorn backend.main:app \
    --host 0.0.0.0 \
    --port "$PORT" \
    --reload \
    --reload-dir backend \
    --reload-dir waveform_editor
