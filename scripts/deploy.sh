#!/usr/bin/env bash
#
# 운영 서버 배포 스크립트 — `uv run poe deploy` 한 줄로 실행합니다.
#
#   1. 코드 상태 확인
#   2. DB 백업 및 롤백 지점 기록
#   3. 코드 받기 및 라이브러리 설치
#   4. DB 스키마 갱신     alembic upgrade head (검토된 마이그레이션 적용)
#   5. 관리자 계정 확인   없을 때만 생성
#   6. HTTPS 인증서 확인  없거나 만료가 가까우면 발급/갱신
#   7. 서비스 재시작      systemd 유닛이 없으면 설치, 있으면 restart
#   8. 동작 확인          https://127.0.0.1:<APP_PORT>/ 응답 확인
#
# 어느 단계에서든 실패하면 즉시 멈추고, 되돌리는 방법을 안내합니다.
# DB는 2번에서 백업한 뒤에 변경합니다. 각 마이그레이션의 변경 내용은 별도 검토합니다.

set -euo pipefail

# bash 내장 명령만 사용 (dirname 없이) — PATH가 비정상인 환경에서도 자기 위치를 찾는다.
case "${BASH_SOURCE[0]}" in
  */*) SCRIPT_DIR="$(cd "${BASH_SOURCE[0]%/*}" && pwd)" ;;
  *) SCRIPT_DIR="$(pwd)" ;;
esac
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

. "$SCRIPT_DIR/load_env.sh"
load_dotenv "$PROJECT_ROOT/.env"

SERVICE_NAME="${NLP_LAB_SERVICE:-nlp-lab}"
SYSTEMD_UNIT_DIR="${SYSTEMD_UNIT_DIR:-/etc/systemd/system}"
SERVICE_UNIT_PATH="$SYSTEMD_UNIT_DIR/$SERVICE_NAME.service"
RENEWAL_HOOK_DIR="${RENEWAL_HOOK_DIR:-/etc/letsencrypt/renewal-hooks/deploy}"
RENEWAL_HOOK_PATH="$RENEWAL_HOOK_DIR/$SERVICE_NAME-restart.sh"
DEPLOY_STATE_DIR="$PROJECT_ROOT/.deploy"
APP_ENV="${APP_ENV:-development}"
APP_PORT="${APP_PORT:-8000}"
HEALTHCHECK_RETRIES="${HEALTHCHECK_RETRIES:-30}"
TOTAL_STEPS=8

step() {
  echo
  echo "[$1/$TOTAL_STEPS] $2"
}

fail() {
  echo
  echo "배포 실패: $1" >&2
  echo "되돌리려면:  uv run poe rollback" >&2
  exit 1
}

has_privilege_runner() {
  if [ "$(id -u)" -eq 0 ]; then
    return 0
  fi
  if command -v sudo >/dev/null 2>&1; then
    return 0
  fi
  return 1
}

run_privileged() {
  if [ "$(id -u)" -eq 0 ]; then
    "$@"
    return
  fi
  sudo -n "$@"
}

mkdir -p "$DEPLOY_STATE_DIR"
mkdir "$DEPLOY_STATE_DIR/lock" 2>/dev/null || fail "다른 배포 또는 롤백이 진행 중입니다."
trap 'rmdir "$DEPLOY_STATE_DIR/lock"' EXIT

# ---------------------------------------------------------------- 1. 확인
step 1 "배포 전 코드 상태 확인"
PREVIOUS_COMMIT=""
DEPLOY_BRANCH=""
if [ "${SKIP_GIT_PULL:-0}" != "1" ] && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  if ! git symbolic-ref -q HEAD >/dev/null 2>&1; then
    fail "브랜치가 아닌 상태(detached HEAD)입니다. 'git checkout main' 후 다시 실행하세요."
  fi
  if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
    fail "서버에서 직접 수정된 파일이 있어 업데이트할 수 없습니다. 'git status'로 확인 후 'git stash'로 치워두세요."
  fi
  PREVIOUS_COMMIT="$(git rev-parse HEAD)"
  DEPLOY_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
fi

# ---------------------------------------------------------------- 2. 백업
step 2 "DB 백업 및 롤백 지점 기록"
BACKUP_PATH="$(uv run python -m app.db.maintenance backup)" || fail "DB 백업에 실패했습니다. 코드는 변경하지 않았습니다."
if [ -n "$BACKUP_PATH" ]; then
  echo "백업 파일: $BACKUP_PATH"
else
  echo "백업할 SQLite 파일 없음 (다른 DB는 별도 백업 필요)"
fi
if [ -n "$PREVIOUS_COMMIT" ]; then
  # One atomic rename publishes the matching code/DB pair, before either changes.
  printf '%s\n' "$PREVIOUS_COMMIT" "$DEPLOY_BRANCH" "$BACKUP_PATH" > "$DEPLOY_STATE_DIR/rollback-state.tmp"
  mv "$DEPLOY_STATE_DIR/rollback-state.tmp" "$DEPLOY_STATE_DIR/rollback-state"
fi

# ---------------------------------------------------------------- 3. 코드/의존성
step 3 "코드 받기 및 라이브러리 설치"
if [ -n "$PREVIOUS_COMMIT" ]; then
  git pull --ff-only || fail "코드를 받아오지 못했습니다. 네트워크 또는 저장소 권한을 확인하세요."
  echo "현재 버전: $(git rev-parse --short HEAD)"
else
  echo "git 업데이트 건너뜀"
fi
uv sync --locked || fail "라이브러리 설치에 실패했습니다."

# ---------------------------------------------------------------- 4. 마이그레이션
step 4 "DB 스키마 갱신 (alembic upgrade head)"
LEGACY_REVISION="$(uv run python -m app.db.maintenance legacy-stamp-revision)" \
  || fail "DB 구조를 인식하지 못했습니다. 개발자에게 위 메시지를 전달하세요. DB는 백업본 그대로입니다."
if [ -n "$LEGACY_REVISION" ]; then
  echo "마이그레이션 이력이 없는 기존 DB → 현재 구조에 맞는 버전($LEGACY_REVISION)으로 표시"
  uv run alembic stamp "$LEGACY_REVISION" || fail "마이그레이션 이력 기록에 실패했습니다."
fi
uv run alembic upgrade head || fail "DB 스키마 갱신에 실패했습니다. 'uv run poe rollback'으로 백업본을 복원할 수 있습니다."

# ---------------------------------------------------------------- 5. 관리자
step 5 "관리자 계정 확인"
uv run poe init-admin || fail "관리자 계정 확인에 실패했습니다."
echo "관리자 계정 준비됨 (이미 있으면 그대로 둠)"

# ---------------------------------------------------------------- 6. HTTPS
step 6 "HTTPS 인증서 확인"
if [ "$APP_ENV" != "production" ]; then
  echo "APP_ENV=$APP_ENV → 개발 환경이라 건너뜀 (운영 서버는 .env에 APP_ENV=production)"
else
  bash "$SCRIPT_DIR/ensure_https_cert.sh" || fail "HTTPS 인증서 준비에 실패했습니다. 80/443 포트 개방과 DNS 설정을 확인하세요."
  if [ ! -f "$RENEWAL_HOOK_PATH" ] && has_privilege_runner; then
    echo "인증서 자동 갱신 후 서비스 재시작 훅 설치: $RENEWAL_HOOK_PATH"
    run_privileged mkdir -p "$RENEWAL_HOOK_DIR"
    printf '#!/usr/bin/env bash\nsystemctl restart %s.service\n' "$SERVICE_NAME" \
      | run_privileged tee "$RENEWAL_HOOK_PATH" >/dev/null
    run_privileged chmod 755 "$RENEWAL_HOOK_PATH"
  fi
fi

# ---------------------------------------------------------------- 7. 서비스
step 7 "서비스 재시작 ($SERVICE_NAME)"
if [ "$APP_ENV" != "production" ]; then
  echo "개발 환경이라 건너뜀 — 개발 서버는 'uv run poe serve'로 직접 실행"
  echo
  echo "완료 (개발 환경)."
  exit 0
fi

if ! command -v systemctl >/dev/null 2>&1; then
  fail "systemd가 없는 환경입니다. 서비스는 직접 재시작하세요: uv run poe serve-https"
fi
if ! has_privilege_runner; then
  fail "서비스 재시작에는 root 또는 비밀번호 없는 sudo가 필요합니다. README의 sudoers 설정을 확인하세요."
fi

if [ ! -f "$SERVICE_UNIT_PATH" ]; then
  echo "systemd 유닛이 없어 새로 설치: $SERVICE_UNIT_PATH"
  sed -e "s#__PROJECT_ROOT__#$PROJECT_ROOT#g" -e "s#__USER__#$(id -un)#g" \
    "$SCRIPT_DIR/nlp-lab.service.template" \
    | run_privileged tee "$SERVICE_UNIT_PATH" >/dev/null
  run_privileged systemctl daemon-reload
  run_privileged systemctl enable "$SERVICE_NAME.service"
fi
run_privileged systemctl restart "$SERVICE_NAME.service" || fail "서비스 재시작에 실패했습니다. 'sudo journalctl -u $SERVICE_NAME -n 50'으로 로그를 확인하세요."

# ---------------------------------------------------------------- 8. 확인
step 8 "동작 확인"
HEALTHCHECK_URL="${HEALTHCHECK_URL:-https://127.0.0.1:$APP_PORT/}"
attempt=0
while [ "$attempt" -lt "$HEALTHCHECK_RETRIES" ]; do
  attempt=$((attempt + 1))
  status_code="$(curl -k -s -o /dev/null -w '%{http_code}' --max-time 5 "$HEALTHCHECK_URL" || true)"
  if [ "$status_code" = "200" ]; then
    echo "$HEALTHCHECK_URL → $status_code OK"
    echo
    echo "배포 완료."
    exit 0
  fi
  sleep 1
done

fail "서비스가 응답하지 않습니다 ($HEALTHCHECK_URL, 마지막 응답: ${status_code:-없음}). 'sudo journalctl -u $SERVICE_NAME -n 50'으로 로그를 확인하세요."
