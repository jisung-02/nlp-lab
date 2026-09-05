#!/usr/bin/env bash
#
# 직전 배포를 되돌립니다 — `uv run poe rollback`
#
#   1. 서비스 정지
#   2. 코드를 배포 직전 커밋으로 되돌림
#   3. DB를 배포 직전 백업본으로 복원 (복원 전 현재 DB도 backups/에 보관)
#   4. 라이브러리 재설치
#   5. 서비스 시작 및 동작 확인
#
# deploy.sh가 남긴 .deploy/rollback-state를 사용합니다.

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
DEPLOY_STATE_DIR="$PROJECT_ROOT/.deploy"
APP_ENV="${APP_ENV:-development}"
APP_PORT="${APP_PORT:-8000}"
HEALTHCHECK_RETRIES="${HEALTHCHECK_RETRIES:-30}"
TOTAL_STEPS=5

step() {
  echo
  echo "[$1/$TOTAL_STEPS] $2"
}

fail() {
  echo
  echo "롤백 실패: $1" >&2
  exit 1
}

run_privileged() {
  if [ "$(id -u)" -eq 0 ]; then
    "$@"
    return
  fi
  sudo -n "$@"
}

has_systemd() {
  [ "$APP_ENV" = "production" ] && command -v systemctl >/dev/null 2>&1
}

mkdir -p "$DEPLOY_STATE_DIR"
mkdir "$DEPLOY_STATE_DIR/lock" 2>/dev/null || fail "다른 배포 또는 롤백이 진행 중입니다."
trap 'rmdir "$DEPLOY_STATE_DIR/lock"' EXIT

DEPLOY_BRANCH="main"
LAST_BACKUP=""
if [ -f "$DEPLOY_STATE_DIR/rollback-state" ]; then
  {
    IFS= read -r PREVIOUS_COMMIT
    IFS= read -r DEPLOY_BRANCH
    IFS= read -r LAST_BACKUP
  } < "$DEPLOY_STATE_DIR/rollback-state"
else
  # Accept records left by earlier deployments.
  [ -f "$DEPLOY_STATE_DIR/previous_commit" ] || fail "되돌릴 배포 기록(previous_commit)이 없습니다."
  PREVIOUS_COMMIT="$(cat "$DEPLOY_STATE_DIR/previous_commit")"
  if [ -f "$DEPLOY_STATE_DIR/branch" ]; then DEPLOY_BRANCH="$(cat "$DEPLOY_STATE_DIR/branch")"; fi
  if [ -f "$DEPLOY_STATE_DIR/last_backup" ]; then LAST_BACKUP="$(cat "$DEPLOY_STATE_DIR/last_backup")"; fi
fi
[ -n "$PREVIOUS_COMMIT" ] && [ -n "$DEPLOY_BRANCH" ] || fail "롤백 기록이 올바르지 않습니다."
if [ -n "$LAST_BACKUP" ]; then
  [ -f "$LAST_BACKUP" ] || fail "백업 파일이 없습니다: $LAST_BACKUP"
fi

echo "되돌릴 커밋 : $PREVIOUS_COMMIT"
echo "복원할 DB   : ${LAST_BACKUP:-(백업 없음 — DB는 그대로 둠)}"

# ---------------------------------------------------------------- 1. 정지
step 1 "서비스 정지"
if has_systemd; then
  run_privileged systemctl stop "$SERVICE_NAME.service" || fail "서비스를 멈추지 못했습니다."
else
  echo "systemd 운영 환경이 아니라 건너뜀"
fi

# ---------------------------------------------------------------- 2. 코드
step 2 "코드 되돌리기 ($PREVIOUS_COMMIT)"
if [ "${SKIP_GIT_PULL:-0}" = "1" ]; then
  echo "SKIP_GIT_PULL=1 → 건너뜀"
else
  # 브랜치를 유지한 채 되돌려야 다음 'poe deploy'의 git pull이 정상 동작한다.
  git checkout --force "$DEPLOY_BRANCH" || fail "브랜치 $DEPLOY_BRANCH 로 전환하지 못했습니다."
  git reset --hard "$PREVIOUS_COMMIT" || fail "코드를 되돌리지 못했습니다."
  echo "현재 버전: $(git rev-parse --short HEAD)  ($(git log -1 --format=%s))"
  echo "다음 'uv run poe deploy' 때 다시 최신 코드로 올라갑니다."
fi

# ---------------------------------------------------------------- 3. DB
step 3 "DB 복원"
if [ -n "$LAST_BACKUP" ]; then
  [ -f "$LAST_BACKUP" ] || fail "백업 파일이 없습니다: $LAST_BACKUP"
  uv run python -m app.db.maintenance restore "$LAST_BACKUP" || fail "DB 복원에 실패했습니다."
else
  echo "복원할 백업이 없어 DB는 그대로 둠"
fi

# ---------------------------------------------------------------- 4. 의존성
step 4 "라이브러리 재설치 (uv sync)"
uv sync || fail "라이브러리 설치에 실패했습니다."

# ---------------------------------------------------------------- 5. 시작
step 5 "서비스 시작 및 동작 확인"
if ! has_systemd; then
  echo "systemd 운영 환경이 아니라 건너뜀"
  echo
  echo "롤백 완료 (개발 환경)."
  exit 0
fi

run_privileged systemctl start "$SERVICE_NAME.service" || fail "서비스 시작에 실패했습니다."
HEALTHCHECK_URL="${HEALTHCHECK_URL:-https://127.0.0.1:$APP_PORT/}"
attempt=0
while [ "$attempt" -lt "$HEALTHCHECK_RETRIES" ]; do
  attempt=$((attempt + 1))
  status_code="$(curl -k -s -o /dev/null -w '%{http_code}' --max-time 5 "$HEALTHCHECK_URL" || true)"
  if [ "$status_code" = "200" ]; then
    echo "$HEALTHCHECK_URL → $status_code OK"
    echo
    echo "롤백 완료."
    exit 0
  fi
  sleep 1
done

fail "서비스가 응답하지 않습니다 ($HEALTHCHECK_URL). 'sudo journalctl -u $SERVICE_NAME -n 50'으로 로그를 확인하세요."
