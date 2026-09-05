# NLP Lab Website

FastAPI + Jinja2 + SQLModel 기반의 연구실 소개/관리 웹사이트입니다.

웹 개발 지식이 없어도 일상적인 유지보수를 할 수 있도록 구성을 최소화하고 운영 명령을 통합했습니다. 코드 변경이나 DB 스키마 변경은 개발자 검토가 필요합니다.

> 기준 시점: 2026-02-18  
> 운영 기준 문서: `AGENTS.md` (이전 PRD 문서 통합본)

---

## 1) 현재 상태 요약

### Public
- `/` 홈: Hero 이미지 슬라이더(관리자 편집 가능)
- `/members`: 멤버 카드 목록
- `/projects`: 상태 필터 + 프로젝트 카드 목록
- `/projects/{slug}`: 프로젝트 상세 + 연관 논문
- `/publications`: 연도 필터
- `/contact`: KR/EN 분기 + 좌측 연락처/우측 지도 레이아웃

### Admin
- `/admin/login` 로그인
- `/admin` 대시보드(멤버/프로젝트/논문/게시글 통계)
- `/admin/members|projects|publications|posts` CRUD
- 모든 admin POST는 CSRF 검증

### UI
- Public/Admin 모두 현재 메인 톤에 맞춘 스타일로 정렬됨
- Contact 지도는 언어별(`hl=ko|en`) 임베드 사용
- Contact 지도 중심 좌표: `37.2397565,127.0832974`

---

## 2) 기술 스택

- Python `>=3.12,<3.13`
- FastAPI `>=0.115,<0.116`
- Jinja2 `>=3.1,<3.2`
- SQLModel `>=0.0.22,<0.1`
- SQLAlchemy `>=2.0.37,<2.1`
- Alembic `>=1.14,<1.15`
- bcrypt `>=5,<6`
- pydantic-settings `>=2.7,<2.8`
- Dev: uv, ruff, ty, pytest

---

## 3) 빠른 시작

### 3.1 설치
```bash
uv venv
uv sync
cp .env.example .env
```

### 3.2 DB 마이그레이션
```bash
uv run alembic upgrade head
```

### 3.3 관리자 계정 초기화(최초 1회)
```bash
uv run python -c "from app.db.init_db import create_initial_admin; create_initial_admin()"
```

### 3.4 실행
```bash
uv run uvicorn app.main:app --reload
```

### 3.5 Poe task로 실행(권장)
이 프로젝트는 `poethepoet` 기반 task를 제공합니다.

```bash
uv run poe serve
```

`serve`는 개발 서버를 시작하기 전에 DB 백업, 최신 마이그레이션 적용,
초기 관리자 확인을 순서대로 실행합니다.

가상환경(`source .venv/bin/activate`)이 이미 활성화된 경우에는 `uv run`을 생략하고
`poe <task>` 형태로 바로 실행해도 됩니다.

```bash
poe serve
poe check
```

### 3.6 운영 서버 배포 — 명령 하나로

운영 서버에서 기억할 명령은 두 개입니다.

```bash
uv run poe deploy     # 평소 업데이트: 상태 확인 → DB 백업 → 코드 받기/설치 → 스키마 갱신 → HTTPS 인증서 → 재시작 → 확인
uv run poe rollback   # 문제 생겼을 때: 직전 커밋 + 직전 DB 백업으로 되돌리기
```

`deploy`가 하는 일(순서대로, 하나라도 실패하면 즉시 멈추고 안내 출력):

