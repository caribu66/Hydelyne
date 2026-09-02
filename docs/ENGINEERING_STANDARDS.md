# Engineering standards

## Change design

Every change begins with explicit acceptance criteria and identifies affected
contracts, data, security, observability, deployment, and rollback. Prefer a
small vertical slice over a layer-wide rewrite. Refactors that do not change
behavior should be separate from feature changes.

Use an ADR when changing architecture or system ownership. An ADR records the
context, decision, alternatives, consequences, migration, and rollback; it is
not a long implementation diary.

## Code quality

- Choose names from the product glossary and existing domain vocabulary.
- Functions do one job and make side effects visible.
- Public functions and cross-layer structures are typed.
- Prefer composition and plain functions over speculative abstraction.
- Do not generalize until at least two real use cases demonstrate the shared
  behavior.
- Keep transport DTOs, domain objects, persistence models, and search documents
  distinct. Map between them deliberately.
- Comments explain constraints and reasons, not syntax.
- Delete dead paths after a safe migration; do not maintain two permanent ways
  to perform one use case.

Large-file warning thresholds are 400 lines for an application module and 300
lines for a UI component. Crossing a threshold is not an automatic rewrite,
but additions require the author to consider extracting a cohesive unit and to
explain why the file remains coherent.

## API and compatibility

- Validate length, shape, range, enum membership, and ownership at boundaries.
- Use stable machine-readable error codes and safe user messages.
- Paginate collection endpoints and enforce server-side maximums.
- Avoid breaking GraphQL field, REST route, task payload, and persisted enum
  changes. Use deprecation and staged rollout when consumers may lag.
- Generate or validate frontend GraphQL types from the backend schema as the
  contract matures; do not maintain silently divergent handwritten shapes.

## Persistence and migrations

- PostgreSQL is the production reference. SQLite tests are useful but cannot
  prove PostgreSQL constraints, locking, JSON, migrations, or query behavior.
- One use case owns its transaction. Commit only after invariants hold.
- Add database constraints for invariants that must survive every code path.
- Use expand/migrate/contract for destructive or incompatible schema changes.
- Backfills are restartable, measurable, and safe under partial completion.
- Test migration heads and upgrade behavior in CI.

## Security and privacy

- Deny access by default; define operation-level roles and resource ownership.
- Use proven password hashing settings and provide an upgrade path as security
  guidance evolves.
- Treat sessions, webhook verification, rate limiting, and revocation as
  explicit security controls with documented dependency-failure behavior.
- Apply least privilege to databases, providers, containers, and CI tokens.
- Never use real customer documents or credentials in tests.
- Minimize stored and logged personal data. Define retention and deletion for
  documents, audit records, backups, and search projections.
- Threat-model authentication, uploads, webhooks, exports, document access,
  LLM prompt/data boundaries, and administrative mutations.

## Reliability and observability

- All network calls have finite timeouts and bounded retries with backoff.
- Retry only operations that are safe or protected by idempotency.
- Log structured events with request/task correlation IDs and safe identifiers.
- Record metrics for request errors/latency, queue age/failures, extraction
  outcomes, indexing drift, provider failures, and database saturation.
- Liveness answers whether the process should restart. Readiness answers
  whether it can serve. Detailed dependency health is access-controlled.
- Degraded operation must be intentional and visible, not an empty `except`.

## Testing strategy

Tests form a pyramid:

1. Pure unit tests for domain rules, mapping, parsing, and UI utilities.
2. Service tests for use cases and failure behavior with controlled adapters.
3. PostgreSQL/Redis/provider-contract integration tests for real semantics.
4. API contract tests for GraphQL and REST authentication, authorization,
   validation, and compatibility.
5. A small Playwright suite for critical authenticated workflows and visual
   accessibility/responsiveness.

Tests must be isolated and deterministic. They do not depend on a developer's
`.env`, live Dropbox, local Redis, local models, test order, or an existing
database file. Every test and network operation has a finite timeout.

## Required quality gates

Backend target:

```bash
cd backend
python -m ruff format --check app tests
python -m ruff check app tests
python -m mypy app
python -m pytest tests -q
alembic heads
```

Frontend target:

```bash
cd frontend
npm ci
npm run lint
npm run test
npm run build
npm run ui:audit:strict
npm run test:e2e:ci
```

Repository target:

```bash
git diff --check
```

CI must run these without `|| true`, fallback installs, implicit live services,
or skipped failures. Vulnerability and secret scanning are blocking according
to an explicitly documented exception policy, not silently ignored.

## Definition of done

A change is done only when:

- acceptance criteria are met;
- behavior, failure, authorization, and boundary cases are tested;
- migrations and compatibility are handled;
- logs/metrics make important failures diagnosable without exposing private
  data;
- relevant quality gates pass;
- documentation and ADRs reflect the result;
- the complete diff contains no unexplained or unrelated changes;
- deployment and rollback are understood; and
- a human reviewer approves high-risk business, security, migration, and LLM
  behavior.

## Review checklist

Reviewers verify correctness first, then boundaries and maintainability:

- Is the requirement implemented, including negative cases?
- Is the code in the owning module and correct layer?
- Are authorization and data ownership explicit?
- Are transactions, retries, idempotency, and partial failures safe?
- Are private data and secrets protected?
- Are public/persisted contracts compatible?
- Do tests prove behavior rather than implementation details?
- Can operations detect, diagnose, and roll back failure?
- Did the change introduce duplication, a new source of truth, or unnecessary
  infrastructure?

