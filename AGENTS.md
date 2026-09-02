# Hydenlyne engineering contract for AI agents

This file is the entry point for every AI-assisted change. It applies to the
whole workspace. More specific `AGENTS.md` files add rules for their directory.

## Read before changing code

Read, in order:

1. This file.
2. `docs/CHANGELOG.md` — what was recently built, by whom/which tool, and why.
   This is the shared handoff point between different AI tools and sessions;
   check it before assuming context has to be re-explained.
3. `docs/ARCHITECTURE.md`.
4. `docs/ENGINEERING_STANDARDS.md`.
5. The nearest directory-specific `AGENTS.md`.
6. Tests and existing implementations adjacent to the requested change.

For consultant retrieval, ingestion vocabulary, Meilisearch, or Qdrant work,
also read `backend/docs/consultant-knowledge-core.md`. For CV/document
extraction work, also read `backend/docs/cv-ingestion-pipeline.md` — CV
extraction is deterministic by design; do not add an LLM call there.

## Repository facts

- This is a true monorepo (ADR 0001): one root repository owns the backend,
  frontend, infrastructure, CI, and docs. A full-stack change is one commit.
- The backend is Python 3.11, FastAPI, Strawberry GraphQL, SQLAlchemy async,
  Alembic, Celery, PostgreSQL, Redis, Meilisearch, Qdrant, and Ollama.
- The frontend is React 19, TypeScript, Vite, Apollo Client, and Tailwind CSS.
- This is a modular monolith with background workers, not a microservice
  architecture. Do not split it into more deployables without an approved ADR.

## Non-negotiable rules

- Make the smallest coherent change that satisfies explicit acceptance
  criteria. Do not combine feature work, broad refactoring, dependency
  upgrades, and formatting churn.
- Inspect the working tree first. Existing changes belong to the user. Do not
  overwrite, revert, or silently absorb unrelated work.
- Preserve module boundaries and dependency direction from
  `docs/ARCHITECTURE.md`.
- Keep transport code thin. GraphQL resolvers, REST handlers, and Celery tasks
  validate/authorize input and call application services; they do not become
  the home of business rules.
- Keep domain code free of FastAPI, Strawberry, Celery, SQLAlchemy sessions,
  HTTP clients, and vendor SDKs.
- Do not access PostgreSQL, Redis, Meilisearch, Qdrant, Ollama, or Dropbox from
  frontend code or domain modules. Use an owned backend adapter/service.
- Do not create a second source of truth for enums, aliases, field names,
  status values, prompts, or API contracts. Search for the existing owner.
- No `any`/`Any`, unexplained `cast()`/`as X`/non-null assertion, or bare
  `# type: ignore`/`@ts-expect-error`. Backend mypy and frontend ESLint/tsc
  both run at real strictness and enforce this; see
  `docs/ENGINEERING_STANDARDS.md` § Type safety for the exact rules and the
  reasoning (weak types here is exactly the debt that turns into a rewrite
  later — fix the root cause, don't suppress the symptom).
- Never add an external dependency without explaining why the standard library
  and existing dependencies are insufficient, checking maintenance/security
  impact, and updating the correct lock or requirements file.
- Every state-changing endpoint requires an explicit authorization decision.
  Authentication alone is not proof that a user may mutate the resource.
- Validate untrusted data at the system boundary. Never trust file names,
  MIME declarations, GraphQL strings, webhook bodies, LLM output, or search
  index contents.
- Do not log secrets, credentials, session tokens, raw CV contents, passport
  data, medical data, or unnecessary personal data.
- Do not swallow exceptions silently. If degraded operation is intentional,
  document the policy, log safe diagnostic context, and expose an observable
  health signal where appropriate.
- Database schema changes require an Alembic migration with upgrade and
  downgrade behavior. Never use `create_all` as a production migration path.
- Changes to API fields, persisted values, events, task payloads, or search
  documents are contract changes and require compatibility analysis.
- Behavioral changes require tests. Bug fixes require a regression test that
  fails without the fix.
- Never weaken, skip, delete, or mark a check non-blocking merely to make CI
  green.
- Generated artifacts, build output, local databases, credentials, uploaded
  documents, and model files must not be committed.

## Required workflow

Before implementation:

1. State the requested outcome and acceptance criteria.
2. Inspect relevant docs, code, tests, and current Git status.
3. Identify affected contracts, data, authorization, failure modes, and
   rollback requirements.
4. List the intended files and confirm the change stays inside the requested
   scope. Create an ADR if the dependency direction, data ownership, or
   deployable topology changes.

During implementation:

1. Implement one vertical slice at a time.
2. Reuse established patterns only when they satisfy these rules; do not copy a
   known legacy exception into new code.
3. Add tests alongside behavior.
4. Keep functions focused, inputs typed, side effects explicit, and errors
   actionable.

Before completion:

1. Run the checks required by the nearest `AGENTS.md` and
   `docs/ENGINEERING_STANDARDS.md`.
2. Review `git diff --check`, the complete diff, and untracked files.
3. Report checks run, failures, assumptions, migrations, security impact,
   compatibility impact, and remaining risk. Never claim a check passed if it
   was skipped, timed out, or was non-blocking.
4. Append a dated entry to `docs/CHANGELOG.md`: what changed, why, which
   tool/agent did it, and any follow-up the next session needs to know about.
   Do this for anything that changes committed code, running data (seeds,
   migrations run by hand), or infrastructure state — not for pure Q&A.

## Architecture decisions

Create an ADR under `docs/decisions/` when a change introduces or replaces a
database, queue, search system, external provider, authentication mechanism,
public API convention, cross-module dependency, or deployable service. Use
`docs/decisions/0000-template.md`.

