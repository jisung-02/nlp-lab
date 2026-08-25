#!/usr/bin/env bash

set -eu

# bash 내장 명령만 사용 (dirname 없이) — PATH가 비정상인 환경에서도 자기 위치를 찾는다.
case "${BASH_SOURCE[0]}" in
  */*) SCRIPT_DIR="$(cd "${BASH_SOURCE[0]%/*}" && pwd)" ;;
  *) SCRIPT_DIR="$(pwd)" ;;
esac
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

. "$SCRIPT_DIR/load_env.sh"
load_dotenv "$PROJECT_ROOT/.env"

require_env() {
  local name="$1"
  local value="${!name:-}"
  if [ -z "$value" ]; then
    echo "Missing required environment variable: $name" >&2
    exit 1
  fi
}

require_env "APP_DOMAIN"

APP_ENV="${APP_ENV:-development}"
APP_HOST="${APP_HOST:-0.0.0.0}"
APP_PORT="${APP_PORT:-443}"
LETSENCRYPT_LIVE_DIR="${LETSENCRYPT_LIVE_DIR:-/etc/letsencrypt/live}"
CERT_DIR="$LETSENCRYPT_LIVE_DIR/$APP_DOMAIN"
CERT_PATH="$CERT_DIR/fullchain.pem"
KEY_PATH="$CERT_DIR/privkey.pem"

if [ "$APP_ENV" != "production" ]; then
  echo "APP_ENV must be set to production for poe serve-https" >&2
  exit 1
fi

bash "$SCRIPT_DIR/ensure_https_cert.sh"

# Multiple worker processes let one slow request (e.g. an admin image
# upload being resized) run alongside public page loads. SQLite runs in
# WAL mode, so concurrent readers across workers are safe.
UVICORN_WORKERS="${UVICORN_WORKERS:-2}"

exec uv run uvicorn app.main:app \
  --host "$APP_HOST" \
  --port "$APP_PORT" \
  --workers "$UVICORN_WORKERS" \
  --ssl-certfile "$CERT_PATH" \
  --ssl-keyfile "$KEY_PATH"
