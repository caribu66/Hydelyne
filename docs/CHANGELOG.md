# Changelog

The running record of what was built, when, by which tool, and why. This is
the shared handoff point between AI tools (Claude Code, Codex, Kilo Code, or
any other) and between sessions of the same tool — read it before assuming
context needs to be re-explained, and append to it before finishing any work
that changes committed code, running data, or infrastructure state.

Newest entries first. Each entry: date, who/what did it, what changed, why,
and any follow-up the next session needs to know about. Keep entries short —
this is an index into commits and docs, not a replacement for either.

## 2026-09-11 — Hidden-Bug Pass 3 Fixes (Muse Spark)

Fixed 4 items from the third sweep: `me` resolver now scrubs by caller tier
like every sibling resolver (+ T1 regression test); `medical_status` unified
on `MEDICAL_STATUS_VALUES` (`fit`/`fit_with_restrictions`/`expired`) —
periodic job no longer writes cert-lifecycle `expiring_soon` into the fitness
flag, seeds/`seed_100` use `fit` (+ regression test); vision extraction caps
source images at 10 MB before base64 (+ regression test); sync worker cert
link fails loudly outside sync context and documents the intentional engine
disposal. `enrich_compliance.py` keeps one `fit_for_offshore` write (file not
writable in this environment — one-off script, fix on next touch).

**Why:** Close C2/C3 scrub bypass, silent filter misses, OOM-sized LLM
payloads, and async-engine footguns.

**Follow-up:** Remaining pass-3 mediums (Content-Disposition, webhook
orphans, 017 CONCURRENTLY, backup durability, seed guards) untouched.

## 2026-09-11 — Hidden-Bug Pass 2 Fixes (Muse Spark)

Fixed 9 high-severity items from the second sweep: agent upload now 404s on
unknown `crew_id` and normalizes `classification` on staff + agent paths
(`documents.py`); prod secret validation covers `FLOWER_PASSWORD`,
`ADMIN_PASSWORD`, dev-default values, and `hydenlyne_pass` in `DATABASE_URL`
(`main.py`); Meilisearch bootstrap creates indexes unconditionally instead of
the dead lazy-handle branch; CORS rejects `*` with credentials and drops
localhost defaults in prod; pagination clamped 1–100 at resolvers and services
(`schema.py`, `assignment.py`, `document_service.py`); `useCrewProfiles`
auto-pagination bounded (250) with error handling and working
`loadMore`/`hasMore`; AI-synthesized profiles no longer fabricate
title/location, re-apply facet filters, and only rank while matching the
current query; missing-expiry certs warn instead of pass on both frontend
(`assignmentUtils.ts`) and backend (`assignment.py`) preflight, with
regression tests each side.

**Why:** Close AuthZ bypass, fail-open compliance, unbounded fetch/DoS,
filter bypass, and silent prod misconfiguration.

**Follow-up:** Remaining medium/low leads (Content-Disposition injection,
webhook orphans, 017 CONCURRENTLY, seed guards, mapper gaps) untouched.

## 2026-09-11 — High-Severity Hidden-Bug Fixes (Muse Spark)

Fixed 11 verified high-severity bugs across auth, booking, cache, queries,
reports, and prod ops: `useAuth` now persists the login token via
`setAuthToken`; `update_status` rejects escalation to active on overlapping
windows (+ regression test); compliance cache invalidation now matches
`CacheService._make_key`; Dockerfile entrypoint uses `set -e` so failed
migrations block startup; `backup.sh` strips `+asyncpg` for `pg_dump` and no
longer logs `DATABASE_URL`; async doc path uses new `get_file_async`;
`crew_query` ranks in SQL before `LIMIT 20`; `build_report_data` accepts
filters and returns `COUNT(*)` totals; login rate limit uses a fixed window
with explicit Redis-down warning; unknown availability maps fail-closed to
`Unavailable`; prod overlay uses `!reset []` to actually clear ports/volumes.

**Why:** Close session loss, double-booking, stale compliance, silent
migration/backup failure, event-loop crash, ranking truncation, unfiltered
reports, and prod port/volume leakage.

**Follow-up:** Verify prod overlay with `docker compose config`; confirm
`requirements-prod.txt` + `scripts/backup.sh` are tracked; consider
mappers/frontend regression test and remaining medium-severity leads.

## 2026-09-06 — Natural Language Search Accuracy Hardening (Kilo)

Improved the reliability and correctness of natural language search by adding
LLM output validation, fixing a frontend result-truncation bug, and expanding
test coverage.

**What changed:**
- `backend/app/services/crew_query.py` — Added `_validate_llm_response()` which
  validates the Ollama JSON payload against a typed schema before it reaches
  database filters. Malformed types are dropped with a warning instead of
  causing silent query corruption.
- `frontend/src/hooks/useSearchWorkspace.ts` — Fixed AI result merging: when
  the backend AI search matches the current query, the workspace now trusts the
  AI result set as the source of truth and synthesizes minimal profiles for
  specialists not present in the local roster, instead of silently dropping
  them.
- `frontend/src/hooks/useCrewQuery.ts` — Exported `isNaturalLanguage()` and
  `shouldShowSummary()` for unit testing.
- `frontend/src/hooks/useCrewQuery.test.ts` — New test file covering NL
  detection heuristics and summary display rules.
- `backend/tests/test_crew_query.py` — Added 5 regression tests for LLM
  payload validation (valid payload, malformed types, invalid intent,
  non-dict input, out-of-range availability).

**Why:** The previous implementation trusted raw `json.loads()` output from the
local LLM and silently truncated AI search results to the currently loaded
client-side roster, causing valid specialists to disappear from search results.

**Follow-up:** Consider adding a labeled precision/recall benchmark set for NL
queries and expanding `isNaturalLanguage()` heuristics to cover more concise
query patterns.

## 2026-09-06 — Production Readiness Hardening (Kilo)

Prepared the application for production deployment by hardening operational
controls, container configuration, and deployment documentation.

**What changed:**
- `docker-compose.prod.yml` — Set `APP_ENV=production` on every service,
  added `restart: unless-stopped`, memory/CPU resource limits, removed internal
  port publishes, and excluded Flower and dev volume mounts from the production
  override.
- `backend/Dockerfile` — Added `--graceful-timeout 30` and
  `--timeout-graceful-shutdown 30` to the uvicorn command for clean container
  termination.
- `backend/app/main.py` — Tightened CORS: localhost origins are now only
  included in non-production environments so a missing `CORS_ORIGINS` cannot
  silently leave dev origins open in production.
- `frontend/nginx.conf.template` — Restricted `/health` to `GET` requests
  using `limit_except` to prevent method-based abuse.
- `backend/requirements-prod.txt` — New production-optimised dependency list
  (runtime deps only, Flower moved to dev).
- `backend/scripts/backup.sh` — New PostgreSQL backup script producing
  compressed, timestamped dumps with 7-day retention.
- `README.md` — Added a Production Deployment section covering environment
  variables, backup strategy, observability, and restart/resource policies.
  Fixed outdated test instructions and service references.

**Why:** Close operational gaps identified during production readiness review:
  uncontrolled dev-mode exposure, unbounded container restarts, missing backup
  strategy, and oversized production images.

**Follow-up:** Consider adding a Prometheus metrics endpoint and automated
  backup cron service inside the Compose network for fully self-hosted
  deployments.

## 2026-09-06 — Performance Optimization Pass (Kilo)

Addressed unbounded queries, missing indexes, cache invalidation scaling,
sync-in-async bridges, and frontend fetch-all pattern.

**What changed:**
- `backend/alembic/versions/017_performance_indexes.py` — New migration adding
  composite index on `campaign_assignments(crew_member_id, status, start_date, end_date)`
  and GIN trigram indexes on `crew_members.full_name`, `professional_summary`,
  `nationality`, and `email`.
- `backend/app/services/assignment.py` — `list_assignments` now accepts
  `limit`/`offset` (defaults 100/0).
- `backend/app/services/crew.py` — `get_expiring_certifications` accepts
  `limit`/`offset`. `check_and_update_expiration_status` processes certifications
  in bounded batches of 200 using keyset pagination. Replaced O(N) Redis
  `SCAN`-based pattern invalidation with explicit per-entity cache key deletion
  for compliance and crew list caches.
- `backend/app/services/reports.py` — `build_report_data` accepts `limit`/`offset`
  for all report-type queries.
- `backend/app/services/document_service.py` — `get_documents_by_crew` and
  `get_pending_documents` accept `limit`/`offset`.
- `backend/app/services/compliance.py` — `evaluate_and_update_compliance_sync`
  processes certifications in bounded batches. `_invalidate_caches_sync` now
  deletes specific compliance cache keys instead of scanning Redis.
- `backend/app/services/cache.py` — Removed unused `type: ignore`.
- `backend/app/services/upload.py` — Replaced deprecated
  `asyncio.get_event_loop()` with `asyncio.run()` in `_download_from_dropbox_sync`.
- `backend/app/services/qdrant.py` — Added `index_document_sync` for
  synchronous Qdrant indexing.
- `backend/app/tasks/document_tasks.py` — `index_document_embeddings` now uses
  `qdrant_service.index_document_sync` instead of `asyncio.run()`.
- `backend/app/graphql/schema.py` — Exposed `limit`/`offset` on
  `campaign_assignments`, `vessel_roster`, `expiring_certifications`,
  `documents_by_crew`, and `pending_reviews` resolvers.
- `frontend/src/hooks/useCrewProfiles.ts` — Reduced `PAGE_SIZE` from 100 to 50,
  removed hidden auto-pagination side effect, added `loadMore` and `hasMore`
  to the hook interface.
- `frontend/src/App.tsx` — Consumed new `loadMore`/`hasMore` exports from
  `useCrewProfiles`.

**Why:** Eliminate unbounded memory/transaction risks, reduce sequential
scans, remove O(N) Redis blocking operations, and make async/sync boundaries
explicit and future-proof.

**Follow-up:** For datasets exceeding ~500 crew, migrate client-side search/filter
to server-side GraphQL queries to avoid downloading the full roster.

