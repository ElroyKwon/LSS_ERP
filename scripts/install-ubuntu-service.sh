#!/usr/bin/env bash
set -Eeuo pipefail

# Installs or updates the lss-erp systemd service on Ubuntu.
# Run from the repository root after backend/.env has been created.

APP_DIR="${APP_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
SERVICE_NAME="${SERVICE_NAME:-lss-erp}"
APP_USER="${APP_USER:-$(id -un)}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
UNIT_PATH="/etc/systemd/system/${SERVICE_NAME}.service"

fail() { printf '\n[ERROR] %s\n' "$*" >&2; exit 1; }

cd "$APP_DIR"

[[ -f "backend/.env" ]] || fail "backend/.env is missing. Create it before installing the service."
[[ -x "backend/venv/bin/uvicorn" ]] || fail "backend/venv/bin/uvicorn is missing. Run scripts/deploy-ubuntu.sh once first."

tmp_unit="$(mktemp)"
cat > "$tmp_unit" <<EOF
[Unit]
Description=LSS ERP FastAPI service
After=network.target

[Service]
Type=simple
User=${APP_USER}
WorkingDirectory=${APP_DIR}/backend
Environment=PYTHONUNBUFFERED=1
ExecStart=${APP_DIR}/backend/venv/bin/uvicorn app.main:app --host ${HOST} --port ${PORT}
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo install -m 0644 "$tmp_unit" "$UNIT_PATH"
rm -f "$tmp_unit"

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"
sudo systemctl --no-pager --full status "$SERVICE_NAME" || true

printf '\nInstalled %s at %s\n' "$SERVICE_NAME" "$UNIT_PATH"
printf 'Logs: sudo journalctl -u %s -f\n' "$SERVICE_NAME"
