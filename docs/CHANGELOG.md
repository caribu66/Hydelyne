# Changelog

The running record of what was built, when, by which tool, and why. This is
the shared handoff point between AI tools (Claude Code, Codex, Kilo Code, or
any other) and between sessions of the same tool — read it before assuming
context needs to be re-explained, and append to it before finishing any work
that changes committed code, running data, or infrastructure state.

Newest entries first. Each entry: date, who/what did it, what changed, why,
and any follow-up the next session should know about. Keep entries short —
this is an index into commits and docs, not a replacement for either.

## 2026-09-05 — Expiry & renewal alerts engine and compliance automation (Slice 3) (Antigravity)

Implemented the offshore crewing compliance alert engine, automated status transitions,
and audit tracking across 30/60/90-day renewal and expiration windows.

- Added `ComplianceAlertService` and `classify_certification_expiry` (`app/services/compliance.py`):
  - Classifies certifications into distinct offshore mobilization windows: `expired` (<0 days, critical),
    `urgent_30d` (0-30 days, urgent renewal required), `warning_60d` (31-60 days, mobilization warning),
    `notice_90d` (61-90 days, advance booking window), and `compliant` (>90 days).
  - Automatically transitions certification statuses: `< 0 days` -> `expired`, `<= 30 days` -> `expiring_soon`.
  - Fixes the bug where `expiring_soon` tickets never transitioned to `expired` once the expiry date passed.
  - Aligns consultant root medical status (`medical_status` = `expired` / `expiring_soon`) whenever medical tickets expire.
  - Records automated compliance transition entries into backing documents' `access_log` for auditability.
  - Invalidates Redis compliance and crew caches for all affected consultants.
  - Stores compliance alert snapshots in Redis (`hydenlyne:compliance:latest_alerts`, 24h TTL) and
    publishes events on the `compliance.alerts` pub/sub channel.
- Refactored Celery task `check_expiring_certifications` (`app/tasks/document_tasks.py`) to delegate
  to `ComplianceAlertService.evaluate_and_update_compliance_sync(session)`.
- Updated `CertificationService.check_and_update_expiration_status` (`app/services/crew.py`) to handle
  all non-expired tickets and maintain medical state.
- Added test suite in `tests/test_compliance_alerts.py` (4 tests) covering window classification,
  lifecycle transitions, audit logging, Redis cache invalidations, and Celery task execution.
- All 140 backend tests and full frontend verification pass cleanly.

## 2026-09-05 — Certification verification controls & backing document preview (Slice 2) (Antigravity)

Exposed verification status, verification actions, and backing document preview
directly within the consultant dossier Completion & Expiry view.

- Exposed `documentRef` on the GraphQL `Certification` type (`app/graphql/types.py`)
  and resolved it from the DB model in `_model_to_graphql_certification` (`app/graphql/schema.py`).
- Enhanced `CertificationService.verify_certification` (`app/services/crew.py`) to
  transition lifecycle `status` to `valid` (or `expiring_soon`/`expired` based on dates)
  upon verification and invalidate the crew member's compliance status cache.
- Frontend GraphQL: Updated `CREW_MEMBERS_QUERY` to include `documentRef` and
  exported `VERIFY_CERTIFICATION` mutation (`frontend/src/lib/queries.ts`).
- Frontend Dossier Pane (`frontend/src/components/SpecialistDossierPane.tsx`):
  - Added verification badge pills (`Verified`, `Rejected`, `Pending Verification`) and
    expiry badges (`Expired`, `Expiring Soon`).
  - Added "View Proof" action opening `DocumentPreviewModal` when `documentRef` is linked.
  - Added "Verify" and "Reject" mutation controls for coordinators/managers with optimistic
    updates, loading spinner, and toast notifications.
- All backend tests (136 passed) and frontend checks (`npm run lint`, `npm test`,
  `npm run ui:audit:strict`) pass cleanly.

## 2026-09-04 — Fix crew list silently truncated past 100 records (Claude Code)

Salvaged from `claude/strange-shannon-e680d4` — a real, confirmed-still-live
bug on `main` before this port, unrelated to anything else in this session.

Follow-up to another minor issue flagged in the prior review entry: a
"Found 13" vs. "14 specialists meet every requirement" count mismatch was
a symptom, not the bug. `useCrewProfiles.ts` fetched crew with a hardcoded
`limit: 100, offset: 0` and never fetched more. With 109 real crew members,
up to 9 were invisible everywhere in the app — browsing, filter chips, and
AI search results all silently missing real specialists with no error or
indication.

Raising the frontend's requested limit alone would not have fixed this:
the backend's `crew_members` resolver also clamps `limit` to <= 100
server-side ("Enforce pagination limits to avoid abuse" —
`app/graphql/schema.py`). Fixed with real pagination in the hook: keep the
existing fast `cache-and-network` first-page fetch for the common case,
and only page through additional 100-record pages via `client.query` when
the first page comes back full — no behavior change at all when the crew
count is under 100. Verified live: the filter panel now shows "Show 109
specialists" (was capped at 100).

Frontend: 46 tests, lint, and build all clean. No backend changes in this
entry.

## 2026-09-05 — Standalone certificate document ingestion & Certification auto-linking (Slice 1) (Antigravity)

Closed the architectural gap where standalone certificate files uploaded to the
Document Vault were stored as dead files (`Document` records) without populating
the consultant's `certifications` table.

- Added `CertificationService.link_extracted_certificate` (`app/services/crew.py`):
  normalizes extracted certificate types via `app/domain/certifications.py`,
  safely parses dates, computes expiry/status, upserts or links existing
  `Certification` rows in-place via `document_ref`, and keeps `CrewMember`
  root medical fields (`medical_status`, `medical_expiry`, `medical_provider`)
  in sync for medical tickets.
- Added `normalize_classification` and `CLASSIFICATION_ALIASES` to
  `app/domain/fields.py`: normalizes `"cert"` (used by GraphQL and the frontend
  API) to canonical `"certificate"` and prevents `ValueError: Unknown document type`
  in `ExtractionService.extract_document`.
- Added missing medical aliases (`"offshore medical"`, `"offshore_medical"`,
  `"oeuk"`, `"eng1"`) to `CERT_ALIASES` in `app/domain/certifications.py`.
- Wired certificate linking into both processing pipelines:
  `app/services/sync_processor.py` (Celery sync worker) and
  `app/services/document_service.py` (async pipeline).
- Added 9 new tests in `tests/test_certificate_document_linking.py` covering
  new cert creation, updating existing unlinked certs, in-place re-extraction,
  medical field synchronization, expired status computation, classification
  normalization, and end-to-end `process_document` linking.
- All 136 backend tests pass cleanly.

## 2026-09-05 — Extract split-pane resize from App.tsx; fixes a real keyboard-focus-theft bug it exposed (Claude Code)