## 2026-09-06 — Code Correctness Checklist (Kilo)

Created a 20-point pre-flight checklist documenting the gates to run before
requesting review or merging.

**What changed:**
- `docs/CODE_CORRECTNESS.md` — New file with 20 items covering type safety,
  linting, testing, dead code, boundaries, naming, file-size limits,
  authorization, secrets, network safety, migrations, git hygiene, UI tokens,
  dependency discipline, and API compatibility.

**Why:** Provide a single reference for the team and CI agents that maps each
best-practice category to a runnable command or concrete artifact check.

**Follow-up:** None.

## 2026-09-06 — Unified Operations + Search Workspace (Antigravity)

Merged the Operations dashboard and the Search Workspace into a single authenticated shell so the same Split / Cards / Matrix views never appear in two places simultaneously.

**What changed:**
- `frontend/src/App.tsx` — `shellKey` simplified to `gate | public | workspace`; the former `ops` and `search` shells are gone. The `workspace` shell permanently renders `<OperationsHome>` wrapping the specialist database as a `children` slot. The results area landmark was renamed `"Specialist database results"` to avoid aria collision with the split view's `"Contractor search results"` section.
- `frontend/src/components/operations/OperationsHome.tsx` — Full rewrite: removed 8 props that delegated to `ContractorSearchPane`; added `children?: ReactNode` slot; layout order is Greeting → Telemetry (KPIs, Needs Attention, Active Projects) → Search Hub → `{searchControl}` → `{children}`.
- `frontend/src/components/operations/ContractorSearchPane.tsx` — **Deleted.** It was the duplicate source of Split / Cards / Matrix views.
- `frontend/src/hooks/useSearchWorkspace.ts` — Removed `if (!isSearchActive) return []` guard so `results` always returns the full/filtered specialist list even when no search is active.
- `frontend/src/components/DensityIndicator.tsx` — Added `role="img"` to fix Axe `aria-prohibited-attr` WCAG violation.
- `frontend/src/components/ModernHeroSearch.tsx` — Responsive sizing fix (padding, min-height, icon, textarea `min-w-0 flex-1`) to prevent textarea width-collapse at 200% CSS zoom on mobile.
- `frontend/tests/operations-home.spec.ts` — Updated bounding-box assertion to `attentionBox.y < searchBox.y` (telemetry is now above search hub).
- Visual baselines regenerated for all 8 authenticated-workspace viewports and the 2 public-shell mobile/tablet snapshots.

**Why:** User identified that Split / Cards / Matrix views existed in both the Operations panel and the Search Workspace, creating confusion. The fix is a single unified surface, not a toggle.

**Follow-up:** None. All 185 Playwright tests pass, 114 Vitest tests pass, 0 TypeScript errors, 0 Axe violations.

## 2026-09-06 — Fix Opening Full Database View & Expanded Contractor Modal (Antigravity)

Fixed opening the full dedicated contractor database search workspace and accessing the expanded contractor profile modal:

- **Full Database View Activation (`frontend/src/hooks/useSearchWorkspace.ts`, `frontend/src/App.tsx`, `frontend/src/components/operations/ContractorSearchPane.tsx`)**:
  - Added explicit `isWorkspaceOpen` state with `openWorkspace()` and `closeWorkspace()` callbacks to `useSearchWorkspace`.
  - Fixed `isSearchActive` calculation so clicking "Open full database view ↗" or submitting search in Operations transitions directly to the full search workspace showing all 108 specialists, even when the query keyword is empty.
  - Linked the "← Operations" return button to `closeWorkspace()`, providing clean, predictable round-trip navigation back to the Operations overview.
- **Contractor Expanded Profile Modal Access (`frontend/src/components/dossier/DossierHeader.tsx`, `frontend/src/components/operations/ContractorSearchPane.tsx`)**:
  - Added an explicit `[ [ ] Expand view ]` button to `DossierHeader` with visible label and accessible tooltip, opening the full `ProfileDetailModal`.
  - Added an "Open expanded view" menu item to the Dossier actions (`...`) dropdown.
  - Added an accessible quick-expand icon button and double-click handler to every candidate card in the Split View roster, structured as accessible sibling controls without nested interactive elements.
  - Added double-click to Cards view contractor cards to open the full modal.
- **Verification**:
  - Automated browser test via Playwright verifying clicking "Open full database view", returning to operations, opening modal from header button, opening modal from candidate card, and opening modal from Cards view.
  - Playwright test suite: 60/60 tests passed across all viewports (`desktop`, `tablet`, `mobile`, `wide`).
  - Vitest: 114/114 tests passed.
  - TypeScript strict check: 0 errors (`npx tsc --noEmit`).
  - Production build: Clean bundle with zero errors.

## 2026-09-06 — Overhaul Operations Split View to Full SpecialistDossierPane & Fix Layout (Antigravity)

Overhauled the Split View in the Operations Contractor Hub to eliminate layout cramping, replace ad-hoc preview blocks with the full-featured `SpecialistDossierPane`, and resolve accessibility heading hierarchy:

- **Full-Featured Specialist Dossier Integration (`frontend/src/components/operations/ContractorSearchPane.tsx`)**:
  - Replaced the makeshift, text-only preview container with the complete, lazy-loaded `<SpecialistDossierPane>`, providing tabs (Overview, Experience, Credentials, Skills, Documents, Radar), AI summary, verified credentials, document vault, and action controls.
  - Upgraded the left roster column with avatar photos, presence indicator dots, day rates, and left accent selection indicator bars.
  - Added previous/next keyboard and click profile navigation handlers (`handlePrevProfile`, `handleNextProfile`).
  - Added avatar images and elevated card styling to Cards (Grid) view.
- **Accessibility & Heading Hierarchy (`frontend/src/components/dossier/DossierOverviewTab.tsx`)**:
  - Corrected heading levels from `<h4>` to `<h3>` under `<h2>` in `DossierOverviewTab.tsx` and changed candidate list names in the roster to semantic `<p>`, ensuring 100% WCAG compliance and passing all Axe accessibility audits.
- **Verification**:
  - Playwright: 60/60 passed across all 4 viewport projects (`desktop`, `tablet`, `mobile`, `wide`).
  - Vitest: 114/114 passed.
  - TypeScript strict: 0 errors.
  - Live browser inspection: Zero console errors, zero warnings.

## 2026-09-06 — Restore Grid, Matrix, and Split Views in Operations Contractor Hub (Antigravity)

Restored full view mode versatility (Split, Cards / Grid, Matrix / Table) directly inside the Operations Command Center:

- **View Mode Switcher (`frontend/src/components/operations/ContractorSearchPane.tsx`)**:
  - Embedded the `SegmentedControl` with `Split`, `Cards`, and `Matrix` directly into the top bar of the Operations contractor hub.
  - Synchronized `viewMode` state across Operations and the dedicated search workspace via `useSearchWorkspace` in `App.tsx`.
- **Three Comprehensive View Renderers**:
  - **Matrix (Table)**: Lazy-loads `<SpecialistTableView>` with sortable columns, rates, bookmarks, compare, and mobilization actions directly in Operations.
  - **Cards (Grid)**: Renders the visual card grid with status badges, day rates, and quick actions.
  - **Split View**: Renders an interactive split pane featuring a candidate list on the left and a live detailed dossier inspector on the right with verified disciplines, key certifications, and quick mobilization triggers.
- **Verification**:
  - Vitest: 114/114 passed.
  - TypeScript: 0 errors (`npx tsc --noEmit`).
  - Playwright: 60/60 passed across all 4 viewport projects.
  - Production build: Zero warnings, code-splitting preserved.

## 2026-09-06 — Operations Command Center Modernization & Search Elevation (Antigravity)

Redesigned and elevated the Operations Panel searches from an awkward bottom-of-page widget into a top-level Command Center:

- **Search-First Command Center (`frontend/src/components/operations/OperationsHome.tsx`)**:
  - Elevated the Operations Search & Mobilization Hub to the primary hero position directly below the greeting, completely removing vertical scroll fatigue.
  - Reorganized operational telemetry: condensed `OperationsMetrics` into a crisp 4-column responsive KPI ribbon (`grid-cols-1 sm:grid-cols-2 lg:grid-cols-4`) with semantic status indicator dots.
  - Positioned `OperationsAttention` and `OperationsProjectsPanel` side-by-side in a balanced 2-column lower deck.
  - Preserved non-staff safe greeting view with guidance messaging.
- **Inline Specialist Discovery & Dispatch (`frontend/src/components/operations/ContractorSearchPane.tsx`)**:
  - Replaced the redirect-heavy contractor input with an in-place specialist discovery pane with real-time text matching across name, discipline, and skills.
  - Added quick discipline filter chips (`All specialists`, `Available now`, `MMO / PAM`, `Hydrography`, `Seismic QC`, `Client Rep`, `Geotech`, `HSE / Safety`) styled with WCAG AAA contrast tokens (`bg-accent-soft text-accent border-border-strong`).
  - Added instant specialist preview cards with full name, title, department, location, day rate, and 1-click **Mobilize** / **View** actions.
- **High-Velocity Vessel Explorer (`frontend/src/components/operations/VesselSearchPane.tsx`)**:
  - Added quick vessel filter chips (`All vessels`, `Survey & Research`, `Offshore & Supply`, `Support & Tug`).
  - Added an instant clear (`X`) button to the search input with automatic empty query refetch.
  - Enhanced vessel cards and crew roster drawer with accessible semantic tokens and smooth interactions.
- **App Integration & Testing (`frontend/src/App.tsx`, `frontend/tests/operations-home.spec.ts`)**:
  - Wired `onSelectProfile` (opens dossier) and `onMobilizeProfile` (opens mobilization inquiry) from the Operations home.
  - Updated bounding-box layout test to assert the search hub sits above operational telemetry.
  - Verified 100% pass rate: 60/60 Playwright tests across all viewports (`desktop`, `tablet`, `mobile`, `wide`) including `@axe-core/playwright` accessibility audits and light/dark theme symmetry.

## 2026-09-06 — Campaign Assignment Eager Loading & Detached Session Fix (Antigravity)

