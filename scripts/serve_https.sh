#!/usr/bin/env bash

set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if [ -f "$PROJECT_ROOT/.env" ]; then
  set -a
  . "$PROJECT_ROOT/.env"
  set +a
fi

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

exec uv run uvicorn app.main:app \
  --host "$APP_HOST" \
  --port "$APP_PORT" \
  --ssl-certfile "$CERT_PATH" \
  --ssl-keyfile "$KEY_PATH"
