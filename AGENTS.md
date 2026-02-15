# AGENTS.md — NLP Lab Website (PRD Detail v1 locked)

## 작업 로그 (요약)

### 완료된 커밋
- `80f2765 refactor(admin): improve readability with helper deduplication`  
  - admin 라우터 CSRF 검증 중복 제거, post hero 경로/파일명 헬퍼 중복 정리, post 입력 파싱 로직 통합(기능 변경 없음)
- `f2adad3 feat(admin): refresh admin interface for clarity`  
  - 관리자 레이아웃·사이드바·헤더·폼/리스트 액션 UX 개선, 대시보드 통계 카드 리디자인, 멤버/프로젝트/논문/게시글 페이지 동기화 정비
- `2c31cc9 feat(public): add hero image slider and content normalization`  
  - 홈 Hero 슬라이드 기능 적용, 슬라이드 경로 정규화, 공개 페이지 반응형 보정
- `8cd1736 fix(admin): stabilize hero image delete and rename flow`  
  - Hero 이미지 삭제/이름 변경/기본 이미지 보호 등 안정성 처리, 관련 테스트 추가
- `1655891 feat: allow admin editing of home hero image`  
  - 관리자 홈 배너 편집 기능 강화(초기 구성 정착)
- `ec9f7d9 feat: 공개 페이지 다국어 전환 복구`
- `7eb5be7 feat(favicon): add favicon.ico and link it in base template`  
  - favicon 및 public css 리팩토링(기본 반영)

### 최근 반영(미커밋)
- 현재 작업 트리 기준으로 `app/static/css/public.css`는 `public-page section` 간격 정리 패치가 이미 커밋되어 반영되어 있습니다.

### 다음 작업 시 참조 규칙(반드시 확인)
- 본 AGENTS 상단의 작업 로그를 먼저 확인한 뒤, 이전 `CSS 토큰/레이아웃 변경` 히스토리와 충돌 여부를 검토하고 진행할 것
- 공용 규칙 충돌 시(예: 색/레이아웃/컴포넌트) 2-line diff 우선 적용 원칙을 유지해 작은 변경 단위로 반영할 것
- 이전에 완료한 커밋 내역은 회귀 테스트 기준으로 함께 보존: `ruff / ty / pytest` 실패 시 즉시 중단 후 원인분리
- `.omx/` 디렉터리 및 OMX 런타임/상태 관련 산출물은 커밋하지 말 것

## 0) Highest priority: PRD is the source of truth
- This project MUST follow "PRD Detail v1 (Implementation Spec)" exactly.
- If a request conflicts with PRD, do NOT proceed silently. Raise the conflict and propose the minimum compliant alternative.
- Exception (approved on 2026-02-14): for public-facing UI design fidelity, the reference sites
  `/Users/chaejisung/Desktop/temp/nlp-lab-site` and `https://vmlab.khu.ac.kr/` take precedence over
  PRD design token/typography/layout constraints.
- This exception is design-only and public-page-only. Architecture, routes, DB models, auth/security,
  migrations, tests, and quality gates remain PRD-locked.

## 1) Core behavior principles (the 65-line guide adapted)
### 1. Think Before Coding
- Before editing, summarize goal/constraints (3–6 bullets).
- If any requirement is ambiguous, ask targeted questions first (do not assume).

### 2. Simplicity First
- Implement the smallest change that satisfies PRD + request.
- No extra features, abstractions, refactors, or dependencies unless explicitly requested.

### 3. Surgical Changes
- Touch the fewest files/lines possible.
- Avoid drive-by formatting/restructuring.

### 4. Goal-driven Execution
- Translate work into verifiable outcomes: routes render, CRUD works, tests pass, quality gates pass.

### 5) Breakable mode (운영중 X)
- For UI prototype work that can affect stability or UX immediately, apply breakable mode.
- Safety requirements for breakable work:
  - Keep all PRD-locked architecture, routes, auth, and schema changes untouched.
  - Preserve fallback paths so `/` and `/admin/posts` render even with malformed banner data.
  - Store slider input in existing `Post.content` with backward compatibility to single-URL mode.
- Validation requirements:
  - Document manual verification steps and record any known visual-only risks.

---

## 2) Architecture & stack are LOCKED
### 2.1 Architecture
- Server-rendered web: FastAPI + Jinja2
- ORM: SQLModel (backed by SQLAlchemy 2.x)
- Migrations: Alembic
- Auth: admin login via session cookie
- Static assets: served from `static/`

### 2.2 Versions (must respect ranges)
Runtime:
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

Dev tools:
- uv: latest stable pinned via lock
- ruff >=0.9,<1.0
- ty >=0.0.1,<0.1
- pytest >=8.3,<8.4

### 2.3 Dependency locking rule
- Use `uv lock` to create lock file.
- CI/local must use the same lock file.
- Minor upgrades are batched monthly (do not upgrade ad-hoc).

---

## 3) Directory structure is FIXED
- Must follow exactly the structure below (create missing files, do not reshuffle):
nlp-lab/
  app/
    main.py
    core/{config.py,security.py,constants.py}
    db/{session.py,init_db.py}
    models/{admin_user.py,member.py,project.py,publication.py,post.py,__init__.py}
    schemas/{auth.py,member.py,project.py,publication.py,post.py}
    repositories/{member_repo.py,project_repo.py,publication_repo.py,post_repo.py}
    services/{auth_service.py,member_service.py,project_service.py,publication_service.py,post_service.py}
    routers/{public.py,admin_auth.py,admin_member.py,admin_project.py,admin_publication.py,admin_post.py}
    templates/
      base.html
      public/{home.html,members.html,projects.html,project_detail.html,publications.html,contact.html}
      admin/{login.html,dashboard.html,members.html,projects.html,publications.html,posts.html}
    static/
      css/{reset.css,common.css,public.css,admin.css}
      js/{hero_slider.js,publications_filter.js,admin_forms.js}
      images/{logo.svg}
  alembic/versions/
  tests/{test_public_routes.py,test_admin_auth.py,test_admin_content_crud.py,test_member_crud.py}
  pyproject.toml
  uv.lock
  alembic.ini
  .env.example
  README.md

