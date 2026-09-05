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

- **Clean, efficient, styled, modular, maintainable code**:
  - **Clean & Readable**: Single-responsibility functions, self-documenting naming, zero dead code, and clear intent without cognitive clutter.
  - **Efficient & Performant**: Minimal re-renders, fast bundle footprints, zero unneeded network requests or duplicate queries, clean memory and listener disposal.
  - **Lean & Lightweight**: Avoid bloat. Question every abstraction and external package. Prefer standard browser APIs and language built-ins over heavy utility libraries. Keep assets, bundle size, and memory usage minimal.
  - **Debt-Resistant**: Treat technical debt prevention as an active discipline. Never take shortcuts, create temporary workarounds, copy legacy exceptions, or leave TODOs without owner and issue. Fix root causes rather than patching symptoms.
  - **Styled & Consistent (Zero Tolerance for Inconsistency)**:
    - **Buttons & Controls**: Use standard rounded corners (`rounded-lg` or `rounded-full`), height scale (`min-h-9`/`min-h-11`), uniform hover/active state transitions, and accessible focus rings (`focus-visible:ring-2 focus-visible:ring-focus`).
    - **Windows, Panes & Surfaces**: Always build surfaces with semantic background tokens (`bg-canvas`, `bg-surface`, `bg-surface-raised`), standardized border strokes (`border-border-subtle`, `border-border-strong`), and uniform radii (`rounded-[14px]`). Never hardcode raw hex, RGB, or arbitrary Tailwind colors (e.g. `bg-gray-*`, `text-blue-*`).
    - **Typography & Fonts**: Use font stack tokens (`font-sans` for interface, `font-mono` for metrics/dates/codes/rates). Follow consistent hierarchy: title (`text-sm font-semibold text-primary`), subtitle/body (`text-xs text-secondary`), and caption (`text-xs text-muted`).
    - **Modals & Dialogs**: Standardize backdrop overlays (`bg-canvas/80 backdrop-blur-xs`), modal wrapper styling (`bg-surface border border-border-subtle rounded-[14px] shadow-2xl p-5 sm:p-6`), header with icon badge + title + close button (`X`), and keyboard focus trap.
    - **Theme Symmetry**: Every component, button, window, and modal MUST look balanced, purposeful, and fully legible in BOTH dark and light themes.
  - **Modular & Decoupled**: Clear separation of concerns between UI components, custom hooks, business logic, domain models, and transport layers. Reusable patterns belong in dedicated modules.
  - **Maintainable & Type-Safe**: Strict TypeScript/Python type safety, zero unexplained casts or suppressions, well-bounded interfaces, and comprehensive test coverage so changes are durable.
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

