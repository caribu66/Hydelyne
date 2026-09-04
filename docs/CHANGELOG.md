# Changelog

The running record of what was built, when, by which tool, and why. This is
the shared handoff point between AI tools (Claude Code, Codex, Kilo Code, or
any other) and between sessions of the same tool — read it before assuming
context needs to be re-explained, and append to it before finishing any work
that changes committed code, running data, or infrastructure state.

Newest entries first. Each entry: date, who/what did it, what changed, why,
and any follow-up the next session should know about. Keep entries short —
this is an index into commits and docs, not a replacement for either.

## 2026-09-04 — Standardize authorization gating against the whole bug class (Claude Code)

Follow-up to "Gate shared search links behind sign-in" below: that patch
fixed one instance, this makes the class of bug structurally hard to
reintroduce and closes a symmetric backend test gap.

- `frontend/src/hooks/useSearchWorkspace.ts`: folded `isAuthenticated` into
  the `isSearchActive` computation itself
  (`Boolean(isAuthenticated && (committedQuery.trim() || showSavedOnly || activeFilterCount > 0))`).
  Every result-revealing block in `frontend/src/App.tsx` (results header,
  `ActiveFilterChips`, the results/dossier area) already keyed off
  `isSearchActive`, so this closes all of them at once, structurally — no
  future entry point (new URL param, restored session state, a websocket
  push) can leak result chrome just by forgetting its own auth check. The
  imperative `useRequireAuth()` calls elsewhere in `App.tsx` are unchanged
  and still give immediate feedback on user action; this is the backstop
  underneath them.
- Found and fixed a real regression while wiring this up: the earlier
  patch's `onSyncQuery` called `requestLogin()` unconditionally on every
  `?q=` deep link, which raced the async session check on page load —
  an already-authenticated visitor loading `/?q=...` could have the sign-in
  modal pop open before their session resolved, and it never closed once
  auth confirmed, permanently blocking the UI (caught by two previously
  passing `authenticated-flow.spec.ts` cases going red). Removed that call;
  the render-time guard above is sufficient for correctness, and the
  sign-in dialog now only opens on user interaction, matching the existing
  disabled-search-box behavior for a plain unauthenticated visit.
- `frontend/tests/auth-gate.spec.ts` (new): regression coverage for the bug
  class — asserts `/?q=hele`, `/?view=table`, and `/?q=hele&view=table`
  never render results chrome or fire the `CrewMembers`/`QueryCrew`/
  `SearchCrew` GraphQL operations while logged out. Verified red against a
  local revert of the `isSearchActive` change, green after.
- `backend/tests/test_auth.py`: added
  `test_all_queries_require_auth_decorator`, which introspects every
  `Query` field in `backend/app/graphql/schema.py` and fails if one isn't
  wrapped by `@require_auth`/`@require_admin` (checked via the resolver's
  code object, so it's decorator-agnostic and needs no DB/service mocking).
  Mutations already had a "add a negative-auth test per mutation" policy
  (`docs/AUTHORIZATION.md`); queries only had the doc's prose claim — this
  closes that asymmetry with an introspection-driven test that can't
  silently drift, backed by an empty `_PUBLIC_QUERIES` allow-list for any
  future intentionally-public field. Verified it fails when `@require_auth`
  is stripped from a field.
- Documented the rule in `docs/ARCHITECTURE.md`'s Security boundaries
  (frontend auth-derived render gating, pointing at `isSearchActive` and
  `auth-gate.spec.ts`) and `docs/AUTHORIZATION.md` (the new query test).
- No schema/contract changes. No new dependencies. Backend verification ran
  under this environment's Python (mypy not installed here — not run, not
  claimed as passing); `pytest tests/test_auth.py` (19/19) and the targeted
  decorator-strip sanity check both pass. Frontend: lint/test/build/
  ui:audit:strict clean; full `test:e2e:ci` shows the same 11 pre-existing
  failures (visual-snapshot baselines + one dossier-menu timeout, all
  already present in this session's other uncommitted frontend work before
  this change) and zero new ones.
