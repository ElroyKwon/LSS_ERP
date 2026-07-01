#!/usr/bin/env bash
set -Eeuo pipefail

APP_ROOT="${APP_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
ENV_FILE="${ENV_FILE:-${APP_ROOT}/deploy/.env}"
ENV_EXAMPLE="${APP_ROOT}/deploy/.env.example"
COMPOSE_FILE="${APP_ROOT}/docker-compose.yml"
PROJECT_NAME="${COMPOSE_PROJECT_NAME:-lss-erp}"

log() { printf '\n[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }
fail() { printf '\n[ERROR] %s\n' "$*" >&2; exit 1; }

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "Required command not found: $1"
}

compose() {
  docker compose --env-file "$ENV_FILE" -p "$PROJECT_NAME" -f "$COMPOSE_FILE" "$@"
}

env_value() {
  local key="$1"
  local default="${2:-}"
  local line
  line="$(grep -m1 "^${key}=" "$ENV_FILE" 2>/dev/null || true)"
  if [[ -n "$line" ]]; then
    printf '%s' "${line#*=}"
  else
    printf '%s' "$default"
  fi
}

rand_secret() {
  openssl rand -base64 36 | tr -d '\n'
}

create_env_if_missing() {
  if [[ -f "$ENV_FILE" ]]; then
    return
  fi
  require_cmd openssl
  mkdir -p "$(dirname "$ENV_FILE")"
  local pg_password secret_key admin_password
  pg_password="$(rand_secret)"
  secret_key="$(openssl rand -hex 48)"
  admin_password="$(rand_secret)"
  umask 077
  cat > "$ENV_FILE" <<EOF
COMPOSE_PROJECT_NAME=${PROJECT_NAME}
APP_HOST_BIND=0.0.0.0
APP_PORT=8000
DB_DATA_DIR=/data/lss-erp/postgres
UPLOAD_DATA_DIR=/data/lss-erp/uploads

POSTGRES_DB=lss_erp
POSTGRES_USER=lss_erp
POSTGRES_PASSWORD=${pg_password}

ENVIRONMENT=production
SECRET_KEY=${secret_key}
API_DOCS_ENABLED=false
AUTO_CREATE_SCHEMA=false
ALLOWED_ORIGINS=https://erp.sauter.co.kr
ALLOWED_HOSTS=erp.sauter.co.kr,localhost,127.0.0.1

NTS_BUSINESS_STATUS_SERVICE_KEY=
POSTAL_SERVICE_KEY=

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=
SMTP_FROM_NAME=LSS ERP
SMTP_ADMIN_EMAILS=

LSS_ERP_ADMIN_USERNAME=admin
LSS_ERP_ADMIN_PASSWORD=${admin_password}
LSS_ERP_ADMIN_NAME=System Admin
LSS_ERP_ADMIN_EMAIL=
LSS_ERP_ADMIN_EMPLOYEE_CODE=
LSS_ERP_ADMIN_ROLE=system_admin
EOF
  log "Created ${ENV_FILE}"
  log "Initial admin account: admin / ${admin_password}"
  log "Store this password securely. Change deploy/.env before rerun if you want a different initial password."
}

cd "$APP_ROOT"

require_cmd docker
require_cmd curl
docker compose version >/dev/null 2>&1 || fail "Docker Compose plugin is required."
[[ -f "$COMPOSE_FILE" ]] || fail "Missing ${COMPOSE_FILE}"
[[ -f "$ENV_EXAMPLE" ]] || fail "Missing ${ENV_EXAMPLE}"

create_env_if_missing

PROJECT_NAME="$(env_value COMPOSE_PROJECT_NAME "$PROJECT_NAME")"
db_data_dir="$(env_value DB_DATA_DIR "/data/lss-erp/postgres")"
upload_data_dir="$(env_value UPLOAD_DATA_DIR "/data/lss-erp/uploads")"
postgres_user="$(env_value POSTGRES_USER "lss_erp")"
postgres_db="$(env_value POSTGRES_DB "lss_erp")"
app_host="$(env_value APP_HOST_BIND "0.0.0.0")"
app_port="$(env_value APP_PORT "8000")"

mkdir -p "$db_data_dir" "$upload_data_dir"

log "Building application image"
compose build app

log "Starting PostgreSQL"
compose up -d db

log "Waiting for PostgreSQL"
for _ in $(seq 1 60); do
  if compose exec -T db pg_isready -U "$postgres_user" -d "$postgres_db" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
compose exec -T db pg_isready -U "$postgres_user" -d "$postgres_db" >/dev/null

log "Applying Alembic migrations"
compose run --rm app alembic upgrade head

log "Ensuring initial admin account"
compose run --rm app python -m app.scripts.create_admin

log "Starting application"
compose up -d app

health_host="$app_host"
if [[ "$health_host" == "0.0.0.0" ]]; then
  health_host="127.0.0.1"
fi
health_url="http://${health_host}:${app_port}/"
log "Checking application response: ${health_url}"
for _ in $(seq 1 60); do
  if curl -fsS --max-time 3 "$health_url" >/dev/null 2>&1; then
    log "LSS ERP Docker deployment completed successfully."
    log "Service URL: ${health_url}"
    exit 0
  fi
  sleep 2
done

compose ps
fail "Application did not respond at ${health_url}. Check logs with: docker compose --env-file ${ENV_FILE} -p ${PROJECT_NAME} -f ${COMPOSE_FILE} logs -f app"