| 단계 | 내용 | DB 안전장치 |
| --- | --- | --- |
| 1 | 배포 전 브랜치와 working tree 상태 확인 | 서버에서 직접 고친 파일이 있으면 멈춤 |
| 2 | **pull 전에** DB 백업 후 `.deploy/rollback-state`를 원자적으로 기록 | **코드/DB 롤백 지점을 함께 저장** |
| 3 | `git pull --ff-only` 후 `uv sync --locked` | |
| 4 | `alembic upgrade head` | 현재 포함된 마이그레이션은 테이블·컬럼·인덱스를 추가함. 향후 마이그레이션에는 삭제 작업도 들어갈 수 있으므로 적용 전 검토 필요. Alembic 이력이 없는 옛 DB는 구조를 보고 자동으로 버전을 표시한 뒤 진행, 인식 못 하면 멈춤 |
| 5 | 관리자 계정 확인 | 이미 있으면 그대로 둠 |
| 6 | `scripts/ensure_https_cert.sh` — 인증서 없거나 만료 30일 이내면 발급/갱신, 갱신 후 재시작 훅 설치 | |
| 7 | systemd 유닛(`nlp-lab.service`) 없으면 설치·enable, 있으면 restart | |
| 8 | `https://127.0.0.1:<APP_PORT>/` 가 200을 줄 때까지 최대 30회 확인 (각 요청 최대 5초, 확인 사이 1초 대기) | |

기존 서버에 처음 적용할 때(1회):

```bash
cd /srv/nlp-lab
uv run poe deploy
```

`deploy`가 working tree 확인, **pull 전에** DB 백업과 `.deploy/rollback-state` 기록, `git pull --ff-only`, `uv sync --locked`를 이 순서로 처리합니다. 수동으로 준비해야 한다면 먼저 clean state를 확인하고 DB 백업과 롤백 상태를 기록한 뒤 pull 하세요.

전제:
- `.env`에 `APP_ENV=production`, `APP_DOMAIN`, `TLS_ADMIN_EMAIL`, `SECRET_KEY`가 있어야 함 (6·7단계는 `APP_ENV=production`일 때만 실행)
- 서비스 재시작과 systemd/갱신 훅 관리는 root이거나 비밀번호 없는 sudo가 필요. 일반 계정이면 `/etc/sudoers.d/nlp-lab`에 아래처럼 제한된 규칙을 둘 수 있습니다:
  `nlplab ALL=(root) NOPASSWD: /usr/bin/systemctl, /usr/bin/tee, /usr/bin/mkdir, /usr/bin/chmod`
- certbot 최초 설치와 인증서 bootstrap은 이 제한 규칙의 대상이 아니며, 별도 root 또는 관리자 권한으로 준비해야 합니다.
- 로컬 DB(`nlp_lab.db`)와 업로드 이미지(`app/static/images/hero/*`, `members/`)는 git이 관리하지 않음. 단, 기본 이미지 `app/static/images/hero/hero.jpg`는 저장소에 추적되는 예외이며, `git pull`로 다른 업로드 이미지를 덮어쓰지 않음
- 백업만 따로 하려면 `uv run poe backup-db`

`poe serve-https`는 Linux + systemd 운영 환경에서 단일 도메인용 HTTPS 서버를 직접 띄우는 경로이며, `deploy`가 설치하는 systemd 유닛이 이 명령을 실행합니다.

운영 요약: 개발 중에는 `serve`, 업데이트는 `deploy`, 배포 직후 문제가 생기면 `rollback`을 사용합니다. 코드 변경이나 DB 스키마 변경이 필요하면 현재 상태와 오류 로그를 보존해 개발자에게 전달하고, 운영자가 임의로 수정하지 않습니다.

필수 `.env` 값:

```bash
APP_ENV=production
APP_DEBUG=false
APP_HOST=0.0.0.0
APP_PORT=443
APP_DOMAIN=lab.example.ac.kr
TLS_ADMIN_EMAIL=admin@example.com
SECRET_KEY=replace-with-a-random-secret-at-least-32-characters-long
ADMIN_PASSWORD=replace-with-a-unique-production-password
```

운영 환경에서는 `SECRET_KEY`를 32자 이상으로 설정하고 기본값을 사용하지 마세요. 다음처럼 생성할 수 있습니다.

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

`ADMIN_PASSWORD`도 반드시 고유한 운영용 비밀번호로 바꾸고, `APP_DEBUG=false`를 권장합니다.

`uv run poe deploy`와 `uv run poe serve`는 관리자 세션 저장소를 포함한 최신 마이그레이션을 자동 적용합니다. `uv run poe serve-https` 또는 Uvicorn을 직접 실행할 때는 먼저 `uv run alembic upgrade head`를 실행하세요. 새 세션 방식에서는 기존 관리자 쿠키가 무효화되므로 관리자가 한 번 다시 로그인해야 합니다.

