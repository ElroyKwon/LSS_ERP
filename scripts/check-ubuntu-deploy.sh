#!/usr/bin/env bash
set -Eeuo pipefail

# Lightweight preflight check for Ubuntu deployment readiness.

APP_DIR="${APP_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
PORT="${PORT:-8000}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:${PORT}/}"

failures=0
check() {
  local label="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    printf '[OK]   %s\n' "$label"
  else
    printf '[FAIL] %s\n' "$label"
    failures=$((failures + 1))
  fi
}

cd "$APP_DIR"

check "git available" command -v git
check "python3 available" command -v python3
check "npm available" command -v npm
check "curl available" command -v curl
check "backend/.env exists" test -f backend/.env
check "backend requirements exists" test -f backend/requirements.txt
check "frontend package-lock exists" test -f frontend/package-lock.json
check "frontend dist exists" test -f frontend/dist/index.html

if [[ -x "backend/venv/bin/python" ]]; then
  check "backend imports" backend/venv/bin/python -c "from app.main import app; print(app.title)"
else
  printf '[WARN] backend/venv is missing. Run scripts/deploy-ubuntu.sh first.\n'
fi

if command -v curl >/dev/null 2>&1; then
  check "HTTP response ${HEALTH_URL}" curl -fsS --max-time 3 "$HEALTH_URL"
fi

if [[ "$failures" -gt 0 ]]; then
  printf '\nPreflight completed with %s failure(s).\n' "$failures"
  exit 1
fi

printf '\nPreflight completed successfully.\n'
