---
name: nlp-lab-ui-maintainer
description: Apply UI/UX updates for the NLP Lab public/admin templates and CSS while preserving routes, auth/security, schema, and CRUD behavior. Use for layout, typography, spacing, and component styling work.
---

# NLP Lab UI Maintainer Skill

1) Limit changes to templates/static assets unless explicitly asked.
2) Do not alter routes, auth flow, DB schema, or CSRF/session logic for UI-only tasks.
3) Keep public/admin visual consistency with current main theme.
4) Preserve resilience paths:
- `/` should render with hero fallback data
- `/admin/posts` should render with malformed/partial hero data
5) Contact page rules (current state):
- Left: localized contact text (KR/EN split)
- Right: map embed
- Map center coordinate: `37.2397565,127.0832974`
- Map language by page language (`hl=ko|en`)
6) Run checks after UI edits:
```bash
uv run ruff check .
uv run pytest -q
```
7) Document manual UI verification points (desktop/tablet/mobile, KR/EN).
