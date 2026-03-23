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

strip_quotes() {
  local value="$1"
  value="${value#\"}"
  value="${value%\"}"
  echo "$value"
}

is_ubuntu() {
  local os_release_file="${OS_RELEASE_FILE:-/etc/os-release}"
  local os_id=""
  local os_like=""

  if [ ! -r "$os_release_file" ]; then
    return 1
  fi

  while IFS='=' read -r key value; do
    case "$key" in
      ID)
        os_id="$(strip_quotes "$value")"
        ;;
      ID_LIKE)
        os_like="$(strip_quotes "$value")"
        ;;
    esac
  done < "$os_release_file"

  case " $os_id $os_like " in
    *" ubuntu "*)
      return 0
      ;;
  esac

  return 1
}

can_run_privileged() {
  if [ "$(id -u)" -eq 0 ]; then
    return 0
  fi

  if command -v sudo >/dev/null 2>&1 && sudo -n true >/dev/null 2>&1; then
    return 0
  fi

  return 1
}

run_privileged() {
  if [ "$(id -u)" -eq 0 ]; then
    "$@"
    return
  fi

  if command -v sudo >/dev/null 2>&1 && sudo -n true >/dev/null 2>&1; then
    sudo "$@"
    return
  fi

  echo "This action requires root or passwordless sudo: $*" >&2
  exit 1
}

resolve_certbot_bin() {
  if [ -n "${CERTBOT_BIN:-}" ]; then
    if command -v "$CERTBOT_BIN" >/dev/null 2>&1 || [ -x "$CERTBOT_BIN" ]; then
      echo "$CERTBOT_BIN"
      return
    fi
  fi

  if command -v certbot >/dev/null 2>&1; then
    command -v certbot
    return
  fi

  if [ -x "${LOCAL_CERTBOT_LINK:-/usr/local/bin/certbot}" ]; then
    echo "${LOCAL_CERTBOT_LINK:-/usr/local/bin/certbot}"
    return
  fi

  if [ -x "${SNAP_CERTBOT_BIN:-/snap/bin/certbot}" ]; then
    echo "${SNAP_CERTBOT_BIN:-/snap/bin/certbot}"
    return
  fi

  echo "certbot"
}

install_certbot_for_ubuntu() {
  local apt_get_bin="${APT_GET_BIN:-apt-get}"
  local mkdir_bin="${MKDIR_BIN:-mkdir}"
  local snap_bin="${SNAP_BIN:-snap}"
  local ln_bin="${LN_BIN:-ln}"
  local local_certbot_link="${LOCAL_CERTBOT_LINK:-/usr/local/bin/certbot}"
  local snap_certbot_bin="${SNAP_CERTBOT_BIN:-/snap/bin/certbot}"

  if ! can_run_privileged; then
    echo "Certbot is missing, but automatic Ubuntu installation requires root or passwordless sudo." >&2
    exit 1
  fi

  echo "Certbot not found; bootstrapping it for Ubuntu"

  if ! command -v "$snap_bin" >/dev/null 2>&1; then
    require_command "$apt_get_bin"
    run_privileged "$apt_get_bin" update
    run_privileged "$apt_get_bin" install -y snapd
  fi

  if command -v systemctl >/dev/null 2>&1; then
    run_privileged systemctl enable --now snapd.socket
  fi

  if [ ! -x "$snap_certbot_bin" ]; then
    run_privileged "$snap_bin" install --classic certbot
  fi

  if [ ! -x "$local_certbot_link" ]; then
    run_privileged "$mkdir_bin" -p "$(dirname "$local_certbot_link")"
    run_privileged "$ln_bin" -sf "$snap_certbot_bin" "$local_certbot_link"
  fi

  if [ ! -x "$local_certbot_link" ] && [ ! -x "$snap_certbot_bin" ]; then
    echo "Automatic Certbot installation finished, but no executable was found." >&2
    exit 1
  fi
}

ensure_certbot_available() {
  local candidate="$1"

  if command -v "$candidate" >/dev/null 2>&1 || [ -x "$candidate" ]; then
    return
  fi

  if is_ubuntu; then
    install_certbot_for_ubuntu
    return
  fi

  echo "Required command not found: $candidate" >&2
  exit 1
}

require_env "APP_DOMAIN"
require_env "TLS_ADMIN_EMAIL"

CERTBOT_BIN="$(resolve_certbot_bin)"
OPENSSL_BIN="${OPENSSL_BIN:-openssl}"
LETSENCRYPT_LIVE_DIR="${LETSENCRYPT_LIVE_DIR:-/etc/letsencrypt/live}"
CERT_DIR="$LETSENCRYPT_LIVE_DIR/$APP_DOMAIN"
CERT_PATH="$CERT_DIR/fullchain.pem"
KEY_PATH="$CERT_DIR/privkey.pem"
RENEWAL_WINDOW_SECONDS="${RENEWAL_WINDOW_SECONDS:-2592000}"

ensure_certbot_available "$CERTBOT_BIN"
CERTBOT_BIN="$(resolve_certbot_bin)"

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