Resolved an async SQLAlchemy `DetachedInstanceError` occurring when `CampaignAssignment` instances (returned after transaction commit) had their relationships (`crew_member`, `vessel`, `project`) accessed outside the active session or in GraphQL resolvers:

- **Eager Loading in Service Layer (`backend/app/services/assignment.py`)**:
  - Added `_assignment_query_options()` helper combining `selectinload(CampaignAssignment.crew_member)`, `selectinload(CampaignAssignment.vessel)`, and `selectinload(CampaignAssignment.project)`.
  - Applied `_assignment_query_options()` to `create_assignment` and `update_status` by reloading the committed record with explicit options instead of `session.refresh(assignment)` (which does not refresh unloaded relationships in async SQLAlchemy).
  - Applied `_assignment_query_options()` to `get_assignment` and `list_assignments` queries.
- **Defensive Inspection in GraphQL Mapping (`backend/app/graphql/schema.py`)**:
  - Hardened `_model_to_graphql_assignment` using SQLAlchemy's inspection API (`sa_inspect(model)`).
  - Verified presence in `state.dict` before reading relationship attributes to avoid triggering any implicit lazy loading on detached model instances.
- **Regression Tests Added (`backend/tests/test_campaign_assignments.py`)**:
  - `test_detached_assignment_graphql_mapping_does_not_fail`: Confirms detached models map gracefully without throwing `DetachedInstanceError`.
  - `test_created_assignment_has_relations_loaded_and_graphql_mapped`: Verifies newly created assignments eagerly load relation objects and accurately populate GraphQL fields (`crew_name`, `vessel_name`).

## 2026-09-06 — End-to-End Hardening Test Suites & Edge-Case Characterization (Antigravity)

Implemented comprehensive hardening tests across backend services, frontend compliance engines, and end-to-end browser interactions:

- **Backend Search & Security Hardening (`backend/tests/test_crew_search_hardening.py`)**:
  - Tested `CrewService.list_crew_members` against SQL injection payloads (`' OR '1'='1`, `'; DROP TABLE crew_members; --`, `admin' --`, `1' UNION SELECT NULL--`).
  - Validated resilient handling of SQL LIKE wildcards (`%`, `%%`, `___`, `\\`, `[%]`, `*`, `?`).
  - Tested 10,000-character payload inputs against buffer/DoS vulnerabilities.
  - Tested international character sets, accents, and unicode (`Björn`, `géophysique`, `Norwegian`).
  - Verified multi-attribute relational matching across `tags`, `certifications`, and past `work_history`.
- **Assignment Interval & Constraint Hardening (`backend/tests/test_campaign_assignments.py`)**:
  - Inverted schedule rejection (`start_date > end_date` throws `ValueError`).
  - Empty or whitespace-only role on board rejection (`role_on_board.strip()` validation).
  - Enclosure interval conflict (attempting to book within an active mobilization window).
  - Envelope interval conflict (attempting to book a window wrapping an existing active assignment).
  - Cancellation decoupling (verifying cancelled assignments immediately release the calendar).
  - Single-day mobilization support (`start_date == end_date`).
- **Frontend Pre-Flight & Calculation Hardening (`frontend/src/utils/assignmentUtils.test.ts`)**:
  - Leap day calendar transitions (`2028-02-28 + 1d = 2028-02-29`, `2028-02-28 + 2d = 2028-03-01`).
  - Year boundary transitions (`2026-12-25 + 10d = 2027-01-04`).
  - Graceful degradation for empty (`[]`) or undefined candidate certifications without exceptions.
  - Extreme role normalization (mixed-case, excessive internal/external whitespace, complex job titles).
- **Playwright Browser Mobilization Suite (`frontend/tests/operations-home.spec.ts`)**:
  - Automated browser test for real-time role switching, search input clearing, discipline chip toggling (`MMO/PAM`, `Hydrography`), and modal dismissal across all viewport projects (`mobile`, `tablet`, `desktop`, `wide`).
- **Results**:
  - Pytest: 233/233 tests passed (100%).
  - Vitest: 114/114 tests passed (100%).
  - Playwright: 60/60 tests passed across 4 viewport targets (100%).
  - Container stack rebuilt and verified live at `http://localhost:5173`.

## 2026-09-06 — Dynamic Role-Based Specialist Discovery & Mobilization Filtering (Antigravity)

Addressed the issue where selecting or searching for a role on board returned the exact same static list of consultants:

- **Root Causes**:
  - *Backend Filter Scope*: In `backend/app/services/crew.py:list_crew_members`, the SQL search predicate only tested `full_name`, `email`, and `nationality`. Searching for roles or disciplines like "MMO", "Hydrographer", "QC", "OBN", or "BOSIET" matched 0 specialists, resulting in empty returns or fallback to unfiltered lists.
  - *Frontend Query Disconnect*: In `VesselMobilizationModal.tsx`, Step 1 role selection did not bind to the candidate query in Step 2; `CREW_MEMBERS_QUERY` was called with `search: candidateQuery.trim() || undefined`, always fetching the same default 12 specialists ordered by creation date regardless of selected role.
- **Backend Search Broadened (`backend/app/services/crew.py`)**:
  - Expanded search conditions in `list_crew_members` across:
    - `CrewMember.full_name`, `email`, `nationality`, `professional_summary`
    - `cast(CrewMember.tags, String)`
    - `CrewMember.certifications.any(Certification.cert_type.ilike(...))`
    - `CrewMember.work_history.any(or_(WorkHistory.role.ilike(...), WorkHistory.project_type.ilike(...)))`
  - Verified keyword query discovery across the 108 crew database: "MMO" (18 found), "Hydrograph" (23 found), "Seismic" (14 found), "HSE" (15 found), "Auditor" (19 found).
- **Frontend Role Discovery & Filtering (`frontend/src/components/operations/VesselMobilizationModal.tsx`, `frontend/src/utils/assignmentUtils.ts`)**:
  - Added `getRoleKeyword(role: string): string` pure helper in `assignmentUtils.ts` mapping roles to search keywords (e.g. MMO, PAM, Hydrograph, Seismic, OBN, Geotech, HSE, Client Rep).
  - Wired `filterByRole` state defaulting to `true`; selecting a role on board in Step 1 automatically triggers a targeted discipline query in Step 2.
  - Added Step 2 search enhancements: clear button (`X`), active role filter badge ("Filtered by role: Hydrograph (23 matched)"), "Show all specialists" toggle, and quick discipline filter chips (`Role focus`, `All`, `MMO/PAM`, `Hydrography`, `Seismic QC`, `Client Rep`, `Geotech`, `HSE`).
  - Rendered top specialist skill/discipline tags on each candidate card in the selection list.
- **Verification Suite**:
  - Vitest: 108 unit tests passed (including 10 new tests for `getRoleKeyword`).
  - Pytest: 30 tests passed (`test_crew_query.py`, `test_campaign_assignments.py`, `test_vessel_api.py`).
  - TypeScript/ESLint: 0 errors across frontend (`tsc --noEmit && eslint .`).
  - UI Audit: 96 source files scanned, 0 issues.
  - Playwright: 56/56 browser tests passing across viewports.
  - Container stack rebuilt with `./scripts/local-stack.sh start`; healthy at `http://localhost:5173`.

## 2026-09-06 — Consultant Compliance Credential Enrichment & Pre-Flight Alignment (Antigravity)

Diagnosed and fixed why candidates appeared non-compliant or had notices in the agent mobilization list:

- **Root Causes**:
  - *Seed Data Gap*: In both `backend/app/seeds.py` and `backend/seed_100.py`, `crew_members.medical_expiry` was never populated (`108/108` were NULL), all core seed certs had `expiry_date=None, status="pending_verification"`, and random uniform sampling across 37 cert types in `seed_100.py` left virtually 0 specialists with both valid OPITO survival and OGUK Medical.
  - *GraphQL Field Omission*: `CREW_MEMBERS_QUERY` in `frontend/src/lib/queries.ts` did not select `medical { status expiry }`, leaving `raw.medical` undefined in `backendCrewToProfile` whenever crew lists were retrieved.
  - *Evaluation Fallbacks*: Preflight compliance in `assignment.py` and `assignmentUtils.ts` previously required `medical_expiry` on the crew entity and did not check `OGUK Medical` records in `certifications`.
- **Changes**:
  - **GraphQL Query**: Updated `CREW_MEMBERS_QUERY` in `frontend/src/lib/queries.ts` to request `medical { status expiry }`.
  - **Seed Automation (`backend/app/seeds.py`, `backend/seed_100.py`)**: Updated seed configurations so all available and on-assignment offshore specialists receive valid `OPITO BOSIET with CA-EBS` and `OGUK Medical` certificates (expiring 2027-2028), valid passport expiry dates, and valid `medical_expiry` on `CrewMember`.
  - **Pre-Flight Evaluation Fallbacks (`backend/app/services/assignment.py`, `frontend/src/utils/assignmentUtils.ts`)**: Enhanced both backend and frontend pre-flight evaluators to inspect `certifications` for verified `OGUK Medical` when `medical_expiry` is open or unset.
  - **Database Migration/Enrichment**: Executed compliance enrichment across PostgreSQL, updating all 39 available specialists to have valid offshore medicals and OPITO BOSIET credentials, turning available candidates to `Compliant ✓` in the mobilization selector.
- **Verification & Edge-Case Characterization Suite**:
  - **Schedule Rotation & Boundaries**: Single-day campaigns, exact boundary overlap vs adjacent next-day non-clash, and prospective candidate scheduling when current assignment completes before campaign start.
  - **Multi-Assignment Concurrency**: Release lifecycle verifying that completing one assignment preserves `on_assignment` with remaining tour end dates, only returning to `available` when all deployments conclude.
  - **Credential Resolution Under Stale Profile Fields**: Verified that newer certificates in `certifications` (OEUK Medical, OPITO FOET refresher) override older/expired profile values.
  - **Mid-Campaign Expiration Warnings**: Validated that certificates expiring during campaign window trigger Notice/Warning rather than silent approval.
  - **Suite Results**: 26/26 Vitest tests in `assignmentUtils.test.ts` (98/98 frontend total), 10/10 Pytest tests in `test_campaign_assignments.py`, Mypy 0 errors, ESLint 0 errors, and 56/56 Playwright tests passing across viewports. Containers rebuilt and live.

