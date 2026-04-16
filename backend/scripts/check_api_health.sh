#!/usr/bin/env bash
# Probe the running API and DB. Exit 0 only if /health reports status=ok and database=connected.
# Usage:  cd backend && bash scripts/check_api_health.sh
#         BASE_URL=http://127.0.0.1:9000 bash scripts/check_api_health.sh

set -euo pipefail
BASE_URL="${BASE_URL:-http://127.0.0.1:8001}"
url="${BASE_URL%/}/health"

body="$(curl -sS --connect-timeout 3 --max-time 10 -f "$url" 2>/dev/null)" || {
  echo "check_api_health: unreachable or HTTP error — $url" >&2
  exit 2
}

python3 -c '
import json, sys
try:
    d = json.loads(sys.stdin.read())
except json.JSONDecodeError as e:
    print("check_api_health: invalid JSON from /health:", e, file=sys.stderr)
    sys.exit(3)
status = d.get("status")
db = d.get("database")
ver = d.get("version", "?")
print(f"status={status!r} database={db!r} version={ver!r}")
ok = status == "ok" and db == "connected"
sys.exit(0 if ok else 1)
' <<<"$body"
