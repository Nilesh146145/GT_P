#!/usr/bin/env bash
# Start the API on port 8001 from the backend directory.
# Requires: backend/.env with a working MONGODB_URL (local mongod or Atlas).
# Usage:  cd backend && bash scripts/dev_api.sh
# After the server is up:  bash scripts/check_api_health.sh

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -x .venv/bin/python ]]; then
  echo "Missing .venv — run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
  exit 1
fi

echo "Stopping anything on port 8001 (if any)..."
lsof -ti :8001 2>/dev/null | xargs kill -9 2>/dev/null || true

echo "Starting uvicorn — check log for 'Connected to MongoDB' (not 'degraded mode')."
exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
