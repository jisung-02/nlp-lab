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

---

## 4) 환경 변수

주요 값(`.env`):
- `APP_ENV` = `development|test|production`
- `APP_DEBUG`
- `SECRET_KEY`
- `DATABASE_URL`
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`
- `ADMIN_SESSION_MAX_AGE_SECONDS`
- `CONTACT_EMAIL`
- `CONTACT_ADDRESS`
- `CONTACT_MAP_URL` (현재 템플릿 커스텀 지도 URL 사용으로 보조값)

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

모델 변경 시 추가:
```bash
uv run alembic revision --autogenerate -m "message"
uv run alembic upgrade head
```

---

## 9) 저장소 위생

커밋 금지:
- `.omx/`
- `.venv/`, 캐시, 로컬 DB, 임시 로그

현재 `.gitignore`에 `.omx/`가 포함되어 있습니다.