## 2026-09-06 — Agent Consultant-to-Vessel Dispatch & Pre-Flight Compliance Matrix (Antigravity)

Investigated offshore consultancy mobilization workflows (Hydenlyne, Atlas Professionals, Brunel, UTM, OCS HR) and implemented direct agent dispatch from vessels with live pre-flight compliance matrix evaluation:

- **Industry Dispatch Architecture Investigation**:
  - Researched the 5-stage dispatch lifecycle for technical energy consultants (Client Reps, Seismic QC, MMO/PAM, Geotechnical CPT, HSE/FLO) deployed to exploration & offshore wind vessels.
  - Documented strict client requirements for zero-tolerance certification validation (OPITO BOSIET/FOET + CA-EBS, OGUK/OEUK Medical valid through campaign window, and IOGP fatigue rotation windows).
- **Pre-Flight Compliance Evaluation Engine (`backend/app/services/assignment.py`, `backend/app/graphql/schema.py`)**:
  - Implemented `evaluate_compliance` on `AssignmentService`, itemizing schedule conflicts, offshore medical validity, and survival/BOSIET certificate status against campaign start/end dates.
  - Exposed `evaluate_assignment_compliance` GraphQL query for staff/admin agents, returning structured checks and overall status (`compliant`, `warning`, `critical`).
  - Added unit and GraphQL characterization tests in `backend/tests/test_campaign_assignments.py` (7 tests passing).
- **Client-Side Pre-Flight Matrix & Helpers (`frontend/src/utils/assignmentUtils.ts`)**:
  - Implemented pure function `evaluateCandidatePreflightCompliance`, evaluating candidate survival certificates, offshore medical, and availability against custom campaign dates in real-time.
  - Added full test suite in `frontend/src/utils/assignmentUtils.test.ts` (19 tests passing).
- **Vessel Mobilization Dispatcher Modal (`frontend/src/components/operations/VesselMobilizationModal.tsx`)**:
  - Built an accessible modal (`useAccessibleDialog`, `focus-visible:ring-focus`, `bg-surface`, `rounded-[14px]`, theme symmetry) for operations agents.
  - Features 3-step dispatch flow: (1) Campaign window & standard offshore discipline selection, (2) Live specialist candidate picker with dynamic pre-flight compliance badges and check breakdowns, (3) Commercial day rate and logistics transit notes.
  - Dispatches `CREATE_CAMPAIGN_ASSIGNMENT` mutation, synchronizes crew availability, refetches vessel rosters, and generates instant mobilization dispatch briefs.
- **Operations & Vessel Search Integration (`frontend/src/components/operations/VesselSearchPane.tsx`, `OperationsHome.tsx`)**:
  - Added `[ ➕ Mobilize ]` action buttons directly on vessel search cards and in empty/active `VesselRosterSection` headers.
  - Connected toast notifications across Operations Home.
  - Added Playwright e2e test verifying complete vessel-initiated mobilization workflow; all 56 Playwright tests passing across viewports.
  - Verified static UI audit (96 files, 0 errors, 0 warnings), ESLint (0 errors/warnings), Vite build, and container stack deployment (`local-stack.sh start`).

## 2026-09-06 — Consultant-to-Vessel Campaign Assignments & Live AIS Integration (Antigravity)

Architected and implemented end-to-end relational consultant mobilization to maritime vessels and offshore campaigns per ADR 0007:

- **ADR 0007 (`docs/decisions/0007-consultant-vessel-assignments.md`)**:
  - Formalized the persistent PostgreSQL `vessels` entity and `campaign_assignments` join relation linking specialists, vessels, and projects.
  - Defined strict schedule conflict rejection for active assignments, lifecycle synchronization with consultant availability status (`on_assignment` / `available`), and data classification tiers (C1 specs, C2 dates/roles, C3 commercial rates).
- **Database & Schema (`backend/alembic/versions/016_vessel_assignments.py`, `backend/app/models/__init__.py`)**:
  - Created `016_vessel_assignments` migration adding `vessels` and `campaign_assignments` tables with foreign keys and performance indexes.
  - Linked `Vessel` and `CampaignAssignment` to `CrewMember.assignments` and `Project.assignments` SQLAlchemy relationships.
- **Assignment Application Service (`backend/app/services/assignment.py`)**:
  - Implemented `create_assignment` with schedule conflict detection for overlapping dates, role validation, upstream vessel auto-resolution via `VesselApiService`, and automatic specialist availability synchronization.
  - Implemented `update_status` supporting `proposed`, `confirmed`, `on_board`, `completed`, and `cancelled` transitions, resetting crew availability upon release.
  - Implemented `list_assignments` and `get_vessel`.
- **GraphQL Schema & Resolvers (`backend/app/graphql/types.py`, `schema.py`)**:
  - Added `CampaignAssignmentStatus`, `VesselType`, `CampaignAssignmentType`, and `CreateCampaignAssignmentInput`.
  - Added queries `campaign_assignments`, `vessel_roster`, and `vessel_record` protected with `@require_auth`.
  - Added mutations `create_campaign_assignment` and `update_campaign_assignment_status` protected with `@require_staff`.
- **Backend Test Coverage (`backend/tests/test_campaign_assignments.py`)**:
  - 5 test scenarios covering creation, schedule conflict rejection, status updates and availability synchronization, date validation, and GraphQL mutation execution. 215 backend tests passing cleanly.
- **Frontend Integration (`frontend/src/`)**:
  - Defined `CampaignAssignment` and `CampaignAssignmentStatus` types in `frontend/src/types.ts`.
  - Added `CREATE_CAMPAIGN_ASSIGNMENT`, `UPDATE_CAMPAIGN_ASSIGNMENT_STATUS`, `VESSEL_ROSTER_QUERY`, and `CAMPAIGN_ASSIGNMENTS_QUERY` in `frontend/src/lib/queries.ts`.
  - Created modular `frontend/src/utils/assignmentUtils.ts` with unit test suite in `assignmentUtils.test.ts` (86 vitest unit tests passing).
  - Upgraded `MobilizationInquiryModal.tsx` from simulated delay to live `useMutation(CREATE_CAMPAIGN_ASSIGNMENT)` with IMO input, error alerts, and booking brief confirmation.
  - Enhanced `VesselSearchPane.tsx` with expandable `VesselRosterSection` displaying active vessel crew rosters with status badges and rotation dates.
  - Replaced the stacked contractor and vessel cards with a unified, segmented tab `<OperationsSearchHub>` in `OperationsHome.tsx`, cutting vertical scroll in half, supporting WAI-ARIA tab keyboard navigation, and preserving deep links via `?tab=vessels`.
  - Passed `npm run test:quality` (`tsc`, `eslint`, `vite build`, `ui:audit:strict`, and 181 Playwright e2e tests across responsive viewports).

## 2026-09-06 — Complete Vessel Search UI, backend tests, and Operations Home navigation polish (Antigravity)

Addressed key polish opportunities across vessel tracking, backend regression coverage, and authenticated workspace navigation:

- **Vessel Search UI completion (`frontend/src/components/operations/VesselSearchPane.tsx`)**:
  - Wired full vessel search results rendering: maps `vesselSearch.vessels` to structured cards displaying vessel name, type badge, flag, IMO, MMSI, callsign, dimensions, and year built.
  - Standardized search input and action button to design tokens: `min-h-11`, `rounded-lg`, `border-border-subtle`, `bg-surface`, `bg-action`, accessible focus rings (`focus-visible:ring-2 focus-visible:ring-focus`), and `Loader2` spinner.
  - Added structured empty state (`"No vessels found matching “...”"`) and graceful unconfigured AIS tracking notice (`VESSELAPI_API_KEY` guidance).
- **Backend Vessel API test suite (`backend/tests/test_vessel_api.py`)**:
  - Implemented unit & integration test coverage for `VesselApiService`: unconfigured fail-closed behavior (`VesselApiNotConfiguredError`), Redis caching round-trips, search pagination and bounds enforcement, coordinate limits, and upstream response coercion. 9 tests passing under strict mypy typing.
- **Operations Home Return Affordance (`frontend/src/App.tsx:735`)**:
  - Added an accessible **"Operations"** return button in the active search header when authenticated, allowing staff to return directly to Operations Home with one click rather than manually clearing individual search query and filter chips.
- **Interactive Readiness Metrics (`frontend/src/components/operations/OperationsMetrics.tsx:14`, `OperationsHome.tsx:134`)**:
  - Turned static readiness metric cards (*Available now*, *On assignment*, *Unavailable*) into accessible button launchpads that trigger instant filtered contractor searches on click.
- **Verification & Gates**:
  - Backend: `ruff check` clean, `mypy` clean, `pytest` 210 passed (9 new).
  - Frontend: `tsc` & `eslint` clean, `vitest` 72 passed, `ui:audit:strict` 93 files clean.
  - Playwright: `operations-home.spec.ts` 56 passed across responsive viewports. Build bundle App chunk at 42.05 kB gzip.

## 2026-09-06 — Calm sign-in and sign-out transitions (Muse Spark)

Evolved the abrupt auth shell into calm-professional motion without changing security or data contracts.

- **Unified auth state (`frontend/src/hooks/useAuth.tsx`, `frontend/src/main.tsx:6`, `11`, `31`)**:
  `useAuth` was two disjoint states (`LoginPage.tsx:24` and `App.tsx:105` each held their own `user`). Login set only its own `user`; `App` waited for `ME_QUERY` `network-only` refetch `App.tsx:1639 void refreshSession()` before `isAuthenticated` flipped — delay + snap from `min-h-[calc(100dvh-4rem)]` hero to `OperationsHome.tsx:89 py-6`. Added lightweight `AuthProvider` + `AuthContext` around `<ApolloProvider>` per ADR `0006-auth-transition-shell` (consolidation, not new global state; `docs/decisions/0006-auth-transition-shell.md`). Both modal and shell now read/write the same `user/initialized`; login propagates optimistically, `refreshSession` is background revalidation only. Renamed `useAuth.ts` → `useAuth.tsx` to host JSX provider.
