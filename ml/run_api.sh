#!/usr/bin/env bash
# Run the ML FastAPI server on port 8000 with correct PYTHONPATH so all routes
# (including POST /api/v1/forecast/binary) are registered.
# Usage: ./run_api.sh   or   ./run_api.sh 8000

set -e
cd "$(dirname "$0")"
PORT="${1:-8000}"
export PYTHONPATH=.
exec uvicorn api.main:app --reload --port "$PORT"