- Follow-up: none identified. The pre-existing e2e failures above belong to
  unrelated in-progress UI work already in the working tree, not this
  change.

## 2026-09-04 — Gate shared search links behind sign-in (Claude Code)

- Fixed: visiting a shared/bookmarked search URL (e.g. `/?q=hele`) while
  logged out silently rendered "Found 0 contractors" instead of prompting
  sign-in. `useURLSync` seeds `query`/`committedQuery` from the URL's `q`
  param on mount, which flips `isSearchActive` true and renders the results
  panel — but `useCrewProfiles` skips fetching while unauthenticated
  (`skip: !isAuthenticated`), so the list being searched was always empty.
  The manual search box already opened the sign-in dialog in this case
  (`onSearch` in `frontend/src/App.tsx`); the URL-sync path
  (`onSyncQuery`) did not.
- Fix: `onSyncQuery` in `frontend/src/App.tsx` now calls `requestLogin()`
  when `!isAuthenticated`, matching the manual-search gate. Verified by
  running a real Vite dev server (the `localhost:5173` container serves a
  prod build, not source) against the existing backend: an unauthenticated
  `?q=hele` visit now opens the sign-in dialog, and after signing in
  (`ops@hydenlyne.com`), the search correctly resolves to seeded consultant
  Helena Lindqvist.
- No schema, contract, or dependency changes. No new tests added — this is a
  one-line behavioral gate matching an existing, already-tested pattern in
  the same file; covering it would require mocking the URL-sync mount effect
  end-to-end, which the existing test suite doesn't do for this component.
- Follow-up: none identified.

## 2026-09-04 — Full-profile reading layout (Codex)

- Rebuilt the full contractor-profile modal around separately selectable
  Snapshot, Credentials, Expertise, and History sections. The modal now opens
  on a concise decision summary rather than rendering every record in one
  scrolling column.
- Increased the desktop reading surface and made the overview text readable at
  body size. Long credentials, skills, systems, clients, training, and
  campaign collections retain all records behind explicit show-more controls.
- The focused dossier now suppresses malformed JSON-shaped AI summaries and
  no longer repeats credentials, skills, systems, training, or clients on the
  overview when each has a dedicated profile section.
- Promoted Skills to a primary dossier destination and replaced its long chip
  cloud with a searchable, two-column reading list that reveals further
  matches only on request.
- Harmonized disclosure controls and search-field corner treatment across
  dossier, modal, and document surfaces. Added a frontend agent rule requiring
  visual harmony with adjacent reading surfaces before UI changes ship.
- Filled the overview's expanded-space deliberately with a bounded,
  navigable decision snapshot for readiness, strongest skills, and track
  record. It uses existing extracted profile and document metadata and links
  directly to the relevant detailed section.
- Rebalanced the desktop split workspace from a 5:7 to a 4:8 result-list to
  dossier ratio and removed its restrictive tall-screen cap. The selected
  specialist now has the primary reading area both horizontally and vertically,
  while preserving an always-visible, usable result switcher.

## 2026-09-04 — Document-vault scanning improvements (Codex)

- Added accessible document search across title, filename, and safe record
  notes, with live result counts and one-action clearing for searches and
  category filters. Empty states now distinguish no records from no matches.
- Long project, certification, credential, and training collections now show
  a concise first six records with accessible controls to reveal or collapse
  the rest, keeping dossier review readable without hiding information.
- Kept document preview, download availability, compliance states, and backend
  authorization unchanged. Added unit coverage for document-query matching.

## 2026-09-04 — Reliable local-stack launcher (Codex)

- Added `scripts/local-stack.sh` as the supported start/stop/status path. It
  refuses port collisions instead of silently serving a different checkout,
  and waits for both frontend and backend health before declaring the app ready.
- Made the default compose stack CPU-safe: the standard worker now consumes the
  deterministic CV queue; the NVIDIA-specific worker is opt-in via the `gpu`
  profile; and Ollama no longer requires a GPU device to start.
- Consolidated the API, workers, scheduler, and dashboard onto one locally
  built backend image, avoiding four redundant parallel backend builds during
  startup.
