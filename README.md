# NLP Lab Website

FastAPI + Jinja2 + SQLModel + Alembic 기반의 NLP Lab 웹사이트 프로젝트입니다.

## Requirements
- Python 3.12
- uv

## Quick Start
```bash
uv venv
uv sync
uv run uvicorn app.main:app --reload
```

## Quality Gates
```bash
uv run ruff check .
uv run ty check
uv run pytest -q
```

## Migration
```bash
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "add_project_slug"
```
