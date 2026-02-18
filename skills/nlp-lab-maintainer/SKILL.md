---
name: nlp-lab-maintainer
description: Maintain the NLP Lab FastAPI SSR codebase safely. Use this for feature maintenance, bug fixes, route/model/security changes, migrations, tests, and release-quality verification in this repository.
---

# NLP Lab Maintainer Skill

1) Read `AGENTS.md` and `README.md` before editing.
2) Keep these invariants:
- FastAPI + Jinja2 SSR architecture
- SQLModel + Alembic migration flow
- Fixed public/admin routes and admin POST CRUD paths
- CSRF required on admin POST
- Session cookie guard on `/admin*`
- Model constraints (unique/length/enum/timestamps)
3) Implement the smallest possible diff.
4) If model changes, always create and apply Alembic migration.
5) Run quality gates:
```bash
uv run ruff check .
uv run ty check
uv run pytest -q
```
6) Never commit runtime artifacts (`.omx/`, caches, local DB).
7) Summarize exactly what changed and which invariants were preserved.
