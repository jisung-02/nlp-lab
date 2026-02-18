# AGENTS.md — NLP Lab Website (Current Maintenance Spec)

Last updated: 2026-02-18

이 문서는 기존 PRD(1~6번 문서)의 핵심 제약을 **현재 코드 상태 기준으로 통합**한 유지보수 기준입니다.
이 저장소에서는 본 문서와 README를 단일 기준으로 사용합니다.

---

## 1) 목적
- Codex/개발자가 동일한 기준으로 빠르게 유지보수하도록 돕는다.
- UI 변경이 많아도 아키텍처/보안/데이터 무결성은 고정한다.
- 변경은 항상 “최소 수정 + 회귀 방지”를 우선한다.

---

## 2) 절대 고정 규칙 (PRD 통합)

### 2.1 아키텍처/스택
- Server-rendered web: FastAPI + Jinja2
- ORM: SQLModel (SQLAlchemy 2.x)
- Migration: Alembic
- Auth: 세션 쿠키 기반 admin 로그인
- 정적 자산: `app/static`

필수 버전 범위:
- Python >=3.12,<3.13
- FastAPI >=0.115,<0.116
- Uvicorn >=0.34,<0.35
- Jinja2 >=3.1,<3.2
- SQLModel >=0.0.22,<0.1
- SQLAlchemy >=2.0.37,<2.1
- Alembic >=1.14,<1.15
- passlib[bcrypt] >=1.7.4,<1.8
- python-multipart >=0.0.20,<0.1
- pydantic-settings >=2.7,<2.8
- ruff >=0.9,<1.0 / ty >=0.0.1,<0.1 / pytest >=8.3,<8.4

### 2.2 고정 라우트
Public:
- `GET /`
- `GET /members`
- `GET /projects`
- `GET /projects/{slug}`
- `GET /publications`
- `GET /contact`

Admin page:
- `GET /admin/login`
- `POST /admin/login`
- `POST /admin/logout`
- `GET /admin`
- `GET /admin/members`
- `GET /admin/projects`
- `GET /admin/publications`
- `GET /admin/posts`

Admin CRUD (POST only):
- Members: `/admin/members`, `/admin/members/{id}/update`, `/admin/members/{id}/delete`
- Projects: `/admin/projects`, `/admin/projects/{id}/update`, `/admin/projects/{id}/delete`
- Publications: `/admin/publications`, `/admin/publications/{id}/update`, `/admin/publications/{id}/delete`
- Posts: `/admin/posts`, `/admin/posts/{id}/update`, `/admin/posts/{id}/delete`

### 2.3 고정 정렬/조회 규칙
- Home projects: `created_at desc`
- Home publications: `year desc, id desc`
- Home posts: `created_at desc` (hero system post 제외)
- Project detail: `Publication.related_project_id == project.id`

### 2.4 데이터 모델 불변 조건
- 공통: `id(int PK)`, UTC timestamp, 문자열 길이 제한, hard delete
- `AdminUser`: username unique(4~50), password_hash
- `Member`: role enum, email unique, display_order default 100
- `Project`: slug unique, status enum, start/end date
- `Publication`: year index, optional related_project_id(FK)
- `Post`: slug unique, content, is_published default true
- 관계: Project(1)-Publication(N) only

### 2.5 보안 규칙
- 비밀번호는 bcrypt 해시만 저장
- `/admin*` 인증 필수(미인증 시 `/admin/login` 리다이렉트)
- CSRF 토큰 검증(모든 admin POST)
- 세션 쿠키: HttpOnly + SameSite=Lax + production에서 Secure

### 2.6 마이그레이션 규칙
- 모델 변경 시 Alembic 마이그레이션 필수
- 순서:
  1) `uv run alembic revision --autogenerate -m "message"`
  2) 수동 검토
  3) `uv run alembic upgrade head`

---

