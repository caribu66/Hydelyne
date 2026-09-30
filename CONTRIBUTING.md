# Contributing to Manifest

Manifest is an internal product repository. Changes should be small, typed,
tested, and consistent with the documented architecture and authorization
model.

## Before opening a change

1. Read `AGENTS.md`, `docs/CHANGELOG.md`, `docs/ARCHITECTURE.md`, and
   `docs/ENGINEERING_STANDARDS.md`.
2. Check `git status` and preserve unrelated work.
3. Identify API, persistence, authorization, migration, and deployment impact.
4. Add or update regression tests for behavioral changes.

## Local checks

Backend, from `backend/`:

```bash
python -m ruff format --check app tests
python -m ruff check app tests
python -m mypy app
python -m pytest tests -q
python -m alembic heads
```

Frontend, from `frontend/`:

```bash
npm ci
npm run lint
npm run test
npm run build
npm run ui:audit:strict
npm run test:e2e:ci
npm audit --audit-level=moderate
```

The CI workflow is the source of truth for required checks. Do not weaken a
check, hide a failure, or add a dependency without documenting the reason.

## Change rules

- Keep GraphQL, REST, and Celery transport code thin; business rules belong in
  application services or the domain layer.
- Add an Alembic migration for database schema changes, including downgrade
  behavior where safe.
- Treat API fields, persisted values, task payloads, events, and search
  documents as compatibility-sensitive contracts.
- Enforce authorization at the backend boundary and add negative tests for
  denied access.
- Never commit credentials, uploaded documents, local databases, generated
  builds, or model files.
- Update `docs/CHANGELOG.md` for committed code, infrastructure, migration, or
  running-data changes.

## Pull requests

Use a focused title and describe the behavior, risk, compatibility impact,
checks run, and any follow-up. Keep formatting-only work separate from
behavior changes where practical.