실행:

```bash
uv run poe serve-https
```

동작 방식:
- 먼저 `scripts/ensure_https_cert.sh`가 Let’s Encrypt 인증서를 확인합니다.
- 인증서가 없거나 갱신 시점에 가까우면 `certbot certonly --standalone --keep-until-expiring`를 실행합니다.
- 유효한 인증서가 있으면 재발급 없이 바로 `uvicorn` HTTPS 서버를 올립니다.
- Ubuntu에서 `certbot`이 없으면 `snapd`, `certbot` snap, `/usr/local/bin/certbot` 링크를 자동 bootstrap 합니다.
- 이 경로는 `APP_ENV=production`이 아니면 실패합니다.

운영 전제:
- DNS `A` 레코드: `APP_DOMAIN -> 서버 공인 IP`
- 방화벽: `80/tcp`, `443/tcp` 허용
- Let’s Encrypt HTTP-01 검증을 위해 `80/tcp`가 외부에서 접근 가능해야 함
- Ubuntu에서는 `certbot`이 없으면 자동 bootstrap 되지만, 그 외 환경은 사전 설치가 필요함
- 인증서는 `/etc/letsencrypt/live/<APP_DOMAIN>/` 아래에 저장되며 repo에 포함하지 않음
- `APP_ENV=production`일 때 admin 세션 쿠키는 `Secure`로 설정됨
- Ubuntu 자동 설치는 root 또는 passwordless `sudo`가 가능할 때만 동작함. README의 제한된 sudo 규칙은 systemd 유닛/갱신 훅 관리에만 해당하며, certbot 최초 설치·인증서 bootstrap은 별도로 root 또는 관리자 권한이 필요함

주요 task:

| Task | 설명 | 명령 |
| --- | --- | --- |
| `serve` | DB 준비 후 개발 서버 실행 | `uv run poe serve` |
| `serve-https` | 운영용 HTTPS 서버 실행 | `uv run poe serve-https` |
| `deploy` | 운영 서버 업데이트 (백업→마이그레이션→인증서→재시작→확인) | `uv run poe deploy` |
| `rollback` | 직전 배포로 되돌리기 | `uv run poe rollback` |
| `backup-db` | DB 백업만 수행 | `uv run poe backup-db` |
| `migrate` | 최신 마이그레이션 적용 | `uv run poe migrate` |
| `migration` | 새 migration 생성 | `MSG="메시지" uv run poe migration` |
| `init-admin` | 초기 관리자 생성 | `uv run poe init-admin` |
| `lint` | Ruff lint | `uv run poe lint` |
| `format` | Ruff format | `uv run poe format` |
| `typecheck` | Ty 타입 검사 | `uv run poe typecheck` |
| `test` | 테스트 실행 | `uv run poe test` |
| `check` | lint + typecheck + test | `uv run poe check` |

---

## 4) 환경 변수

주요 값(`.env`):
- `APP_ENV` = `development|test|production`
- `APP_DEBUG`
- `APP_HOST`
- `APP_PORT`
- `APP_DOMAIN`
- `SECRET_KEY`
- `DATABASE_URL`
- `TLS_ADMIN_EMAIL`
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`
- `ADMIN_SESSION_MAX_AGE_SECONDS`
- `CONTACT_EMAIL`
- `CONTACT_ADDRESS`
- `GOOGLE_SITE_VERIFICATION` (Google Search Console HTML 태그 인증 토큰)
- `NAVER_SITE_VERIFICATION` (네이버 서치어드바이저 HTML 태그 인증 토큰)

## 4.1 systemd 운영 예시
`uv run poe deploy`가 유닛이 없으면 `scripts/nlp-lab.service.template`로 자동 설치합니다. 수동으로 만들 때의 참고용:

`/etc/systemd/system/nlp-lab.service`

```ini
[Unit]
Description=NLP Lab HTTPS service
After=network.target

[Service]
Type=simple
User=nlplab
WorkingDirectory=/srv/nlp-lab
EnvironmentFile=/srv/nlp-lab/.env
AmbientCapabilities=CAP_NET_BIND_SERVICE
ExecStart=/usr/bin/env bash -lc 'cd /srv/nlp-lab && uv run poe serve-https'
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

