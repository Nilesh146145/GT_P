#!/usr/bin/env bash
# Always uses .venv so the reloader subprocess sees reportlab, openai, eval-type-backport, etc.
# (Running bare `uvicorn` may pick up ~/Library/Python/... and miss venv packages.)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
PY="$ROOT/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "Missing .venv. Run:"
  echo "  cd \"$ROOT\" && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi
exec "$PY" -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