`App.tsx` (1597 lines, the largest file in the whole decomposition backlog)
had a fully self-contained ~100-line resizable-split-pane feature
(drag/keyboard/double-click, clamped, persisted to localStorage) with zero
existing test coverage — no unit test (this codebase's Vitest runs in a
`node` environment with no jsdom/testing-library, so DOM/hook tests aren't
this project's convention; interactive behavior is verified via Playwright)
and no e2e test either. Wrote one first
(`resizes the split pane with the keyboard, clamps it, and persists the
ratio` in `authenticated-flow.spec.ts`), confirmed it passes against the
unrefactored code, then extracted into `frontend/src/hooks/
useSplitPaneResize.ts`.

**The extraction surfaced a real, pre-existing bug — not something this
change introduced.** The new test passed every time run in isolation but
failed consistently (same assertion, same value, every run) inside the full
`npm run test:e2e:ci` suite. Isolation-passes-but-full-suite-fails pointed
at a race, not a flake, and the trace confirmed it: `Home` press received
`"60"` instead of `"25"` — the separator's own handler never ran.

Root cause: `useKeyboardNavigation.ts` has a `window`-level keydown listener
for result-list shortcuts (Home/End/arrows/j/k) whose guard excludes
`INPUT`/`TEXTAREA`/`SELECT`/`BUTTON`/`A` — but not a custom
`role="separator"` `<div>`. The separator's own `onKeyDown` never called
`stopPropagation()`, so every Home/End/arrow press on it *also* fired the
global handler, which calls `selectResultAt(...)` and moves DOM focus to a
result row via `requestAnimationFrame` a frame later. Under light load
(an isolated test run) that rAF callback consistently lost the race against
the test's next keypress; under real parallel load (the full suite, or —
critically — a real user's system doing anything else) it consistently won,
silently yanking keyboard focus off the resize handle onto the results list
mid-interaction. This is a genuine accessibility bug for real keyboard
users, exposed by a test that happened to chain multiple key presses the
way an actual user holding/repeating keys would.

Fix: `handleSplitterKeyDown` now calls `e.stopPropagation()` alongside the
existing `e.preventDefault()` for every key it handles, so the event never
reaches the global window listener. Verified via **two consecutive full
`npm run test:e2e:ci` runs** (the same repeat-until-confident bar used for
the earlier Framer Motion timing fix): **93 passed, 0 failed, both times**
(up from 90 — the 3 new passes are this test across
tablet/desktop/wide; mobile skips it, split view starts at tablet width).

- New `frontend/src/hooks/useSplitPaneResize.ts`: state, localStorage
  persistence, and all three interaction handlers (pointer-drag,
  double-click-to-cycle-presets, keyboard), returning `minRatio`/`maxRatio`
  alongside the ratio itself so `App.tsx`'s `aria-valuemin`/`aria-valuemax`
  JSX didn't need its own duplicate copy of those constants.
- `App.tsx`: removed the five now-fully-unused module-level constants and
  the `useRef`/`KeyboardEvent` imports that had no remaining use once the
  hook took over.

Verified: `npm run lint` (0 errors), `npm run test` (54 passed), `npm run
build` (135.18 kB entry chunk, stable), `npm run ui:audit:strict` (68 files,
0 findings). Result: `App.tsx` **1597 → 1505 lines** (92 lines).

**Follow-up for the next session**: `App.tsx` is still 1505 lines and still
the largest file in the backlog — the remaining bulk is mostly JSX (view
mode rendering, modals wiring, result cards) rather than more extractable
hooks like this one; the next slice there is a bigger, more careful job
(component decomposition, not hook extraction). Worth a second look at
`useKeyboardNavigation.ts`'s guard itself, independent of this fix — any
other custom-role interactive element added later without an explicit
`stopPropagation()` will hit the same class of bug.

## 2026-09-05 — Extract duplicated menu keyboard-nav from SpecialistDossierPane into a hook (Claude Code)

First frontend slice of the large-file backlog — `App.tsx` and
`SpecialistDossierPane.tsx` were skipped in earlier rounds because a
concurrent session was actively editing them; picked back up once that
settled.

Found the same kind of thing the backend slices kept finding: not
arbitrary bulk, but a specific, extractable piece. `SpecialistDossierPane.tsx`
had two nearly byte-for-byte identical ~35-line `useEffect` blocks — one for
the "more sections" overflow menu, one for the "header actions" menu — each
wiring up click-outside-to-close, Escape-to-close-and-refocus-trigger, and
arrow/Home/End roving focus among `[role="menuitem"]` children. Two
independent, real use cases of the exact same interaction contract is
precisely the bar `AGENTS.md` sets for justified abstraction ("do not
generalize until at least two real use cases demonstrate the shared
behavior") — this already had two, just not yet named as one thing.

- New `frontend/src/hooks/useMenuKeyboardNav.ts`, matching the existing
  `useAccessibleDialog.ts` hook's exact shape and conventions (`open`,
  `RefObject`, `onClose`, included in the effect's dependency array rather
  than fighting React over referential stability). Takes an
  `autoFocusFirstItem` flag since the header-actions menu autofocuses on
  open and the section menu doesn't — the one real behavioral difference
  between the two blocks, preserved rather than papered over.
- `SpecialistDossierPane.tsx`'s two effects replaced with two hook calls;
  the "more sections" menu's combined guard
  (`!isMoreSectionsOpen || isRadarModalOpen`) became the single boolean
  `isMoreSectionsOpen && !isRadarModalOpen` passed as `open`.

Verified: `npm run lint` (0 errors), `npm run test` (54 passed), `npm run
build` (134.76 kB entry chunk, unchanged), `npm run ui:audit:strict` (67
files now, 0 findings), and — the real test, since this is interactive
keyboard-navigation behavior — `npm run test:e2e:ci` **90 passed, 0
failed**, including the tests that specifically assert keyboard
accessibility of these exact menus
("keeps secondary result actions keyboard accessible without visual
clutter", "progressively discloses specialist dossier sections"). No
manual browser click-through beyond that: reaching an authenticated dossier
view in this environment hits the same CORS/port artifact documented in an
earlier entry, and the e2e suite already exercises the modified code path
with real assertions, which is stronger evidence than an unscripted manual
click.

Result: `SpecialistDossierPane.tsx` **1078 → 1023 lines** (55 lines, a
real but modest win — the actual duplication removed was ~70 lines,
partly offset by the new 57-line hook file, which is the honest
accounting for extracting shared behavior rather than deleting code).

**Follow-up for the next session**: `SpecialistDossierPane.tsx` is still
1023 lines and mostly one large component body with several tab-content
sections (`overview`/`experience`/`expertise`/`systems`/`credentials`/
`vault`) that could become child components — a bigger, more careful slice
than this one since it means threading many props/callbacks, not just
deduplicating an already-self-contained effect. `App.tsx` (1597 lines,
frontend AGENTS.md's app shell) remains untouched and is the largest file
left in the whole backlog.

## 2026-09-05 — Extract deterministic query rules from crew_query.py into app/domain (Claude Code)

Next item on the large-file backlog after `schema.py` (`App.tsx` and
`SpecialistDossierPane.tsx` were skipped this round — both are being
actively edited by a concurrent session, making them risky moving targets;
`crew_query.py` was the one file on the list nobody else was touching).

This wasn't the same kind of debt schema.py had (misplaced layer
responsibility spread across many resolvers) — `crew_query.py` is one
846-line service with a few very large methods. Rather than splitting it
arbitrarily, looked for a piece that's a genuine architectural mismatch:
`_apply_deterministic_query_rules` (118 lines) and its helper
`normalize_search_typos` (plus the `NATIONALITY_ALIASES`/`TYPO_VOCABULARY`
constants they use) are a `@staticmethod` and a pure function — no
database, no LLM client, no framework dependency, operating only on
strings and dicts. That's exactly `app/domain/`'s charter ("pure
vocabulary, normalization, invariants... must not import from
api/auth/graphql/models/services/tasks" — `docs/ARCHITECTURE.md`), and the
file already imports `CERT_ALIASES`/`CERT_FAMILIES` from
`app/domain/certifications.py`, an established sibling for exactly this
kind of content.

- New `app/domain/crew_query_rules.py`: `NATIONALITY_ALIASES`,
  `TYPO_VOCABULARY`, `normalize_search_typos()`, and
  `apply_deterministic_query_rules()` (renamed from the private
  `CrewQueryService._apply_deterministic_query_rules` static method to a
  plain module function, since it's no longer tied to the service class at
  all).
- `crew_query.py`'s one call site (`_classify_intent`) now imports and
  calls the module function directly. Removed `re`, `get_close_matches`,
  and the `CERT_ALIASES`/`CERT_FAMILIES` imports — all three became fully
  unused once their only call sites moved.
- Existing test coverage was already strong here (5 of 7 tests in
  `test_crew_query.py` exercise this exact logic directly), so this was
  verified as a pure move rather than needing new characterization tests
  first: updated those 5 call sites from
  `CrewQueryService._apply_deterministic_query_rules(...)` to
  `apply_deterministic_query_rules(...)` and confirmed identical pass/fail
  behavior.

Result: `app/services/crew_query.py` **846 → 651 lines** (23%). Verified:
`ruff format --check`/`ruff check` (clean), `mypy app` (0 issues, 49 source
files), `bandit -r app -q` (exit 0), `pytest tests -q` (**127 passed** —
same count as before, 0 new, 0 removed, confirming this really was a pure
move), `alembic heads` (single head). No behavior change, no API/contract
change.

**Follow-up for the next session**: `crew_query.py` is still 651 lines,
mostly from `_handle_search` (236 lines) and `CREW_QUERY_PROMPTS` (a
~95-line block of LLM prompt template strings) — the prompts are pure data
and a safe, purely mechanical move to their own module
(`crew_query_prompts.py`, alongside the service rather than in
`app/domain/`, matching how `app/services/reports.py`'s
`REPORT_TEMPLATES` is already scoped) whenever that file is picked up
again. `_handle_search` is a bigger question: it's not pure like the rules
extraction was (it needs `db_session`), so splitting it would mean
multiple focused query-building helper methods, not a layer move — a
different, more careful slice than this one. `App.tsx` and
`SpecialistDossierPane.tsx` remain untouched, still better scoped once the
concurrent frontend work settles.

## 2026-09-05 — Extract remaining document/cert/project mutations out of graphql/schema.py (slice 3) — closes the "direct DB orchestration" debt item (Claude Code)

Third and final slice targeting `docs/AUDIT_2026-09-02.md`'s "GraphQL
schema ... contain[s] direct database orchestration" finding. Extracted
the six resolvers still doing inline `select()`/session work:
`reprocessDocument` → `DocumentService.reprocess_document`;
`updateCertification`/`verifyCertification` →
`CertificationService.update_certification`/`.verify_certification`
(`app/services/crew.py`); `createProject`/`updateProject`/
`assignCrewToProject` → new methods on `ProjectService`
(`app/services/project.py`, previously read-only from slice 1).

All six had only negative-authorization (FORBIDDEN) test coverage in
`test_auth.py` — zero prior test verified their actual success-path
behavior. Wrote 7 characterization tests
(`backend/tests/test_project_and_certification_mutations.py`), ran them
against the unrefactored resolvers first, then extracted, then confirmed
unchanged.

**Checked what's left rather than assuming this is "close enough"**: grepped
every remaining `get_session_factory()` call site in `schema.py` (4 left:
`crewSummary`, `queryCrew`, `generateReport`, the retired
`uploadCvAndExtract`). All four open a session purely to hand it to a
service method (`consultant_knowledge_service.summarize/search`,
`report_service.build_report_data`) — the pattern `backend/AGENTS.md`
explicitly recommends ("receive sessions/clients through explicit
parameters"), not raw inline queries. **Zero resolvers with direct database
orchestration remain in `schema.py`** — this closes that audit finding
completely, not just reduces it.

Result: `app/graphql/schema.py` **843 → 793 lines** this slice (**1040 →
793, ~24%, across all three slices**). Verified: `ruff format --check`/
`ruff check` (clean), `mypy app` (0 issues, 48 files), `bandit -r app -q`
(exit 0), `pytest tests -q` (**127 passed**, up from 120 — 7 new, 0
removed, every pre-existing test unchanged), `alembic heads` (single head).
No API/contract change.

**Follow-up for the next session**: with the GraphQL-orchestration debt
item closed, the large-file backlog is now: `App.tsx` (1597 lines, still
growing from concurrent UI work), `SpecialistDossierPane.tsx` (1078),
`crew_query.py` (846, untouched, no direct-orchestration issue — it's large
because of genuinely complex natural-language query parsing, a different
kind of debt than schema.py's was). `schema.py` itself, at 793 lines, is
still over the 400-line threshold but no longer has a clear next extraction
target the same way it did — further reduction there would mean
decomposing the file by GraphQL concern (e.g. separate `queries.py`/
`mutations.py` modules), not moving more logic out, since the logic that
belonged elsewhere is now elsewhere.

## 2026-09-05 — Extract crew-member mutations out of graphql/schema.py (slice 2) (Claude Code)

Second slice of the large-file decomposition, picking up exactly where
slice 1's changelog entry recommended: `createCrewMember`/
`updateCrewMember`/`deleteCrewMember`, the highest-stakes resolvers left in
the file (real transaction/cache-invalidation/Dropbox-cascade ordering,
where earlier slices were pure reads).

Before touching anything, checked what was actually tested. Existing
coverage was decent but had one real, load-bearing gap:
`deleteCrewMember`'s own docstring promises "Dropbox files are removed
before database metadata so a failed remote deletion leaves the member and
their documents recoverable" — and nothing verified that invariant held. A
careless extraction (e.g. moving the DB delete before the Dropbox delete,
or losing the `raise` on Dropbox failure) would have shipped silently.
Wrote two new characterization tests first
(`backend/tests/test_crew.py`), ran them against the *unrefactored*
resolver to confirm they pass now, then extracted, then confirmed they
still pass:

- `test_delete_crew_member_retains_everything_when_dropbox_delete_fails`:
  creates a crew member with a Dropbox-backed document, forces
  `delete_from_dropbox` to fail, asserts the mutation errors *and* the crew
  member and their document are still in the database afterward.
- `test_admin_cannot_delete_own_account`: the self-delete guard had zero
  prior coverage.

Extracted into `CrewService` (`app/services/crew.py`), matching its
existing method style:
- `create_crew_member(crew: CrewMember)`: takes an already-built,
  unpersisted model instance — DTO construction and DTO→model mapping stay
  in `app/graphql/` (mapping is that layer's job per
  `docs/ARCHITECTURE.md`'s ownership table), the service just persists and
  indexes.
- `update_crew_member(crew_id, updates: dict)`: takes a plain dict of
  fields to set instead of the `CrewMemberUpdateDTO` object. Deliberate:
  importing a GraphQL-layer DTO into `app/services/` would invert the
  documented dependency direction (services must not depend on the
  transport layer). The resolver now does
  `dto.model_dump(exclude_none=True)`, which also replaced the original
  10-line if-each-field-is-not-None chain with one line — a genuine
  simplification, not just a move.
- `delete_crew_member(crew_id, requesting_user_id)`: the full cascade
  (self-delete guard, Dropbox-then-DB deletion ordering, post-commit cache
  and search-index cleanup) moved as one unit. The resolver now only reads
  `current_user` off the GraphQL context (a transport-layer concern) and
  passes the plain id through.
- Moved `_reload_crew_with_relations` from `schema.py` into `crew.py`
  alongside the methods that actually use it.
- Removed `AsyncSession`, `selectinload`, and `document_upload_service`
  imports from `schema.py` — all three became fully unused once their only
  call sites moved.

Result: `app/graphql/schema.py` **963 → 843 lines** this slice (**1040 →
843, ~19%, across both slices so far**). Verified: `ruff format --check`/
`ruff check` (clean), `mypy app` (0 issues, 48 files — caught one real typing
gap: `_reload_crew_with_relations`'s `session` parameter needs to stay typed
as `AsyncSession`, not loosened to `Any`, or the return type erases to `Any`
too), `bandit -r app -q` (exit 0), `pytest tests -q` (**120 passed**, up
from 118 — 2 new, 0 removed, every pre-existing test unchanged), `alembic
heads` (single head). No API/contract change — every GraphQL field,
argument, and response shape is identical.

**Follow-up for the next session**: `app/services/reports.py` and
`app/services/document_service.py`'s remaining mutation-side resolvers
(`uploadDocument`, `confirmExtraction`, `reprocessDocument`,
`confirmDocumentMatch`, project create/update/assign, certification
add/update/verify) are the next candidates — lower individual stakes than
crew-member delete since most already delegate to a service, but several
still do inline `select()`/session work in the resolver. `App.tsx`
(currently 1597 lines) and `SpecialistDossierPane.tsx` (1078) remain
untouched; they're a differently-shaped problem (UI state coupling, not
transaction ordering) and still actively growing from concurrent UI work,
so they're better scoped as their own session once that work settles.

## 2026-09-05 — Fix flaky/failing Playwright visual & a11y tests: wire prefers-reduced-motion into Framer Motion (Claude Code)

Closed the 12 failing e2e visual-regression tests flagged by the last audit
run — but the real bug was one level deeper than "stale snapshots."

Inspected every diff image before touching anything (per `frontend/AGENTS.md`:
"Do not update visual snapshots until the rendered change has been inspected
and confirmed intentional"). Cropped and compared the "Refine filters"
button, the result-card action icons, and the dossier header's shortlist
button pixel-for-pixel against the recent UI-polish commits' own changelog
entries — all matched exactly (button pill treatment, inline bookmark/compare
icons, expanded shortlist label), confirming these were deliberate, symmetric
(dark+light) design changes, not regressions. Ran `npm run test:e2e:update`
to accept them.

That still left 6 tests failing, non-reproducibly at first glance — but two
consecutive full `test:e2e:ci` runs against the freshly-written baselines
failed the exact same 6 tests both times, with diff images showing the
dossier pane's content doubled/ghosted vertically. That ruled out simple
staleness (a stale baseline doesn't reproduce *identically* against a
just-regenerated one) and pointed at a real timing bug: **Framer Motion
animations were still in flight when Playwright captured the screenshot**.

Root cause: `expect.toHaveScreenshot`'s `animations: 'disabled'` (already
configured) and the `@media (prefers-reduced-motion: reduce)` block in
`index.css` both only affect native CSS animations/transitions. This app's
extensive recent Framer Motion work (`AnimatePresence`, `motion.div` on
nearly every modal, card, and panel) drives animation via its own JS engine,
which neither mechanism touches — so screenshots were structurally capturing
non-deterministic mid-animation frames, and (very likely) so was an axe-core
accessibility scan that hit one transient low-contrast frame in one earlier
run (a color-contrast violation on the filter dialog that never recurred
once this fix landed — same root cause, different symptom).

Fix, applied at the source rather than papered over with a sleep in the
tests:
- `frontend/src/main.tsx`: wrapped the app in `<MotionConfig
  reducedMotion="user">` (re-exported from `framer-motion` via the `motion`
  package) — this is what actually makes Framer Motion check
  `prefers-reduced-motion` at runtime; the app previously had zero code path
  that did this despite `frontend/AGENTS.md` explicitly requiring it.
- `frontend/playwright.config.ts`: added `contextOptions: { reducedMotion:
  'reduce' }` so every test browser context requests it deterministically
  (`reducedMotion` isn't a top-level `use` option in this Playwright
  version's types — it nests under `contextOptions`).
- Regenerated all 12 snapshot baselines with motion now actually settled.

Verified motion is genuinely fixed, not lucky: ran `npm run test:e2e:ci`
**three consecutive times** after the fix — **90 passed, 2 skipped, 0
failed, every time** (previously: different-looking failures depending on
which run). Also verified in a live dev server that the app still renders
and the menu drawer still opens/animates correctly with `MotionConfig` in
place — wrapping the whole tree in a context provider is exactly the kind of
change that's easy to get subtly wrong. `npm run lint` (0 errors — Playwright
config typing required the `contextOptions` nesting fix above), `npm run
test` (54 passed), `npm run build` (134.76 kB entry chunk, no warning —
bundle fix from two sessions ago still holding), `npm run ui:audit:strict`
(0 findings), `npm audit` (0 vulnerabilities).

No API/contract change. This is a test-infrastructure and accessibility-
implementation fix, not a product behavior change — the app looks and
behaves identically to a user with no motion-reduction preference; it's
Playwright's synthetic browser context, and any real user with
`prefers-reduced-motion` set, that now actually gets what
`frontend/AGENTS.md` already promised.

## 2026-09-05 — Extract direct DB orchestration out of graphql/schema.py (slice 1) (Claude Code)

First slice of the large-file decomposition flagged since
`docs/AUDIT_2026-09-02.md` (P2 #9, 1006 lines at the time; P2 #10 — "GraphQL
schema ... contain[s] direct database orchestration", listed as a known
legacy exception in `docs/ARCHITECTURE.md`). Treated as a genuine multi-slice
project rather than one pass: `docs/ARCHITECTURE.md` explicitly calls for
"extract cohesive use cases/components gradually, with characterization
tests and no behavior-changing big-bang rewrite," so this covers exactly the
`project`/`projects`/`documentsByCrew`/`generateReport` resolvers — the ones
doing raw `select()` calls directly in the GraphQL layer instead of calling a
service — and stops there. `App.tsx`, `SpecialistDossierPane.tsx`, and
`crew_query.py` are unchanged; still open for future slices.

None of these four resolvers had any prior test coverage (`generateReport`
especially — a ~100-line branch with an LLM-success path and a
deterministic-fallback path, both completely unverified). Wrote
characterization tests first, ran them against the *unrefactored* code to
confirm they genuinely capture current behavior, then extracted, then
confirmed the same tests still pass unchanged — the standard "prove it's a
move, not a rewrite" sequence, not skipped for expediency:

- `backend/tests/test_project_and_document_queries.py` (new, 4 tests):
  `project`, `projects` (including status filtering), `documentsByCrew`
  (including that it doesn't leak another crew member's documents).
- `backend/tests/test_generate_report.py` (new, 5 tests): all four
  `ReportType` variants' deterministic data-building, plus the LLM-enriched
  success path overriding the fallback summary/data.
- `app/services/project.py` (new): `ProjectService.get_project` /
  `.list_projects`, matching the existing `CrewService`/`DocumentService`
  pattern exactly (plain class, `get_session_factory()` per method, no
  constructor state).
- `app/services/document_service.py`: added `get_documents_by_crew`
  alongside the existing `get_document`/`get_pending_documents`.
- `app/services/reports.py`: added `build_report_data` (the deterministic
  data-gathering per report type) and `build_fallback_summary` (the
  LLM-failure fallback text), both taking an explicit `AsyncSession`
  parameter rather than opening a hidden connection — `ReportService` didn't
  previously touch the database at all, only LLM formatting.
- `app/graphql/schema.py`: the four resolvers now call these services and
  map the result; removed the `Select`/`Any` imports that became unused once
  the multi-branch `stmt` reassignment (previously typed `Select[Any]` to
  let mypy accept different row types across branches) moved into
  `build_report_data`, where each branch returns immediately and needs no
  shared variable.

Result: `app/graphql/schema.py` **1040 → 963 lines** (still well over the
400-line threshold — this is one slice, not the fix). Verified:
`ruff format --check`/`ruff check` (clean), `mypy app` (0 issues, 48 files),
`bandit -r app -q` (exit 0), `pytest tests -q` (**118 passed**, up from 109 —
9 new, 0 removed, all pre-existing tests unchanged), `alembic heads` (single
head). No API/contract/schema change — every GraphQL field, argument, and
response shape is identical; this is purely which Python function executes
the query.

**Follow-up for the next session**: the highest-value next slice is
probably the crew-member mutations (`createCrewMember`/`updateCrewMember`/
`deleteCrewMember`) — they carry real transaction/cache-invalidation/
Dropbox-cascade ordering that's currently correct but embedded in the
resolver, and moving it needs the same characterization-tests-first
discipline given the higher stakes (cache invalidation only after commit,
Dropbox-delete-before-DB-delete ordering in `deleteCrewMember`). Frontend
`App.tsx`/`SpecialistDossierPane.tsx` decomposition is a separate, larger
effort with different risk shape (tightly-coupled local state, not
transaction ordering) — better scoped on its own.

## 2026-09-05 — Remove unused `@google/genai` dependency; review mockProfiles bundle cost (Claude Code)

Closed one of the two small cleanup items flagged during the bundle-size fix
and reviewed the other rather than forcing it in.

- **Removed `@google/genai`** from `frontend/package.json`: confirmed zero
  imports anywhere in `src/`, scripts, or tests (grepped the whole tree, not
  just a hunch — this project's AI features run through the backend/Ollama
  per `docs/ARCHITECTURE.md`, not a client-side Gemini SDK; `@google/genai`
  and `GEMINI_API_KEY` in `.env` look like leftover AI-Studio-template
  scaffolding, per the `vite.config.ts` comment referencing "AI Studio").
  Also dropped its now-dead entry from `vite.config.ts`'s `manualChunks`
  vendor pattern. `npm install` removed 37 packages from the dependency
  tree; the production build output is byte-identical (same chunk names/
  sizes) confirming it was never actually reachable in the shipped bundle —
  this is a `package.json`/node_modules cleanliness fix, not a size fix.
- **Reviewed, did not change, `src/data/mockProfiles.ts`**: it's a
  362-line fabricated-profile fallback (24.9 kB source, ~7.3 kB gzip) used
  by `useCrewProfiles.ts` only when `DEMO_MODE_ENABLED` is true, which
  `docker-compose.yml` correctly defaults to `false` and
  `docker-compose.prod.yml` doesn't override — so this is a deliberate,
  correctly-gated demo/showcase feature, not the mock-data-in-production
  violation `frontend/AGENTS.md` warns about. It does still ship in the
  bundle unconditionally (static import), so a dynamic `import()` gated on
  `DEMO_MODE_ENABLED` would trim a few KB gzip further. Chose not to do
  that here: `useCrewProfiles` is core, currently-untested data-loading
  plumbing used app-wide, and reworking it to async-load a fallback for a
  ~4-6 kB gzip saving (out of a 37 kB entry chunk) is a worse risk/reward
  trade than the mechanical fixes in this session — flagging for a future
  session with a test added first, not fixing blind.

Verified: `npm run lint` (0 errors), `npm run test` (54 passed), `npm run
build` (byte-identical chunk sizes to the prior build), `npm run
ui:audit:strict` (0 findings), `npm audit` (0 vulnerabilities). No app code
changed. No migration, no API/contract change.

## 2026-09-05 — Refine Specialist Dossier Pane and Profile Detail Modal (Antigravity)

Elevated the specialist detail presentation in `SpecialistDossierPane.tsx` and `ProfileDetailModal.tsx`:
- **Avatar framing & presence**: Upgraded profile modal avatars to `w-16 h-16 rounded-2xl` with an inset border ring (`ring-1 ring-border-subtle/80 shadow-sm`) and `ring-2 ring-surface` border on availability indicators.
- **Header actions standard**: Upgraded modal shortlist button to an explicit 44px `Shortlist`/`Saved` pill with filled active state, added an active `Comparing` badge, and standardized focus mode, close, and 3-dots trigger controls to `min-h-11 min-w-11` (44px touch targets).
- **Navigation tabs**: Upgraded dossier section tabs (`sectionButtonClass`) to `min-h-11` with active pill indicator and refined metadata counters.

Verified: `npm run lint` (0 errors), `npm run test` (54 passed), `npm run build` (all chunks clean), `npm run ui:audit:strict` (66 files, 0 findings), deployed to container.

## 2026-09-05 — Elevate candidate comparison selection and floating dock (Antigravity)

Substantially improved the candidate comparison experience across `App.tsx` and `ComparisonBar.tsx`:
- **Direct 1-click comparison controls**: Added dedicated `Scale` icon action buttons in both Grid Cards and Split View list items, eliminating the need to drill into the 3-dots menu to compare candidates.
- **Active card highlight & comparing badge**: Cards added to comparison now gain an immediate elevated border and soft surface tint (`border-2 border-border-strong shadow-md ring-1 ring-border-strong/50`), plus a subtle `Comparing` badge in the header.
- **Slot-based floating comparison dock**: Replaced the generic overlapping avatar circles in `ComparisonBar.tsx` with dedicated comparison slots displaying avatar, name, and rate, plus an open slot prompt (`+ Select 1 more to compare`), 44px min-height action targets, and mobile-friendly removal controls.

Verified: `npm run lint` (0 errors), `npm run test` (54 passed), `npm run build` (all chunks clean), `npm run ui:audit:strict` (66 files, 0 findings), deployed to container.

## 2026-09-05 — Refine Hero search and discovery cards for executive showcase (Antigravity)

Refined the entry hero and search experience in `ModernHeroSearch.tsx`:
- **Search container depth**: Enhanced the search box with `bg-surface/90 backdrop-blur-sm`, permanent subtle 1px border contrast (`border-border-subtle hover:border-border-strong`), and focused ring elevation (`ring-2 ring-focus/25 bg-surface`).
- **Showcase discovery chips**: Elevated prompt chips with pill styling (`rounded-full px-3.5 py-1.5 text-xs font-medium`), active contrast ring, and added a dedicated `Environmental Lead` quick preset.
- **Executive 3-pillar feature cards**: Upgraded the Discover, Shortlist, and Request summary blocks into discrete micro-cards with individual icon containers and border contrast.
- **Editorial typography**: Tightened headline tracking (`tracking-[-0.03em]`) and refined font weights.

Verified: `npm run lint` (0 errors), `npm run test` (54 passed), `npm run build` (all chunks clean), `npm run ui:audit:strict` (66 files, 0 findings), live container deployed.

## 2026-09-05 — Refine Specialist cards, table actions, and avatar framing for executive showcase (Antigravity)

Polished the specialist presentation layer in `App.tsx`, `SpecialistTableView.tsx`, and `SpecialistDossierPane.tsx` for executive showcase standards with restrained precision styling and zero visual clutter:
- **Card surface & border fidelity**: Updated grid cards from fragile `border-transparent` to permanent, subtle `border-border-subtle hover:border-border-strong bg-surface hover:bg-surface-raised/40` with smooth elevation shadows in both dark and light modes.
- **Avatar framing & availability indicators**: Refined avatars to `h-12 w-12` (grid) and `w-9 h-9` (table) with an inset border ring (`ring-1 ring-border-subtle/80`) and clean `ring-2 ring-surface` border for immediate availability dots.
- **Direct tactile bookmarking controls**: Placed a direct 1-click bookmark button in both grid card headers and split-view list items, plus an explicit 44px `Shortlist`/`Saved` button in `SpecialistDossierPane.tsx`.
- **Table action targets**: Upgraded action button targets in `SpecialistTableView.tsx` to `min-h-11 min-w-11` (44px standard) with accessible labels and tooltips.
- **Vendor bundle code-splitting**: Configured path-based `manualChunks` in `frontend/vite.config.ts` to properly split deep imports (`react-dom/client`, `@apollo/client`, `motion`, `d3`), eliminating oversized entry chunks.

Verified: `npm run lint` (0 errors), `npm run test` (54 passed), `npm run build` (all chunks clean), `npm run ui:audit:strict` (66 files, 0 findings), `git diff --check` (clean).

## 2026-09-05 — Wire the Playwright e2e suite into CI (Claude Code)

Closed the last standing CI-completeness gap the strict repo audit had
flagged three rounds running: `.github/workflows/ci.yml`'s frontend job
never ran `npm run test:e2e:ci`, despite it being in both `AGENTS.md`
files' required gate list, so a green CI run still wasn't proof of the
full documented bar.

Checked first whether this was actually safe to add rather than assuming
it: the suite (`authenticated-flow.spec.ts`, `auth-gate.spec.ts`,
`ui-consistency.spec.ts`) fakes auth via `localStorage` and mocks every
GraphQL call via Playwright's `page.route()` — it needs no database,
Redis, Meilisearch, or backend process. `playwright.config.ts`'s
`webServer` starts its own Vite dev server, and the existing snapshot
filenames already carry a `-linux` suffix matching the `ubuntu-latest`
runner. So this was a real "just wire it in," not a hidden infra project.

- Added `Install Playwright browsers` (`npx playwright install --with-deps
  chromium` — only `chromium` is needed since all four projects
  (`mobile`/`tablet`/`desktop`/`wide`) use it) and `E2E tests (Playwright)`
  (`npm run test:e2e:ci`) steps to the frontend CI job, after the existing
  build/UI-audit steps, matching the order already documented in
  `docs/ENGINEERING_STANDARDS.md`'s required gate list.
- Verified by running the exact CI command (`npm run test:e2e:ci`, which
  sets `CI=1`) locally, not just reading the config: 90 passed, 2 skipped,
  ~28s, across all four viewport projects.

No app code changed. No migration, no API/contract change.

## 2026-09-05 — Fix main bundle chunk size: broken manualChunks + 3 more lazy modals (Claude Code)

Closed the bundle-size finding from the strict repo audit (main chunk 381.57 kB
minified / 112.63 kB gzip, over Vite's 250 kB warning). Root cause was a real
bug, not just missing effort: `vite.config.ts`'s `manualChunks` was
object-form, keyed by bare specifier (`react: ['react', 'react-dom']`, etc.).
Object-form only routes the *exact* listed module — `main.tsx` imports
`createRoot` from `'react-dom/client'`, a different resolved module than bare
`'react-dom'`, so all of `react-dom`'s actual implementation
(`react-dom-client.production.js`) fell through into the entry chunk instead
of the `react` chunk, which is why that chunk was previously a suspicious
3.89 kB — it held nothing real. The same bare-specifier gap let a chunk of
`framer-motion`'s internals (the package `motion` depends on and re-exports)
leak into the entry chunk too, past the `motion: ['motion']` entry.

- Rewrote `manualChunks` as a function matching on the resolved
  `node_modules/<pkg>/` path instead of the bare import specifier, so every
  subpath and transitive internal file of `react`/`react-dom`/`scheduler`,
  `@apollo/client`/`graphql`, `motion`/`framer-motion`, `d3`/`d3-*`, and
  `lucide-react`/`@google/genai` lands in its intended chunk regardless of
  which entry point pulled it in. Verified via Vite's own build API
  (`vite.build({ write: false })`, inspecting each chunk's `.modules` map) —
  not guesswork — before and after.
- `AddCrewMemberModal`, `AppMenuDrawer`, and `FilterModal` (which pulls in the
  25 kB `FilterSidebar`) were statically imported in `App.tsx` despite being
  interaction-gated (menu/filter/add-crew), and two of the three were already
  rendered inside the existing `<Suspense fallback={null}>` block used for
  every other on-demand modal — just never converted to `lazy()`. Converted
  all three to the exact `lazy(() => import(...).then(...))` pattern already
  used for the other 8 lazy components in this file; added a dedicated
  `<Suspense>` around `AppMenuDrawer`, the one of the three rendered outside
  that block.
- Result: entry chunk **381.57 kB → 130.41 kB** minified (**112.63 kB →
  37.34 kB gzip**) — no chunk-size warning at all on this build. `react` now
  correctly carries 193.82 kB (was fake); `motion` grew to 128.88 kB
  (correctly absorbing what used to leak). This project's own gzip bundle
  budget plugin (`gzipBundleBudget` in `vite.config.ts`, 150 KiB gzip
  entry / 100 KiB async, already enforced as a hard build error) was already
  satisfied before this change (112.63 < 150) — so the real, meaningful
  problem here was the misconfigured vendor split and unnecessary eager
  loading, not a budget that needed loosening. Fixing it directly is why
  this holds up as more than a number chase.

Not addressed here: `@google/genai` is listed as a manual-chunk vendor
package but is never imported anywhere in `src/` — dead production
dependency (unlike the `express` devDependency removed in the prior CI-gate
fix, this one costs nothing in the shipped bundle since Rollup only bundles
what's actually imported, so it's a `package.json`/node_modules cleanliness
issue, not a runtime one). Flagging, not fixing, to keep this change focused
on the bundle-size acceptance criterion. `src/data/mockProfiles.ts` (in the
entry chunk for `FILTER_PRESETS`) is also worth a follow-up look given
`frontend/AGENTS.md`'s "no mock profiles/placeholder fallbacks in production
data paths" rule — not investigated here, same reason.

Verified: `npm run lint` (0 errors), `npm run test` (54 passed), `npm run
build` (no warnings, gzip budget plugin passes), `npm run ui:audit:strict`
(66 files, 0 findings). Manually exercised in a live dev server: unauthenticated
shell loads, the lazily-loaded `AppMenuDrawer` opens correctly with no console
errors, and the lazily-loaded `LoginPage` renders/submits correctly (the
submit itself hit an unrelated CORS error from a stray already-running
preview container occupying the expected dev port — an environment
collision, not a regression; confirmed via console output, not touched).
Could not manually exercise the authenticated `FilterModal`/
`AddCrewMemberModal` paths for the same reason. No API/contract/migration
change.

## 2026-09-05 — Fix currently-failing CI security/vuln gates and pin floating image tags (Claude Code)

A repo-wide strict audit (comparing actual gate output against
`docs/AUDIT_2026-09-02.md` and `docs/ENGINEERING_STANDARDS.md`, not just the
changelog's self-reported numbers) found that two gates CI already runs as
blocking (no `|| true`) were failing on `main` right now, undetected because
no prior session had run the full `-r app` bandit scan or `npm audit` and
reported the complete output:

- **Backend SAST (`bandit -r app/ -q`) was failing**: 7 findings across
  `app/services/upload.py`, `app/api/dropbox.py`, `app/services/dropbox_auth.py`,
  `app/main.py`, and `app/services/extraction.py`.
  - 7 × B113 (`httpx.AsyncClient()` constructed with no `timeout=`): all were
    Dropbox network calls. Most already passed `timeout=` to the individual
    `.request()`/`.post()` call and so were not actually unbounded at runtime,
    but bandit only inspects the client constructor — moved the timeout onto
    `AsyncClient(timeout=...)` itself at all 7 call sites (30s for metadata/
    listing calls, 60s for content upload/download, matching the existing
    per-call values where one was set).
  - 2 × B110 (`except Exception: pass`) — silent failure with zero
    diagnostics, violating this repo's own "degraded operation must be
    intentional and visible" rule: Meilisearch index setup at startup
    (`app/main.py`) and vision-prompt formatting (`app/services/extraction.py`)
    now log a warning instead of swallowing the exception. No behavior change
    otherwise — both remain non-fatal by design.
  - 1 × B105 (hardcoded-password heuristic false-positive on
    `TOKEN_URL = "https://api.dropbox.com/oauth2/token"`, flagged only because
    the constant name contains "token"): suppressed with `# nosec B105`,
    matching the exact convention already used in `app/main.py` for the same
    check, with a one-line comment stating why it's safe.
- **Frontend vulnerability scan (`npm audit --audit-level=moderate`) was
  failing**: 3 moderate transitive vulnerabilities (`qs`/`body-parser`) via a
  direct devDependency, `express@^4.21.2`. Grepped the full frontend source,
  tests, scripts, and config for any import/usage — none exists; it has been
  dead weight since the frontend's first commit. Removed it from
  `package.json` and regenerated `package-lock.json` rather than bumping a
  version, since the real fix was deleting an unused dependency, not
  patching one.
- **Unpinned infra images** (`docs/AUDIT_2026-09-02.md` P2 #13): pinned
  `docker.io/qdrant/qdrant:latest` → `v1.19.0` and
  `docker.io/ollama/ollama:latest` → `0.33.2` in `docker-compose.yml`,
  matching the versions actually pulled/running locally (verified via
  `podman inspect` image labels and `ollama --version`) so this is a lock,
  not a version bump. `docker-compose.prod.yml` doesn't redefine either
  image and inherits the pin.
- **CI gate coverage gap**: `.github/workflows/ci.yml`'s backend job never
  ran `alembic heads`, despite it being in both `AGENTS.md` files' required
  gate list. Added it as a final step; confirmed it needs no database
  connection or `.env` (`env -i` smoke test), so it's safe in CI as-is.

Not fixed in this pass, and deliberately not attempted here because they are
broad refactors rather than mechanical fixes (mixing them into this diff would
violate the "don't combine fixes with broad refactoring" rule): the frontend
main bundle chunk (381.57 kB minified, no code-splitting) and the large-file
list from `docs/AUDIT_2026-09-02.md` P2 #9, both of which have grown since
that audit rather than shrunk. Recommend a dedicated session for each.

Verified: `ruff format --check`, `ruff check`, `mypy app` (0 issues/47 files),
`bandit -r app -q` (exit 0, was exit 1), `pytest tests -q` (109 passed, 2
deselected), `alembic heads` (single head, works with no env vars set),
`npm run lint` (0 errors), `npm run test` (54 passed), `npm run build`,
`npm run ui:audit:strict` (66 files, 0 findings), `npm audit
--audit-level=moderate` (0 vulnerabilities, was 3), `pip-audit --strict` (0
vulnerabilities), `git diff --check` (clean). No migration, no API/contract
change, no auth change.

**Note for the next session**: `frontend/AGENTS.md` and several
`frontend/src` files were being edited by a concurrent session
(Antigravity, see the entry below) while this one ran — left entirely
untouched here; only `frontend/package.json`/`package-lock.json` were
touched on the frontend side.

## 2026-09-05 — Frontend UI consistency, modal motion overhaul, strict type safety & E2E suite hardening (Antigravity)

Audit, bug fixes, type-safety hardening, systematic animation harmonization, and end-to-end verification across the frontend:

- **Modal & Dialog Motion Standardization**:
  - `frontend/src/components/LoginPage.tsx`: Integrated `AnimatePresence` and Framer Motion into the modal presentation with smooth backdrop blur fade (`opacity: 0` -> `1`) and card entrance/exit scaling (`scale: 0.96, y: 8` -> `scale: 1, y: 0`), adhering to `frontend/AGENTS.md` modal surface token standards (`rounded-[14px]`, `border-border-subtle`, `bg-surface`, `shadow-2xl`). Standardized close button label to `Close dialog`.
  - `frontend/src/App.tsx`: Moved `LoginPage` inside the primary preloaded `<Suspense>` block with controlled `isOpen={isLoginOpen}`, eliminating lazy-chunk download delays on click and enabling smooth exit transitions.
  - `frontend/src/components/ConfirmDialog.tsx`: Upgraded to `AnimatePresence` and `motion.div` with standardized backdrop (`bg-canvas/80 backdrop-blur-xs`) and scale/slide transitions.
  - `frontend/src/components/DocumentUploadModal.tsx`: Upgraded with `AnimatePresence` and `motion.div` modal card transitions.
  - `frontend/src/components/DocumentPreviewModal.tsx`: Converted from legacy `bg-black/80` and CSS `ui-overlay-enter` to `AnimatePresence` + `motion.div` with semantic tokens and smooth exit animations.
  - `frontend/src/components/SpecialistDossierPane.tsx`: Modernized the Skills Radar dialog to use `AnimatePresence` and `motion.div` with semantic `bg-canvas/80 backdrop-blur-xs`.
  - `frontend/src/components/AddCrewMemberModal.tsx`: Replaced ad-hoc `keydown` event listener with `useAccessibleDialog` focus trap, Escape handler, and focus restoration.
  - `frontend/src/index.css`: Removed legacy `.ui-overlay-enter`, `.ui-surface-enter`, `.ui-drawer-enter` classes and keyframes now that all dialogs use unified Framer Motion springs.
- **Automated CI Regression Guard for UI Consistency (`scripts/ui-audit.mjs`)**:
  - Enhanced static analyzer `npm run ui:audit:strict` with rules enforcing:
    1. Every `*Modal.tsx` and component declaring `role="dialog"` or `role="alertdialog"` must include `<AnimatePresence>`, `<motion.div>`, and `useAccessibleDialog`.
    2. Zero legacy CSS overlay animation classes (`ui-overlay-enter`, `ui-surface-enter`, `ui-drawer-enter`).
    3. Zero raw color modal backdrops (`bg-black`, `bg-white`).
  - Documented mandatory modal & dialog motion contract in `frontend/AGENTS.md`.
- **Strict Type Safety & Non-Null Assertion Elimination (`npm run lint`)**:
  - Replaced all 14 `@typescript-eslint/no-non-null-assertion` instances across `useAccessibleDialog.ts`, `useSearchWorkspace.ts`, `mappers.ts`, `main.tsx`, `filterUtils.ts`, and `filterUtils.test.ts` with explicit type guards, nullish coalescing fallbacks, and safe index narrowing. `npm run lint` now passes with **0 errors and 0 warnings**.
  - Generalized `useAccessibleDialog<T extends HTMLElement>` to accept any subtype of `HTMLElement`, maintaining type safety without casts.
- **Accessibility & ARIA Compliance**:
  - `frontend/src/components/AppMenuDrawer.tsx`: Replaced `<motion.aside role="dialog">` with `<motion.div role="dialog">`, fixing the W3C ARIA violation where `role="dialog"` was applied to an HTML `<aside>` element.
  - `frontend/tests/ui-consistency.spec.ts`: Added assertion to wait for the drawer dialog to complete its exit transition before executing full-page axe-core audits in light mode.
- **Dossier Systems Experience & Empty State Rendering**:
  - `frontend/src/components/SpecialistDossierPane.tsx`: Resolved a rendering bug where `systemsCategories` was always initialized as an object of empty arrays, causing the section to render empty tags without displaying the intentional empty-state message (`No systems experience was found in the CV.`). Added `hasSystemsCategories` validation to properly display empty states.
  - `frontend/tests/authenticated-flow.spec.ts`: Aligned the progressive disclosure test with the unified `Systems experience` secondary section and empty state assertion.
- **Visual Baseline Synchronization**:
  - Updated Playwright snapshot baselines across mobile, tablet, desktop, and wide viewports to reflect the verified contractor card design and split-pane layout.
- **Verification**:
  - `npm run test:quality` (`lint`, `build`, `ui:audit:strict`, and `test:e2e:ci`) passed with 100% success (0 lint issues, 54 unit tests passing, 90 e2e tests passing, clean UI audit).

## 2026-09-05 — Correction: the "3 pre-existing mypy errors" no longer reproduce (Claude Code)

Was asked to fix the 3 mypy errors flagged in the "Fix Meilisearch
filter-injection" entry below (`app/services/cache.py:28` unused-ignore;
`app/services/meilisearch.py:175`/`:236` no-any-return in
`search_crew_members`/`search_documents`). Investigated before patching:

- Removing the `# type: ignore[no-untyped-call]` in `cache.py` reintroduces a
  real error — `redis.asyncio.utils.from_url` is still genuinely untyped
  (`def from_url(url, **kwargs):`, no annotations) under the pinned
  `redis==6.2.0`. The ignore is correct and still required.
- Adding an `isinstance(result, dict)` guard around `index.search(...)` in
  `meilisearch.py` would be dead validation: `meilisearch==0.28.0` ships real
  inline types and `Index.search()` is already typed
  `-> Dict[str, Any]`, so returning it from a `-> dict[str, Any]` function is
  not an Any-return under mypy's actual analysis.
- Verified with `mypy app` against both the existing `.venv` (already at
  pinned versions) and a from-scratch venv built only from
  `requirements.txt` + `requirements-dev.txt`: **0 errors, 47 files clean**
  in both.

Root cause of the original report: that session's own note says its venv was
"missing `mypy` and `qdrant-client` despite both being pinned" and had them
patched in ad hoc rather than installed via a clean `pip install -r
requirements-dev.txt` — the same reproducibility gap `docs/AUDIT_2026-09-02.md`
P2 #12 already flagged. Whatever was installed at the time (most likely an
older `meilisearch` or `redis`) genuinely produced those 3 errors then; they
don't exist against the current pins. No code changes made — `cache.py` and
`meilisearch.py` are correct as committed. Follow-up: rebuild the backend venv
from `requirements*.txt` at the start of a session rather than patching
individual packages into whatever venv is already present.

## 2026-09-05 — Fix `pip install -e .` on backend flat layout (Claude Code)

Closed a real, previously-flagged CI-breaking bug (noted as out-of-scope in
the 2026-09-02 "Authorization matrix" session): `backend/pyproject.toml` had
no `[tool.setuptools]` package config, and the flat layout (`app/`, `tests/`,
`alembic/`, `data/`, plus loose scripts like `seed_100.py` all top-level,
with both `app/` and `tests/` carrying `__init__.py`) gave setuptools two
plausible top-level packages to choose between. Automatic discovery refuses
to guess in that case and `pip install -e .` — the exact command
`.github/workflows/ci.yml`'s backend job runs — failed outright.

- Added `[build-system]` (`setuptools>=68`) and
  `[tool.setuptools.packages.find] include = ["app*"]` so only `app` and its
  subpackages install; `tests/`, `alembic/`, `data/`, and the loose root
  scripts are correctly left alone (they were never meant to be an
  installed package).
- Verified: built a clean venv and ran `pip install -e . --no-deps`, then
  confirmed `import app` resolves to the workspace source — the CI failure
  mode is actually gone, not just plausible-looking. `ruff check`,
  `pytest tests -q` (109/109), and `alembic heads` (single head) still clean.

## 2026-09-05 — Fix Meilisearch filter-injection in /api/search/* (Claude Code)

Closed a real, previously-flagged-but-unfixed security bug (noted in the
2026-09-02 "Real strict typing" session as found-but-out-of-scope): `backend/
app/api/search.py` spliced the `availability`, `classification`, and
`crew_id` query params unescaped into Meilisearch filter strings via
f-string (`f'availability_status = "{availability}"'`). Meilisearch filters
are interpreted, not parameterized, so a value containing `"` could break out
of the intended clause and inject arbitrary filter syntax.

- `availability` and `classification` are now allowlisted against the
  canonical enums already owned by `app/domain/fields.py`
  (`AVAILABILITY_STATUS_VALUES`, `DOCUMENT_CLASSIFICATIONS`) instead of a new
  parallel list — a mismatch returns `422` with a machine-readable message.
- `crew_id` is validated as a well-formed UUID (`CrewMember.id` is generated
  via `uuid.uuid4()`) before it reaches the filter string.
- Added `backend/tests/test_search_filter_injection.py`: regression tests
  proving injection payloads are rejected with `422` and that valid inputs
  still produce the expected filter clause.
- Verified: `ruff format --check` / `ruff check` clean on the changed files,
  `pytest tests -q` 109/109 passing, `bandit -r app/api/search.py` clean,
  single Alembic head. `mypy app` shows 3 pre-existing errors in
  `app/services/cache.py` and `app/services/meilisearch.py` (unrelated to
  this change, not introduced by it — flagged, not fixed, to keep this slice
  small).

**Environment note:** this session's backend virtualenv was missing `mypy`
and `qdrant-client` despite both being pinned in `requirements-dev.txt`/
`requirements.txt` — installed them to actually run the gates rather than
skip them. This is the same environment-reproducibility gap
`docs/AUDIT_2026-09-02.md` P2 #12 already flagged; worth a `pip install -r
requirements-dev.txt` at session start going forward.

## 2026-09-05 — Application-wide smooth transitions & exit animations overhaul (Antigravity)

Comprehensive refactor eliminating abrupt component pops and unmount jumps across all workspace interactions and modals:

- **Modals & Drawers (`AnimatePresence` Exit Transitions)**:
  - `frontend/src/components/AppMenuDrawer.tsx`: Replaced static CSS classes with Framer Motion slide-in drawer (`initial={{ x: '100%' }}`, `animate={{ x: 0 }}`, `exit={{ x: '100%' }}`) and fading backdrop overlay (`exit={{ opacity: 0 }}`).
  - `frontend/src/components/CandidateCompareModal.tsx`: Added Framer Motion enter/exit animations (`scale: 0.96, y: 8` -> `scale: 1, y: 0`) and backdrop fade on unmount.
  - `frontend/src/components/MobilizationInquiryModal.tsx`: Wrapped in `AnimatePresence` with smooth enter and exit motion for backdrop and modal surfaces.
  - `frontend/src/components/FilterModal.tsx`: Added `AnimatePresence` with smooth scaling and fading overlay.
  - `frontend/src/components/ShortcutsModal.tsx`: Wrapped with `AnimatePresence` and spring-free ease curves.
  - `frontend/src/components/ExportShortlistModal.tsx`: Added `AnimatePresence` with smooth scale/fade exit.
  - `frontend/src/components/AddCrewMemberModal.tsx`: Added `AnimatePresence` with smooth exit for backdrop and dialog card.
  - `frontend/src/components/ProfileDetailModal.tsx`: Upgraded modal shell to `motion.div` and wrapped instance in `AnimatePresence`.
- **Workspace View Mode Transitions (`App.tsx`)**:
  - Wrapped view mode containers (`split`, `table`, `grid`) in `<AnimatePresence mode="wait">` keyed by `viewMode` with directional fade/slide (`initial={{ opacity: 0, y: 6 }}`, `animate={{ opacity: 1, y: 0 }}`, `exit={{ opacity: 0, y: -6 }}`), eliminating visual layout jumps when toggling views.
- **Dynamic Elements & Notification Banners**:
  - `frontend/src/components/ActiveFilterChips.tsx`: Added Framer Motion `layout` and `<AnimatePresence>` to active filter chips so badges glide together smoothly when individual filters are dismissed.
  - `frontend/src/components/ComparisonBar.tsx`: Wrapped floating bottom action bar in conditional `AnimatePresence` so it slides out cleanly to `y: 80` when cleared or dismissed.
  - `frontend/src/components/Toast.tsx`: Replaced CSS animation with `AnimatePresence` + `motion.div` (`initial={{ opacity: 0, y: 16 }}`, `animate={{ opacity: 1, y: 0 }}`, `exit={{ opacity: 0, y: 16 }}`), ensuring toast notifications fade out smoothly upon auto-dismissal.
- **Verification**:
  - `npm run lint` (0 errors), `npm run ui:audit:strict` (PASS across all 66 source files), `npm test` (54 tests passing), `npm run build` (clean bundle), deployed and running on port 5173.

## 2026-09-04 — Lighthouse audit & web vitals optimization (Antigravity)

Conducted end-to-end Lighthouse audit and resolved all flagged opportunities, boosting scores across all core categories:

- **Audit Results**:
  - **Performance**: `97 / 100` (FCP: 1.0s, LCP: 1.1s, CLS: 0, TBT: 0ms, Speed Index: 1.0s)
  - **Accessibility**: `100 / 100`
  - **Best Practices**: `100 / 100` (improved from 92)
  - **SEO**: `100 / 100` (improved from 92)
- `frontend/src/initTheme.ts` & `frontend/index.html`:
  - Migrated inline theme determination script from `index.html` to a bundled pre-render module (`initTheme.ts`), resolving the Content Security Policy (CSP) violation for inline scripts (`script-src 'self'`).
- `frontend/public/robots.txt`:
  - Created standard crawler `robots.txt`, resolving the 404/SPA index.html fallback error flagged by search engine crawlers.
- `frontend/nginx.conf.template`:
  - Configured 1-year immutable caching for fingerprinted static assets (`Cache-Control: public, max-age=31536000, immutable`) and revalidation rules for `index.html`.
- `frontend/src/App.tsx`:
  - Added explicit intrinsic `width={104}` and `height={28}` attributes to the header brand logo image, eliminating unsized image warnings and preventing Cumulative Layout Shift (CLS).

## 2026-09-04 — Specialist comparison flow, avatar photos & single-contractor quick-add (Antigravity)

Fixed unresponsive comparison button when 1 contractor is selected, restored profile avatar images, and enhanced single-candidate comparison flow:

- `frontend/src/components/CandidateCompareModal.tsx`:
  - Restored contractor avatar images (`img` element with `referrerPolicy="no-referrer"` and graceful monogram fallback on missing/error) so specialist photos display properly in each column card.
  - Added an in-modal guidance banner when 1 contractor is selected with an accessible quick-add select dropdown right at the top of the matrix to immediately pick a second specialist to compare side by side.
  - Fully supports seamless matrix comparison whether initiated from the workspace list or directly within the modal.
- `frontend/src/components/SpecialistTableView.tsx`:
  - Added specialist avatar image support (`img` with initials fallback) in table rows matching card and modal representations.
- `frontend/src/components/ComparisonBar.tsx`:
  - Removed disabled state on the primary comparison button when 1 profile is selected so users can click into the comparison modal immediately.
  - Replaced misleading static text with actionable CTA: `Compare (1) · Add more` when 1 is selected, and `Compare Matrix (N)` when 2 or more are selected.
  - Aligned button styling with design system semantic tokens (`min-h-9 px-3.5 rounded-lg bg-action hover:bg-action-hover text-on-action focus-visible:ring-2 focus-visible:ring-focus`).

## 2026-09-04 — Specialist comparison matrix (CandidateCompareModal) polish (Antigravity)

Polished the side-by-side specialist comparison modal (`CandidateCompareModal.tsx`) to strictly adhere to design system tokens and dual-theme fidelity:

- `frontend/src/components/CandidateCompareModal.tsx`:
  - Standardized the modal shell with `bg-surface border border-border-subtle rounded-[14px] shadow-2xl` and backdrop blur (`bg-canvas/80 backdrop-blur-xs`).
  - Replaced legacy column card borders and background colors with `rounded-[14px] bg-surface-raised/40 border-border-subtle hover:border-border-strong`.
  - Upgraded avatars to high-contrast monogram square avatars (`rounded-[10px] bg-surface-raised border border-border-subtle`) with floating availability indicator dots.
  - Standardized all button controls (`min-h-9 px-3 rounded-lg`, `text-on-action bg-action hover:bg-action-hover`) and focus rings (`focus-visible:ring-2 focus-visible:ring-focus`).
  - Upgraded matrix rows with uniform `border-border-subtle` separators, `badge-accent` competency tags, and `font-mono` metrics.
  - Aligned candidate selector dropdown with semantic border and focus states.

## 2026-09-04 — High-density matrix (SpecialistTableView) modernization (Antigravity)

Modernized the high-density table matrix view for specialists (`SpecialistTableView.tsx`) to strictly adhere to design system tokens and dual-theme fidelity:

- `frontend/src/components/SpecialistTableView.tsx`:
  - Replaced legacy zinc borders (`divide-zinc-800/60`) and ad-hoc color classes with semantic tokens (`divide-border-subtle/80`, `bg-surface-raised`, `border-border-strong`).
  - Standardized action buttons with minimum 36-44px touch targets (`inline-flex min-h-9 min-w-9 rounded-lg`), accessible focus rings (`focus-visible:ring-2 focus-visible:ring-focus`), and semantic state colors.
  - Replaced raw image avatars with high-contrast monogram square avatars (`rounded-[10px] bg-surface-raised border border-border-subtle`) with floating availability indicator dots.
  - Upgraded table status badges to semantic tokens (`badge-accent`, `badge-positive`, `badge-neutral`).
  - Enhanced column toggle dropdown menu with backdrop blur, semantic tokens (`bg-surface border border-border-strong rounded-[14px] shadow-2xl`), and keyboard accessibility attributes.

## 2026-09-04 — Codified engineering standards across AGENTS.md guidelines (Antigravity)

Codified the core engineering pillars (clean, efficient, styled, modular, maintainable, lean, and debt-resistant) and strict theme consistency into the project's agent guidance documents:

- `AGENTS.md`:
  - Added explicit engineering mandate to "Non-negotiable rules" covering Clean & Readable, Efficient & Performant, Lean & Lightweight (zero bloat, minimal bundles), Debt-Resistant (prevent technical debt, fix root causes), Styled & Consistent (zero tolerance for inconsistency across buttons, windows/surfaces, typography/fonts, modals, and dual-theme symmetry), Modular & Decoupled, and Maintainable & Type-Safe.
- `frontend/AGENTS.md`:
  - Added strict theme and design consistency specifications across buttons (token hierarchy & 44px min touch targets), windows/panels (semantic surfaces & uniform `rounded-[14px]`), typography (`font-sans`/`font-mono` role hierarchy), and modal architecture (backdrop, shell, focus trap).
  - Enforced dual-theme fidelity across both dark and light modes.
- `backend/AGENTS.md`:
  - Updated "Backend rules" to enforce Pythonic clean code, async I/O efficiency, minimal resource overhead, active technical debt mitigation, strict Ruff styling and domain vocabulary, layer separation, and complete type safety.

## 2026-09-04 — Split-pane resize drag handle & responsive ergonomics (Antigravity)

Implemented interactive draggable divider between candidate list and dossier pane in split view:

- `frontend/src/App.tsx`:
  - Transformed split view container into a responsive flex layout with dynamic `splitRatio` percentage on desktop breakpoints (`md:`).
  - Built interactive draggable gutter (`role="separator"`, `aria-orientation="vertical"`, `aria-valuenow`, `aria-valuemin="25"`, `aria-valuemax="60"`).
  - Added smooth mouse/pointer dragging with global window listeners, body cursor styling, and text selection safety.
  - Implemented double-click preset cycling snapping between 35% (default balanced) -> 50% (wide list) -> 28% (compact list) -> 35%.
  - Added keyboard accessibility: ArrowLeft / ArrowRight to adjust ratio by 2%, Home / End to snap to bounds, and Enter / Space to cycle presets.
  - Persisted user's chosen ratio in `localStorage` (`hydenlyne_split_pane_ratio`).
- `frontend/src/components/ShortcutsModal.tsx`:
  - Added divider resize shortcut documentation (`← / → (divider)`) to the cheatsheet.

## 2026-09-04 — Linear-feel keyboard mastery & micro-interactions (Antigravity)

Implemented tactile power-user keyboard navigation and micro-interactions across the workspace for rapid, mouse-free candidate appraisal:

- `frontend/src/hooks/useKeyboardNavigation.ts`:
  - Upgraded candidate list navigation (`J`/`K`, `ArrowDown`/`ArrowUp`, `Home`/`End`) to smoothly auto-scroll focused rows into view (`behavior: 'smooth'`).
  - Added layout view hotkeys: <kbd>1</kbd> for Split view, <kbd>2</kbd> for Cards grid, <kbd>3</kbd> for Matrix spreadsheet, with instant toast feedback.
  - Added contractor quick comparison toggle hotkey <kbd>X</kbd> to rapidly compare up to 4 contractors on the fly without clicking.
- `frontend/src/App.tsx`:
  - Connected `viewMode`, `setViewMode`, and `onToggleCompare` into the keyboard navigation pipeline.
  - Added subtle keyboard hints (<kbd>J</kbd>/<kbd>K</kbd>) directly in the sticky Results list header.
  - Added selected contractor focus indicators and subtle <kbd>↵</kbd> action hints.
  - Added a floating, high-utility keyboard command bar hint at the bottom right during active searches with a 1-click trigger to the full shortcuts modal.
- `frontend/src/components/ShortcutsModal.tsx`:
  - Expanded shortcuts cheatsheet with <kbd>1</kbd>/<kbd>2</kbd>/<kbd>3</kbd> view switching, <kbd>F</kbd> focus mode toggle, <kbd>X</kbd> comparison toggle, and <kbd>M</kbd> mobilization inquiry.
- `frontend/src/types.ts`:
  - Added exported `DossierTab` type definition for modular tab handling.

## 2026-09-04 — Overhaul contractor card & expanded dossier UI/UX (Antigravity)

Redesigned contractor cards across both the non-expanded list view and expanded dossier pane to resolve visual clutter, cramped proportions, and lack of visual hierarchy.

- `frontend/src/App.tsx`:
  - Elevated non-expanded contractor card: added crisp active indicator accent strip, redesigned avatar presentation with floating status dot, clean 2-tier typography, day rate pill badge, distinct department & availability status pills, and clean metadata strip with dot separators.
  - Eliminated micro-badge crowding and restored breathing room while preserving compact scanability.
  - Expanded split-pane workspace container to dynamic viewport height `md:h-[calc(100vh-145px)] md:min-h-[660px]`, eliminating cramped vertical pinch.
- `frontend/src/components/SpecialistDossierPane.tsx`:
  - Compacted the pinned upper area from ~300px down to ~110px: consolidated day rate, department, exp, rating, and location directly alongside the header title strip.
  - Relocated the "Why this contractor" insight block into the Overview tab body so fixed chrome leaves maximum vertical room for actual content.
  - Rendered slim, flush segmented navigation tabs and streamlined action button paddings.
  - Redesigned "At a glance" cards (Deployment, Strengths, Track Record) with clean border treatment, subtle hover elevation, and status indicators.
  - Refined systems, training, geo, and client tag groupings with consistent spacing and modern pill styling.
- `frontend/src/components/ModernHeroSearch.tsx`:
  - Added interactive Recent Searches dropdown with localStorage persistence and 1-click jump/clear.
  - Smoothed search container transitions between calm and active states without jarring layout jumps.

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

## 2026-09-04 — Fix training/qualifications data corrupted by an unconditional fallback (Claude Code)

Salvaged from claude/strange-shannon-e680d4 — a real, confirmed-still-live
data-integrity bug on main before this port, unrelated to anything else in
this session.

Follow-up to a minor issue flagged in the prior review entry: one
credentials-row display artifact ("Maritime — Maritime Academy Szczecin,
Poland Compressed Air Emergency Breathing UK") turned out to be one visible
fragment of a much larger data-corruption bug. Helena Lindqvist's real
`training_qualifications` DB column held 27 garbled, misordered fragments
instead of 14 clean rows.

Root cause in `cv_processing.py`'s `extract_cv_deterministically`: the
table-based extractor (`cv_table_extractor.py`) already produces correct,
clean rows — confirmed by testing it directly — but the function then
called `training_from_text()` (a naive line-by-line regex scan meant only
as a last-resort recovery when the table extractor finds nothing)
*unconditionally*, letting it silently overwrite the already-correct
table-derived result whenever it returned anything non-empty, which it
always does for a real CV with a training table whose cells wrap across
multiple visual PDF lines. This landed real, compliance-relevant training
and certification dates in the wrong order in the database. Fixed by
gating the fallback on the table path having produced nothing
(`if not extraction_result.get("training_qualifications")`).

No test had exercised the real pipeline
(`TextExtractionService.extract_text()` → `extract_cv_deterministically()`)
with real extracted text for this field — the existing test passed
`text=""`, which made `training_from_text` a no-op and masked the bug.
Added a regression test that goes through the real pipeline and fails
without the fix (verified). Also repaired Helena Lindqvist's existing
corrupted DB record directly (the code fix only prevents future
corruption, not already-stored bad data) and invalidated her cached AI
summary, since it had been generated using the corrupted training list as
context. Verified live: her Credentials tab now shows 14 clean, correctly
structured training rows.

141 backend tests pass (up from 134); ruff format/check, mypy strict,
single Alembic head all clean.

## 2026-09-04 — Fix infinite re-render loop in natural-language search (Claude Code)

Salvaged from `claude/strange-shannon-e680d4` — a real, confirmed-still-live
bug on `main` before this port, unrelated to anything else in this session.

Found during a live application review: a natural-language search (e.g.
"Who has medical experience?") triggered a continuously-firing "Maximum
update depth exceeded" React error — an actual infinite re-render loop
burning CPU in the browser tab, not a one-off warning.

Root cause: `useCrewQuery.ts` built the returned `CrewQueryResult` object as
a fresh literal on every hook call, never memoized. `ModernHeroSearch.tsx`'s
`onAIResults` effect depends on that object reference; since it was never
referentially stable when the underlying data hadn't changed, the effect
fired every render, called `setAiQueryData` in `App.tsx`, which triggered
the re-render that produced a new object, which fired the effect again —
forever, once an AI-classified query populated `data.queryCrew`.

Fixed by wrapping the object construction in `useMemo(() => ..., [data])`.
Verified via a genuinely fresh tab (not a warm Vite HMR session, which
produced an unrelated, expected "Rendered more hooks than previous render"
transient once from hot-swapping in a new hook mid-session — not a real bug,
confirmed gone on a clean reload): zero console errors on repeated NL
searches. `npm run lint`, `test` (46 passed), and `build` all clean.

**Follow-up noted, not investigated further:** the search results header
("Found 13 specialists") and the criteria panel ("14 specialists meet every
requirement") showed inconsistent counts for the same query, reproducibly.
Also, one credentials/training row on a real profile concatenated education
and a training course without a separator ("Maritime — Maritime Academy
Szczecin, Poland Compressed Air Emergency Breathing UK").


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