- **Shell AnimatePresence (`frontend/src/App.tsx:428`, `461`, `601`)**:
  Replaced the `if (!authInitialized) return` hard gate and the bare `&&` siblings `(!isAuthenticated || isSearchActive) ModernHeroSearch` / `!isSearchActive && isAuthenticated OperationsHome` / `isSearchActive` results header+chips+area with one grouped `AnimatePresence mode="wait" initial={false}` keyed by `shellKey = !authInitialized ? gate : !isAuthenticated ? public : isSearchActive ? search : ops`. Each branch is `motion.div initial {opacity:0,y:8} animate {opacity:1,y:0} exit {opacity:0,y:-6} duration 0.18-0.20 ease [0.22,1,0.36,1]` — calm-professional, no scale, token-consistent with existing modal/drawer/list/toast (`LoginPage.tsx:145`, `AppMenuDrawer.tsx:92`, `App.tsx:930`, `Toast.tsx:14`, `index.css:81`). Ambient `bg-radial-ambient` stays mounted; header remains outside presence with skeleton `h-8 w-20 animate-pulse` while `!authInitialized` to avoid premature `Sign in` reveal. `MotionConfig reducedMotion="user"` honors `prefers-reduced-motion`.
- **Sign-out choreography (`frontend/src/App.tsx:428`)**:
  `handleLogout` now closes the drawer `setIsMenuOpen(false)`, awaits `logout()` (optimistic `setUser(null)` + `clearStore`), then delays heavy workspace purge (`handleResetAll`, `clearShortlist`, `history.replaceState('/')`, etc.) by `220 ms` so the exiting `ops`/`search` snapshot animates intact instead of blanking mid-exit. Shows toast `Signed out — workspace cleared` via existing `Toast.tsx:14` motion after exit. Drawer exit `x:100% 0.24` completes before background snap — no snap-behind-drawer.
- **Sign-in polish**: Modal exit `200 ms` and shell crossfade `200 ms` overlap behind `bg-canvas/80 backdrop-blur-xs`; optimistic `setUser` means no `ME_QUERY` wait before ops home appears. No backend change; cookie `hydenlyne_session` still `schema.py:527` / `delete_cookie` + `revoke_session_token`.
- **OperationsHome stagger (`frontend/src/components/operations/OperationsHome.tsx:1`, `88`)**:
  Added `motion` container `staggerChildren 0.06 delayChildren 0.02` and `itemVariants {opacity:0,y:8 →1,0 0.20 [0.22,1,0.36,1]}` for greeting, attention/metrics/projects grid, and Find-a-contractor card — matches list stagger `App.tsx:930` and remains invisible under `prefers-reduced-motion`.
- **Snapshots & gates**: `npm run lint` clean, `npm run test` 72 passed, `npm run build` App `145.86 kB → 39.45 kB gzip` (motion already in bundle), `npm run ui:audit:strict` 91 clean, `npm run test:e2e:ci` `auth-gate` 16 passed, `operations-home`+`public-shell` 64 passed, `authenticated-flow` 69 passed (regenerated `authenticated-workspace-light-{mobile,tablet}` 1 px anti-alias baselines). `git diff --check` clean.

No migration, no new dependency, no public API change. Follow-up: none — transitions respect `isSearchActive` single checkpoint `useSearchWorkspace.ts:73`; future deep-link or restored-session entry points remain gated.

## 2026-09-06 — Open a dedicated pending-document review workspace (Codex)

- **Operations home**: The “Documents ready for review” action now opens an accessible, full pending-document dialog instead of opening and scrolling to the compact header Documents dropdown. The dialog shows each upload and contractor, supports opening the contractor dossier, and retains the existing approve/reject API workflow. Completed reviews refresh the home count and open dossier documents.
- **Regression coverage**: Operations-home browser coverage verifies the dialog and its pending documents across the configured responsive projects.

## 2026-09-06 — Automatically select and report compute mode (Codex)

- **Local launcher**: `scripts/local-stack.sh` now detects external power, NVIDIA device access, CDI availability, and `nvidia-smi` before each start. It selects CPU on battery or an unusable GPU, enables the GPU compose overlay and worker profile only when all checks pass, and prints the chosen mode with its reason. Explicit `HYDENLYNE_COMPUTE_MODE=cpu|gpu` overrides are safe: forced GPU fails rather than silently changing mode.
- **GPU overlay and regression test**: Added a narrowly scoped `docker-compose.gpu.yml` overlay which gives Ollama the NVIDIA device only in validated GPU mode, plus deterministic shell coverage for AC/GPU, battery/CPU, and rejected forced-GPU states. README documents the runtime policy.

## 2026-09-06 — Restore CPU-safe local stack startup (Codex)

- **Compose runtime**: Removed the unconditional NVIDIA CDI device requirement from the general Ollama service. It prevented the entire local stack from starting on hosts without `/dev/nvidia0`, despite the documented CPU-safe default. The explicit GPU Celery worker remains separately protected behind its `gpu` compose profile.

## 2026-09-06 — Put operations ahead of search after sign-in (Codex)

- **Authenticated home**: Moved the existing contractor search into a compact control below the greeting and staff operations summary. The large hero-height search remains only on the logged-out page; submitted searches retain the existing sticky result control. This makes actions, readiness, and active projects visible before search consumes vertical space.
- **Regression coverage**: Browser coverage asserts the “Needs attention” summary renders above “Find a contractor,” as well as retaining all existing search, responsive, role, and accessibility checks.

## 2026-09-06 — Correct operations-home status meanings (Codex)

- **Active projects**: `OperationsProjectsPanel` now requests only the existing GraphQL `ACTIVE` project status, so its heading and empty state no longer include planning, completed, or cancelled projects. Browser coverage asserts the query variable and absence of a planning project.
- **Crew readiness**: Preserved the backend `unavailable` state as frontend `Unavailable` rather than misrepresenting it as “Open to offers.” The operations card now clearly reports unavailable specialists as not currently available; existing genuinely open-to-offers profile data remains distinct.

## 2026-09-06 — Operations home for authenticated staff (Muse Spark)

Evolved the authenticated calm state into an operations home while preserving the public, logged-out hero and its privacy gate.

- **OperationsHome (`frontend/src/components/operations/OperationsHome.tsx`, `OperationsGreeting.tsx`, `OperationsAttention.tsx`, `OperationsMetrics.tsx`, `OperationsProjectsPanel.tsx`)**:
  New focused surface that replaces the signed-in empty search state. Shows a personal greeting via `getGreetingForUser` (first name, time-aware), a “Needs attention” list (pending contractor-upload documents via `GET /api/documents/review-queue` and expiring certifications via existing `expiringCertifications(days:60)` GraphQL), compact crew-readiness metrics (available / on assignment / open to offers / total derived from live `crewMembers` profiles), active-project overview (safe fields `clientName/projectName/projectType/location/country/startDate/endDate/status` via new typed `PROJECTS_QUERY`), and the existing natural-language contractor search as the prominent next action. Cards are role-aware: full operational cards only for `staff`/`admin` (checked via `isStaffOrAdmin`); non-staff see the greeting + safe search fallback with no sensitive detail. All actions are real: “Documents ready for review” opens the existing `IncomingDocumentAlert` (`#incoming-document-review` details), “Certificates expiring” triggers `Who has certifications expiring soon?` search, project rows trigger `projectType + location` search. Uses semantic tokens (`bg-surface`, `border-border-subtle`, etc.), `rounded-[14px]`, `min-h-9/11`, focus rings, and responsive layout (2×2 metric grid on desktop, stacked cards on mobile). Includes loading/empty/unavailable states (“No documents await review”, “Project data is unavailable”, etc.) and respects backend authorization (frontend is UX only).
- **Search hero preservation (`frontend/src/components/ModernHeroSearch.tsx:137`, `332`)**:
  Public hero (“Find the right contractor…”, Discover/Shortlist/Mobilize) now renders only for `!isAuthenticated`, keeping the logged-out privacy value proposition unchanged while the signed-in calm state shows the operations greeting instead. No change to `isSearchActive` gating for result-bearing UI.
- **Typed project contract (`frontend/src/lib/queries.ts:268`)**:
  Added `PROJECTS_QUERY` exposing only operationally safe fields; backend `project`/`projects` already exist and are tier-scrubbed (`scrub_project`).
- **Document review anchor (`frontend/src/components/IncomingDocumentAlert.tsx:61`)**:
  Added `id="incoming-document-review"` to the `<details>` so the operations home can open the existing review control without duplicating queue logic.
- **App composition (`frontend/src/App.tsx:6`, `103`, `240`, `653`)**:
  Imported `OperationsHome` and `isStaffOrAdmin`, added `handleOperationsSearch`/`handleOpenDocumentReview` callbacks, and composed the authenticated calm state as `ModernHeroSearch` (sticky search) + `OperationsHome` (greeting + metrics + attention + projects) without altering search-result behaviour or `isSearchActive` semantics. Keeps `App.tsx` from growing unchecked — operations concerns live in `src/components/operations/`.
- **Pure utils and unit tests (`frontend/src/utils/operationsHome.ts`, `frontend/src/utils/operationsHome.test.ts`)**:
  Added `getFirstName`, `isStaffOrAdmin`, `getGreeting`, `deriveCrewReadinessMetrics`, `formatProjectSearchQuery`, `formatExpiringCertSearchQuery` with 72 Vitest cases (total 72, up from 58). No fabricated coverage/mobilization counts — only real profile/queue/cert/project data.
- **Playwright coverage (`frontend/tests/operations-home.spec.ts`)**:
  Staff sees greeting, attention counts, 2×2 metrics, projects, and actionable rows; non-staff sees greeting + safe search and no operational cards; documents row opens review control; certificates row and project rows trigger filtered searches; empty/unavailable states; responsive and a11y checks across 375/768/1024/1440 (mobile/tablet/desktop/wide) plus light-theme variant. Updated `authenticated-workspace` and `public-shell` baselines after intentional Menu/hero changes. `172 passed, 3 skipped, 1 flaky` (light mobile 1-pixel retry) in `npm run test:e2e:ci`.