인증서 갱신 후 재시작 훅:
- 경로: `/etc/letsencrypt/renewal-hooks/deploy/nlp-lab-restart.sh`
- 예시 내용:

```bash
#!/usr/bin/env bash
systemctl restart nlp-lab.service
```

자동갱신 점검:

```bash
sudo certbot renew --dry-run
```

---

## 5) 라우트

### Public
- `GET /`
- `GET /members`
- `GET /projects`
- `GET /projects/{slug}`
- `GET /publications`
- `GET /contact`
- `GET|HEAD /robots.txt`, `/llms.txt`, `/sitemap.xml`, `/favicon.ico`
- `GET|HEAD /googlef810f48826f17ab4.html` (Google Search Console 검증)

### Admin Page
- `GET /admin/login`
- `POST /admin/login`
- `POST /admin/logout`
- `GET /admin`
- `GET /admin/members`
- `GET /admin/projects`
- `GET /admin/publications`
- `GET /admin/posts`

### Admin CRUD (POST)
- `/admin/members`, `/admin/members/{id}/update`, `/admin/members/{id}/delete`
- `/admin/projects`, `/admin/projects/{id}/update`, `/admin/projects/{id}/delete`
- `/admin/publications`, `/admin/publications/{id}/update`, `/admin/publications/{id}/delete`
- `/admin/posts`, `/admin/posts/{id}/update`, `/admin/posts/{id}/delete`

---

## 6) 데이터 모델(요약)

- `AdminUser`: username(unique), password_hash
- `AdminSession`: token_hash(PK), admin_user_id(FK), expires_at, credential_hash. `AdminUser 1 - N AdminSession` 관계로 DB 세션을 만료/폐기함
- `Member`: role enum, email unique, display_order
- `Project`: slug unique, status enum, start/end date
- `Publication`: year index, optional related_project_id
- `Post`: slug unique, is_published, content

관계:
- `Project 1 - N Publication` (`Publication.related_project_id`)
- `AdminUser 1 - N AdminSession` (`AdminSession.admin_user_id`)

관리자 로그아웃은 해당 세션을 DB에서 폐기하고, 비밀번호가 바뀌면 credential hash 불일치로 기존 세션을 사용할 수 없습니다.

주의:
- 모델 변경 시 Alembic migration 반드시 포함

---

## 7) 유지보수 (Codex 기준)

### 문서 우선순위
1. `AGENTS.md`
2. `README.md`

### 저장소 내 Codex skills
- `skills/nlp-lab-maintainer/SKILL.md`
- `skills/nlp-lab-ui-maintainer/SKILL.md`
- `skills/security-best-practices/SKILL.md` (OpenAI curated)
- `skills/security-threat-model/SKILL.md` (OpenAI curated)
- `skills/playwright/SKILL.md` (OpenAI curated)
- `skills/screenshot/SKILL.md` (OpenAI curated)

### 권장 사용
- 기능/라우트/보안/DB 변경: `nlp-lab-maintainer`
- 스타일/UI 조정: `nlp-lab-ui-maintainer`
- FastAPI 보안 모범사례 점검: `security-best-practices`
- 릴리즈 전 AppSec 위협 모델링: `security-threat-model`
- UI 흐름 자동 점검: `playwright` (`screenshot`은 캡처 fallback)

### 스킬 도입 정책
- 기본 도입원: `openai/skills`의 `skills/.curated/*`
- 실험/외부 저장소 스킬은 명시적 승인 시에만 추가
- 스킬은 저장소 `skills/`에 벤더링하여 재현 가능하게 유지

---

## 8) 품질 게이트

커밋 전 필수:
```bash
uv run ruff check .
uv run ty check
uv run pytest -q
```

동일 작업(Poe task):
```bash
uv run poe check
```

모델 변경 시 추가:
```bash
uv run alembic revision --autogenerate -m "message"
uv run alembic upgrade head
```

---

## 9) 저장소 위생

커밋 금지:
- `.venv/`, 캐시, 로컬 DB, 임시 로그
