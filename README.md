# NLP Lab Website

FastAPI + Jinja2 + SQLModel + Alembic 기반 NLP 연구실 웹사이트입니다.

## 1. Requirements

- Python 3.12.x
- `uv`

## 2. Local Setup

```bash
uv venv
uv sync
cp .env.example .env
```

`.env`에서 최소한 아래 값은 운영 환경에 맞게 변경하세요.

- `SECRET_KEY`
- `DATABASE_URL`
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`

## 3. DB Migration

```bash
uv run alembic upgrade head
```

## 4. 관리자 초기 계정 준비

1) `.env`에 관리자 계정을 설정합니다.

```env
ADMIN_USERNAME=admin
ADMIN_PASSWORD=change-me-now
```

2) 초기 관리자 계정을 1회 생성합니다.

```bash
uv run python -c "from app.db.init_db import create_initial_admin; create_initial_admin()"
```

이미 동일한 `ADMIN_USERNAME`이 존재하면 추가 생성되지 않습니다.

## 5. Run

```bash
uv run uvicorn app.main:app --reload
```

- Public: `/`, `/members`, `/projects`, `/projects/{slug}`, `/publications`, `/contact`
- Admin: `/admin/login`, `/admin`, `/admin/members`, `/admin/projects`, `/admin/publications`, `/admin/posts`

## 6. Quality Gates

```bash
uv run ruff check .
uv run ruff format .
uv run ty check
uv run pytest -q
```

## 7. Migration Workflow

```bash
uv run alembic revision --autogenerate -m "add_project_slug"
uv run alembic upgrade head
```

## 8. Release Smoke Checklist

1. `uv run alembic upgrade head`
2. Public 6개 화면 렌더링 확인
3. Admin 6개 화면 렌더링 및 로그인/로그아웃 확인
4. 관리자 CRUD(Member/Project/Publication/Post) 기본 동작 확인
5. `uv run ruff check .`, `uv run ty check`, `uv run pytest -q` 통과
