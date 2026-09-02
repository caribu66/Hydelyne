# Backend engineering rules

These rules extend the root `AGENTS.md` for `backend/`.

## Intended boundaries

- `app/api/`: REST transport, request validation, authorization, response
  mapping. No durable business rules.
- `app/graphql/`: GraphQL schema, DTOs, mapping, validation, and resolvers.
  Resolvers should delegate to services.
- `app/domain/`: framework-independent vocabulary and business rules. It must
  not import from `api`, `auth`, `graphql`, `models`, `services`, or `tasks`.
- `app/services/`: application use cases and infrastructure adapters. New code
  should receive sessions/clients through explicit parameters where practical
  instead of creating hidden global connections.
- `app/models/`: SQLAlchemy persistence models only. Models are not API DTOs.
- `app/tasks/`: thin Celery entry points. Tasks must be idempotent, retry-safe,
  observable, and delegate actual work to services.
- `tests/`: unit, integration, contract, and security regression tests.

Current files do not fully satisfy these boundaries. Treat direct database
access in resolvers, singleton clients, the synchronous extraction engine, and
large service modules as legacy exceptions to reduce deliberately—not patterns
to reproduce.

## Backend rules

- Target Python 3.11. Use explicit types for public functions and meaningful
  domain types instead of unstructured dictionaries when crossing layers.
- Use async SQLAlchemy for request and service paths. Do not introduce another
  engine or session factory. The synchronous engine in `sync_processor.py` is
  a documented legacy exception.
- Make transaction ownership explicit. The application service performing a
  use case owns commit/rollback; helpers must not unexpectedly commit a
  caller-owned transaction.
- Avoid module-level mutable clients and settings in new code when they make
  tests or configuration reloads unreliable. Prefer injected dependencies or
  narrow factories.
- Set finite connect/read/write/pool timeouts for every network client. Define
  whether each dependency fails open or closed and test that behavior.
- External writes are not atomic with PostgreSQL. For important PostgreSQL +
  queue/search/Dropbox workflows, use idempotency and a recorded retry/outbox
  strategy; do not rely on best-effort calls after commit without recovery.
- Celery tasks accept stable identifiers, not ORM instances or secrets. A task
  may run more than once and must handle duplicate delivery safely.
- LLM output is untrusted input. Validate it against a typed schema, constrain
  values, retain provenance, and provide deterministic fallback behavior.
- Search indexes and vector stores are projections. PostgreSQL remains the
  system of record unless an ADR explicitly changes ownership.
- Any access to CVs, documents, medical status, identity data, or contact data
  requires authorization and an auditable access path.
- Do not expose raw exception text or provider responses to clients.
- Add migrations in one linear Alembic chain. Test upgrade from the previous
  revision and, where safe, downgrade. Destructive migrations require a staged
  expand/migrate/contract plan and backup/rollback notes.

## Verification

The target backend gate is:

```bash
cd backend
python -m ruff format --check app tests
python -m ruff check app tests
python -m mypy app
python -m pytest tests -q
alembic heads
git diff --check
```

Security-sensitive changes also run focused tests for authentication,
authorization, rate limiting, file validation, path traversal, and secret
handling. Database behavior that differs between SQLite and PostgreSQL requires
a PostgreSQL integration test.

The audit records gaps between this target and the current environment/CI. Do
not hide those gaps by changing this contract to match weaker behavior.

