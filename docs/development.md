# 개발 환경과 명령어

이 문서는 NLP Lab 웹사이트를 로컬에서 실행하고 유지보수할 때 필요한 명령과 설정을 정리한다. 프로젝트 소개와 주요 기능은 [README](../README.md), 운영 서버 절차는 [운영 가이드](operations.md), 전체 운영 기준은 [AGENTS.md](../AGENTS.md)를 참고한다.

## 로컬 시작

Python 3.12와 `uv`를 준비한 뒤 저장소 루트에서 실행한다.

```bash
uv venv
uv sync
cp -n .env.example .env
uv run poe serve
```

`cp -n`은 이미 있는 `.env`를 덮어쓰지 않는다. 처음 생성된 `.env`에서는 개발용 기본값을 사용하므로, 관리자 계정과 연락처를 로컬 환경에 맞게 확인한다. `poe serve`는 실행 전에 DB 백업, 최신 마이그레이션, 초기 관리자 확인을 수행한 뒤 Uvicorn 개발 서버를 실행한다.

브라우저에서 <http://127.0.0.1:8000>을 열고, 관리자 화면은 `/admin/login`에서 확인한다. `uv run uvicorn app.main:app --reload`로 직접 실행할 수도 있다.

`poe serve`와 직접 실행하는 로컬 Uvicorn 명령은 Uvicorn 기본값인 `127.0.0.1:8000`을 사용한다. 이 경로에서는 `.env`의 `APP_HOST`와 `APP_PORT`가 서버 바인딩을 바꾸지 않는다. `APP_HOST`와 `APP_PORT`를 실제로 읽어 HTTPS 서버를 띄우는 경로는 운영용 `uv run poe serve-https`이며, `APP_ENV=production`, `APP_DOMAIN`, 인증서와 운영 권한이 필요하다.

## 자주 쓰는 작업

| 작업 | 명령 |
| --- | --- |
| 개발 서버 | `uv run poe serve` |
| DB 백업 | `uv run poe backup-db` |
| 최신 마이그레이션 적용 | `uv run poe migrate` |
| 새 마이그레이션 생성 | `MSG="변경 내용" uv run poe migration` |
| 관리자 계정 확인/생성 | `uv run poe init-admin` |
| 린트 | `uv run poe lint` |
| 포맷 | `uv run poe format` |
| 타입 검사 | `uv run poe typecheck` |
| 테스트 | `uv run poe test` |
| 전체 품질 검사 | `uv run poe check` |
| 운영 배포 | `uv run poe deploy` |
| 직전 배포 복구 | `uv run poe rollback` |

모델이나 스키마를 바꾸면 `uv run poe migration`으로 마이그레이션을 만들고 내용을 검토한 뒤 `uv run poe migrate`로 적용한다. 배포 전 기본 게이트는 `uv run poe check`이다.

## 환경 변수

`.env.example`을 기준으로 `.env`를 작성한다. 비밀값은 저장소에 커밋하지 않는다.

| 변수 | 의미 |
| --- | --- |
| `APP_ENV` | `development`, `test`, `production` 중 실행 환경. 운영에서는 `production`을 사용한다. |
| `APP_DEBUG` | FastAPI 디버그 모드. 로컬에서만 필요할 때 켠다. |
| `APP_HOST` | `serve-https`가 바인딩할 주소. 로컬 `poe serve`의 Uvicorn 기본 바인딩에는 적용되지 않는다. |
| `APP_PORT` | `serve-https`가 사용할 HTTPS 포트. 로컬 `poe serve`는 `8000`을 사용한다. |
| `APP_DOMAIN` | 운영 도메인과 Let’s Encrypt 인증서 경로에 사용한다. |
| `SECRET_KEY` | 세션 서명 키. 운영에서는 32자 이상의 무작위 값이 필수다. |
| `DATABASE_URL` | SQLModel/SQLAlchemy 연결 URL. 기본값은 `sqlite:///./nlp_lab.db`다. |
| `TLS_ADMIN_EMAIL` | 운영 HTTPS 인증서 발급·갱신 연락처다. |
| `ADMIN_USERNAME` | 초기 관리자 사용자명이다. |
| `ADMIN_PASSWORD` | 초기 관리자 비밀번호다. 운영에서는 기본값을 반드시 바꾼다. |
| `ADMIN_SESSION_MAX_AGE_SECONDS` | 관리자 세션의 최대 수명(초)이다. 기본값은 8시간이다. |
| `CONTACT_EMAIL` | 공개 Contact 페이지에 표시할 이메일이다. |
| `CONTACT_ADDRESS` | 공개 Contact 페이지에 표시할 주소다. |
| `GOOGLE_SITE_VERIFICATION` | Google Search Console 검증 토큰이다. |
| `NAVER_SITE_VERIFICATION` | 네이버 서치어드바이저 검증 토큰이다. |

운영 업데이트는 `uv run poe deploy`, 장애 시 복구는 `uv run poe rollback`을 사용한다. 운영 배포는 DB 백업, 코드 동기화, 마이그레이션, HTTPS 인증서 확인, systemd 재시작과 상태 확인을 순서대로 수행한다. 명령의 전제와 실패 시 대응은 [운영 가이드](operations.md)에서 확인한다.

## 저장소 위생과 문서

`.venv/`, `.uv-cache/`, `nlp_lab.db`, 업로드 이미지, 임시 로그와 `.deploy/` 산출물은 커밋하지 않는다. 모델 변경은 마이그레이션과 함께 검토한다. 성능 측정 결과와 한계는 [성능 측정](performance.md)에 기록한다.

구조와 보안 경계는 [구조와 유지보수 기준](architecture.md), 변경 기준과 유지보수 규칙은 [AGENTS.md](../AGENTS.md)를 참고한다. 라우트나 데이터 모델을 바꾸기 전에는 관련 테스트를 함께 확인하고, 변경 후에는 `uv run poe check`를 실행한다.