---

## 4) DB model rules are LOCKED
### 4.1 Common
- PK: `id: int`
- Timestamps: `created_at`, `updated_at` in UTC
- Strings must have explicit length constraints
- Deletion: hard delete in v1

### 4.2 Models (must match PRD)
- AdminUser: id, username(unique, 4~50), password_hash, created_at
- Member: id, name<=100, role enum(professor,researcher,phd,master,undergrad), email(unique), photo_url?, bio?, display_order default 100, created_at, updated_at
- Project: id, title<=200, slug(unique), summary<=300, description, status enum(ongoing,completed), start_date, end_date?, created_at, updated_at
- Publication: id, title<=300, authors, venue, year(index), link?, related_project_id?(FK project.id), created_at
- Post: id, title<=200, slug(unique), content, is_published default true, created_at, updated_at

### 4.3 Relationships
- Project(1) - Publication(N) via Publication.related_project_id only

### 4.4 Alembic operation rules
- Any model change MUST include a new migration file.
- Commands:
  1) `uv run alembic revision --autogenerate -m "message"`
  2) manually review/edit migration
  3) `uv run alembic upgrade head`
- `SQLModel.metadata.create_all()` is allowed only for early dev/test convenience (not production migration).

---

## 5) Routes & screens are LOCKED
### 5.1 Public pages (must exist)
- GET /                      (PUB-01)
- GET /members               (PUB-02)
- GET /projects              (PUB-03)
- GET /projects/{slug}       (PUB-04)
- GET /publications          (PUB-05)
- GET /contact               (PUB-06)

Home sorting rules:
- Projects: created_at desc
- Publications: year desc, then id desc
- Posts: created_at desc

Project detail:
- show publications where related_project_id matches the project.id

### 5.2 Admin pages (must exist)
- GET /admin/login
- POST /admin/login
- POST /admin/logout
- GET /admin                 (dashboard)
- GET /admin/members
- GET /admin/projects
- GET /admin/publications
- GET /admin/posts

### 5.3 Admin CRUD APIs (must exist, POST only as specified)
- POST /admin/members
- POST /admin/members/{id}/update
- POST /admin/members/{id}/delete
- POST /admin/projects
- POST /admin/projects/{id}/update
- POST /admin/projects/{id}/delete
- POST /admin/publications
- POST /admin/publications/{id}/update
- POST /admin/publications/{id}/delete
- POST /admin/posts
- POST /admin/posts/{id}/update
- POST /admin/posts/{id}/delete

---

## 6) Auth & security (must follow)
- Store only bcrypt hashes
- Session cookie options:
  - HttpOnly=true
  - SameSite=Lax
  - Secure=true in production
- Any /admin/* route requires auth; unauthenticated users are redirected to /admin/login
- CSRF: server-issued token 방식 적용 (v1)

---

## 7) Design constraints are LOCKED (default baseline)
### 7.1 Tokens
- Background: #f3f4f6
- Card: #ffffff
- Text: #2b2b2b
- Secondary text: #5b6470
- Accent: #0f4c81
- Danger: #b42318

### 7.2 Typography
- Pretendard (fallback: Noto Sans KR, sans-serif)
- Base 16px
- h1 32px bold lh 1.3 / h2 24px semibold / h3 20px semibold

### 7.3 Layout
- Max width 1120px
- Padding: desktop 24 / tablet 20 / mobile 16
- Card gap 16px, section gap 48px
- Admin: 2-column layout (sidebar 220px + fluid content)

---

## 8) Project operations (PR/quality gates are mandatory)
### 8.1 Branch naming
- feat/<scope>-<short-desc>
- fix/<scope>-<short-desc>
- chore/<scope>-<short-desc>

### 8.2 PR requirements (when writing PR descriptions)
- Purpose
- UI capture
- DB migration 여부
- Test results
Merge requires:
- ruff check pass
- ty check pass
- tests pass
- 1 approval

### 8.3 Standard dev commands (do not invent others)
- uv venv
- uv sync
- uv run uvicorn app.main:app --reload
- uv run ruff check .
- uv run ruff format .
- uv run ty check
- uv run pytest -q
- uv run alembic upgrade head
- uv run alembic revision --autogenerate -m "add_project_slug"

---

## 9) Definition of Done (release-ready)
- All PRD routes render successfully
- Admin CRUD works for Member/Project/Publication/Post
- Any model change includes Alembic migration
- uv/ruff/ty quality gates pass
- New dev can run locally with README only

<!-- OMX:RUNTIME:START -->
<session_context>
**Session:** omx-1771121259406-dts8ak | 2026-02-15T02:07:39.602Z

**Compaction Protocol:**
Before context compaction, preserve critical state:
1. Write progress checkpoint via state_write MCP tool
2. Save key decisions to notepad via notepad_write_working
3. If context is >80% full, proactively checkpoint state
</session_context>
<!-- OMX:RUNTIME:END -->