- **Quality gates**: `npm run lint` (tsc + eslint) clean, `npm run test` 72 passed, `npm run build` 41.0 KiB gzip for `App` chunk (under 100 KiB async budget), `npm run ui:audit:strict` 91 files clean, `git diff --check` clean.

No migration, new dependency, public API, or ADR — full mobilisation/coverage intelligence still waits for real project-to-contractor assignment data.

## 2026-09-06 — Make workspace navigation clearer on every screen (Codex)

- **Workspace menu (`frontend/src/App.tsx`, `frontend/src/components/AppMenuDrawer.tsx`)**:
  Kept the existing sticky, role-aware workspace navigation and made its
  hamburger trigger visibly say “Menu” at every width. Connected the trigger
  and dialog with `aria-controls`/`aria-expanded`, and added a concise dialog
  description so assistive technology receives its purpose before the action
  groups. This is intentionally not a breadcrumb or new site navigation:
  Hydenlyne is a single-page private workspace and those patterns would add
  noise without new destinations. No data, API, authorization, or persistence
  contracts changed.
- **Regression coverage (`frontend/tests/ui-consistency.spec.ts`)**: asserts
  the visible mobile-safe Menu label while retaining the existing overflow and
  accessibility coverage.

## 2026-09-06 — Restore public hero and repair logged-out shell a11y/visual tests (Muse Spark)

Restored the privacy-safe value proposition that had regressed to logo-only.
Addresses the logged-out review verdict and the stale public-shell test suite
(9 failures, 3 flaky before this slice).

- **Public hero (`frontend/src/components/ModernHeroSearch.tsx:128`)**:
  Replaced the `sr-only` brand heading with the approved visible H1
  “Find the right contractor for the next campaign.” plus supporting line
  “Search Hydenlyne’s private specialist network by discipline, certification,
  region, and availability.”  Replaced the surveillance-toned footer
  “Private workforce system · Access is monitored” with the factual
  “Private workforce network. Access is protected.”  Made the static
  three-step preview Discover → Shortlist → Mobilize render for every calm
  (logged-out) shell — no names, documents, rates or live availability are
  exposed — previously it was `isAuthenticated`-gated.  Keeps the glossary
  (`shortlist`/`mobilization`) and preserves the existing sign-in gate;
  no placeholder “Request access” CTA was added until a real operations
  contact route exists.
- **Shell landmarks (`frontend/src/App.tsx:406`, `frontend/src/main.tsx:32`)**:
  Both the `authInitialized` gate and the `Suspense` fallback in `main.tsx`
  were landmark-free (`<html>`-only during the initial async session check
  and lazy load).  They now render `<main id="main-content">` and the same
  approved H1 so axe’s `landmark-one-main`/`page-has-heading-one` checks
  and the Playwright heading wait never race the session request.  Preserves
  `isSearchActive` as the single auth-derived checkpoint (`useSearchWorkspace.ts`)
  — `frontend/tests/auth-gate.spec.ts` (16 cases) still passes, unauthenticated
  `?q=`/`?view=` deep links never render result chrome nor fire
  `CrewMembers`/`QueryCrew`/`SearchCrew`.
- **Sign-in surface (`frontend/src/components/LoginPage.tsx:122`)**:
  Aligned the dialog footer copy with the shell trust line.
- **Tests (`frontend/tests/ui-consistency.spec.ts:5`, snapshots)**:
  Fixed the stale expectation that still looked for the campaign headline
  while the component rendered only `sr-only`.  Added explicit waits for the
  headline (and for `Private workforce network…`/`Discover`/`Mobilize`)
  before axe/screenshot so the suite no longer races the session/lazy load.
  Regenerated `public-shell-*-linux.png` baselines.  Verified
  `20 passed, 0 failed` twice consecutively (was `12 passed, 9 failed, 3 flaky`);
  `auth-gate` remains `16 passed`.  `lint`/`tsc`/`vitest` (58)/`build`/
  `ui:audit:strict` clean.

Follow-up: no pricing or social-proof placeholders added per the guide (internal
private workforce system).  If Hydenlyne later wants a genuine
“Request access / contact operations” path from the logged-out page, add a real
route/handler rather than a mailto placeholder.  The backend least-privilege
changes from the preceding entries in this working tree (`backend/app/domain/
access_tiers.py`, `backend/app/graphql/scrub.py`, etc.) remain uncommitted on
purpose — they belong to the security release and should be committed/released
separately from this UI slice.

## 2026-09-06 — Enforce least privilege across every read path (step 2+3 of security release) (Muse Spark)

Implemented field-level least-privilege for every GraphQL, REST, and search
projection read path per ADR 0005:

- **GraphQL tier scrubbing** (`backend/app/graphql/scrub.py`, `backend/app/graphql/schema.py:77`):
  Added `scrub_crew_member`/`scrub_certification`/`scrub_document`/`scrub_project`
  helpers using `access_tiers.tier_for_role`. `crewMembers`/`searchCrew`/`crewMember`
  now tier-scrub (T1 C1-only, T2 C1+C2, T3 full; roster workHistory/internalNotes
  and `certNumber`/`issuingBody` stripped for T1, passport/visa/medical/insurance
  and `dateOfBirth` stripped for T1/T2). `expiringCertifications` tightened to
  `@require_staff`, `complianceStatus` to `@require_admin`, `document`/`documentsByCrew`
  return `null`/`[]` for T1 and strip `extractedText`/`extractedData` for T2,
  `project`/`projects` scrub `requirements`/`crewAssigned`, `generateReport`
  branches `COMPLIANCE`/`PERFORMANCE`/`PROJECT_READINESS` to T2+ (T1 `FORBIDDEN`).
- **REST hardening** (`backend/app/api/documents.py:510`, `backend/app/api/search.py:54`,
  `backend/app/api/dropbox.py:265`): `GET /api/documents/{id}/download` and
  `POST /api/dropbox/download/{id}` now `@require_admin_rest` (T3), `GET
  /api/documents/{id}/status` now `@require_staff_rest` (T2), `GET
  /api/search/documents` now `@require_staff_rest` with C3 stripping for T2,
  `GET /api/search/crew` strips `MEILISEARCH_CREW_DENIED_FIELDS` defense-in-depth.
- **Search-index minimisation** (`backend/app/services/consultant_knowledge.py:68`,
  `backend/app/services/meilisearch.py:63`, `backend/app/domain/access_tiers.py:192`):
  General `crew_members` index is now C1-only (`id`, `full_name`, `nationality`,
  `country_of_residence`, `gender`, `languages`, `flying_point`,
  `availability_status`, `tags`, `publication_status`, plus C1 text fields);
  `email`/`phone`/`passport`/`medical`/`insurance` and `extracted_data` never
  indexed; searchable attributes C1-only. Reindex via existing keyset path
  produces C1-only docs.
- **Frontend** (`frontend/src/lib/queries.ts:3`): Split roster query to
  C1-only `CREW_MEMBERS_QUERY` (removed `email`/`phone`/`dateOfBirth`/`passport`/
  `visa`/`medical`/`insurance`/`workHistory`/`internalNotes` and limited
  `certifications` to C1 fields); added `CREW_MEMBER_DETAIL_QUERY` (C1+C2+C3)
  for T2/T3 dossier views. `DocumentsByCrew` remains tier-scrubbed server-side.
- **Tests** (`backend/tests/test_field_level_auth.py`, `backend/tests/test_meilisearch_sync.py:51`):
  Added 24 negative authorization cases covering T1/T2/T3 for roster/detail
  field redaction, documents `null`/`[]`/C3 stripping, `expiringCertifications`
  `FORBIDDEN` for T1, `complianceStatus`/`generateReport` branching, REST 403s
  for download/status/document-search, crew-search hit stripping, and
  `test_meilisearch_doc_is_C1_only`. Updated `test_meilisearch_sync` to assert
  C1-only (no `email`/`phone`). All 201 backend tests pass (2 deselected);
  frontend `tsc --noEmit`/`eslint`/`vitest` (58) and `ui:audit:strict` clean.
- **Docs** (`docs/AUTHORIZATION.md`): Updated GraphQL/REST tables to reflected
  enforced decorators/tiers, search policy to describe C1-only projection and
  hit stripping, and enforcement status to implemented (remaining follow-up:
  wire `CREW_MEMBER_DETAIL_QUERY` into dossier pane, append-only audit table,
  retention/outbox).

## 2026-09-06 — Define access tiers and data classifications (policy, step 1 of security release) (Muse Spark)

Established the single authoritative data-classification policy that gates the
follow-up least-privilege enforcement. No runtime behavior changed in this
commit — policy precedes code so every later field check has one source of
truth.

- **ADR 0005** (`docs/decisions/0005-field-level-access-and-data-classification.md`):
  Defines three classifications — **C1 Recruiter-safe** (name, role, skills,
  availability, verified certification status/dates), **C2 Restricted
  operational** (contact details, work history, certificate numbers, document
  metadata), **C3 Compliance-only** (DOB, passport/visa/medical/insurance,
  raw documents, `extracted_text`/`extracted_data`, storage paths) — and three
  access tiers **T1** (any authenticated → C1), **T2** (staff scoped + admin →
  C1+C2), **T3** (admin only → C1+C2+C3). Records fail-closed default
  (unmapped field = C3/deny), Meilisearch separation (general index C1-only,
  compliance projection only with proven need), and the expand/migrate/contract
  path for enforcement. Includes alternatives, consequences, and validation
  checklist.

- **`docs/AUTHORIZATION.md`**: Promoted from operation-level matrix to
  field-level matrix. Added Data classification section, exhaustive
  field → class mapping (mirroring the domain module), Access tiers table
  with scope rules (draft ownership, `submitted_by` scoping for staff), per-query
  and per-REST target tiers (e.g. `crewMembers`/`searchCrew` T1/C1-only,
  `/download` T3/C3, `complianceStatus` T3), Search and projection policy
  (C1-only general `crew_members` index, `SEARCHABLE_DOCUMENTS_FILTER`
  retention, deletion/revocation propagation), and Enforcement status
  (policy-only this commit, code enforcement next). No role widened.

