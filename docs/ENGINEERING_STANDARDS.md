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

## Type safety

Backend mypy (`backend/pyproject.toml`) and frontend `tsconfig.json` are both
configured at real strictness — `mypy app` and `npm run lint` are the actual
gate, not a formality. Do not weaken either config to make a change pass;
fix the change instead. Specifically:

- **No `any` / `Any` without a reason.** `@typescript-eslint/no-explicit-any`
  is a blocking ESLint error; Python's `Any` is allowed only at a genuine
  external boundary (unshaped JSON from an HTTP response, a third-party
  return value) — never propagated through a function signature you own. If
  a third-party package lacks types, check for `py.typed` first
  (`python -c "import pkg, os; print(os.path.dirname(pkg.__file__))"` then
  look for a `py.typed` marker) — most do, and the real types are almost
  always better than a hand-written guess. If it's genuinely untyped, wrap
  the exact methods you call in a local `Protocol`, not a blanket `Any`.
- **No unexplained casts.** A `cast()` / `as X` / non-null assertion (`!`) is
  allowed only with a one-line comment stating the invariant that makes it
  safe (e.g. "guarded by the length check above"). An assertion with no
  comment is a rejected review finding, not a style nit.
- **`# type: ignore` and `@ts-expect-error` need a specific code** —
  `# type: ignore[attr-defined]`, never a bare `# type: ignore` — and a
  reason. Backend mypy has `enable_error_code = ["ignore-without-code"]` to
  make a bare ignore a hard error.
- **Prefer a real fix over a suppression.** Before reaching for `Any`/cast/
  ignore, check whether the actual bug is a wrong model/type annotation
  (SQLAlchemy's own column-type class used where the Python value type
  belongs is a real recurring mistake — `Mapped[Optional[date]]`, not
  `Mapped[Optional[Date]]`), a variable reused for two unrelated types, or a
  missing null-guard. Strict mode's job is to surface exactly these; treating
  its complaint as a formality to silence defeats the point.
- **Don't paper over stale/dead state with a suppression.** An unused
  variable, import, or parameter is either dead (delete it) or a half-wired
  feature (leave a one-line comment saying what's missing, prefixed `_` to
  satisfy the linter) — never silence the warning without deciding which.

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
- documentation, ADRs, and `docs/CHANGELOG.md` reflect the result;
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