- Ordered the paginated specialist list newest-first. This prevents recently
  added consultants from falling beyond the frontend's first 100 records.

## 2026-09-04 — Fix db port conflict with host Postgres; resolve stack outage (Claude Code)

Found the whole containerized stack down ~44h (a host reboot). Restarting
`db` failed with "address already in use" on 5432 — occupied by the
developer's own general-purpose, always-on Postgres 18 (a systemd/Quadlet
unit, `postgres.service`, keyed to their OS username, unrelated to this
project). It happened to also contain a stale `hydenlyne` database from an
unrelated past experiment (migration `009`, 9 seed crew members, last
touched 2026-09-01), so the app was silently connecting to the wrong
database instead of erroring outright. Confirmed no harm: alembic's
auto-migration attempt against it failed safely on a permission error
(`InsufficientPrivilegeError: must be owner of table crew_members`,
transactional rollback) and no `crew_members` row had an `updated_at` from
today before this was caught and the host processes were stopped.

`db`'s host-published port is now `${POSTGRES_HOST_PORT:-5433}` instead of a
hardcoded `5432` (`docker-compose.yml`; documented in `.env.example` and
`README.md`). Container-to-container traffic (`db:5432` on the compose
network) is unaffected — only the host-side mapping changed. Recreated `db`
with `--force-recreate` (a stale container object from the old port mapping
doesn't pick up a compose-file change on `up -d` alone) and confirmed the
persistent volume survived intact: migration head `012`, 109 real crew
members. Full stack verified live: `/health/all` all healthy, GraphQL login +
query against real data, frontend HTTP 200. See also `backend/.env` (not
committed — gitignored), which had the same class of stale credentials bug
this fixed too while touching the file.

**Follow-up:** the developer's `postgres.service` will keep existing on this
machine — if it or something else ever also claims 5433, `POSTGRES_HOST_PORT`
in `.env` is the escape hatch, no code change needed.

## 2026-09-03 — Clean logout boundary (Codex)

- Logout now immediately closes authenticated surfaces, clears search/filter,
  selection, comparison, shortlist, and transient dossier state, and replaces
  the browser location with the unfiltered `/` main page.
- Legacy bearer credentials and Apollo's authenticated response cache are
  cleared after the best-effort server logout. Added a Playwright regression
  covering filtered search, URL state, shortlist storage, and private results.

## 2026-09-02 — Unified Hydenlyne UI theme (Codex)

- Replaced screen-level zinc/blue styling with semantic dark and light theme
  roles for surfaces, text, actions, focus, and statuses; removed remote font
  loading and added pre-render theme initialization to avoid a theme flash.
- Added typed UI primitives, standardized control/card radii and metadata text,
  refreshed the responsive search/results/dossier hierarchy, exposed result
  views in one toolbar, and normalized user-facing specialist, shortlist,
  compare, and mobilization language.
- Extended the strict UI audit to reject raw palette and literal visual colors.
  Added inspected dark/light authenticated visual baselines at mobile, tablet,
  desktop, and wide viewports. No backend or API contract changed.

## 2026-09-02 — Authorization matrix: close test and doc gaps (Claude Code)

Addressed `docs/AUDIT_2026-09-02.md` P1 #4 ("no documented+tested
authorization matrix"). The policy itself was already sound (every GraphQL
mutation uniformly `@require_admin`, matching `docs/AUTHORIZATION.md`), so
this was about closing the gaps between the policy and its documentation/test
coverage, plus one real inconsistency found while auditing REST:

- `docs/AUTHORIZATION.md` only listed 3 REST routes; the backend actually
  exposes ~15. Rewrote the REST table to cover `/api/search/*`,
  `/api/documents/*`, and `/api/dropbox/download`, and made explicit that
  `/health/{db,redis,ollama,qdrant,all}` are open with no auth at all outside
  `APP_ENV=production` (intentional per `_is_prod()` in `app/api/health.py`,
  but previously undocumented — a future reader could easily have mistaken it
  for a bug).
