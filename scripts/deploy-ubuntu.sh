#!/usr/bin/env bash
set -Eeuo pipefail

# LSS ERP Ubuntu deployment helper.
# Run from the repository root on the Ubuntu server.

APP_DIR="${APP_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
BRANCH="${BRANCH:-main}"
SERVICE_NAME="${SERVICE_NAME:-lss-erp}"
PORT="${PORT:-8000}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:${PORT}/}"
SKIP_PULL="${SKIP_PULL:-0}"
SKIP_MIGRATIONS="${SKIP_MIGRATIONS:-0}"
SKIP_SERVICE_RESTART="${SKIP_SERVICE_RESTART:-0}"
ALLOW_DIRTY="${ALLOW_DIRTY:-0}"

log() { printf '\n[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }
fail() { printf '\n[ERROR] %s\n' "$*" >&2; exit 1; }

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "Required command not found: $1"
}

cd "$APP_DIR"

require_cmd git
require_cmd python3
require_cmd npm
require_cmd curl

if [[ ! -f "backend/.env" ]]; then
  fail "backend/.env is missing. Create it from backend/.env.example and set production values first."
fi

if [[ "$ALLOW_DIRTY" != "1" ]] && [[ -n "$(git status --porcelain)" ]]; then
  fail "Working tree has uncommitted changes. Commit/stash them or run with ALLOW_DIRTY=1."
fi

if [[ "$SKIP_PULL" != "1" ]]; then
  log "Updating source from origin/${BRANCH}"
  git fetch origin "$BRANCH"
  git checkout "$BRANCH"
  git pull --ff-only origin "$BRANCH"
fi

log "Preparing Python virtual environment"
if [[ ! -d "backend/venv" ]]; then
  python3 -m venv backend/venv
fi
source backend/venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt

if [[ "$SKIP_MIGRATIONS" != "1" ]]; then
  log "Applying database migrations"
  (cd backend && ../backend/venv/bin/alembic upgrade head)
else
  log "Skipping database migrations"
fi

log "Installing frontend dependencies"
if [[ -f "frontend/package-lock.json" ]]; then
  (cd frontend && npm ci)
else
  (cd frontend && npm install)
fi

log "Building frontend"
(cd frontend && npm run build)
[[ -f "frontend/dist/index.html" ]] || fail "frontend/dist/index.html was not created."

if [[ "$SKIP_SERVICE_RESTART" != "1" ]]; then
  log "Restarting systemd service: ${SERVICE_NAME}"
  sudo systemctl restart "$SERVICE_NAME"
  sudo systemctl --no-pager --full status "$SERVICE_NAME" || true
else
  log "Skipping service restart"
fi

log "Checking HTTP response: ${HEALTH_URL}"
for i in {1..30}; do
  if curl -fsS --max-time 3 "$HEALTH_URL" >/dev/null; then
    log "Deployment completed successfully"
    exit 0
  fi
  sleep 2
done

fail "Service did not respond at ${HEALTH_URL}. Check: sudo journalctl -u ${SERVICE_NAME} -n 100 --no-pager"