- **`backend/app/domain/access_tiers.py`** (new, strict-typed, framework-free):
  Machine-readable field → class maps for `CrewMember`/`Certification`/
  `WorkHistory`/`Document`/`Project`, nested GraphQL paths (`passport.number`,
  etc.), `MEILISEARCH_CREW_C1_FIELDS` allow-list and `MEILISEARCH_CREW_DENIED_FIELDS`
  deny-list, and helpers `classification_for_crew_field`, `is_allowed_for_tier`,
  `tier_for_role`. Verified `ruff format --check` / `ruff check` clean,
  `mypy app/domain/access_tiers.py` 0 issues. Backend `ruff check app` clean;
  `ruff format --check app tests` still flags pre-existing `app/api/documents.py`
  formatting (not introduced here); `mypy app` shows the pre-existing
  `numpy/__init__.pyi` 3.12 syntax error (env pin mismatch, not introduced here).

Follow-up (same security release, next PR): replace broad `CrewMember` returns
with tier-scoped DTOs/field resolvers, split Meilisearch to C1-only and rebuild
via `reindex_all_crew` keyset path, split `CREW_MEMBERS_QUERY` / `DocumentsByCrew`
frontend queries, and add negative authorization tests for every C2/C3 field,
document classification, and download route. Audit append-only table, retention,
and outbox/reconciliation remain steps 4–6.

## 2026-09-05 — Route & modal dynamic code-splitting and bundle payload optimization (Antigravity)

Optimized the initial frontend bundle delivery and eliminated monolithic route coupling:
- **Top-Level Route Splitting (`src/main.tsx`)**:
  - Dynamically split `App.tsx` (the recruiter workspace) and `ContractorDocumentUploadPage.tsx` (the external contractor upload portal) via `React.lazy()` and `Suspense`.
  - External contractors uploading compliance documents now load only the 4.64 kB entry chunk and their 17.33 kB portal chunk, completely skipping the 136 kB main recruiter dashboard and mock datasets.
  - Reduced the initial entry bundle `index-*.js` from **162.94 kB (44.66 kB gzip)** down to **4.64 kB (2.27 kB gzip)** — a **97% reduction** in initial JavaScript payload.
- **Heavy Modal Lazy-Loading (`SpecialistDossierPane.tsx`)**:
  - Dynamically imported `DocumentPreviewModal` and `DossierRadarModal` on demand when requested by user interaction, deferring document previewing and SVG radar dependencies from the main pane mount.
- **Verification**:
  - `npm run lint` (`tsc --noEmit && eslint .`) clean with 0 errors.
  - `npm test` (58/58 unit tests passed).
  - `npm run ui:audit:strict` passed across 84 source files.
  - `npx playwright test search-bar-natural-language.spec.ts` (20/20 E2E tests passed).
  - Production `vite build` completed in 6.62s.

## 2026-09-05 — Specialist dossier modular decomposition & UI architecture hardening (Antigravity)

Decomposed monolithic `SpecialistDossierPane.tsx` (previously 1,238 lines) into clean, decoupled sub-tab components located in `frontend/src/components/dossier/`:
- **Sub-Tab Architecture**:
  - `DossierHeader.tsx`: Handles focused contractor workspace banner, contractor avatar/status, rate badge, shortlist toggle, and accessible ellipsis actions.
  - `DossierOverviewTab.tsx`: Encapsulates context strip, AI summary, executive bio, interactive at-a-glance metrics cards, survey disciplines, and summary credentials.
  - `DossierExperienceTab.tsx`: Encapsulates past client track record, historical projects data table, geographical zones, and survey disciplines.
  - `DossierCredentialsTab.tsx`: Manages personal details, certifications badge grid, completion/expiry list with 30/60/90-day warning badges, proof viewer trigger, and compliance verification controls.
  - `DossierExpertiseTab.tsx`: Manages technical competency tags with live real-time query filtering.
  - `DossierSystemsTab.tsx`: Renders categorized hardware and software system proficiencies.
  - `DossierRadarTab.tsx`: Displays candidate skill radar chart and methodology criteria.
  - `DossierBottomBar.tsx`: Houses animated email copy feedback, LinkedIn deep link, and mobilization request triggers.
  - `DossierRadarModal.tsx`: Extracted modal dialog and backdrop with focus trap for radar exploration.
- **Engineering Standards Compliance**:
  - Reduced `SpecialistDossierPane.tsx` from 1,238 lines down to 296 lines (satisfying the `<300` lines threshold from `docs/ENGINEERING_STANDARDS.md`).
  - 100% semantic color token adherence verified by `npm run ui:audit:strict` (84 source files clean).
  - TypeScript strict typing (`tsc --noEmit`), ESLint, Vitest (58 tests passed), and production Vite build passed with zero warnings.

## 2026-09-05 — Natural language search bar testing & offshore medical refinement (Antigravity)

Executed end-to-end testing of the search bar across natural language queries and automated UX flows:
- **Natural Language Live Verification**: Evaluated multiple plain English queries against the live backend engine (`queryCrew` via GraphQL with PostgreSQL and Ollama):
  - `"Show surveyors available immediately"`: matched 11 contractors with active availability.
  - `"Who has BOSIET certification?"`: matched 14 contractors with valid or active BOSIET credentials.
  - `"Find crew with IMCA"`: matched 9 contractors with IMCA credentials across IMCA Survey QC, Client Rep, and Geotech.
  - `"Find Dutch consultants available immediately"`: matched 3 available Dutch specialists.
  - `"Show specialists with JNCC MMO"`: matched 10 MMO accredited contractors.
  - `"Find crew with NEBOSH"`: matched 8 contractors with NEBOSH credentials.
  - `"Who has valid STCW?"`: matched 5 contractors with in-date STCW certificates.
  - `"Show available client reps"`: matched 4 available client representatives.
  - `"Who has a current offshore medical?"`: refined `app/domain/crew_query_rules.py` to recognize "offshore medical" as part of the medical certificate family rather than creating a separate project/skill requirement that falsely constrained results. Now reliably returns the 5 specialists with valid offshore medicals.
- **Automated Frontend Test Suite (`tests/search-bar-natural-language.spec.ts`)**: Added 20 automated Playwright tests verifying:
  - Input debounce and natural language query execution with GraphQL integration.
  - Interactive AI criteria badges and summary banner rendering (`CrewQuerySummary`).
  - Filtered contractor dossiers rendering in the results workspace.
  - Keyboard shortcuts (`/` to focus, `Enter` to search, `Escape` to blur).
  - "Recent Searches" history dropdown in localStorage (storage, retrieval, jump-to-search, clear history).
  - Quick discovery chips populating and triggering searches.
  - Search clear (`X`) button resetting the workspace to the calm hero state.
  - All 20 tests passed across mobile, tablet, desktop, and wide viewports.
- **Code Quality**: `tsc --noEmit`, ESLint, vitest (58 tests), and backend query tests (11 tests in `test_crew_query.py`) all pass cleanly.

## 2026-09-05 — Contractor document upload portal redesign (Antigravity)

Redesigned the contractor document upload route (`/upload/:token`) into an exceptionally crafted, fully responsive, professional maritime portal:
- **Branding & Top Bar**: Integrated `HydenlyneAnimatedLogo` with the signature orange seismic waveform animation, 256-bit encryption session badge, and in-page dark/light `ThemeToggle`.
- **Classification & Drag-and-Drop Dropzone**: Added segmented classification selectors for Certificates, Medical / ENG1, Seaman's Book, and Passport / ID; interactive drag-and-drop dropzone with animated hover states, format chips (`PDF`, `DOCX`, `JPG`, `PNG`, `Max 50MB`), and mobile/touch file selection.
- **Client-Side Validation & Preview**: Instant size checks (≤ 50MB) and format validation with actionable alert feedback and selected file preview card.
- **Multi-Upload & Completion Flow**: Confirmed submission card with receipt details and "Upload Another Document" button to allow batch uploads without page reload.
- **Strict Theme & Design System Conformance**: Built with 100% semantic color tokens (`bg-canvas`, `bg-surface`, `bg-surface-raised`, `border-border-subtle`, `text-primary`, `text-secondary`, `text-muted`, `var(--ui-brand-pulse)`), zero raw palette colors, passing strict UI audits and gzip bundle budgets.
- **API & Testing**: Updated `frontend/src/lib/documentsApi.ts` to return typed expiry information (`PublicDocumentRequestInfo`) and support classification payloads; added unit tests in `frontend/src/lib/documentsApi.test.ts`.

## 2026-09-05 — Application containers rebuild and full stack refresh (Antigravity)

Executed clean production compilation and full container stack refresh:
- **Frontend Container Rebuild**: Validated TypeScript (`tsc --noEmit`) and ESLint, built production client assets, rebuilt multi-stage image `localhost/hydenlyne-crew-dms_frontend:latest`, and recreated `hydenlyne-crew-dms_frontend_1` on port 5173.
- **Backend & Worker Stack Refresh**: Confirmed Alembic schema migrations at head (`015_contractor_document_requests`), restarted FastAPI backend (`hydenlyne-crew-dms_backend_1`), and restarted all Celery queues (`celery_worker`, `celery_compute_worker`, `celery_beat`, `flower`).
- **Verification**: Verified health endpoints (`5173/health`, `8000/health/`), GraphQL schema, document review endpoints, and confirmed all 176 backend unit/integration tests pass.

## 2026-09-05 — Contractor document review & compliance approval workflow (Antigravity)

Implemented end-to-end admin/staff review actions for incoming contractor documents and vault documents:
- **Domain Service (`app/services/document_requests.py`)**: Added `DocumentRequestService.resolve_review` supporting resolution by review ID or document ID. Validates actor authorization (staff scoping rules vs admin), transitions `IncomingDocumentReview.status` to `resolved` or `rejected`, sets `Document.extraction_status` to `approved` or `rejected`, and records access logs via `audit_service.log_access`.
- **API Transport (`app/api/documents.py`)**:
  - Added `POST /api/documents/review-queue/{review_id}/action` (actions: `approve`, `reject`).
  - Added `POST /api/documents/{document_id}/review` (actions: `approve`, `reject`) for direct compliance review on any vault document.
  - Enriched `GET /api/documents/review-queue` response with document metadata (`file_type`, `file_size`, `classification`, and `extraction_status`).