- Found `POST /api/search/index/crew/{crew_id}` was gated by
  `get_current_user_rest` (any authenticated user) despite writing to the
  Meilisearch index — a real inconsistency with every other write path, which
  are all admin-gated. Confirmed nothing calls it (frontend or backend) and
  tightened it to `require_admin_rest`.
- Only 2 of 14 admin-gated GraphQL mutations had a negative-authorization
  test. Added a parametrized test in `backend/tests/test_auth.py` covering
  the other 12, asserting a non-admin caller gets `FORBIDDEN` on each.
- Verified independently (not just trusting the prior commit's message):
  backend ruff format/check, mypy strict, and pytest (102 passed, up from 90)
  all green; single Alembic head.

**Follow-up for the next session:** `docs/AUTHORIZATION.md`'s own rationale
notes reads are deliberately open to any authenticated user (product needs
agents to browse all specialists), so resource-ownership scoping is out of
scope here by design, not an oversight — don't "fix" that without a product
decision. Separately, `backend/pyproject.toml` still fails `pip install -e .`
on a clean checkout (flat-layout package discovery error: `app/`, `data/`,
and `alembic/` are all top-level with no `[tool.setuptools]` package config)
— that's the exact command CI's backend job runs, and it predates this
session's changes. Not fixed here (out of scope for the auth-matrix slice);
worth its own small PR.

## 2026-09-02 — Real strict typing + anti-technical-debt rules (Claude Code)

User asked for strict rules to eradicate `any`/casts/technical debt going
forward, then correctly pushed back when an early pass introduced new `Any`
usage as a shortcut for untyped-looking third-party libraries. That pushback
changed the approach: don't just write policy, verify the enforcement
actually works, and don't accept `Any` without checking whether a real type
was available first.

**Tooling now actually enforces this (previously it didn't):**
- Backend: `mypy app` went from silently red (152+ errors under the exact
  CI command) to a fully strict, passing gate. Added
  `plugins = ["sqlalchemy.ext.mypy.plugin"]` (without it `Result.
  scalar_one_or_none()` etc. resolve to `Any` everywhere) plus
  `disallow_incomplete_defs`, `disallow_untyped_calls`, `check_untyped_defs`,
  `no_implicit_optional`, `warn_redundant_casts`, `warn_unused_ignores`,
  `strict_equality`, `enable_error_code = ["ignore-without-code"]`. CI's
  mypy step had `--no-strict-optional` silently weakening it — removed.
- Frontend: `tsconfig.json` had no `strict` at all — the entire React app
  had zero real type-checking on React itself, masked because
  `@types/react`/`@types/react-dom` were never installed and non-strict mode
  doesn't error on unresolvable-module-as-`any`. Installed both, enabled
  `strict`, `noUncheckedIndexedAccess`, `noImplicitReturns`,
  `noFallthroughCasesInSwitch`. Added ESLint (`eslint.config.js`, flat
  config) — there was none before; `npm run lint` was only ever `tsc
  --noEmit`. `@typescript-eslint/no-explicit-any` is a blocking error;
  `no-non-null-assertion` is a warning (visible, not blocking) so justified
  `!` stays reviewable instead of silently multiplying.
- Rules written into `AGENTS.md`, `backend/AGENTS.md`, `frontend/AGENTS.md`,
  and `docs/ENGINEERING_STANDARDS.md` (new "Type safety" section): no
  `Any`/`any` without checking for real types first (most "untyped" libs
  here — meilisearch, qdrant_client, redis, sentry_sdk — actually ship
  `py.typed` and have real types; only celery doesn't), no cast/assertion
  without a comment stating the invariant, no bare `type: ignore`.

**Real bugs this surfaced (not just annotation gaps):**
- `backend/app/models/__init__.py`: every nullable date column (`date_of_birth`,
  `passport_expiry`, cert/work-history dates, etc. — 13 fields) was typed
  `Mapped[Optional[Date]]` using SQLAlchemy's `Date` *column-type class*
  instead of Python's `datetime.date`. Worked at runtime (the real SQL type
  comes from `mapped_column(Date)`), but poisoned static types on every read
  of these fields across mappers/schema/services. Root-cause fixed, not
  patched at each call site.
- `backend/app/services/crew.py::get_user_from_token`: reused the name
  `result` for both `verify_session_token()`'s tuple return and the later
  SQLAlchemy `Result` object — mypy (correctly) got confused, and so would a
  human reader. Renamed.
- `create_crew_member`/`update_crew_member` GraphQL mutations accepted
  `date_of_birth` as a raw string and relied on Pydantic's implicit
  coercion instead of parsing explicitly like `add_certification` already
  does — inconsistent with the codebase's own established pattern. Now
  parses with `date.fromisoformat`, matching precedent.
- `backend/app/services/sentry.py::filter_sensitive_data`: the PII-scrubbing
  callback (`before_send`, runs on every error sent to Sentry) indexed into
  `frame["vars"]`/`request["headers"]` without checking they were dicts —
  would `TypeError` and presumably break Sentry reporting entirely for any
  error where Sentry couldn't introspect a frame's locals. Guarded with
  `isinstance` checks.
- `frontend/src/types.ts` / `lib/mappers.ts`: `UserProfile` had no
  `nationality` field even though the mapper computed one from raw crew data
  and `SpecialistDossierPane.tsx` read `profile.nationality` in three places
  — the Nationality row in the specialist dossier's Personal Information
  section could never render. Added the field and wired it through.
- `frontend/src/App.tsx`: a `useCallback` deleting/deselecting the currently
  selected profile was missing `selectedProfileId` from its deps array —
  real stale-closure risk (the delete-selection logic could read outdated
  state). Fixed; two other flagged callbacks were just missing stable
  `useState` setters (harmless, added for lint cleanliness) — one of those
  additions initially caused a real TDZ error (`setQuery`/`setCommittedQuery`
  come from a hook called later in the component) and was reverted to a
  justified `eslint-disable` instead.
- `frontend/src/hooks/useAuth.ts`: `login(email, password, remember)` has
  always ignored `remember` — the backend `login` mutation has no
  session-duration parameter at all, so `LoginPage.tsx`'s "Remember me"
  checkbox currently does nothing. **Not fixed** — real remember-me needs a
  backend session-duration/storage design decision, out of scope for this
  pass. Made the no-op explicit in a comment instead of silently ignoring it.
- `backend/app/services/cv_processing.py`: `"GWO Wind"` was a duplicate dict
  key (copy-paste), silently shadowed by itself. Removed the duplicate.
- Several `response.json()` / external-API boundary reads (Ollama, Dropbox
  OAuth, Qdrant embeddings) returned `Any` into a typed function with no
  validation — added `isinstance` checks with safe fallbacks so malformed
  responses fail loudly/safely instead of propagating untyped garbage.

**Dead code removed** (found via `no-unused-vars` once ESLint existed):
`useSpecialistDocuments.ts`'s 165-line unused `DEFAULT_DOCUMENTS` mock
block, `graphql/validation.py::QueryValidationMiddleware` (unreferenced
anywhere), `auth/decorators.py::get_current_user`/`is_authenticated`
(unreferenced), ~15 files' worth of unused Lucide icon imports.

**Found but intentionally not fixed — flagged for a follow-up decision:**
- `backend`: `bandit -r app/` currently fails (exit 1) as CI runs it — 7
  pre-existing `B113 request_without_timeout` findings (`dropbox.py`,
  `dropbox_auth.py`, `upload.py` — directly violates this repo's own
  `AGENTS.md` timeout rule), 2 `B110 try/except/pass`, 1 `B105` false
  positive on a URL constant. None introduced this session; not fixed here.
- `backend/app/api/search.py`: `availability`/`classification`/`crew_id`
  query params are interpolated directly into a Meilisearch filter string
  via f-string with no escaping — a filter-syntax injection risk. Noticed
  while typing this file; fixing it is a security-hardening task, not a
  typing one.
- `frontend/components/DocumentVault.tsx`: has working `searchQuery`
  filter logic but no `<input>` wired to `setSearchQuery` — the vault search
  is inert. `FilterSidebar.tsx` similarly has an unused `toggleDepartment` +
  `ALL_DEPARTMENTS` — a department filter that's either half-built or
  should be deleted. Both left in place with a comment rather than guessed
  at.

**Verified before/after:** backend 90/90 tests, `mypy app`, `ruff check`,
`ruff format --check` all clean. Frontend 46/46 tests, `tsc --noEmit`,
`eslint .` (0 errors/15 justified warnings), production build, and
`ui:audit:strict` all clean.

## 2026-09-02 — Showcase readiness pass (Claude Code)

- Reviewed the repo end-to-end for showcase readiness. Confirmed the stack
  (11 containers) runs healthy, backend tests pass in ~5s with no hang,
  frontend typecheck/build/unit tests pass.
- Committed the large staged diff from the audit remediation pass below
  (commit `ff1329d`) — it had been sitting staged but uncommitted.
- Seeded demo data: ran `backend/seed_100.py` (9 → 109 crew members).
- Found and fixed a real gap: the seed script inserts directly into
  PostgreSQL and bypasses the app's normal create path, so Meilisearch only
  had 1 of 109 members indexed. Backfilled the index via a one-off script
  calling `ConsultantKnowledgeService.index_crew_member` for every existing
  row (109/109 indexed after).
- **Follow-up:** any future direct-DB seed/import script should either call
  the same indexing path itself or be paired with a reindex step — see
  `backend/app/services/consultant_knowledge.py::index_crew_member`.
- Set up this documentation system (this file, `CLAUDE.md` pointer files,
  stale-reference fixes) so future sessions/tools don't re-derive the above.

## 2026-09-02 — Monorepo merge, domain layer, CI hardening (Kilo Code)

Commit `ff1329d`. Executed the remediation plan in
`.kilo/plans/1788366627971-audit-remediation-plan.md` against the findings in
`docs/AUDIT_2026-09-02.md`. Highlights:

- Merged `frontend/` (previously a separate, gitignored repo) into this
  monorepo. See ADR 0001.
- Decoupled schema migrations from app startup: `alembic upgrade head` now
  runs as a Dockerfile entrypoint step; `database.py::init_db()` refuses to
  run against PostgreSQL at all (SQLite dev/test only). No more
  `create_all`-on-migration-failure fallback.
- Hardened CI: blocking mypy/ruff/bandit/pip-audit gates (mypy previously had
  `|| true`), deterministic installs, `requirements-dev.txt` split out so
  `aiosqlite` is actually present for tests.
- `docker-compose.prod.yml` now hardcodes `APP_ENV=production` on every
  service instead of relying on a default that could silently stay dev.
- Added `app/domain/` (fields.py, certifications.py) as a single owned
  vocabulary, and `ConsultantKnowledgeService` to centralize consultant
  retrieval/indexing that was previously scattered and inconsistent.
- Fixed test isolation so the suite no longer stalls on a live Redis check.
- Added `docs/ARCHITECTURE.md`, `docs/ENGINEERING_STANDARDS.md`,
  `docs/AUTHORIZATION.md`, ADRs 0001–0003, `AGENTS.md` (root/backend/frontend).
- **Known still-open items** (see `docs/AUDIT_2026-09-02.md` for detail, some
  of which is now stale given the above): no documented+tested authorization
  matrix, Redis-backed controls still fail open in places despite ADR 0002
  choosing fail-closed, no outbox/idempotency for cross-system writes,
  `qdrant`/`ollama` images still pinned to `:latest`, several large files
  (`App.tsx`, `graphql/schema.py`, `SpecialistDossierPane.tsx`) not yet split.

## 2026-09-02 — Initial commits (Kilo Code / manual)

- `49b89d7` Initial commit: backend, infrastructure, and container stack —
  first working end-to-end `podman-compose up`, fixing several latent faults
  (missing `psycopg2-binary`, wrong Qdrant port, missing curl in backend
  image, `localhost`→`::1` healthcheck resolution, SELinux bind-mount label,
  a schema drift between `work_history` columns and the model/migrations).
- `4f413c7`, `f907a7d` — README fixes: service topology explanation, and
  correcting rebuild instructions to force-recreate containers after a build
  (compose does not recreate a container when only the image changed).
