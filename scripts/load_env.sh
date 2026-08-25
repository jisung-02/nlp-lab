#!/usr/bin/env bash
#
# .env 로더 — 다른 스크립트에서 `. "$SCRIPT_DIR/load_env.sh"` 후 `load_dotenv "$PROJECT_ROOT/.env"`.
#
# `. .env`로 직접 실행하면 `CONTACT_ADDRESS=Seoul, Republic of Korea`처럼 따옴표 없이
# 공백이 들어간 값에서 "Republic: command not found"로 스크립트가 죽는다. 앱(pydantic-settings)은
# 그런 값을 정상적으로 읽으므로, 여기서도 실행하지 않고 KEY=VALUE로만 해석한다.
#
# 우선순위는 앱과 동일: 이미 환경변수로 설정된 값이 .env보다 우선한다.

load_dotenv() {
  local env_file="$1"
  local line key value

  [ -f "$env_file" ] || return 0

  while IFS= read -r line || [ -n "$line" ]; do
    line="${line%$'\r'}"
    case "$line" in
      "" | "#"*) continue ;;
    esac
    line="${line#export }"
    case "$line" in
      *=*) ;;
      *) continue ;;
    esac

    key="${line%%=*}"
    value="${line#*=}"
    case "$key" in
      "" | *[!A-Za-z0-9_]*) continue ;;
    esac

    if [ "${#value}" -ge 2 ]; then
      case "$value" in
        \"*\") value="${value#\"}"; value="${value%\"}" ;;
        \'*\') value="${value#\'}"; value="${value%\'}" ;;
      esac
    fi

    if [ -z "${!key+x}" ]; then
      export "$key=$value"
    fi
  done < "$env_file"
}
