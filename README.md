# NLP Lab Website

FastAPI + Jinja2 + SQLModel 기반의 연구실 소개/관리 웹사이트입니다.

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
- passlib[bcrypt] `>=1.7.4,<1.8`
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

가상환경(`source .venv/bin/activate`)이 이미 활성화된 경우에는 `uv run`을 생략하고
`poe <task>` 형태로 바로 실행해도 됩니다.

```bash
poe serve
poe check
```

### 3.6 운영용 HTTPS 실행
`poe serve-https`는 Linux + systemd 운영 환경에서 단일 도메인용 HTTPS 서버를 직접 띄우는 경로입니다.

필수 `.env` 값:

```bash
APP_ENV=production
APP_HOST=0.0.0.0
APP_PORT=443
APP_DOMAIN=lab.example.ac.kr
TLS_ADMIN_EMAIL=admin@example.com
SECRET_KEY=change-me
```

실행:

```bash
uv run poe serve-https
```

동작 방식:
- 먼저 `scripts/ensure_https_cert.sh`가 Let’s Encrypt 인증서를 확인합니다.
- 인증서가 없거나 갱신 시점에 가까우면 `certbot certonly --standalone --keep-until-expiring`를 실행합니다.
- 유효한 인증서가 있으면 재발급 없이 바로 `uvicorn` HTTPS 서버를 올립니다.
- 이 경로는 `APP_ENV=production`이 아니면 실패합니다.

운영 전제:
- DNS `A` 레코드: `APP_DOMAIN -> 서버 공인 IP`
- 방화벽: `80/tcp`, `443/tcp` 허용
- Let’s Encrypt HTTP-01 검증을 위해 `80/tcp`가 외부에서 접근 가능해야 함
- `certbot`은 서버에 사전 설치되어 있어야 함
- 인증서는 `/etc/letsencrypt/live/<APP_DOMAIN>/` 아래에 저장되며 repo에 포함하지 않음
- `APP_ENV=production`일 때 admin 세션 쿠키는 `Secure`로 설정됨

주요 task:

| Task | 설명 | 명령 |
| --- | --- | --- |
| `serve` | 개발 서버 실행 | `uv run poe serve` |
| `serve-https` | 운영용 HTTPS 서버 실행 | `uv run poe serve-https` |
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
- `CONTACT_MAP_URL` (현재 템플릿 커스텀 지도 URL 사용으로 보조값)

## 4.1 systemd 운영 예시
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
- `Member`: role enum, email unique, display_order
- `Project`: slug unique, status enum, start/end date
- `Publication`: year index, optional related_project_id
- `Post`: slug unique, is_published, content

관계:
- `Project 1 - N Publication` (`Publication.related_project_id`)

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
