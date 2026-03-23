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

require_command() {
  local command_name="$1"
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Required command not found: $command_name" >&2
    exit 1
  fi
}

require_env "APP_DOMAIN"
require_env "TLS_ADMIN_EMAIL"

CERTBOT_BIN="${CERTBOT_BIN:-certbot}"
OPENSSL_BIN="${OPENSSL_BIN:-openssl}"
LETSENCRYPT_LIVE_DIR="${LETSENCRYPT_LIVE_DIR:-/etc/letsencrypt/live}"
CERT_DIR="$LETSENCRYPT_LIVE_DIR/$APP_DOMAIN"
CERT_PATH="$CERT_DIR/fullchain.pem"
KEY_PATH="$CERT_DIR/privkey.pem"
RENEWAL_WINDOW_SECONDS="${RENEWAL_WINDOW_SECONDS:-2592000}"

require_command "$CERTBOT_BIN"

if [ -f "$CERT_PATH" ] && [ -f "$KEY_PATH" ] && command -v "$OPENSSL_BIN" >/dev/null 2>&1; then
  if "$OPENSSL_BIN" x509 -checkend "$RENEWAL_WINDOW_SECONDS" -noout -in "$CERT_PATH" >/dev/null 2>&1
  then
    echo "Using existing TLS certificate for $APP_DOMAIN"
    exit 0
  fi
fi

echo "Issuing or renewing TLS certificate for $APP_DOMAIN"
"$CERTBOT_BIN" certonly \
  --standalone \
  --non-interactive \
  --agree-tos \
  --keep-until-expiring \
  -m "$TLS_ADMIN_EMAIL" \
  -d "$APP_DOMAIN"

if [ ! -f "$CERT_PATH" ] || [ ! -f "$KEY_PATH" ]; then
  echo "Certificate issuance completed but files were not found at $CERT_DIR" >&2
  exit 1
fi

echo "TLS certificate is ready for $APP_DOMAIN"