- **Frontend UI & API**:
  - `frontend/src/lib/documentsApi.ts`: Added `actionIncomingDocumentReview` and `reviewDocumentById`.
  - `frontend/src/hooks/useSpecialistDocuments.ts`: Exposed `reviewDocument(profileId, docId, action, note)` and mapped `isVerified: doc.extractionStatus === 'approved'`.
  - `frontend/src/components/IncomingDocumentAlert.tsx`: Added inline Approve (check) and Reject (X) buttons with loading spinners and feedback toasts.
  - `frontend/src/components/DocumentPreviewModal.tsx`: Added compliance review status badges ("Pending Review", "Approved for Compliance", "Rejected") and Approve/Reject action buttons with confirmation.
  - `frontend/src/components/DocumentVault.tsx`: Added status chips (`Needs Review`, `Rejected`), inline quick-review buttons for pending documents, and forwarded review actions to `DocumentPreviewModal`.
  - `frontend/src/components/SpecialistDossierPane.tsx`, `ProfileDetailModal.tsx`, `App.tsx`: Wired review handling and auto-refresh on action resolution.
- **Testing & Quality**: Added 4 test cases in `backend/tests/test_documents.py` covering approval, rejection, cross-staff authorization denial, and direct document ID reviews. 176 backend tests passed. TypeScript typecheck, ESLint, and Vite production build passed cleanly.

## 2026-09-05 — Fix PostgreSQL naive datetime collision on document request creation (Antigravity)

Resolved "Failed to fetch" network error occurring when staff clicked "Request documents":
- Root Cause: `DocumentRequestService.create` in `app/services/document_requests.py` generated `expires_at = datetime.now(timezone.utc) + timedelta(...)` with an offset-aware timezone (`tzinfo=timezone.utc`). PostgreSQL column `document_requests.expires_at` was created as `TIMESTAMP WITHOUT TIME ZONE` in migration 015, causing `asyncpg` to throw `TypeError: can't subtract offset-naive and offset-aware datetimes` on `INSERT`.
- Exception Handling & CORS: The resulting unhandled 500 error triggered Starlette's server error middleware outside `CORSMiddleware`, causing the browser to receive an error response missing CORS headers and report `TypeError: Failed to fetch`.
- Fixes:
  - `backend/app/services/document_requests.py`: Normalized `expires_at` to naive UTC before persistence into `document_requests.expires_at`, and ensured expunged requests attach timezone-aware UTC datetime.
  - `backend/app/main.py`: Reordered middleware so `CORSMiddleware` wraps error-logging and rate-limiting middlewares, guaranteeing CORS headers accompany error responses.
  - `frontend/src/lib/documentsApi.ts`: Parsed JSON error payload `detail` to surface actionable error messages on API failures.

## 2026-09-05 — Celery queue segregation, Thin Transport docs, and keyset reindexing backpressure (Antigravity)

Tackled three key scalability and maintainability improvements:
- **Celery Worker Queue Segregation** (`app/tasks/celery_app.py`, `docker-compose.yml`): Defined explicit queues `high_priority`, `heavy_compute`, and `indexing`. Segregated worker topology into `celery_worker` (concurrency 4, processing `high_priority,default` for compliance checks, alerts, and quick tasks) and `celery_compute_worker` (concurrency 2, processing `heavy_compute,indexing` for OCR, Ollama extraction, and embedding sync) to prevent heavy tasks from starving latency-sensitive jobs. Added regression test `tests/test_celery_routes.py`.
- **Re-indexing Backpressure & Keyset Pagination** (`app/services/consultant_knowledge.py`, `app/services/meilisearch.py`, `reindex_crew_search.py`): Replaced unbounded in-memory table loading (`.scalars().all()`) and 1-by-1 HTTP calls with keyset-paginated cursor streaming (`WHERE id > :last_id ORDER BY id ASC LIMIT :batch_size`) and bulk Meilisearch batching (`index_crew_members` and `delete_crew_members`). Added `--batch-size` CLI flag to `reindex_crew_search.py`. Added unit test `tests/test_reindex_batching.py`.
- **Dual-Transport Maintenance & Thin Transport Rule** (`docs/ARCHITECTURE.md`): Codified the Thin Transport architectural contract for FastAPI REST routes and Strawberry GraphQL resolvers, establishing zero direct ORM mutations in transport, strict domain service encapsulation, and canonical exception mapping.

## 2026-09-05 — Edge-case audit, ADR 0002 fail-closed fix, and upload link security (Antigravity)

Conducted end-to-end edge-case testing across auth, document search, and contractor uploads:
- Fixed critical ADR-0002 token revocation fail-open bug (`app/auth/session.py`): `is_token_revoked` now explicitly verifies Redis availability and fails closed when Redis is offline or errors. Added 3 regression tests in `tests/test_auth.py`.
- Repaired Meilisearch document search projection (`app/api/search.py`, `app/services/meilisearch.py`): Replaced restrictive `extraction_status = "approved"` filter with `SEARCHABLE_DOCUMENTS_FILTER = 'extraction_status IN ["approved", "extracted"]'`, making certificates, passports, and non-CV compliance documents searchable.
- Hardened contractor upload links (`app/api/documents.py`, `app/services/document_requests.py`): Non-admin staff cannot create links for drafts submitted by other staff; review queue queries are scoped to owned drafts/approved contractors; contractor link upload rejects CV classifications (which require staff review workflow).
- Resolved contractor upload race condition (`app/api/documents.py`): Added `IntegrityError` rollback and storage cleanup for concurrent identical idempotency keys; aligned extraction failure dispatch status.
- Fixed email file magic bytes (`app/services/upload.py`): Added standard RFC 5322 MIME headers (`From:`, `Received:`, `Date:`, `Subject:`, etc.) to prevent rejection of valid `.eml` files.
- Fixed test suite DB isolation bootstrap (`backend/tests/conftest.py`): Added `Base.metadata.create_all` to `_ensure_tables` to guarantee per-PID SQLite schema creation.
- Enhanced public upload URL routing (`frontend/src/main.tsx`): Supported optional trailing slashes and decoded tokens.

## 2026-09-05 — Staff document-request permission (Codex)

Made the new secure document-request link available to both staff agents and
administrators, while keeping manual document upload and deletion restricted
to document managers. This gives agents the intended contractor-facing action
without widening access to existing sensitive document controls.

## 2026-09-05 — Contractor document upload links and review queue (Codex)

Added provider-free, 14-day contractor document-upload links so operations can
replace WhatsApp downloads with direct, validated submissions. Uploaded files
reuse the existing storage/extraction pipeline and create durable staff review
queue entries; raw tokens are never stored. Added migration 015, public upload
page, staff link creation from the document vault, regression coverage, and ADR
0004. Follow-up: expose the review queue as a dedicated staff workspace panel
and add email delivery once a provider is available.

## 2026-09-05 — Animated Hydenlyne Logo & Clean Minimal Search Hero (Antigravity)

Moved the pulse line animation off the search bar and placed it directly inside the official Hydenlyne logo (`HydenlyneAnimatedLogo`) centered above the search input. The signature orange waveform draws across the company mark from left to right (spike up, plunge down, and horizontal underline under "HYDENLYNE") with smooth `motion/react` stroke easing upon calm view mount, then settles into the authentic brand mark. Restored the search bar container to a pristine, minimalist rounded input free of extraneous border shapes. Verified via strict UI token audits, unit tests, and production build.

## 2026-09-05 — Live migration and search projection rebuild (Codex)

Applied Alembic revisions 013 and 014 to the configured live PostgreSQL
database, advancing it to `014_upload_idempotency`. Rebuilt the Meilisearch
contractor projection: all 110 approved contractors were indexed with
`publication_status=approved`; no current non-approved records were indexed.
The live backend health check returned healthy.

## 2026-09-05 — Review-gated CV ingestion and staff submissions (Codex)

Added a `staff` role boundary and changed CV-led specialist creation into a
draft → deterministic extraction → administrator review → publication flow.
CV extraction now stages a durable `CVReview` proposal and never changes or
indexes the canonical profile until an admin approves the reviewed data.
Drafts are excluded from ordinary and natural-language search and are visible
only to their submitter or an admin. Exact name/email duplicates are blocked
unless an administrator explicitly confirms the person is distinct.

Added migrations `013_add_cv_review_workflow` and
`014_add_document_upload_idempotency`, staff/admin authorization,
approval/rejection and role-promotion GraphQL operations, draft document access
checks, the guided submission/review UI, an admin staff-access screen,
privacy-safe profile-read auditing, and focused security/publication tests.
Review decisions are transactionally locked so concurrent administrators cannot
publish conflicting outcomes.
CV uploads also carry a bounded idempotency key so a lost response and browser
retry cannot create a second document for the same submission.
Document search now excludes all processing, rejected, and failed extractions.
The legacy password migration now supports offline SQL generation, allowing the
complete migration chain to be checked before deployment.
Added `backend/reindex_crew_search.py` for safe, repeatable rebuilding of the
Meilisearch projection after direct imports or search-field contract changes.
The upload UI safely retries against the original draft, queue failures are
visible, and legacy agent CV uploads cannot bypass review. Natural-search
fallback rules cover North Sea work, surveyors available next month, offshore
medics, in-date qualifications, and experience thresholds when the local AI
service is unavailable.

Validation: backend Ruff, mypy, Bandit, 160 pytest tests (2 deselected), one
Alembic head, and PostgreSQL upgrade/downgrade SQL pass. Frontend lint, 54 unit
tests, production build, strict UI audit, and Playwright (105 passed, 3 skipped)
pass; browser coverage
includes accessible CV review and staff-access dialogs across mobile, tablet,
desktop, and wide viewports.

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