## 3) 현재 UI 상태 (2026-02-18)
- Public 페이지: 메인 톤(Work Sans/Fraunces, muted gradient) 기반
- Admin 페이지: 메인 톤과 시각적으로 정렬된 편집형 테마
- Home hero: 다중 이미지 슬라이더 + admin/posts에서 파일 업로드/이름변경/삭제
- Contact: 좌측 정보 + 우측 지도, KR/EN 텍스트 분리
  - 지도 임베드: 언어별 `hl` 분기
  - 지도 중심 좌표: `37.2397565,127.0832974`

디자인 예외:
- Public 디자인 fidelity는 레퍼런스 기반 조정 허용
- 단, 아키텍처/보안/라우트/DB는 본 문서 고정 규칙 우선

---

## 4) 작업 원칙
1. 먼저 AGENTS/README를 읽고 범위를 확정한다.
2. 요구사항 충족 최소 수정만 한다(불필요한 리팩토링 금지).
3. 기능 변경 없는 스타일 수정이라도 회귀 테스트를 실행한다.
4. 모델/스키마 변경은 migration 없는 커밋 금지.
5. 실패 시 한 번에 크게 고치지 말고 원인 분리 후 단계적으로 수정.

---

## 5) 표준 명령
- `uv venv`
- `uv sync`
- `uv run uvicorn app.main:app --reload`
- `uv run ruff check .`
- `uv run ruff format .`
- `uv run ty check`
- `uv run pytest -q`
- `uv run alembic upgrade head`
- `uv run alembic revision --autogenerate -m "message"`

권장 게이트:
1) `uv run ruff check .`
2) `uv run ty check`
3) `uv run pytest -q`

---

## 6) Codex 유지보수 스킬 (스택 매칭 + 안전 기준)

### 6.1 스킬 소스/검증 기준
- 검색 범위:
  - 저장소 로컬: `skills/`
  - 시스템 기본: `~/.codex/skills/.system/*`
  - 공식 큐레이션: `openai/skills` (`skills/.curated/*`)
- 채택 기준:
  1) 현재 스택(FastAPI SSR + 보안 + UI 검증)에 직접 도움이 될 것
  2) 출처가 명확할 것(공식 curated 또는 저장소 내부 커스텀)
  3) 불필요한 외부 배포/비밀키 연동이 없는 보수적 스킬 우선

### 6.2 현재 사용 스킬
- 로컬 커스텀
  - `skills/nlp-lab-maintainer/SKILL.md`
  - `skills/nlp-lab-ui-maintainer/SKILL.md`
- 공식 curated(가져온 스킬, source: `openai/skills`)
  - `skills/security-best-practices/SKILL.md`
  - `skills/security-threat-model/SKILL.md`
  - `skills/playwright/SKILL.md`
  - `skills/screenshot/SKILL.md`

### 6.3 스택 기준 권장 매핑
- 기능/구조/DB/라우트 작업: `nlp-lab-maintainer`
- UI/템플릿/CSS 작업: `nlp-lab-ui-maintainer`
- FastAPI 보안 점검/하드닝: `security-best-practices`
- 릴리즈 전 위협 모델링: `security-threat-model`
- 브라우저 플로우 회귀 점검: `playwright` (+ 필요 시 `screenshot`)

### 6.4 안전 운영 규칙
- 기본은 `openai/skills` curated만 사용한다.
- 실험(`.experimental`) 또는 제3자 저장소 스킬은 **명시적 승인 없이는 도입 금지**.
- 스킬 추가 시 라이선스 파일 포함 여부를 확인하고 함께 버전 관리한다.
- 스킬 스크립트 실행 전 반드시 내용 검토 후 사용한다(프로젝트 비밀정보/운영환경 보호).

---

## 7) 커밋/리포지토리 위생
- 커밋 전 반드시 quality gate 3종 통과
- `.omx/` 산출물, 로컬 DB/캐시, 임시 로그는 커밋 금지
- 작은 단위 커밋 권장 (`feat/...`, `fix/...`, `chore/...`)
