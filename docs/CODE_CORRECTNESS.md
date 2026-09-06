# 20-point correctness checklist

Use this as a pre-flight checklist before requesting review or merging a change.
Each item maps to a concrete gate that can be run locally.

## 1. Type checker passes with zero errors

Run the strict type checker for every layer you touched:

```bash
cd backend && python -m mypy app
cd frontend && npx tsc --noEmit
```

No `Any`, `any`, uncommented `cast()`, bare `# type: ignore`, or `!`
assertions may remain.

## 2. Linter and formatter are clean

```bash
cd backend && python -m ruff check app tests && python -m ruff format --check app tests
cd frontend && npm run lint
```

Fix every warning; do not add inline disable comments without a code and reason.

## 3. Tests exist and pass

Unit, service, integration, and contract tests for the changed behavior:

```bash
cd backend && python -m pytest tests -q
cd frontend && npm run test
```

Regression tests are required for bug fixes.

## 4. No dead code or unused imports

Undelete dead paths during the same change as the migration that makes them
obsolete. An unused import or variable is either deleted or marked with a
leading underscore and a one-line TODO comment; it is never silently suppressed.

## 5. Every cast and assertion is explained

A `cast()`, `as X`, or `!` is allowed only when a one-line comment states the
invariant that makes it safe. If you cannot name the invariant, the type model
is wrong; fix it instead.

## 6. Boundaries are validated explicitly

Length, shape, range, enum membership, and ownership checks live at the system
boundary (GraphQL resolver, REST handler, Celery task input). Domain code
assumes invariants already hold.

## 7. Files stay under the size threshold

Application modules must stay below 400 lines; UI components below 300 lines.
Crossing the threshold requires a justification in the PR description and an
extracted cohesive unit.

## 8. Names match the domain glossary

Types, functions, and variables use vocabulary from the existing codebase and
product glossary. Do not introduce synonyms or abbreviations that shadow
existing terms.

## 9. Functions have a single responsibility

Every function does one job, and any side effect (DB write, queue push, log,
metric) is explicit in the function name or the caller chain.

## 10. Public and cross-layer code is fully typed

DTOs, domain objects, persistence models, and search documents are distinct and
deliberately mapped. Do not share a model across transport, domain, and storage
boundaries.

## 11. Full quality gates run green

Run every gate that CI runs:

```bash
cd backend && python -m alembic heads
cd frontend && npm run build
cd frontend && npm run ui:audit:strict
cd frontend && npm run test:e2e:ci
git diff --check
```

## 12. Diff contains only intended changes

Review the complete diff before requesting review. No unrelated refactors,
dependency bumps, or formatting churn should be mixed into a feature change.

## 13. Authorization is explicit at every mutation

Authentication alone is not authorization. Every state-changing endpoint has a
role or ownership check that can reject the request even when the caller is
authenticated.

## 14. No secrets or private data leak

No credentials, session tokens, raw CV contents, passport data, or medical
records appear in logs, metrics, test fixtures, or documentation.

## 15. Network calls are bounded

Every external call has a finite timeout and a bounded retry with backoff.
Retries are only used for idempotent or externally protected operations.

## 16. Database changes have migrations

Schema changes require an Alembic migration with both `upgrade` and `downgrade`
behavior. Destructive changes follow expand/migrate/contract. Backfills are
restartable, measurable, and safe under partial completion.

## 17. Whitespace and line endings are clean

```bash
git diff --check
```

Catches trailing whitespace and missing-newline-at-EOF before CI.

## 18. UI tokens are used, not raw values

Frontend surfaces use semantic tokens (`bg-surface`, `border-border-subtle`,
`rounded-[14px]`) instead of raw hex or arbitrary Tailwind classes. Interactive
elements expose `hover`, `active`, `focus-visible`, `disabled`, `loading`, and
`error` states.

## 19. New dependencies require a written justification

Add a new package only after proving the standard library and existing
dependencies are insufficient. Update the correct lock or requirements file and
note the security and maintenance impact in the PR.

## 20. Public contracts remain compatible

GraphQL fields, REST routes, Celery task payloads, persisted enums, and search
documents do not change without a deprecation plan and staged rollout. Frontend
types are generated or validated against the backend schema; handwritten shapes
must not silently diverge.
