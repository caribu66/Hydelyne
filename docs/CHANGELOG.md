# Changelog

## Showcase stack live with demo data (2026-09-30)

- Committed the tree as `0c92236` (61 files; `.claude/worktrees/` left
  untracked, `.env` stays ignored). Repo-local git identity set from the
  user's email (name derived as Sebastien Joseph Gregor — correct on request).
- Local stack (`scripts/local-stack.sh`) running: backend/frontend healthy,
  unauthenticated `me` returns `{me: null}`, admin login works
  (`admin@hydenlyne.local`, local-only `.env` password), seeded 100 crew via
  additive `seed_100.py` for 107 total with working keyword search.
- Observed, not blocking the demo (browser uses cookies, which work): a body
  `token` replayed as `Authorization: Bearer` got `UNAUTHENTICATED` on
  `crewMembers`. Follow-up: check token-vs-cookie handling in the auth
  context path. Also noted live: login rate limiting (5/5min) engages
  correctly — avoid rapid repeat logins during the demo. Tool: OpenCode/Muse Spark.

## Showcase readiness — all backend tests green (2026-09-30)

- Fixed all 11 failing backend tests on top of the uncommitted WIP tree; full
  suite is now 736 passed (2 `llm`-marked deselected by default config), with
  `ruff check`, `mypy` (60 files), single Alembic head, and `git diff --check`
  clean. Frontend untouched and green: `tsc`+ESLint, 239 vitest tests,
  `ui:audit:strict`. Both container images (`backend/`, `frontend/`) build
  under Podman and `compose config` validates. Tool: OpenCode/Muse Spark.
- Root causes (verified against HEAD via `git stash`, not assumed):
  - 5 failures pre-existed at HEAD (never-passing tests): wrong import
    (`app.services.auth`, which does not exist — `auth_service` lives in
    `app.services.crew`), a detail query that never selected `documentRef`,
    two Dropbox download fixtures using 3-part paths that were never managed
    (endpoint correctly 404s), and a patch target
    (`app.services.upload.dropbox_request`) that never existed — the call
    goes through `dropbox_request_status`.
  - 6 failures came from the WIP tree: `list_crew_members` was made lenient
    (blank→unfiltered, oversized→`[]`), `_extracted_certification_status`
    was reordered expiry-first, and the medical projection was loosened to
    not-rejected; conftest's new `index_document`/`delete_document`
    instance mocks shadowed the real methods two task-wait tests exercise.
- Deliberate contract decisions where committed tests conflicted:
  - Blank/oversized keyword search stays fail-closed (`ValueError`, matching
    GraphQL/REST/`process_query`); the two hardening tests were aligned to
    the strict contract instead of weakening the boundary test.
  - Lifecycle vs trust split into two axes: `_extracted_certification_status`
    stays verification-first; `link_extracted_certificate` derives
    date-driven warnings (`expired`/`expiring_soon`) from document evidence
    but demotes positive `valid` to `pending_verification` (same demotion as
    `update_certification`); the medical projection uses one shared
    `counts_as_medical_evidence` predicate (verified, or document-backed and
    not rejected — bare pending rows never populate), now shared by both
    reconcile paths and the compliance recompute instead of three copies.
- Remaining risk: `ruff format --check` still flags pre-existing drift in 44
  files (untouched lines only — new/edited lines are format-clean); the
  `alembic` venv shim has a stale shebang (use `python -m alembic`).

## Container startup, build hardening & session initialization fixes (2026-09-17)

- Removed `:ro` flag from Ollama `/models` volume mount in `docker-compose.yml` so Ollama can initialize its manifests directory and download models on clean hosts without read-only filesystem crashes.
- Added `frontend/.dockerignore` and `backend/.dockerignore` to prevent host `node_modules`, `dist`, `.venv`, and build caches from stomping on container build stages during `COPY . .`.
- Removed build-time `nginx -t` from `frontend/Dockerfile` which failed under rootless Podman build namespaces attempting to bind port 80.
- Resolved "Loading session…" hang:
  - In `backend/app/graphql/schema.py`, removed `@require_auth` from `me` and added session token user extraction so `me` query returns `data: { me: null }` without error when unauthenticated instead of raising an `UNAUTHENTICATED` GraphQLError.
  - In `frontend/src/lib/apollo.ts`, guarded `hydenlyne:session-expired` so `Me` probe queries do not trigger false session expirations and cache resets.
  - In `frontend/src/hooks/useAuth.tsx`, ensured `setInitialized(true)` is set on session expiration so the public view is rendered without blocking.
- Successfully verified `./scripts/local-stack.sh start` and end-to-end unauthenticated/authenticated flows: all 11 services running and healthy. Tool: Antigravity.

## Hidden-Bug Pass 376 — AI-result synthesis and sorting integrity (2026-09-15)

- AI-synthesized roster rows now reuse the local mapper's conventions instead
  of maintaining a divergent fallback set: initials avatars via `avatarFor`
  (empty `src` broke images in shortlist/detail views) and tag-derived
  departments via `departmentFromTags` (empty badge), both newly exported from
  `lib/mappers.ts` as the single source of truth.
- Unknown experience now sorts last in ascending experience order (previously
  presented first as zero years), mirroring the existing rate-asc
  nulls-last pattern. Descending order already placed unknowns last.
- The dossier "latest project" is now derived by parsed start-date instead of
  lexicographic comparison, so malformed values like "Q3 2024" can no longer
  outrank a real ISO date; entries without parseable dates sort last. New
  `latestWorkHistoryEntry` helper in `dossierUtils.ts` with coverage.
- Left deliberately unchanged after inspection: the tag-derived title guess
  and `On-site` default match the local mapper's own conventions; unknown
  availability mapping to `Unavailable` matches the backend fail-closed
  doctrine; the experience-range filter excluding unknowns is fail-closed too.
- Added regression coverage (6 tests). Frontend tests (239), TypeScript,
  ESLint, build, and UI audit passed. Tool: OpenCode/Muse Spark.

## Hidden-Bug Pass 375 — provider timeouts and worker efficiency (2026-09-15)

- Bounded all synchronous search-provider calls with finite client timeouts:
  Qdrant 30s (`QDRANT_REQUEST_TIMEOUT_SECONDS`, also used by both `/health`
  probes) and Meilisearch 10s (`MEILISEARCH_REQUEST_TIMEOUT_SECONDS`). Both
  SDKs default to no timeout, so a hung provider used to park worker threads
  indefinitely. Existing fail-closed handlers now engage instead.
- `setup_indexes` no longer swallows configuration failure: it propagates so
  the existing lifespan warning fires, instead of booting with silently
  unconfigured search attributes.
- Batched the periodic compliance medical recompute from two round-trips per
  affected crew to two queries total, with identical recompute semantics.
- Triaged two hunt claims as non-bugs: `document_indexable_text` excludes
  `extracted_text` deliberately (C3 must stay PostgreSQL-only, documented on
  the helper), and `reconcile_crew_projection` closes its session before
  network I/O while `index_crew_member` re-reads the source row itself.
- Added regression coverage (4 tests). Full suite 702 passed with only the 34
  failures already proven pre-existing at HEAD. Ruff check clean, format clean
  on touched lines, mypy zero new errors. Tool: OpenCode/Muse Spark.

## Hidden-Bug Pass 374 — availability fail-closed creation default (2026-09-15)

- Profiles created without recorded availability now persist as `unavailable`
  instead of `available`: changed the ORM default on
  `CrewMember.availability_status` and the `CrewMemberCreateDTO`/`CrewMemberDTO`
  defaults to match the GraphQL read side and the mobilization compliance
  preflight (missing availability is not evidence of mobilizability). No
  migration: the column has no `server_default`, so this is an ORM-side
  default change only. Seeds set availability explicitly and are unaffected.
- Triaged the remaining contract-batch claims without changing them:
  `DocumentClassification.CERT="cert"` is consumed only by the retired
  `uploadDocument` mutation; `CertType` values are the persisted source via
  `addCertification`; publication `approved` defaults carry documented intent
  (explicit creation paths) and would need a migration; pagination defaults
  are bounded server-side; the Qdrant projection gap is search-quality work
  for a later pass with a reindex plan.
- Updated the `test_create_crew_member` assertion and added an ORM persistence
  regression test. Full suite 698 passed with only the 34 failures already
  proven pre-existing at HEAD. Ruff check clean, format clean on touched
  lines, mypy zero new errors. Tool: OpenCode/Muse Spark.

## Hidden-Bug Pass 373 — backend security fail-open and authz fixes (2026-09-15)

- Login brute-force protection now survives a Redis outage: `increment_rate_limit`
  falls back to a bounded process-local fixed-window counter instead of leaving
  logins unmetered. Logins keep working; the 6th rapid attempt is still throttled.
- Dropbox webhook signature verification is now mandatory in every environment:
  without a configured app secret the endpoint returns 503 instead of queuing
  sync work for unauthenticated requests.
- Admin document downloads (local and Dropbox routes) now fail closed with a
  retryable 503 when the audit write fails, instead of serving unlogged C3 bytes.
- Contractor-upload broker failures now mark the paired review-queue row `failed`
  alongside the document, so staff no longer see a stale `unread` item for a
  document that can never be processed.
- `crewSummary` now enforces `can_access_profile` and denies T1 callers like
  `documentsByCrew`, returning the same not-found string so denials do not
  oracle whether a profile ID exists.
- Added regression coverage (10 tests). Backend: targeted suites pass (login
  rate-limit, crew summary, dropbox deletion, field-level auth minus 3
  pre-existing failures, documents minus 5 pre-existing failures); full suite
  697 passed with 34 failures all proven identical at HEAD (no live
  Redis/Meilisearch/providers in this sandbox). Ruff check clean, ruff format
  clean on touched lines (5 files were already format-dirty at HEAD), mypy
  shows zero new errors (11 pre-existing, dependency-drift). Tool: OpenCode/Muse
  Spark. Note: the repo backend `.venv` is broken in this environment (its base
  interpreter path does not exist); verification used a fresh Python 3.11 venv
  in /tmp with the pinned requirements.

## Hidden-Bug Pass 372 — frontend trust and lifecycle fixes (2026-09-15)

- Restricted `hasOriginalDocumentFile` to HTTPS(S) and inert data-URL document
  binaries (PDF, images, octet-stream, plain text), so `data:text/html` payloads
  from untrusted index contents can no longer be opened as original files.
- Fixed `mobilizationMailto` encoding the whole recipient (breaking `+`/`@`) and
  letting a stored `?`/`#` split the subject; only the subject is now encoded.
- Closed a CSV-injection bypass where leading whitespace, tabs, or line breaks
  hid `=`, `+`, `-`, `@`, `|`, `%` prefixes from the formula guard.
- Made shortlist copy failures visible (inline alert) and preserved the secure
  upload link in a toast when the clipboard is unavailable, instead of losing it.
- Retained Blob object URLs for a 5s grace period across document, shortlist,
  comparison, and bundle downloads so Firefox/Safari can consume them.
- Added regression coverage. Frontend tests (233), TypeScript, ESLint, build,
  and UI audit passed. Tool: OpenCode/Muse Spark.

## 2026-09-13

- **CV extraction failure-state fix** — Codex — exceptional CV extraction
  failures now mark the linked review as `failed` together with the document,
  preventing reviews from remaining invisibly stuck in `processing`.
- **Stale extraction-claim recovery** — Codex — documents no longer remain
  permanently stuck in `processing` when a worker dies after claiming them.
  Added a shared persisted processing lease, stale-claim recovery to both
  synchronous and asynchronous extraction paths, migration, and regression
  coverage.
- **Split-pane drag cleanup** — Codex — unmounting during a pane drag now
  removes global pointer listeners and restores document interaction styles.
- **Toast timer isolation** — Codex — repeated identical notifications can no
  longer be dismissed early by the previous notification's timeout.
- **Service-status polling race fix** — Codex — a slow health response can no
  longer overwrite the result of a newer poll with stale service states.
- **Copy-feedback timer isolation** — Codex — delayed copy confirmations can
  no longer clear the confirmation state of a newer profile or reopened modal.
  Copy timers are now identity-checked or cancelled on lifecycle changes,
  including mobilization dialogs.
- **Deletion completion state isolation** — Codex — a late contractor-delete
  response can no longer clear a different contractor selected while the
  deletion was in flight. Modal cleanup now checks the deleted profile ID.
- **Contractor onboarding operation isolation** — Codex — late CV-upload
  failures can no longer overwrite a newly reopened onboarding form. Added
  operation-lifecycle regression coverage.
- **Staff and CV refresh race isolation** — Codex — late account-refresh
  responses can no longer commit rows from an earlier session after the active
  session changes. Added request/session guard coverage.
- **Operational count error isolation** — Codex — project and vessel-roster
  counts now hide retained values when their current account-scoped request
  fails, preventing stale operational metadata from appearing beside an error.
- **Staff and CV review error isolation** — Codex — staff-account and CV-review
  modals now hide previously committed rows when the current account-scoped
  request fails, instead of showing stale records alongside the error.
  Added shared readiness coverage.
- **Vessel search error isolation** — Codex — vessel lookup no longer renders
  retained results from a previous successful search when the current lookup
  fails. Added focused regression coverage.
- **Document mutation refresh reporting** — Codex — successful document
  deletion or review is no longer reported as a failed mutation when the
  follow-up vault refresh is unavailable; the user is told that refresh is
  unavailable instead. The result is now propagated through all document
  surfaces. Added focused regression coverage.
- **Document Apollo error handling** — Codex — document-vault refreshes now
  treat GraphQL errors returned alongside partial data as failures instead of
  committing an apparently successful empty or incomplete document set.
- **Roster pagination Apollo errors** — Codex — automatic roster pages and
  explicit load-more requests now treat GraphQL errors returned with partial
  data as failed requests instead of committing empty pages or incorrect
  pagination state.
- **Summary refresh fail-closed** — Codex — a new profile-summary request now
  clears any previous summary before loading and rejects Apollo responses that
  contain errors, preventing stale or partially authorized text from remaining
  visible.
- **Account-scoped Apollo pagination checks** — Codex — dossier opening,
  CV-review pagination, staff-account pagination, and exported roster refreshes
  now reject GraphQL errors returned with partial data instead of presenting
  incomplete account-scoped results as successful.
- **Mutation Apollo error checks** — Codex — contractor creation and deletion
  now reject GraphQL errors returned alongside mutation data instead of
  continuing as if the account change succeeded.
- **Login refresh race fix** — Codex — the sign-in modal no longer starts a
  second uncaught session refresh after the authentication hook has already
  verified the login, preventing duplicate requests and unhandled refresh
  rejections.
- **AI search error isolation** — Codex — the natural-language search hook no
  longer publishes retained Apollo data when the current query fails,
  preventing results from an earlier query from appearing as the latest answer.
- **Roster retained-data fail-closed** — Codex — the main roster resolver now
  rejects retained Apollo data when the current roster request has failed,
  preventing a stale account scope from remaining visible during an outage or
  authorization error. Added regression coverage.
- **Document preview refresh reconciliation** — Codex — an open preview now
  closes when its document is removed and adopts refreshed data when the same
  record changes, including previews opened from the credentials tab, preventing
  stale compliance details or review controls from remaining visible.
- **Detail-modal document session wiring** — Codex — the standalone contractor
  detail modal now passes the authenticated session scope into its document
  vault, restoring downloads, uploads, requests, deletes, and review actions
  that previously returned early as unauthenticated. Its profile/session
  lifecycle state now resets as well, preventing confirmation and tab state
  from carrying into another record or account.
- **Certification override cleanup** — Codex — successful verification actions
  now release their optimistic local override after the mutation succeeds, so
  later authoritative cache updates cannot be masked for the session.
- **Direct review response validation** — Codex — document review now requires
  the returned extraction status to match the requested approve or reject
  action, preventing stale responses from being reported as success.
- **Rejected CV status handling** — Codex — contractor onboarding now treats a
  rejected CV extraction as a terminal failure instead of reporting that the
  CV was successfully submitted for review.
- **Review action response validation** — Codex — incoming-document actions
  now require `resolved` for approval and `rejected` for rejection, preventing
  a non-terminal response from being shown as a successful decision.
- **Authenticated upload idempotency** — Codex — the document modal now sends
  a stable idempotency key for each selected file, preventing duplicate
  records when an upload is retried after an uncertain response.
- **Document refresh fail-closed** — Codex — a failed same-session document
  refresh now removes the prior profile result instead of leaving deleted or
  no-longer-authorized documents visible indefinitely.
- **Summary session race fix** — Codex — AI profile summaries now verify the
  active session before committing a completed request, preventing a late
  response from an earlier account from populating the current profile view.
- **Roster error fallback fix** — Codex — authenticated roster errors no longer
  fall back to mock contractors when demo mode is enabled, preventing fictional
  records from appearing as live data during an outage.
- **Document review claim timestamp** — Codex — resolving an unread contractor
  document now records the first claim time, while retries preserve the
  original timestamp for accurate queue audit history.
- **Dossier session-state reset** — Codex — certification overrides and pending
  document/delete controls now reset when the authenticated session changes,
  preventing optimistic state from one account from persisting into another.
- **Certification verification failure rollback** — Codex — verification now
  handles both Apollo GraphQL and transport errors, preventing an optimistic
  local status from remaining visible after a failed mutation.
- **Inquiry mutation error handling** — Codex — the general mobilization
  inquiry now checks Apollo errors before displaying a successful assignment
  reference, matching the operational mobilization flow.
- **Dropbox CV review reset** — Codex — synchronous Dropbox re-extraction now
  clears the prior approval payload, reviewer, note, and timestamp when a new
  CV evidence snapshot reopens review. Added regression coverage for stale
  decision metadata.
- **Strict compliance expiry dates** — Codex — document-vault and certification
  status now reject impossible date-only calendar values instead of allowing
  JavaScript date normalization to turn them into a different valid date.
  Added regression coverage for invalid February dates.
- **Vessel search response race fix** — Codex — vessel results are now
  committed only from the latest search request, preventing a slower earlier
  response from replacing the results for the query currently shown.
- **Vessel roster response race fix** — Codex — expanded vessel rosters now
  commit only the current vessel/session response, preventing an older roster
  request from replacing the roster currently shown.
- **Mobilization candidate refresh fix** — Codex — candidate lists now clear
  while role/search results are loading or failed, preventing an old query’s
  candidate from being selected for a new query. Assignment creation also
  checks GraphQL errors before showing success.
- **Review mutation error fix** — Codex — staff-role changes and CV approval or
  rejection now treat resolved Apollo GraphQL errors as failures before
  refreshing or reporting the operation as successful.
- **Review list response isolation** — Codex — staff-account and CV-review
  dialogs now render only explicitly committed results for the active session,
  preventing a late Apollo response from replacing the current account’s list.
- **Document modal state reset** — Codex — document review controls and vault
  filters now reset when the active document, profile, or session changes,
  preventing stale loading/confirmation state or filters from affecting the
  next document view.
- **Session verification fail-closed** — Codex — auth now clears the local
  identity when the `me` verification query fails instead of retaining a
  possibly stale Apollo identity; explicit session-refresh failures also end
  the local session.

- **Project date display fix** — Codex — operations project dates now parse
  date-only values in local calendar time, preventing users west of UTC from
  seeing the previous day. Added formatting regression coverage.
- **Mobilization date default fix** — Codex — mobilization forms now calculate
  their seven-day default start date in local calendar time instead of adding
  UTC milliseconds, preventing timezone-dependent start-date drift.
- **Export filename date fix** — Codex — shortlist and comparison CSV names
  now use the user’s local calendar date instead of UTC, avoiding misleading
  dates around midnight.
- **Operations session-scope fix** — Codex — expiring-certification counts
  now refetch and remain hidden until the current staff session is confirmed,
  preventing the previous account’s scoped count from persisting after a
  session switch.
- **Operations project session-scope fix** — Codex — project data now stays
  hidden until the current session’s refresh completes, preventing unchanged
  Apollo variables from reopening the previous account’s project list.
- **Vessel session-scope fix** — Codex — vessel rosters, search results, and
  mobilization candidates now remain gated until account or vessel refreshes
  complete, preventing stale operational data from persisting.
- **Staff modal session-scope fix** — Codex — staff accounts and CV reviews
  now remain gated while a session refresh is pending, preventing stale
  account-scoped Apollo data from being marked current prematurely.
- **Vessel search race fix** — Codex — each new vessel search now invalidates
  older requests, preventing a slower earlier response from replacing the
  latest query state.
- **Document review session reset** — Codex — the review modal now clears its
  previous queue before loading a new account scope, preventing old review
  rows from remaining visible during a session switch.
- **Empty roster fallback fix** — Codex — an authenticated empty roster now
  remains empty even when demo mode is enabled, preventing mock contractors
  from appearing as real account data. Added regression coverage.
- **Document calendar-date fix** — Codex — date-only document values now render
  in their stored calendar day across time zones instead of shifting backward
  near UTC midnight. Added regression coverage.
- **Apollo refresh error fix** — Codex — account-scoped refreshes now treat
  GraphQL errors returned under `errorPolicy: all` as failures, preventing
  stale staff, CV, vessel, project, and roster data from being marked current.
  Added session-scope regression coverage.

- **Roster profile-field search** — Codex — extended the approved contractor
  keyword search to include all searchable C1 profile fields, including
  country of residence, languages, education, experience, and flying point.
  Natural-language search now matches languages and flying point too. Added
  regression coverage.

- **CV review ownership hardening** — Codex — CV approvals and rejections now
  verify that the review document belongs to the reviewed contractor and that
  the owner is still a contractor profile, preventing legacy or tampered review
  rows from mutating login accounts.
- **Direct CV processing race hardening** — Codex — the lower-level CV
  processing service now locks and revalidates its owner before applying
  extracted profile data.
- **Document status access race hardening** — Codex — staff status reads now
  lock the linked contractor row together with the document before checking
  publication and role eligibility.
- **Review-alert action race fix** — Codex — document-review actions no longer
  share invalidation state with background polling, preventing an approve or
  reject button from remaining stuck when a poll overlaps the action.
- **Upload response validation** — Codex — frontend upload clients now validate
  required server response fields before showing a successful upload state.
- **Upload-link response validation** — Codex — public request and staff link
  creation clients now reject malformed or unusable link responses instead of
  rendering an invalid upload workflow.
- **Document workflow response validation** — Codex — review queue, review
  action, document status, and admin service-status clients now reject
  malformed successful responses instead of crashing or entering invalid UI
  states.
- **CV preview response validation** — Codex — the staff CV preview client now
  rejects malformed successful payloads before populating contractor identity
  fields.
- **Document status contract validation** — Codex — upload, status, and review
  clients now reject impossible workflow status values instead of treating
  unknown server states as successful processing.
- **Review queue race hardening** — Codex — incoming-document queue reads now
  lock the joined document and contractor rows before returning metadata,
  preventing stale account/publication state from being exposed during a
  concurrent role change.
- **Review lock-order hardening** — Codex — staff review resolution now locks
  document, contractor, and review rows in the same order as extraction and
  ingestion, preventing a PostgreSQL deadlock during concurrent processing.
- **Assignment lock-order hardening** — Codex — assignment status changes now
  lock the contractor before the assignment, matching creation-time conflict
  locking and preventing concurrent booking transitions from deadlocking.
- **Browser download lifecycle fix** — Codex — document blob URLs are now
  revoked after the download navigation is scheduled, avoiding cancellations
  in browsers that consume the anchor asynchronously.
- **Meilisearch task confirmation** — Codex — search projection writes and
  deletes now wait for provider task completion instead of reporting success
  when Meilisearch has only accepted the asynchronous operation.
- **Meilisearch configuration confirmation** — Codex — startup index
  configuration now waits for searchable, filterable, and sortable settings to
  finish instead of logging success after task submission.
- **Export download lifecycle fix** — Codex — shortlist, comparison, and
  document-vault exports now defer Blob URL cleanup until the browser has had
  a chance to begin the download.
- **Public upload token race fix** — Codex — an upload finishing after the
  public link changed can no longer mark the replacement link complete or show
  the stale request's error.
- **Authenticated upload success handling** — Codex — a post-upload roster
  refresh failure no longer masquerades as an upload failure, preventing users
  from retrying a document that was already persisted.
- **Document refresh promise wiring** — Codex — dossier upload callbacks now
  return their refresh promises instead of detaching them as unhandled async
  work.
- **Mutation refresh error boundaries** — Codex — CV review, staff-role, and
  contractor deletion flows now distinguish committed mutations from failed
  follow-up refreshes, preventing misleading failure messages and duplicate
  retries.
- **Detached refresh rejection handling** — Codex — contractor creation, CV
  approval, document-review refreshes, and operational panel reloads now handle
  background refresh failures instead of creating unhandled promise rejections.
- **Roster session fail-closed guard** — Codex — a failed account-switch
  refetch can no longer promote Apollo's retained previous roster to the new
  session; the roster stays empty until current-session data succeeds.

- Closed a semantic-search publication boundary: the Qdrant document worker now
  excludes documents linked to staff/login account rows, matching the existing
  Meilisearch and visibility rules. Added a regression test for legacy account
  rows. Tool: Codex. Follow-up: continue auditing background reconciliation
  paths for source-of-truth and privacy boundaries.
- Added a fail-closed guard to the synchronous document worker so legacy
  documents linked to staff/login accounts are rejected before extraction or
  review/certification projection. Tool: Codex. Follow-up: continue auditing
  background reconciliation paths for source-of-truth and privacy boundaries.
- Closed a certification mutation gap: updating or verifying a legacy
  certification linked to a staff/login account now fails as not found, matching
  contractor-only creation and projection rules. Added regression coverage.
  Tool: Codex. Follow-up: continue auditing background reconciliation paths for
  source-of-truth and privacy boundaries.
- Closed the same legacy-account gap in the async document worker and manual
  confirmation flow, and removed account-owned rows from the pending-review
  queue while preserving unlinked recovery records. Added regression coverage.
  Tool: Codex. Follow-up: continue auditing background reconciliation paths for
  source-of-truth and privacy boundaries.
- Corrected the admin manual crew-index response so an account row removed from
  the general index is reported as excluded rather than falsely reported as
  indexed. Tool: Codex. Follow-up: continue auditing background reconciliation
  paths for source-of-truth and privacy boundaries.
- Hardened the shared document service so account-owned documents cannot be
  created or requeued for reprocessing before reaching the worker boundary.
  Added regression coverage. Tool: Codex. Follow-up: continue auditing
  background reconciliation paths for source-of-truth and privacy boundaries.
- Ensured the async fail-closed document path also cleans up any stale derived
  search/vector projections after rejecting a legacy account-owned document.
  Added cleanup assertions to the regression test. Tool: Codex. Follow-up:
  continue auditing background reconciliation paths for source-of-truth and
  privacy boundaries.
- Restricted direct availability updates to contractor profiles so staff/login
  account rows cannot receive contractor mobilization state. Added regression
  coverage. Tool: Codex. Follow-up: continue auditing background reconciliation
  paths for source-of-truth and privacy boundaries.
- Manual document matching now locks the target profile before validating its
  contractor eligibility, closing a role-change race during relinking. Added a
  regression test. Tool: Codex. Follow-up: continue auditing background
  reconciliation paths for source-of-truth and privacy boundaries.
- Both synchronous and asynchronous document extraction now lock the linked
  profile before contractor eligibility checks, closing a concurrent role-change
  race during processing. Added lock assertions to regression tests. Tool:
  Codex. Follow-up: continue auditing background reconciliation paths for
  source-of-truth and privacy boundaries.
- Document-request review creation now locks and revalidates the owner before
  committing a review, closing the equivalent role-change race in contractor
  upload intake. Tool: Codex. Follow-up: continue auditing background
  reconciliation paths for source-of-truth and privacy boundaries.
- Dropbox ingestion now locks the recovered or existing document owner before
  linking or resetting external-file metadata, preventing concurrent role
  changes from attaching provider events to login accounts. Tool: Codex.
  Follow-up: continue auditing background reconciliation paths for source-of-
  truth and privacy boundaries.
- Generic document and manual certification creation now lock the owner before
  contractor eligibility checks, closing two remaining role-change races in
  shared services. Tool: Codex. Follow-up: continue auditing background
  reconciliation paths for source-of-truth and privacy boundaries.
- Restricted the general contractor profile-update service to contractor rows;
  staff/login account details remain managed through dedicated account paths.
  Added regression coverage. Tool: Codex. Follow-up: continue auditing
  background reconciliation paths for source-of-truth and privacy boundaries.

- Restricted the periodic certification-expiry updater to contractor profiles.
  Certifications accidentally attached to password-backed or staff/admin
  account rows are no longer mutated or fed into medical-profile projection
  reconciliation. Applied the same boundary to the synchronous compliance
  alert evaluator used by the Celery task. Tool: Codex.

- Closed the same account boundary in medical certification projection
  helpers. Legacy account-linked certificates can no longer rewrite a login
  row's denormalized medical status or expiry. Added regression coverage.
  Tool: Codex.

- Closed legacy account-row paths in contractor document reviews. Existing
  request records for login accounts can no longer create review items, and
  direct review resolution now rejects account-owned documents before any
  decision or projection work. Tool: Codex.

- Made missing contractor availability explicit as `Availability not recorded`
  across profile detail, dossier, print, mobilization, and shortlist export
  surfaces instead of rendering a blank status. Extended the shared label to
  comparison, table, and shortlist paths so whitespace-only values are also
  explicit. Added a focused frontend utility regression test. Tool: Codex.

- Closed a Dropbox ingestion boundary gap where a managed path could attach a
  file to a password-backed or staff/admin account row. Owner recovery now
  accepts contractor profiles only, matching the rest of document ingestion
  and search visibility rules. Added a focused regression test. Tool: Codex.

- Closed the same account boundary in manual document matching. Existing login
  accounts can no longer become document owners through the GraphQL match path;
  invalid targets return the existing not-found behavior. Added focused
  regression coverage. Tool: Codex.

- Prevented certification mutations from attaching contractor credentials to
  password-backed or staff/admin account rows. Added an isolated service
  regression test. Tool: Codex.

- Applied the contractor-account boundary to automatic certificate linking as
  well, preventing legacy or manually linked account documents from creating
  certification projections. Tool: Codex.

- Applied the contractor-account boundary to reviewed CV extraction, preventing
  legacy account-linked reviews from publishing profile data or creating CV
  evidence on login rows. Added regression coverage. Tool: Codex.

- Restricted the staff-management account list to password-backed or explicitly
  staff/admin rows. Ordinary contractor profiles no longer appear in role
  management merely because they share the `CrewMember` table. Added regression
  coverage. Tool: Codex.

- Fixed role changes leaving stale derived data behind. Promoting a contractor
  into a staff/account row now removes its Meilisearch projection and document
  vectors after the source commit, with the existing cleanup task queued when a
  provider cleanup is not confirmed. Summary and compliance caches are also
  invalidated. Tool: Codex.

- Made direct compliance-status calculation fail closed for password-backed or
  staff/admin account rows. Legacy certifications attached to login accounts
  can no longer appear in the compliance aggregate. Tool: Codex.

## 2026-09-13

- Hardened the backend test database fixture against sandbox PID reuse and
  retained SQLite cleanup connections. Each run now gets a unique database
  path and a non-pooling cleanup engine; cache invalidation is isolated from
  external Redis during tests. Tool: Codex.

## 2026-09-13

- Hardened the grid and table contractor views against incomplete live profile
  payloads. Missing availability now renders a neutral recorded-data label
  instead of throwing during results rendering. Tool: Codex.

## 2026-09-13

- Closed stale-projection and direct-ID account leaks across REST search,
  contractor summaries, document requests, and staff/agent document uploads.
  PostgreSQL rehydration now excludes password-backed and staff/admin rows even
  when an old Meilisearch record remains, and legacy document-request tokens
  for accounts are no longer usable. Expiring-certification alerts also ignore
  account rows, as do review-queue and semantic-document projections. Added
  regression coverage. The bearer-link lock rechecks this boundary as well,
  and compliance alert snapshots exclude account rows. Semantic document
  rehydration and reconciliation now enforce the same rule.
  Tool: Codex.

## 2026-09-13

- Closed contractor-account boundary bypasses in direct operations paths:
  campaign assignments and project assignments now reject password-backed or
  staff/admin rows, and legacy account assignments are hidden from contractor
  project and campaign views. Single-profile GraphQL access also hides other
  login accounts from non-admins while preserving the dedicated staff-account
  surface. Added regression coverage. Tool: Codex.

## 2026-09-13

- Aligned the certification ORM model with the legacy-nullable lifecycle
  columns used by PostgreSQL and retrieval rules. Null status or verification
  values now remain representable as unknown instead of failing persistence;
  natural-search coverage now passes against the test schema. Tool: Codex.

## 2026-09-13

- Applied the contractor-only account boundary to structured natural-language
  search, name summarization, and compliance search, preventing approved login
  accounts from appearing in AI retrieval results. Added regression coverage.
  Tool: Codex.

## 2026-09-13

- Added a synchronous epoch-aware lock to roster pagination so rapid repeated
  “load more” actions cannot issue duplicate page requests or append duplicate
  contractors before React commits the loading state. Tool: Codex.

## 2026-09-13

- Excluded staff, administrator, and password-backed login accounts from
  contractor availability, compliance, performance, and project-readiness
  reports. Project assignment visibility now uses the same contractor-only
  boundary, including administrator project reports, with regression coverage.
  Also made the compliance regression fixture relative to the test date. Tool:
  Codex.

## 2026-09-13

- Made empty GraphQL assignment responses fail visibly in both mobilization
  flows instead of silently leaving the operator without confirmation or an
  actionable retry path. Tool: Codex.

## 2026-09-13

- Corrected mobilization inquiry confirmation copy to reflect its persisted
  `PROPOSED` status. It now says the request was recorded and remains pending
  operations confirmation instead of implying a scheduled booking. Tool:
  Codex.

## 2026-09-13

- Preserved legacy approved contractor rows with a null role in relational
  roster discovery, matching the general search projection while continuing
  to exclude staff and password-backed accounts. Added regression coverage.
  Tool: Codex.

## 2026-09-13

- Prevented natural-language search from briefly showing the previous
  response under a newly entered query while Apollo was still loading the new
  payload. Added a completed-query identity check and regression coverage.
  Tool: Codex.

## 2026-09-13

- Reset mobilization inquiry and vessel-assignment form state when opening a
  new contractor or vessel, preventing prior identifiers, dates, clients,
  rates, and instructions from leaking into the next request. Tool: Codex.

## 2026-09-13

- Prevented mobilization inquiries from creating random synthetic vessel
  records when the required IMO was blank. The form now requires the vessel
  identifier and deployment port, and omits blank vessel names instead of
  persisting fabricated values. Tool: Codex.

## 2026-09-13

- Removed fabricated vessel-assignment defaults for campaign name and port,
  and changed blank dispatch-summary fields to explicit “Not recorded” values.
  Operators still retain the intentional role, proposed date, and duration
  defaults. Tool: Codex.

## 2026-09-13

- Prevented staff and administrator login accounts from appearing in
  contractor roster, keyword search, or the general Meilisearch projection.
  Account records remain available through the dedicated staff-management
  surface, while legacy profession-valued contractor roles remain supported.
  Added regression coverage. Tool: Codex.

## 2026-09-13

- Removed fabricated upload-time issue and expiry date defaults from the
  admin document form. Dates are now persisted only when explicitly recorded
  from the evidence. Tool: Codex.

## 2026-09-13

- Consolidated clipboard handling across profile, dossier, table, keyboard,
  and mobilization actions so success states and toasts occur only after a
  confirmed write. Browser denial or unsupported clipboard APIs now report
  failure. Added utility coverage. Tool: Codex.

## 2026-09-13

- Fixed the profile email copy control reporting success before the clipboard
  operation completed. Clipboard denial or unavailable browser support now
  shows an actionable error instead. Tool: Codex.

## 2026-09-13

- Prevented rejected documents with future expiry dates from receiving a
  positive compliance badge. They now show an explicit rejected-document
  state, with regression coverage. Tool: Codex.

## 2026-09-13

- Made partial login-profile fields fail closed instead of inheriting
  “approved” and “available” GraphQL defaults when those facts are not loaded.
  The shared GraphQL type defaults now fail closed as well; added
  authentication regression coverage. Tool: Codex.

## 2026-09-13

- Fixed a document-extraction race where a review completed while extraction
  was in flight was returned as a false failure, causing unnecessary Celery
  retries. The worker now preserves the authoritative rejected or approved
  terminal status and has regression coverage. Tool: Codex.

## 2026-09-13

- Prevented malformed live roster data from falling through to unrelated demo
  contractors after a mapper failure. The roster now stays empty and exposes
  the live-data warning. Tool: Codex.

## 2026-09-13

- Replaced stock portrait fallbacks for live contractors with neutral initials
  avatars so missing photos cannot imply another person’s identity. Added
  mapper regression coverage. Tool: Codex.

## 2026-09-13

- Corrected compliance report filtering and output to derive certification
  status from verified expiry evidence instead of stale stored status labels.
  Removed a duplicate certification identifier in report rows and added
  regression coverage. Tool: Codex.

## 2026-09-13

- Corrected dashboard compliance aggregates so the valid count is derived
  from verified expiry dates rather than stale lifecycle status labels. Added
  regression coverage. Tool: Codex.

## 2026-09-13

- Updated assignment credential checks to use verified expiry dates instead of
  stale certificate lifecycle labels when evaluating mobilization eligibility.
  Added regression coverage. Tool: Codex.

## 2026-09-13

- Updated valid certification search filters to use verified certificates with
  non-expired dates rather than trusting stale `valid` or `expiring_soon`
  lifecycle labels. Added regression coverage. Tool: Codex.

## 2026-09-13

- Corrected natural-language compliance results to derive expired and
  expiring-soon states from certificate expiry dates instead of trusting stale
  persisted lifecycle status. Added regression coverage. Tool: Codex.

## 2026-09-13

- Prevented the dossier overview from crashing when a partial profile omits
  availability; rendering now uses an explicit not-recorded fallback in both
  the status check and summary sentence. Tool: Codex.

## 2026-09-13

- Removed fabricated availability and document-permanence fallbacks. Missing
  values now display as “not recorded” in shortlist, comparison, export, and
  document-preview surfaces. Tool: Codex.

## 2026-09-13

- Replaced the document preview’s fabricated “Issued: Current” fallback with
  “Issued: Not recorded” when no issue date exists. Tool: Codex.

## 2026-09-13

- Prevented unreviewed documents with future expiry dates from being labeled
  “Valid”; they now show that an expiry is recorded while retaining the
  date-based warning state. Added regression coverage. Tool: Codex.

## 2026-09-13

- Removed the misleading “Verified Permanent” document label: reviewer
  approval does not prove that a document has no expiry. Added regression
  coverage for approved documents without a recorded expiry. Tool: Codex.

## 2026-09-13

- Prevented dossier credentials with malformed expiry dates from falling back
  to a stored “valid” status; they now display an explicit invalid-date
  warning. Tool: Codex.

## 2026-09-13

- Ensured pending certificates still display independent expired or
  expiring-date warnings instead of hiding the date risk behind the pending
  verification badge. Tool: Codex.

## 2026-09-13

- Prevented certification tooltips from claiming “Certified,” “Accredited,”
  or “Valid” for records that are not explicitly verified. Unverified
  credentials now use neutral recorded/pending wording. Tool: Codex.

## 2026-09-13

- Corrected dossier certification badges to derive expired/expiring warnings
  from the recorded expiry date instead of trusting stale persisted status.
  Added date-status regression coverage. Tool: Codex.

## 2026-09-13

- Distinguished malformed expiry dates from genuinely permanent documents so
  verified records with invalid dates cannot clear the document audit. Added
  warning-state and regression coverage. Tool: Codex.

## 2026-09-13

- Prevented confirmed assignments and active-status promotions for contractors
  marked unavailable or still assigned during the campaign window. Added
  regression coverage. Tool: Codex.

## 2026-09-13

- Prevented confirmed assignments when verified medical or survival
  certification has expired. Added matching client-side blocking and backend
  regression coverage boundary. Tool: Codex.

## 2026-09-13

- Aligned frontend mobilization compliance with the backend verification
  policy: certificates without explicit verified status no longer pass
  preflight checks. Added regression coverage. Tool: Codex.

## 2026-09-13

- Renamed recommendation indicators that were incorrectly presented as
  contractor verification or verified representation. Match ranking no longer
  implies credential evidence. Added to the hidden-bug audit. Tool: Codex.

## 2026-09-13

- Replaced unsupported offshore-mobilization compliance claims in the document
  vault with wording limited to verified/current recorded documents, and kept
  missing company history out of cohort summaries. Added frontend regression
  coverage. Tool: Codex.

## 2026-09-13

- Hardened the crew creation service contract so every caller must explicitly
  choose draft or approved publication; this prevents future internal callers
  from publishing by omitting the review decision. Tool: Codex. Follow-up:
  keep new creation paths explicit about their publication state.

The running record of what was built, when, by which tool, and why. This is
the shared handoff point between AI tools (Claude Code, Codex, Kilo Code, or
any other) and between sessions of the same tool — read it before assuming
context needs to be re-explained, and append to it before finishing any work
that changes committed code, running data, or infrastructure state.

## Hidden-Bug Pass 371 — unsupported verification claims in summaries (2026-09-13)

- Removed unsupported “verified”, “accredited”, and “verified alumni” claims
  from generated frontend cohort summaries when the underlying profile data
  does not establish those facts.
- Added regression coverage. Frontend tests (175), TypeScript, ESLint, and
  diff checks passed. Tool: Codex.

## Hidden-Bug Pass 370 — unknown experience rendered as zero (2026-09-13)

- Preserved missing audited experience as unknown instead of converting it to
  `0` years across live profile mapping, AI results, filters, exports, dossier
  views, skill scoring, and cohort averages.
- Added regression coverage. Frontend tests (174), TypeScript, ESLint, and
  diff checks passed. Tool: Codex.

## Hidden-Bug Pass 369 — false compliance clearance in exports (2026-09-13)

- Fixed compliance-bundle manifests declaring full clearance whenever no
  document was expired, even when documents were expiring, unverified, or had
  no recorded expiry.
- Clearance now requires at least one document and every document to be
  verified and valid/permanent. Frontend tests (173), TypeScript, ESLint, and
  diff checks passed. Tool: Codex.

## Hidden-Bug Pass 368 — invalid dates in review and preview surfaces (2026-09-13)

- Replaced direct date rendering in document preview and CV review surfaces
  with the safe document-date formatter, preventing malformed timestamps from
  displaying `Invalid Date`.
- Frontend tests (172), TypeScript, ESLint, and diff checks passed. Tool: Codex.

## Hidden-Bug Pass 367 — document vault invalid-date handling (2026-09-13)

- Fixed malformed upload and expiry dates producing `NaN` sort results or
  `Invalid Date` in document-vault tooltips and compliance-bundle exports.
- Centralized safe document-date parsing and added regression coverage.
  Frontend tests (172), TypeScript, ESLint, and diff checks passed. Tool: Codex.

## Hidden-Bug Pass 366 — malformed recent-date sorting (2026-09-13)

- Fixed recent-profile sorting so malformed or missing `dateAdded` values are
  treated as unknown/old instead of producing `NaN` comparators and unstable
  ordering.
- Added regression coverage. Frontend tests (170), TypeScript, ESLint, and
  diff checks passed. Tool: Codex.

## Hidden-Bug Pass 365 — natural-search residence matching (2026-09-13)

- Fixed location criteria in natural search so matching now includes the
  authoritative nationality and country-of-residence fields, not only free
  text and work-history-derived fields.
- Added a Norway residence regression case. Ruff and diff checks passed; the
  database-backed search test stalled in this environment. Tool: Codex.

## Hidden-Bug Pass 364 — natural-search profile field preservation (2026-09-13)

- Preserved authoritative residence, nationality, education, summary,
  languages, tags, training, geography, and systems fields from backend
  natural-search results when the full roster record is not yet loaded.
- Added parser coverage. Frontend tests (169), TypeScript/ESLint, and the
  production build passed. Tool: Codex.

## Hidden-Bug Pass 363 — contractor upload boundary regression tests (2026-09-13)

- Updated expiry and publication recheck fixtures to match the current
  fail-before-file-persistence flow. The tests now assert that invalid links
  do not write or clean up an upload. Tool: Codex.

## Hidden-Bug Pass 362 — backend test lint gate (2026-09-13)

- Fixed the unsorted import block in the document-task regression tests so the
  full backend Ruff check is clean. Tool: Codex.

## Hidden-Bug Pass 361 — assignment date boundary consistency (2026-09-13)

- Reused strict calendar-date validation in compliance evaluation so internal
  callers cannot pass `datetime` values where assignment dates are required.
- Added regression coverage. The database-backed test fixture stalled in this
  environment; the direct boundary check and static checks passed. Tool: Codex.

## Hidden-Bug Pass 330 — Dropbox deletion transaction ordering (2026-09-13)

- Fixed document deletion removing a Dropbox original before the database
  transaction committed, which could leave a live row pointing at missing
  storage after a commit failure.
- Metadata now commits first; failed remote cleanup is queued for retry. Added
  regression coverage. Tool: Codex.

## Hidden-Bug Pass 331 — crew deletion transaction ordering (2026-09-13)

- Applied the same transaction-safety fix to whole-contractor deletion, which
  previously removed Dropbox files before deleting the database records.
- Metadata now commits first and failed remote cleanup is queued for retry.
  Updated regression coverage. Tool: Codex.

## Hidden-Bug Pass 332 — document/contractor lock ordering (2026-09-13)

- Fixed a deadlock path where contractor deletion locked the contractor first
  while Dropbox revision/review workflows locked the document first and then
  refreshed contractor medical projections.
- Contractor deletion and single-document deletion now follow the shared
  document-then-contractor lock order. Tool: Codex.

## Hidden-Bug Pass 333 — zero day-rate roster display (2026-09-13)

- Fixed the vessel roster hiding a valid zero agreed day rate because the
  render condition treated `0` as absent. Tool: Codex.

## Hidden-Bug Pass 334 — zero day-rate profile surfaces (2026-09-13)

- Applied the same zero-value fix across profile cards, comparison views,
  shortlist exports, the dossier header, and the specialist table.
- A stored zero day rate is now displayed and exported consistently instead of
  being mislabeled as unavailable. Tool: Codex.

## Hidden-Bug Pass 335 — shortlist zero-rate and CSV consistency (2026-09-13)

- Fixed the legacy shortlist hook hiding zero day rates in copied summaries and
  exports.
- Its CSV path now uses the shared escaping and formula-safety encoder instead
  of maintaining a separate unsafe formatter. Tool: Codex.

## Hidden-Bug Pass 336 — fabricated live profile ratings (2026-09-13)

- Fixed the specialist table showing a made-up `4.9` rating when live backend
  profiles have no rating data.
- Rating displays now consistently show an unavailable marker when absent and
  still preserve legitimate zero ratings. Tool: Codex.

## Hidden-Bug Pass 337 — remaining zero-rate exports (2026-09-13)

- Fixed shortlist and comparison text/CSV exports still treating a zero day
  rate as “N/A” or “On Request.” Tool: Codex.

## Hidden-Bug Pass 338 — mobilization compliance fallback (2026-09-13)

- Fixed dispatch summaries claiming `Verified` when no pre-flight compliance
  report was available.
- Missing compliance evaluation is now labeled `Not checked`. Tool: Codex.

## Hidden-Bug Pass 339 — fabricated dossier print facts (2026-09-13)

- Fixed printable dossiers inventing an `£850` day rate, `4.9` satisfaction
  score, and “Verified Offshore” accreditation when the profile had no such
  data.
- Missing values now remain explicitly unavailable in the printed record.
  Tool: Codex.

## Hidden-Bug Pass 340 — remaining fabricated profile metrics (2026-09-13)

- Removed the remaining default `4.9` rating from profile cards and comparison
  exports.
- Mobilization inquiries no longer invent an `£850` rate, send it as an
  agreed administrator rate, or insert a fake client email when data is absent.
  Tool: Codex.

## Hidden-Bug Pass 329 — comparison export object-URL cleanup (2026-09-13)

- Fixed comparison CSV export leaking a browser Blob URL after each download.
- The generated URL is now revoked after the download is triggered. Frontend
  tests, lint, build, and UI audit passed. Tool: Codex.

## Hidden-Bug Pass 328 — CSV field escaping and formula safety (2026-09-13)

- Fixed comparison and shortlist exports inconsistently escaping CSV fields,
  allowing commas, quotes, and newlines to corrupt rows.
- Centralized CSV encoding and neutralized spreadsheet formula prefixes such as
  `=`, `+`, `-`, and `@`. Added regression coverage. Tool: Codex.

## Hidden-Bug Pass 327 — encoded mobilization mailto links (2026-09-13)

- Fixed profile mobilization links interpolating stored email values directly
  into `mailto:` URLs.
- Recipients and subjects are now encoded centrally, preventing URL delimiters
  or control characters from altering the mailto query. Tool: Codex.

## Hidden-Bug Pass 326 — LinkedIn URL scheme validation (2026-09-13)

- Fixed profile footer links trusting a supplied LinkedIn URL without checking
  its scheme or host.
- Links now accept only HTTPS `linkedin.com` hosts and otherwise use the safe
  search fallback. Added regression coverage. Tool: Codex.

## Hidden-Bug Pass 325 — document URL scheme validation (2026-09-13)

- Fixed document download controls trusting any truthy `fileUrl` instead of
  applying the existing safe `data:`/HTTP(S) URL check.
- Unsafe schemes such as `javascript:` now fall back to the authorized backend
  download path or are rejected. Added regression coverage. Tool: Codex.

## Hidden-Bug Pass 324 — shortlist CSV download encoding (2026-09-13)

- Fixed shortlist CSV export using `encodeURI` on a data URL, which left
  characters such as `#`, `&`, and `?` able to corrupt downloaded content.
- Exports now use a Blob URL and revoke it after download. Frontend unit,
  lint, build, and UI-audit checks passed; Playwright was unavailable because
  the Chromium executable is not installed. Tool: Codex.

## Hidden-Bug Pass 322 — streamed Meilisearch health probe (2026-09-13)

- Fixed the Meilisearch health check buffering a response body that was used
  only for its status code.
- The probe now streams and closes the response without changing health
  semantics. Tool: Codex.

## Hidden-Bug Pass 321 — bounded Ollama health responses (2026-09-13)

- Fixed Ollama health and readiness probes buffering provider responses that
  were used only for status checks.
- The non-production model-list response is now streamed with a 256 KiB cap
  and validated before names are returned. Tool: Codex.

## Hidden-Bug Pass 320 — streamed Dropbox status checks (2026-09-13)

- Fixed Dropbox upload, delete, and health calls buffering response bodies that
  the application only used for their HTTP status.
- Added a streamed status-only helper and regression coverage for large
  non-JSON responses. Tool: Codex.

## Hidden-Bug Pass 319 — bounded Dropbox token responses (2026-09-13)

- Fixed Dropbox OAuth refresh responses being buffered and parsed without a
  size boundary.
- Token responses now stream with a 64 KiB cap while preserving Basic Auth and
  existing refresh/error semantics. Tool: Codex.

## Hidden-Bug Pass 318 — bounded Dropbox listing responses (2026-09-13)

- Fixed Dropbox folder and cursor-listing payloads being buffered by the
  generic HTTP request helper before parsing.
- Added a streamed 512 KiB JSON boundary with safe malformed-payload handling
  and preserved one-time token refresh/retry behavior. Tool: Codex.

## Hidden-Bug Pass 317 — bounded and validated embedding responses (2026-09-13)

- Fixed Ollama embedding responses being buffered without a size limit before
  JSON parsing.
- Embeddings are now streamed with a 256 KiB cap and accepted only when they
  contain exactly 384 finite values, matching the Qdrant collection contract.
- Added regression coverage for oversized responses and invalid dimensions.
  Tool: Codex.

## Hidden-Bug Pass 316 — Ollama model lifecycle response buffering (2026-09-13)

- Fixed model load and unload control requests using buffered HTTP helpers even
  though their response bodies were ignored.
- These requests now stream and close provider responses, with regression
  coverage for the request payloads and lifecycle behavior. Tool: Codex.

## Hidden-Bug Pass 311 — legacy bearer-token isolation (2026-09-13)

- Fixed the browser still reading and sending legacy bearer tokens from
  storage, which could override the HttpOnly session cookie and send requests
  as a previous account after account switching.
- REST document calls, Apollo GraphQL, and service health checks now rely on
  cookie credentials; legacy token keys are removed during auth initialization
  and are never written or used for authorization.
- Updated frontend auth fixtures and regression coverage. Tool: Codex.

## Hidden-Bug Pass 312 — login token exposure (2026-09-13)

- Fixed the GraphQL login response exposing the raw session token even though
  browser authentication had moved to an HttpOnly cookie.
- The legacy nullable field remains deprecated for compatibility, but is now
  always null; added regression coverage proving the cookie is set without
  returning the credential. Tool: Codex.

## Hidden-Bug Pass 313 — PDF page-count resource bound (2026-09-13)

- Fixed PDF text and deterministic CV extraction walking unbounded page trees
  before applying text/output limits.
- Added a shared 200-page boundary, bounded text accumulation while parsing,
  and regression coverage for oversized page counts. Tool: Codex.

## Hidden-Bug Pass 314 — Ollama response buffering (2026-09-13)

- Fixed Ollama extraction responses being fully buffered and JSON-parsed before
  the downstream extraction limit could run.
- Provider responses are now streamed and capped at 1 MB for both async and
  synchronous workers, with regression coverage for oversized chunked output.
- Tool: Codex.

## Hidden-Bug Pass 315 — Unicode download filenames (2026-09-13)

- Fixed document download headers retaining Unicode characters in the supposed
  ASCII fallback, which could make Starlette fail while encoding the response.
- The fallback is now strictly ASCII and path separators are percent-encoded
  in the RFC 5987 filename value. Added regression coverage. Tool: Codex.

## Hidden-Bug Pass 277 — availability status/date invariant (2026-09-13)

- Fixed the general crew update path allowing `on_assignment` without an
  availability date and retaining stale dates after returning to another
  availability state.
- Centralized the invariant in the shared availability-date helper and added
  regression coverage.
- Tool: Codex.

## Hidden-Bug Pass 276 — password-hash cost bound (2026-09-13)

- Fixed password verification trusting an unbounded PBKDF2 iteration count from
  stored hashes, which could turn a malformed hash into a login CPU denial of
  service.
- Added a maximum supported iteration count and regression coverage.
- Tool: Codex.

## Hidden-Bug Pass 275 — unknown-account login timing (2026-09-13)

- Fixed login returning immediately for unknown email addresses while valid
  accounts incurred password-hash verification cost, reducing the account
  enumeration timing signal with a dummy PBKDF2 verification.
- Added regression coverage proving the dummy verification runs.
- Tool: Codex.

## Hidden-Bug Pass 274 — passwordless development login opt-in (2026-09-13)

- Fixed authentication allowing any account without a password hash to log in
  whenever `APP_ENV=development`, despite the code documenting an explicit
  opt-in requirement.
- Added a disabled-by-default `ALLOW_PASSWORDLESS_DEV_LOGIN` setting and
  regression coverage for both fail-closed and explicit opt-in behavior.
- Tool: Codex.

## Hidden-Bug Pass 273 — auto-classified contractor CV rejection (2026-09-13)

- Fixed the asynchronous extraction path allowing a contractor upload with no
  declared classification to be auto-classified as a CV and enter the staff
  administrator review workflow.
- Centralized the restricted CV upload origins and added regression coverage;
  these uploads are now rejected consistently with the worker path.
- Tool: Codex.

## Hidden-Bug Pass 272 — CV review reprocessing stale data (2026-09-12)

- Fixed CV reprocessing retaining fields from an older review proposal when
  those fields were absent from the latest extraction.
- Both asynchronous and synchronous extraction paths now replace the staged
  evidence snapshot atomically; added a regression test.
- Tool: Codex.

## Hidden-Bug Pass 271 — deterministic CV review payload bounds (2026-09-12)

- Bounded deterministic table and free-text CV payloads before they are
  persisted for administrator review, including fields that bypass the LLM
  extraction normalizer.
- Added regression coverage for oversized personal and summary values.
- Tool: Codex.

## Hidden-Bug Pass 254 — seed credential logging (2026-09-12)

- Removed the development seed password and operations account identifier from
  logs; the seed command now reports only non-sensitive setup status.
- Added a regression test covering the seed command's log output.
- Tool: Codex.

## Hidden-Bug Pass 255 — readiness HTTP status (2026-09-12)

- `/health/all` now returns HTTP 503 when any required dependency is unhealthy,
  while preserving the per-service status details for diagnostics.
- Added focused readiness response tests.
- Tool: Codex.

## Hidden-Bug Pass 256 — browser bearer-token persistence (2026-09-12)

- Stopped the browser login flow from persisting the bearer token in
  `localStorage` or `sessionStorage`; authenticated browser requests now rely
  on the backend's HttpOnly session cookie.
- Removed the token field from the frontend login selection while retaining the
  backend field for compatibility with existing non-browser clients.
- Tool: Codex.

## Hidden-Bug Pass 257 — failed extraction payload privacy (2026-09-12)

- Stopped persisting malformed LLM response fragments in document
  `extracted_data`; failed extraction now retains only the safe error and
  review-needed markers.
- Updated the extraction-boundary regression test to assert that raw model
  output is not retained.
- Tool: Codex.

## Hidden-Bug Pass 258 — invalid report payload privacy (2026-09-12)

- Stopped persisting unbounded malformed LLM report output in serialized report
  data; invalid responses now produce a bounded generic summary.
- Added regression coverage proving untrusted model output is not retained.
- Tool: Codex.

## Hidden-Bug Pass 259 — extracted-text retention bound (2026-09-12)

- Capped persisted PDF, DOCX, and email extraction text at 100,000 characters
  in both asynchronous and worker extraction paths.
- Added a regression test for the shared output boundary.
- Tool: Codex.

## Hidden-Bug Pass 260 — unsupported Outlook MSG handling (2026-09-12)

- Stopped accepting `.msg` uploads that had no matching parser and were later
  read as UTF-8 text; `.eml` remains the supported email format.
- Added a regression test proving Outlook compound files fail at the upload
  boundary instead of being silently misprocessed.
- Tool: Codex.

## Hidden-Bug Pass 261 — unsupported legacy document formats (2026-09-12)

- Stopped accepting legacy `.doc` files through direct and Dropbox ingestion,
  matching the actual `python-docx` parser support for `.docx` only.
- Removed stale `.doc` and `.zip` choices from the browser upload controls so
  the UI and backend advertise the same supported formats.
- Tool: Codex.

## Hidden-Bug Pass 262 — upload format source-of-truth (2026-09-12)

- Removed the remaining `.doc` allow-list entry and stale contractor-upload
  control value.
- Dropbox ingestion now reuses the shared upload extension allow-list instead
  of maintaining a second copy that could drift.
- Tool: Codex.

## Hidden-Bug Pass 263 — legacy parser fallback removal (2026-09-12)

- Removed the remaining `.doc` branches from asynchronous and synchronous text
  extraction, preventing legacy stored rows from entering the unsupported
  `python-docx` parser path.
- Added regression coverage for rejection in both extraction paths.
- Tool: Codex.

## Hidden-Bug Pass 264 — Dropbox content revalidation (2026-09-12)

- Added a shared stored-content validator and applied it before asynchronous
  and worker extraction, so Dropbox webhook metadata cannot bypass magic-byte,
  extension, or size validation.
- Added pure regression coverage for mismatched PDF and unsupported Outlook
  content.
- Tool: Codex.

## Hidden-Bug Pass 265 — oversized Dropbox cache writes (2026-09-12)

- Reject oversized downloaded and cached document bytes before they can be
  returned to extraction or written into the local cache.
- Added a regression test for the shared size boundary.
- Tool: Codex.

## Hidden-Bug Pass 266 — report model output schema (2026-09-12)

- Constrained report-model JSON to bounded, report-specific fields and limited
  string/list/number shapes before it is returned or persisted.
- Added a regression test proving unexpected fields and oversized values are
  discarded.
- Tool: Codex.

## Hidden-Bug Pass 267 — extraction model output boundary (2026-09-12)

- Restricted persisted extraction data to known schema fields and bounded nested
  strings, lists, objects, and response length before downstream processing.
- Added regression coverage proving unknown and oversized model fields are not
  retained.
- Tool: Codex.

## Hidden-Bug Pass 268 — natural-language model output bound (2026-09-12)

- Bounded generated crew-query prose before it is returned to callers, while
  preserving deterministic fallback behavior for oversized structured output.
- Added regression coverage for oversized generated summaries.
- Tool: Codex.

## Hidden-Bug Pass 269 — intent model response bound (2026-09-12)

- Added a response-size guard before parsing LLM intent-classification JSON so
  oversized or malformed output uses deterministic query rules.
- Added regression coverage for the fallback path.
- Tool: Codex.

## Hidden-Bug Pass 270 — deterministic CV line bounds (2026-09-12)

- Bounded long training and systems lines before deterministic CV extraction
  results enter the review payload, rather than only bounding them during later
  profile application.
- Added regression coverage for both fallback sections.
- Tool: Codex.

## Hidden-Bug Pass 242 — nginx CSP inheritance (2026-09-12)

- Restored the Content-Security-Policy header on the nested asset and
  `index.html` locations, whose `add_header` directives replace the server-level
  header set in nginx.
- Tool: Codex.

## Hidden-Bug Pass 243 — worker migration startup race (2026-09-12)

- Celery workers and beat now wait for the migration-owning backend to become
  healthy before starting, preventing task consumption during schema upgrade.
- Tool: Codex.

## Hidden-Bug Pass 244 — search filter validation ordering (2026-09-12)

- Document search now validates `classification` and `crew_id` before a
  staff visibility query can return an empty result early.
- Added regression coverage proving malformed filters still return 422 for a
  staff account with no visible profiles.
- Tool: Codex.

## Hidden-Bug Pass 245 — production Flower image dependency (2026-09-12)

- Added the existing Flower dependency to `requirements-prod.txt`, matching
  the Compose service that runs Flower from the production backend image.
- This prevents the declared monitoring container from failing immediately
  with an unavailable `flower` command.
- Tool: Codex.

## Hidden-Bug Pass 246 — production Flower profile (2026-09-12)

- Marked Flower as an explicit `observability` profile in the production
  override so the monitoring UI is not started by the default production
  stack, matching the documented trusted-network policy.
- Tool: Codex.

## Hidden-Bug Pass 247 — production API documentation exposure (2026-09-12)

- Disabled FastAPI Swagger, ReDoc, and OpenAPI routes in production, matching
  the existing production GraphQL introspection policy.
- The root response no longer advertises a documentation route in production;
  development retains the documentation links.
- Added focused application-surface regression tests.
- Tool: Codex.

## Hidden-Bug Pass 248 — production example-secret validation (2026-09-12)

- Production startup now rejects the `SESSION_SECRET_KEY` and
  `MEILI_MASTER_KEY` placeholders shipped in `.env.example`, not only the
  Compose defaults.
- Added regression coverage for both documented placeholders.
- Tool: Codex.

## Hidden-Bug Pass 249 — worker production-secret validation (2026-09-12)

- Moved production-secret validation into shared configuration and invoke it
  when Celery loads, so workers, beat, and Flower fail closed like the API
  when production credentials are missing or defaulted.
- Added focused configuration and startup-surface regression coverage.
- Tool: Codex.

## Hidden-Bug Pass 250 — malformed LLM diagnostic privacy (2026-09-12)

- Stopped logging raw rejected entity values from LLM classification output;
  diagnostics now retain only the field name and runtime type.
- Added regression coverage proving untrusted values do not enter logs.
- Tool: Codex.

## Hidden-Bug Pass 251 — Sentry payload privacy (2026-09-12)

- Disabled Sentry exception-local capture and request-body capture because
  uploaded CV/document content can appear in those payloads.
- Added a regression test for the telemetry configuration.
- Tool: Codex.

## Hidden-Bug Pass 252 — Sentry request-token redaction (2026-09-12)

- Redacted contractor upload-link tokens from Sentry request URLs and made
  authorization, cookie, and API-key header filtering case-insensitive.
- Added regression coverage for both telemetry boundaries.
- Tool: Codex.

## Hidden-Bug Pass 253 — Apollo console privacy (2026-09-12)

- Stopped logging the complete Apollo network-error object in the browser;
  response bodies, URLs, and provider details can now remain out of console
  diagnostics.
- Tool: Codex.

## Hidden-Bug Pass 157 — synchronous extraction approval gate (2026-09-12)

- Fixed the synchronous Dropbox/Celery extraction path restoring `approved` to
  a document that had no stored evidence after reprocessing.
- CVs now remain `awaiting_review`, and other incomplete approved rows reopen as
  `needs_review`, matching the asynchronous document service.
- Added focused regression coverage for both transitions.
- Tool: Codex.

## Hidden-Bug Pass 158 — certificate date normalization (2026-09-12)

- Fixed certificate extraction treating Python `datetime` values as SQL date
  values. Date-only normalization now strips the time component before
  lifecycle comparisons and persistence.
- Added a focused boundary regression test.
- Tool: Codex.

## Hidden-Bug Pass 159 — CV approval payload boundary (2026-09-12)

- Fixed the CV review service accepting non-object approval payloads from
  direct callers and failing later with an uncontrolled attribute error.
- Added a pre-database regression test matching the GraphQL JSON-object gate.
- Tool: Codex.

## Hidden-Bug Pass 160 — manual extraction payload boundary (2026-09-12)

- Fixed manual document confirmation accepting non-object extraction payloads
  from direct callers before JSON persistence or certificate projection.
- Added a pre-database regression test for malformed confirmation data.
- Tool: Codex.

## Hidden-Bug Pass 161 — service collection boundaries (2026-09-12)

- Fixed crew updates and report generation accepting non-object direct inputs
  and failing with uncontrolled collection or attribute errors.
- Added pre-database regressions for malformed update and filter payloads.
- Tool: Codex.

## Hidden-Bug Pass 162 — extraction mapping boundaries (2026-09-12)

- Fixed certificate linking and CV profile application accepting non-object
  extraction payloads from direct or worker callers.
- Added pre-database regressions for malformed extraction data.
- Tool: Codex.

## Hidden-Bug Pass 163 — report type dispatch (2026-09-12)

- Fixed direct report-service callers passing an unknown report type and being
  silently routed to performance data.
- Added a pre-database regression test for invalid report types.
- Tool: Codex.

## Hidden-Bug Pass 164 — document classification boundary (2026-09-12)

- Fixed non-string document classifications reaching persistence or raising
  during normalization from direct service callers.
- Classification values are now normalized before document creation, with a
  focused malformed-value regression.
- Tool: Codex.

## Hidden-Bug Pass 84 — assignment rate validation (2026-09-12)

- Fixed campaign assignment creation accepting negative or non-finite agreed
  day rates.
- The application service now enforces finite non-negative commercial values,
  with regression coverage independent of GraphQL validation.
- Tool: Codex.

## Hidden-Bug Pass 83 — strict mobilization date validation (2026-09-12)

- Fixed frontend assignment dates accepting invalid calendar values that
  JavaScript silently normalizes, such as `2026-02-31`.
- Duration validation now requires finite whole days, matching the backend
  contract; regression tests cover both cases.
- Tool: Codex.

## Hidden-Bug Pass 82 — frontend medical expiry authority (2026-09-12)

- Fixed assignment preflight retaining a stale profile medical expiry when a
  verified certificate had an earlier expiry date.
- The frontend now mirrors backend authority rules and has a focused utility
  regression test.
- Tool: Codex.

## Hidden-Bug Pass 81 — authoritative medical expiry (2026-09-12)

- Fixed assignment compliance trusting a stale denormalized medical expiry
  over newer verified certificate evidence.
- Verified certificate dates now determine mobilization medical checks, with a
  regression test for stale profile projections.
- Tool: Codex.

## Hidden-Bug Pass 80 — verified compliance aggregate counts (2026-09-12)

- Fixed compliance aggregates counting unverified certificates as expired or
  expiring while also counting them as pending verification.
- Expiry aggregates now require verified evidence, with regression coverage.
- Tool: Codex.

## Hidden-Bug Pass 79 — compliance renewal status recovery (2026-09-12)

- Fixed periodic and asynchronous compliance evaluation leaving renewed
  certificates stuck in `expiring_soon` or `expired` status.
- Date-derived lifecycle states now reconcile in both directions, with
  regression tests for both checkers.
- Tool: Codex.

## Hidden-Bug Pass 78 — agent upload idempotency isolation (2026-09-12)

- Fixed API-key document uploads treating a staff or contractor upload with
  the same idempotency key as an agent retry.
- Cross-channel key reuse now returns a conflict, including the concurrent
  insert recovery path, while legitimate agent retries remain idempotent.
- The reverse collision (staff upload reusing an agent key) is also rejected.
- Preserved legitimate staff-upload retries in their concurrent insert
  recovery path; agent-only ownership checks remain confined to agent uploads.
- Tool: Codex.

## Hidden-Bug Pass 75 — CV review session query gate (2026-09-12)

- Fixed the CV review modal starting an account-scoped GraphQL query while no
  session existed, which could leave it stuck on an unauthenticated result
  when authentication completed without remounting the modal.
- The query now waits for a live session key, with a focused session-scope
  regression test.
- Tool: Codex.

## Hidden-Bug Pass 76 — staff modal session isolation (2026-09-12)

- Fixed the staff-access modal retaining and rendering the previous
  administrator's account list when logout or account switching happened
  while the modal remained mounted.
- The modal now waits for the current session before querying or rendering
  account data, and refetches after an account transition.
- Tool: Codex.

## Hidden-Bug Pass 77 — vessel search session isolation (2026-09-12)

- Fixed the operations vessel search pane rendering cached results from a
  previous account during session changes.
- Vessel results now require a completed network-only request for the current
  session, and transient search/roster state is cleared during transitions.
- Tool: Codex.

## Hidden-Bug Pass 74 — certification service status validation (2026-09-12)

- Hardened the certification service boundary against invalid lifecycle and
  verification values. GraphQL enums normally constrain these inputs, but
  service callers and background paths can bypass GraphQL; they now fail
  before opening a database transaction instead of persisting contradictory
  certification states.
- Added focused non-database regression tests for both validation paths.
- Tool: Codex.

Newest entries first. Each entry: date, who/what did it, what changed, why,
and any follow-up the next session needs to know about. Keep entries short —
this is an index into commits and docs, not a replacement for either.

## Hidden-Bug Pass 67 — compliance task retry (2026-09-12)

- Fixed the daily certification/compliance task acknowledging transient
  failures as successful Celery jobs with a "failed" return payload.
- Database or provider failures now use bounded Celery retries, preventing
  expiration statuses and operational alerts from remaining stale until the
  next scheduled run.
- Tool: Codex.

## Hidden-Bug Pass 68 — embedding task retry (2026-09-12)

- Fixed semantic document indexing acknowledging Qdrant/Ollama failures as
  successful Celery jobs with a failed result payload.
- Embedding writes now retry after transient provider failures, while
  permanently non-searchable or deleted documents retain their cleanup path.
- Tool: Codex.

## Hidden-Bug Pass 69 — review-alert session gate (2026-09-12)

- Fixed the frontend incoming-document alert polling the review queue while
  no authenticated session key was present.
- The alert now stays empty during logout and account transitions, preventing
  a still-valid old cookie from repopulating the previous account's queue.
- Tool: Codex.

## Hidden-Bug Pass 70 — failed-extraction audit isolation (2026-09-12)

- Fixed the async document extraction failure path treating audit persistence
  as part of the extraction outcome after the failed state was already
  committed.
- Audit-store outages are now logged as degraded observability while the
  authoritative failed extraction result remains stable and non-retryable.
- Tool: Codex.

## Hidden-Bug Pass 71 — rejected-certification keyword search (2026-09-12)

- Fixed relational crew keyword search matching contractors solely because
  they held a certificate whose lifecycle or verification status was rejected.
- Pending evidence remains searchable for follow-up, while rejected evidence
  no longer makes a contractor appear qualified.
- Tool: Codex.

## Hidden-Bug Pass 72 — unpublished compliance alert projection (2026-09-12)

- Fixed periodic compliance evaluation publishing unpublished contractor
  names, emails, certificate numbers, and document references into the shared
  Redis alert snapshot.
- Unpublished evidence is still status-maintained, but only approved
  contractors contribute to shared operational alerts.
- Tool: Codex.

## Hidden-Bug Pass 73 — stale review recovery race (2026-09-12)

- Fixed certificate-projection recovery reopening a document after a newer
  review/reprocess decision had already committed.
- Recovery now requires the document to remain approved and the incoming
  review resolution timestamp to match the approval that failed projection.
- Tool: Codex.

## Hidden-Bug Pass 66 — account-switch Apollo cache reset (2026-09-12)

- Fixed successful frontend login transitions replacing the auth token while
  retaining Apollo's previous account-scoped cache, which could briefly show
  stale workspace data when switching accounts without a full logout.
- The cache is now cleared before the new account becomes visible; existing
  session-scoped network guards remain defense-in-depth if cache clearing is
  unavailable.
- Tool: Codex.

## Hidden-Bug Pass 60 — session-bound natural search results (2026-09-12)

- Fixed the frontend natural-language search hook retaining Apollo's previous
  lazy-query result across logout, account changes, disabled sessions, or a
  changed query and briefly exposing stale result data in the workspace.
- Added a session-scope regression test for the result gate.
- Tool: Codex.

## Hidden-Bug Pass 61 — document search publication boundary (2026-09-12)

- Fixed REST document search returning stale extracted documents owned by
  unpublished contractor drafts to administrators.
- PostgreSQL publication state is now rechecked for every document-search hit;
  unowned orphan documents remain available only to administrators for recovery.
- Added an administrator regression test.
- Tool: Codex.

## Hidden-Bug Pass 62 — review alert draft dossier navigation (2026-09-12)

- Fixed staff document-review alerts failing to open dossiers for the staff
  member's own unpublished draft, which is intentionally absent from the
  approved contractor roster.
- Review-alert navigation now performs a session-scoped detail fetch and
  opens the existing dossier modal without weakening backend authorization.
- Tool: Codex.

## Hidden-Bug Pass 63 — pending medical evidence in assignment compliance (2026-09-12)

- Fixed medical expiry projection and assignment compliance accepting
  unverified certificates in both async and periodic paths, which could make
  pending evidence appear deployable.
- Validity-filtered natural search now requires verified evidence; broad
  evidence-on-file searches and compliance alerts still surface pending work.
- Current medical/certification search now includes verified certificates in
  the `expiring_soon` window until their actual expiry date.
- Compliance aggregates no longer count a `valid` but unverified certificate
  as verified-valid.
- Verification reset now returns a previously verified certificate to
  `pending_verification` instead of leaving contradictory `valid` state.
- Manual status updates can no longer mark unverified evidence as `valid`.
- Added regressions covering pending and unverified-valid medical certificates.
- Tool: Codex.

## Hidden-Bug Pass 64 — account-scoped operations cache (2026-09-12)

- Fixed active project and mobilization candidate panels briefly rendering
  Apollo data from a previous authenticated account during session changes.
- Both operational queries now require the current session scope and a fresh
  network result before rendering.
- Tool: Codex.

## Hidden-Bug Pass 65 — cache symlink containment (2026-09-12)

- Replaced string-prefix cache containment checks with path-aware resolved-path
  checks for document reads, local uploads, deletion, and Dropbox cache writes.
- Added a regression preventing a cache-directory symlink from exposing files
  outside the managed cache root.
- Tool: Codex.

## 2026-09-12 — Hidden-Bug Pass 52 (Codex)

Deletion cleanup now retries derived Meilisearch and Qdrant projection removal
after a committed admin or Dropbox deletion when either provider is unavailable.
This prevents deleted documents from remaining searchable indefinitely; the
next session should verify the bounded Celery retry path against live providers.

Document extraction now keeps the committed extraction result when a derived
Meilisearch or Qdrant cleanup call fails. Provider outages are logged for
repair instead of incorrectly changing a successfully extracted document to
`failed`.

Crew deletion now retries failed cache, profile-search, and document-vector
cleanup after the source transaction commits, preventing deleted crew data
from surviving a transient Redis, Meilisearch, or Qdrant outage.

Crew and assignment updates now queue a bounded source-of-truth reconciliation
when Meilisearch is unavailable after commit, preventing a draft/unpublished
change from leaving an approved profile in the public search projection.

Document deletion now continues through derived-search cleanup when Redis cache
invalidation fails, and schedules the same bounded cleanup retry instead of
leaving deleted evidence searchable behind an early cache exception.

Contractor review decisions now continue Qdrant cleanup or approved embedding
dispatch when post-commit Redis invalidation fails, keeping cache outages from
skipping the remaining derived-state transition.

CV review approval and rejection retries now likewise continue search/vector
reconciliation when cache invalidation fails after the review commit.

Dropbox revision processing and document relinking now continue cache-file,
extraction, and projection work when Redis invalidation fails after commit.

Idempotent retries for contractor, staff, and agent uploads now requeue
extraction when the original broker dispatch failed, instead of permanently
returning the failed row without another processing attempt.

Certificate-review recovery now continues Qdrant and search cleanup when its
post-recovery Redis invalidation fails.

Concurrent idempotent-upload losers now retry failed Dropbox orphan cleanup,
preventing remote files with no database record from accumulating after a
duplicate upload race.

Certification mutations now treat Redis cache invalidation as best-effort, so
a committed certification change is not reported as failed during a cache
outage.

Crew availability and assignment mutations now likewise continue their search
projection reconciliation when summary-cache invalidation fails.

Deletion retry decisions now also inspect the cache service's boolean result;
Redis failures are handled even though the cache adapter intentionally swallows
the underlying exception.

The deleted-crew retry task now applies the same false-result handling, so it
retries rather than falsely reporting completion when Redis remains unavailable.

Meilisearch and Qdrant false results are now treated as cleanup failures in
deletion and reconciliation paths, preventing provider outages that return a
normal response from being mistaken for successful projection removal.

The admin crew-index endpoint now returns a service-unavailable error when
indexing is not confirmed instead of falsely reporting success.

Successful extraction, manual confirmation, and document relinking now queue
bounded Meilisearch reconciliation when the provider returns an unconfirmed
result rather than raising an exception.

CV approval and rejection workflows now queue crew and document projection
repair when their providers return unconfirmed results.

The synchronous extraction worker now preserves a committed `extracted` status
when certificate linking fails afterward, instead of incorrectly marking the
document extraction as failed.

Rejected, deleted, and superseded documents now schedule bounded semantic
projection cleanup when Qdrant reports an unconfirmed deletion.

GraphQL project assignment projections now hide rejected profiles and drafts
owned by another staff member, while preserving approved profiles and the
requesting staff member's own drafts. This closes a C2 publication-scope leak
through `crew_assigned`.

The project visibility helper now applies own-draft scope only to `staff`; a
regular authenticated user cannot receive draft assignment IDs even through a
future unscrumbed service caller.

Dropbox revision processing now invalidates the document's stable-path local
cache before re-extraction, preventing old binary content from being served or
processed after a file is modified in Dropbox.

Administrator document reprocessing now dispatches extraction after resetting
the source state, and marks the document failed if the broker cannot accept
the task instead of leaving it indefinitely pending.

Dropbox revision cleanup failures are now best-effort, so a Meilisearch or
Qdrant outage cannot prevent the revised source file from being queued for
fresh extraction.

Contractor document review decisions now remain retryable after a committed
approval when derived projection cleanup fails; provider outages no longer
turn a successful source-of-truth decision into an unrecoverable API error.

Vessel roster rendering now waits for the current authenticated session's
successful response and suppresses cached roster data during account changes
or failed refreshes, preventing one staff account's draft assignments from
appearing in another account's workspace.

## 2026-09-12 — Hidden-Bug Pass 51 (Codex)

Campaign assignment vessel keys now reject blank or overlong IMO values before
creating local vessel and assignment records.

Vessel identifiers now reject URL path and query delimiters before provider
requests or local persistence.

Manual extraction confirmation no longer reports a mutation failure when its
post-commit access-audit write is temporarily unavailable; the failure is
logged while the committed document result remains authoritative.

Contractor document review decisions now use the same post-commit audit
failure policy, avoiding false mutation failures after approval or rejection
has already been committed.

Idempotent CV rejection retries now reconcile the rejected document's search
projection as well as its profile and semantic projections, removing stale
searchable evidence after a prior reconciliation outage.

The same idempotent rejection retry now invalidates cached summary and
compliance results, preventing stale contractor state after a partial failure.

Repeated rejected contractor-review actions now retry document search
reconciliation before returning the terminal-state error.

Staff document-review endpoints now require contractor-upload provenance and a
matching incoming-review row, preventing staff from approving ordinary
admin-uploaded documents by ID.

Staff visibility scopes now distinguish unpublished drafts from rejected
profiles, preventing a submitting staff member from accessing rejected-profile
documents, certifications, assignments, reports, or search hits.

The GraphQL contractor-detail resolver now applies the same draft-only rule,
closing the remaining rejected-profile visibility path.

Assignment, expiring-certification, and report services now default to an
unprivileged actor role; privileged data requires an explicit admin context.

Document reset, deletion, and Dropbox-revision paths now attempt semantic
projection cleanup even when Meilisearch reconciliation fails, preventing stale
Qdrant evidence from surviving a PostgreSQL state transition.

VesselAPI cache keys now include the configured upstream base URL, and provider
position coordinates are range-validated before reaching GraphQL. Unexpected
vessel-position adapter failures now use the safe upstream error contract.

CV approval retries now requeue semantic embeddings for every approved document
on the newly published contractor, including older documents whose original
indexing dispatch may have failed.

Meilisearch contractor indexing now performs a post-write source check and
corrective write when a newer PostgreSQL profile update races the projection.

Stale Meilisearch removal requests now restore the current approved profile if
an approval commits while the delete is being submitted.

Document extraction, manual confirmation, review decisions, and deletion now
reconcile the document Meilisearch projection. Previously the index had a
search API and writer but no application write path, so successful documents
could remain invisible to document search.

Added `backend/reindex_document_search.py` for a one-time PostgreSQL-authoritative
backfill of existing document records.

Extraction failures now remove stale document-search projections before Celery
retry escalation, preventing an older successful extraction from remaining
searchable after the source row becomes failed.

Assignment compliance now evaluates verified medical certificates marked
`expiring_soon` or `expired` using their recorded expiry dates instead of
incorrectly reporting that no expiry was recorded.

Natural-language compliance authorization now locks explicit expired,
expiring, renewal, and non-compliant queries to the compliance intent before
the role gate runs, so an intent-model misclassification cannot expose a T1
profile search result.

Natural-language certificate searches now exclude records whose primary status
is `rejected`, in addition to rejected verification records, so declined
evidence cannot make a contractor appear qualified.

Natural-language search result payloads now also omit rejected certificate
types from otherwise matching profiles, preventing declined evidence from
reappearing in the returned qualification list.

Report filter objects now validate scalar/list shapes before SQL construction,
and malformed values return `BAD_USER_INPUT` instead of raising an unhandled
server-side type error.

Dropbox external deletion now removes the document's Meilisearch projection
after the PostgreSQL row is committed, matching local deletion and preventing
deleted evidence from remaining searchable.

Dropbox revisions now remove the old Meilisearch projection when the document
returns to `pending`, preventing stale extracted evidence from remaining
searchable during reprocessing.

Extraction audit persistence is now best-effort after the document commit, so
an audit-store outage cannot overwrite a successful extraction as `failed`.

The same lifecycle-date handling now applies to BOSIET/FOET survival
certificates.

CV publication now reconciles keyword document projections for every approved
document belonging to the newly published contractor, including older
documents that were extracted while the profile was still a draft.

The semantic indexing worker now removes stale Qdrant vectors when queued work
finds a deleted, rejected, unpublished, or otherwise non-searchable document,
when a replacement write fails, or when certificate projection recovery reopens
an approved document for review.

**Why:** leaving the previous vector searchable could surface withdrawn
document evidence after the PostgreSQL source record had changed.

Incoming-document alert actions now ignore late approve/reject responses after
logout or account/role changes, matching the modal's session-generation guard.

CV rejection retries now repeat semantic-vector cleanup when the review is
already rejected, allowing an earlier Qdrant outage to be repaired safely.

Incoming document rejection retries now do the same while preserving the
existing terminal-decision error response.

Vessel search, position, radius, and local vessel-record GraphQL queries now
require staff/admin access, matching the staff-only operations workspace rather
than relying on frontend tab visibility.

Incoming document review authorization now runs before terminal-state checks,
preventing error responses from revealing another staff member's draft status.

Operations document and expiring-certification counts are now reset and
refetched across authenticated account/role transitions; cached operational
counts cannot flash into another staff session.

## 2026-09-12 — Hidden-Bug Pass 49 (Codex)

GraphQL work-history projections now preserve the C2 `documentRef` field for
authorized staff/admin detail reads while T1 users continue receiving no work
history rows.

**Why:** the persisted source-document reference was omitted from the
GraphQL type and mapper, silently losing provenance for operations users.

## 2026-09-12 — Hidden-Bug Pass 48 (Codex)

Corrected the project T1 scrubber so `waterDepth`, like `crewAssigned`,
`requirements`, and `documentRef`, remains redacted for recruiter-level users.

**Why:** the previous projection fix accidentally preserved `waterDepth` despite
the authoritative access-tier mapping classifying it as C2.

## 2026-09-12 — Hidden-Bug Pass 47 (Codex)

Project GraphQL reads now preserve stored `waterDepth` and `documentRef` data;
the latter is redacted for T1 callers alongside other C2 project fields.

**Why:** these persisted/authorized project fields were omitted by the
GraphQL type and mapper, so project reads silently lost source data.

## 2026-09-12 — Hidden-Bug Pass 46 (Codex)

The CV review modal now clears and refetches its Apollo-backed data when the
authenticated account or role changes, and does not render prior-session data
while the new request is loading.

**Why:** fixed query variables allowed an administrator’s review list and
notes to remain visible briefly in a staff session.

## 2026-09-12 — Hidden-Bug Pass 45 (Codex)

Vessel roster rendering now applies an explicit administrator gate to agreed
day rates, preventing Apollo-cached commercial data from flashing in a staff
session during role transitions.

**Why:** the backend redacted rates for staff, but a previously cached admin
response could still be rendered before the network response replaced it.

## 2026-09-12 — Hidden-Bug Pass 44 (Codex)

The document-review modal now scopes loading and approve/reject responses to
the authenticated session, ignoring late results after logout or role change.

**Why:** an in-flight review action could refresh the next session’s queue or
show a result toast for the previous account.

## 2026-09-12 — Hidden-Bug Pass 43 (Codex)

Document-upload status polling is now cancelled when the modal closes or its
contractor changes, and late responses are ignored by an operation-generation
guard.

**Why:** a delayed status response could refresh the wrong dossier or display a
private extraction toast after logout/profile transition.

## 2026-09-12 — Hidden-Bug Pass 42 (Codex)

Project GraphQL reads now expose the persisted `crewAssigned` field to C2/C3
callers and redact it for T1 callers.

**Why:** project assignment mutations wrote the field, but the GraphQL type and
mapper dropped it, making assignments invisible in project reads.

## 2026-09-12 — Hidden-Bug Pass 41 (Codex)

Document status access now fails closed for staff when its contractor owner is
missing, preventing orphaned document metadata from being exposed through a
stale foreign-key reference.

**Why:** the endpoint rejected non-approved existing contractors but allowed a
missing contractor row to fall through as visible.

## 2026-09-12 — Hidden-Bug Pass 40 (Codex)

Deleting a contractor now removes that ID from legacy project assignment JSON
in the same database transaction as contractor and campaign-assignment
deletion.

**Why:** project records could retain orphaned contractor IDs and report stale
readiness assignments after the contractor was deleted.

## 2026-09-12 — Hidden-Bug Pass 39 (Codex)

Frontend session boundaries now include both account ID and role. Profile,
document, summary, roster, alert, and AI query state is hidden or reset
immediately when a role changes, preventing an administrator’s cached evidence
from flashing into a staff session.

**Why:** the previous boundary used only user ID, so same-account role changes
could retain role-scoped data for one render and stale asynchronous responses.

## 2026-09-12 — Hidden-Bug Pass 38 (Codex)

Summary and compliance cache keys now include the authoritative profile and
certification state. A slow request that finishes after an update can only
populate an obsolete generation key, which newer requests will not read.

**Why:** invalidation alone allowed an in-flight old computation to repopulate
the deleted key with stale data.

## 2026-09-12 — Hidden-Bug Pass 37 (Codex)

Meilisearch crew indexing now reloads the profile from PostgreSQL immediately
before writing the derived document. Concurrent updates can no longer submit
an older ORM snapshot after a newer profile update.

**Why:** stale index writes could make a current contractor disappear from
keyword search even though PostgreSQL held the latest profile.

## 2026-09-12 — Hidden-Bug Pass 36 (Codex)

Document embedding tasks now re-read PostgreSQL state before and after the
Qdrant upsert. If a Dropbox revision, classification, publication state, or
review status changes while indexing, the newly written vector is removed and
the task reports the work as stale.

**Why:** an older queued embedding could run after revision invalidation and
reintroduce a stale semantic-search projection.

## 2026-09-12 — Hidden-Bug Pass 35 (Codex)

Synchronous Celery document extraction now records the same extraction audit
event as the asynchronous path, including model, confidence, and terminal
status. Audit failures are logged without converting an already-committed
extraction into a retryable failure.

**Why:** Dropbox/worker extraction was bypassing the document audit history,
leaving production extraction decisions without an auditable event trail.

## 2026-09-12 — Hidden-Bug Pass 22 (Codex)

Document search now returns an empty authoritative result when Meilisearch
provides only malformed hits or an empty page. Added initialization for the
source-of-truth hit accumulator; the existing stale-projection regression now
passes instead of raising `UnboundLocalError` and returning a 500.

**Why:** derived search payloads must fail closed when no hit can be resolved
against PostgreSQL.

## 2026-09-12 — Hidden-Bug Pass 23 (Codex)

Natural-language search result parsing now validates optional backend fields
before they enter the result workspace. Invalid nested values are discarded
while valid profile results remain usable; added regression coverage for
malformed certification, availability, email, and experience values.

**Why:** the previous parser validated only `id` and `name`, allowing malformed
JSON/LLM output to reach typed filters and React rendering at runtime.

## 2026-09-12 — Hidden-Bug Pass 24 (Codex)

Document compliance metadata (`title`, issue/expiry dates, and notes) is now
classified explicitly as T2/C2 in the access-tier map, matching the existing
GraphQL scrubber and authorization documentation.

**Why:** these fields were visible to authorized staff but missing from the
machine-readable field map, which treats unmapped fields as deny-by-default.

## 2026-09-12 — Hidden-Bug Pass 25 (Codex)

Document preview rendering now sanitizes extracted `personal_information`
values before displaying them, dropping nested objects, arrays, and non-finite
numbers instead of trusting an unsafe TypeScript cast. Added focused utility
tests.

**Why:** malformed extraction JSON could otherwise reach React as an object and
cause a render error in the administrator document preview.

## 2026-09-12 — Hidden-Bug Pass 26 (Codex)

Contractor-document approval now reopens the review and returns the document
to `needs_review` if certificate projection linking fails after the decision
transaction. Any partial certificate link is detached during recovery.

**Why:** the previous post-commit projection failure left the document marked
approved and the review resolved, preventing a safe retry.

## 2026-09-12 — Hidden-Bug Pass 27 (Codex)

Document preview actions now hide terminal-state review controls. Rejected
documents no longer show an impossible “Re-approve” action, and approved
documents no longer show an impossible “Revoke Approval” action.

**Why:** the backend correctly rejects decisions that would overwrite terminal
document states, but the frontend still presented those actions.

## 2026-09-12 — Hidden-Bug Pass 28 (Codex)

Document preview no longer offers approval while extraction is still pending,
processing, or failed. Rejection remains available for non-terminal uploads,
so staff can clear an unusable review item.

**Why:** the backend accepts approval only for `extracted` and `needs_review`
documents, but the previous pending-review banner showed approval for every
non-terminal extraction state.

## 2026-09-12 — Hidden-Bug Pass 29 (Codex)

Live roster mapping now filters parsed tag JSON to strings before applying
classification and display rules. Added a regression test for mixed malformed
tag arrays.

**Why:** one non-string tag previously caused regex operations to throw and
could make the entire live roster fall back to an empty/demo state.

## 2026-09-12 — Hidden-Bug Pass 30 (Codex)

Certificate projection recovery now invalidates compliance and summary caches
after reopening a failed approval.

**Why:** the previous recovery restored the database state but left cached
approved compliance data available until the normal cache TTL elapsed.

## 2026-09-12 — Hidden-Bug Pass 31 (Codex)

Manual extraction confirmation now refuses documents whose worker is already
processing them.

**Why:** an administrator could confirm a document mid-extraction, after which
the worker would overwrite the confirmed data when it finished.

## 2026-09-12 — Hidden-Bug Pass 32 (Codex)

Dropbox revision processing now invalidates compliance and summary caches and
removes the old semantic embedding before re-extraction.

**Why:** replacing a source file reset the database row but left derived
compliance data and semantic results referring to the previous binary.

## 2026-09-12 — Hidden-Bug Pass 33 (Codex)

Incoming document alerts are now scoped to the authenticated account and
ignore out-of-order refresh responses.

**Why:** a slow prior poll could overwrite newer review data, and account
switches could briefly retain another user’s review queue.

## 2026-09-12 — Hidden-Bug Pass 34 (Codex)

Non-admin CV review responses no longer expose submitter or reviewer account
identifiers. Administrators retain those audit fields.

**Why:** staff CV listings were ownership-scoped but still returned C3 audit
identifiers that the authorization policy reserves for administrators.

## 2026-09-12 — Hidden-Bug Pass 21 (Codex)

Authentication-bound overlays now close immediately on logout, session expiry,
and account transitions, preventing private dossier, document review, CV
review, staff-access, comparison, and inquiry surfaces from remaining mounted
during the public-shell transition. Added a focused browser regression test
for session expiry.

**Why:** the modal state was not included in the existing privacy cleanup
paths, so an open private overlay could survive explicit logout.

Logout now reports `SERVICE_UNAVAILABLE` when server-side session revocation
cannot be persisted, while still expiring both accepted session cookies.
Added a regression test for failed revocation.

The frontend now surfaces a warning when server-side logout cannot be
confirmed instead of displaying a successful-signout message after only local
cleanup.

**Why:** ignoring a failed Redis revocation made logout look successful even
though an old bearer token could become valid again after Redis recovered.

## 2026-09-12 — Hidden-Bug Pass 20 (Codex)

Staff mobilization inquiries now omit the administrator-only agreed day rate
from the assignment mutation. The staff confirmation and copied dispatch
brief label the rate as administrator-confirmed; administrators retain the
commercial field.

**Why:** valid staff submissions were rejected because the inquiry modal sent
a day rate that the backend correctly restricts to administrators.

## 2026-09-12 — Hidden-Bug Pass 19 (Codex)

Regular authenticated users can no longer open the staff-only mobilization
inquiry flow and submit a mutation that the backend would reject. The UI now
shows an operations-staff guidance message instead.

**Why:** the mobilization action was exposed across contractor views while
`createCampaignAssignment` requires staff or administrator authorization.

## 2026-09-12 — Hidden-Bug Pass 18 (Codex)

Staff vessel mobilization now omits administrator-only agreed day rates from
the assignment mutation. The staff confirmation and copied dispatch brief no
longer display an unsaved rate; administrators retain the commercial field.

**Why:** the operations UI was available to staff but always sent a day rate,
which the backend correctly rejected as an administrator-only field.

Frontend lint, unit tests, build, and strict UI audit passed.

## 2026-09-12 — Hidden-Bug Pass 17 (Codex)

The scheduled certification-expiration check now recomputes each affected
contractor's medical projection from all remaining medical certificates.

**Why:** an older medical certificate expiring could overwrite a valid root
`medical_status` even when a newer certificate was still current. Added
regression coverage for overlapping medical evidence in both async and
synchronous expiration workers.

## 2026-09-12 — Hidden-Bug Pass 16 (Codex)

Reprocessing an approved contractor-uploaded document now reopens its existing
incoming review row. Dropbox revision ingestion applies the same reset.
Manual extraction confirmation also reopens the row when the document is a
contractor upload.

**Why:** extraction correctly returned the document to `needs_review`, but a
previously resolved queue row stayed resolved, making the new evidence
invisible to staff. Added regression coverage for both manual reprocessing and
Dropbox revisions.

## 2026-09-12 — Hidden-Bug Pass 15 (Codex)

Document cleanup now captures the crew ID, storage path, and document ID before
deleting and committing the ORM row. Normal and Dropbox-triggered deletion no
longer read fields from a potentially expired deleted instance during cache,
file, or semantic-index cleanup. Added Dropbox cleanup regression coverage.
Crew deletion now captures document cleanup data before deleting the account
and its documents for the same reason.

**Why:** async SQLAlchemy can expire deleted instances after commit; a cleanup
read could fail and leave derived files or semantic projections behind.

## 2026-09-12 — Hidden-Bug Pass 14 (Codex)

Orphaned Dropbox document records are now administrator-only through both the
GraphQL single-document resolver and the REST status endpoint. Added staff
regression coverage for both paths.

**Why:** crew-less recovery records were documented as admin-only, but a staff
user who knew a document ID could previously read its metadata.

## 2026-09-12 — Hidden-Bug Pass 13 (Codex)

The authenticated roster now suppresses cached profiles across account
transitions and waits for the current session's network response before
rendering or paginating results.

**Why:** `cache-and-network` could briefly show the previous account's cached
draft roster while a new account was still being authenticated.

Failed current-session roster requests now leave the roster empty instead of
falling back to Apollo's retained previous-account data.

Frontend lint, unit tests, build, and strict UI audit passed after the change.

Approving a contractor document now explicitly queues its semantic projection
after the review gate opens, so the worker-side pre-approval skip does not
leave accepted evidence absent from semantic search.

Publishing a contractor through CV approval now queues every already-approved
or extracted document attached to that contractor, covering documents accepted
while the profile was still a draft.

Reprocessing a certificate document now detaches its old certification
projection, reconciles medical fields, clears compliance caches, and removes
the stale semantic projection before extraction restarts.

**Why:** Resetting an approved certificate to `pending` previously left the
old credential linked and usable while the source document was being replaced.
Added a regression test covering the stale projection cleanup.

Contractor-link certificate uploads now remain out of certification
projections until the associated staff review is approved.

**Why:** Extraction previously linked the certificate immediately after it
returned usable data, allowing unapproved contractor evidence to affect
compliance during the review window.

The same review gate now applies to manual administrator extraction
confirmation: contractor-link documents remain `needs_review` and do not enter
certificate or semantic projections until explicitly approved.

Added a regression test for this manual-confirmation path.

Administrator document relinking now applies the same approval gate before
rebuilding certificate and semantic projections for contractor-link uploads.

The certificate projection service also enforces this invariant defensively,
with a regression test preventing direct internal callers from linking
unapproved contractor evidence.

Authoritative document search, reports, semantic-hit hydration, and embedding
workers now enforce the same contractor-review predicate, preventing stale or
queued derived projections from exposing extracted-but-unapproved evidence.

The consultant profile access layer now applies that predicate when returning
linked document summaries as well.

## 2026-09-12 — Hidden-Bug Pass 11 (Codex)

Certification aliases in deterministic natural-language search now require
word boundaries before being inferred as certificate requirements.

**Why:** Raw substring matching could interpret ordinary words such as
“approved” or “these” as ROV or HSE certificate requests, producing incorrect
search constraints. Exact terms such as “ROV” and “HSE” remain supported.

## 2026-09-12 — Hidden-Bug Pass 12 (Codex)

Assignment creation and activation now calculate contractor availability from
all active assignments, preserving the latest active assignment end date.

**Why:** Activating a non-overlapping earlier assignment after a later active
tour could move `availability_date` backwards and make the contractor appear
available too soon.

Nationality aliases in deterministic search now require word boundaries.

**Why:** Substring matching could interpret words such as “polished” as the
Polish nationality and apply an unintended nationality filter.

The workspace now treats an empty AI search response as authoritative instead
of falling back to local keyword matching.

**Why:** A valid AI no-match response could previously leave unrelated local
keyword matches visible, making the search result misleading.

AI-only synthesized profiles now normalize backend availability statuses into
the frontend's display vocabulary.

**Why:** Raw values such as `available` and `on_assignment` could render
incorrectly and fail the workspace's availability filters.

Frontend document compliance now treats a date-only expiry occurring today as
expiring today rather than already expired.

**Why:** Parsing a date-only value at midnight made the browser disagree with
the backend's date-based expiry semantics for the rest of that day.

Documents without an expiry now say “No expiry recorded” until review is
approved; only approved documents use “Verified Permanent.”

**Why:** The previous label implied compliance approval for pending documents.

Document vault mapping now recognizes the backend’s canonical `certificate`
classification as a frontend certificate category.

**Why:** Certificate documents were previously mapped to “Other” unless they
used the legacy `cert` alias.

The document vault no longer claims 100% mobilization compliance while any
listed document remains unverified or rejected.

**Why:** The previous summary considered only expiry dates and could present
pending or rejected evidence as fully cleared.

An empty document vault now reports that no compliance documents are recorded
instead of displaying a 100% compliance claim.

**Why:** A zero-document collection is not evidence of mobilization clearance.

Original document downloads now use authenticated fetches with the stored
Bearer token instead of unauthenticated browser links.

**Why:** REST document downloads are admin-gated and browser navigation does
not attach the app's local/session-storage Authorization header.

Account transitions now clear shared workspace state when a different account
logs in during the logout exit animation, while preserving account-scoped
shortlists.

**Why:** The delayed logout cleanup correctly avoided touching the new session,
but without a new-session reset the previous account's query and dossier state
could remain visible.

Manual document title, issue date, expiry date, and notes now persist through
the upload API and are returned to the document vault.

**Why:** The upload form previously collected these values but discarded them,
leaving compliance records with misleading or missing metadata.

The upload status poll now refreshes the vault after extraction completes, so
the visible document status does not remain stale after processing.

**Why:** The previous poll only displayed a toast and left the old pending row
in the dossier until another manual refresh.

## 2026-09-12 — Hidden-Bug Pass 10 (Codex)

The production GraphQL introspection guard now permits `__typename`, while
continuing to block `__schema` and `__type` schema enumeration.

**Why:** `__typename` is a standard response meta-field used by Apollo and
fragment clients; treating it as introspection rejected otherwise valid
production queries.

Deferred logout cleanup now checks for a newly established session before
clearing workspace state.

**Why:** A quick logout followed by login could allow the previous account's
exit-animation timer to clear the new account's filters, selection, and URL.

Mobilization pre-flight checks now exclude rejected and pending certification
records when deciding whether medical and survival evidence is valid.

**Why:** The backend excludes rejected and non-valid evidence, but the
frontend could previously display a false compliant result for those records.

Natural-language “current” and “valid certification” searches now exclude
certificates whose lifecycle is still `pending_verification`.

**Why:** Search results could previously present awaiting-review evidence as a
qualified match even though assignment compliance correctly required `valid`.

Finnish nationality queries now normalize to the canonical `Finnish` value.

**Why:** The deterministic rule previously emitted `Finnic`, which did not
match stored nationality values and silently produced empty results.

Environmental natural-language searches no longer infer a JNCC MMO
certification requirement from the generic `environmental` skill term.

**Why:** The alias was valid for neither every environmental specialist nor
every environmental role, so it could silently discard otherwise relevant
search results.

GraphQL bulk contractor roster and keyword search results are now always C1
only, including when staff or administrators request sensitive fields directly
in a forged selection set. C2/C3 detail remains available only through the
explicit profile-detail path.

The frontend bulk roster query now requests only C1 fields as well; medical
evidence remains confined to the explicit profile-detail query.

Dropbox deletion and revision events now match stored paths case-insensitively,
covering Dropbox's `path_lower` webhook value when uploaded filenames retain
uppercase characters.

**Why:** Exact matching could leave deleted or revised documents and their
projections behind after a provider event.

The Dropbox webhook verification endpoint now echoes the challenge as a
plain-text response with `nosniff`, and malformed notification payloads are
rejected or ignored safely before background work is scheduled.

**Why:** Dropbox requires a plain-text challenge response for registration;
the previous JSON response could prevent webhook setup entirely.

Administrator document vault cards and previews now use the authenticated
document download endpoint for original files; staff and user views remain
metadata/compliance-record only.

**Why:** The backend download route existed, but the frontend only considered
a missing `fileUrl`, so administrator download controls were permanently
disabled.

Contractor document approval now requires extraction to reach `extracted` or
`needs_review`; pending, processing, and failed documents may still be
rejected but cannot be approved. Review controls disable approval until that
state is reached.

**Why:** Approving a pending document marked it as approved before extraction,
allowing the worker to publish low-confidence or failed evidence without a
human decision.

Approving an extracted certificate held for human review now rebuilds its
certification projection immediately after the document approval commits.

**Why:** Review-gated extraction intentionally withheld certification linking;
without this follow-up, approval made the document searchable while compliance
data remained absent or stale.

**Why:** The documented access policy treats bulk discovery as C1-only; the
previous resolver selected its response scrubber from the caller role and
could export cross-profile contact, work-history, or compliance fields.

Roster pagination now discards stale account/session responses before advancing
the active pagination offset or clearing the current session's loading state.

**Why:** A delayed request from a previous session could otherwise skip the
first page of the newly authenticated session or alter its loading indicator.

- Reprocessing a previously rejected certificate document now reopens the linked certification for verification even when extraction produces identical values. This prevents the old rejected verification flag from permanently excluding fresh approved evidence. Added a regression test; the database-backed test remains blocked by the existing async fixture hang in this environment.

- Relinking an already approved certificate document now rebuilds its certification projection for the new contractor, matching the existing extracted-document path. Added regression coverage; the database-backed test remains blocked by the existing async fixture hang in this environment.

- Draft duplicate detection now trims stored names and emails before case-insensitive comparison, so legacy whitespace-padded records cannot bypass the possible-duplicate guard. Added a regression test; the database-backed test remains blocked by the existing async fixture hang in this environment.

- Certificate linking now locks and rechecks the source document before creating evidence, closing the race where a concurrent rejection could otherwise leave a certification linked to a rejected document. Added regression coverage; the database-backed test remains blocked by the existing async fixture hang in this environment.

- CV approval and rejection now lock the document before the review row, matching Dropbox revision handling and refusing decisions for documents no longer awaiting review. This prevents stale CV approvals and removes a document/review lock-order deadlock. Added a regression test; the database-backed test remains blocked by the existing async fixture hang in this environment.

- Contractor document review now also locks the document before its review queue row, matching Dropbox revision handling and preventing the corresponding concurrent review/revision deadlock. Existing review regressions cover the state transition; the database-backed suite remains blocked by the existing async fixture hang in this environment.

- Dropbox webhook ingestion now marks new and revised documents `failed` when Celery dispatch fails, making them visible to the existing retry/reprocess workflow instead of leaving them indefinitely `pending`. Added regression coverage; the database-backed test remains blocked by the existing async fixture hang in this environment.

- REST and consultant keyword crew search now reapplies exact availability/classification filters where applicable against PostgreSQL and rehydrates crew result fields from the source of truth, preventing stale Meilisearch projections from returning outdated or incorrectly filtered records. Added regression coverage; database-backed search tests remain blocked by the existing async fixture hang in this environment.

- Frontend session state now treats login, logout, expiry, and explicit refresh as generation-guarded transitions. This prevents an out-of-order `ME` response from restoring the previous account or overwriting a successful login. Frontend lint and unit tests pass.

- The live roster hook now scopes auto-pagination and manual page loads to the authenticated user session, preventing late responses from a prior session from repopulating local state after logout or account change. Frontend lint and unit tests cover the unchanged hook contract.

- Recent search history is now stored per authenticated user instead of under one shared browser key, preventing account-switch exposure of private search terms. Frontend lint and unit tests pass.

- Added an admin-only `staffAccounts` GraphQL query for role management. The Staff Access modal no longer relies on the approved-only contractor roster, so draft and rejected account records remain promotable or demotable. Added a service regression test.

- Document access, extraction, and periodic compliance audit writes now lock the source document before appending to its JSON audit log, preventing concurrent events from overwriting one another. Added a regression test for repeated audit appends.

- Existing contractor upload links now become unusable when the linked profile is rejected, preventing a pre-rejection bearer token from adding documents to a rejected contractor. Added a regression test.

- Private document and AI-summary hooks now reset on authenticated user-ID changes, not only on logout, and reject in-flight responses from the prior account. This closes a session-switch race that could briefly show another user’s dossier data.

- Shortlist state now reports only IDs and counts for the currently loaded user namespace, closing the one-render logout/account-switch race that could display the previous user's shortlist count before storage hydration completed.

- Session verification now rejects signed payloads without a valid user ID and `jti`, and revocation lookup fails closed for missing identifiers, preventing legacy or malformed tokens from creating non-revocable authenticated sessions. Added a regression test.

- Authentication now canonicalizes email whitespace/case and fails closed when duplicate profile rows share a login address, preventing `MultipleResultsFound` errors or arbitrary-account selection after an administrator explicitly allows a distinct profile. Added a regression test.

- Direct document review now refuses already-approved or rejected documents, preventing a caller with a known document ID from reopening a terminal decision and invalidating previously accepted certification evidence. Added a regression test.

- Natural-language profile summaries now handle overlapping names safely: a unique exact match wins, while ambiguous partial matches request clarification instead of raising a database multiple-results error or summarizing an arbitrary contractor. Added a regression test.

Natural-language searches for valid certifications now require an allowed certification lifecycle status as well as a future expiry date, preventing rejected credentials with future-dated metadata from matching. Added a regression fixture for rejected BOSIET credentials.

Assignment compliance now ignores rejected future-dated medical and survival certificates instead of treating their dates as usable. Added regression coverage for rejected credentials.

Periodic compliance alerts and expiring-certification listings now exclude rejected credentials, preventing discarded certificates from generating operational renewal alerts.

Staff-created crew responses now pass through field-tier redaction, preventing C3 fields submitted during draft creation from being returned to staff callers. Added a GraphQL regression test for date-of-birth and passport redaction.

Login rate-limit keys now canonicalize surrounding email whitespace, so trivial formatting variants cannot bypass the per-email brute-force bucket.

Per-contractor compliance totals now exclude rejected certification records, keeping rejected evidence out of valid, expiry, and pending counts as well as alert feeds.

Assignment compliance now excludes rejected credentials from expired and expiring survival-certificate branches too, so discarded evidence cannot create a false critical failure.

The roster pagination callback now fails closed when authentication has been cleared, preventing a stale `loadMore` handler from fetching private profiles after logout or session expiry.

Certificate-document rejection, deletion, relinking, Dropbox deletion, and Dropbox revision invalidation now reconcile denormalized medical expiry fields, preventing discarded medical evidence from remaining effective through the contractor profile projection.

Replacement CV approval now removes only CV-sourced certification and work-history projections, preserving manually entered and independently verified records. Added regression coverage for the preservation boundary.

CV replacement also now reconciles the contractor medical projection when a prior CV-sourced medical certification is removed.

CV replacement now preserves operator-entered email and phone values, which the deterministic CV parser intentionally does not extract.

Replacement CV approval now preserves the existing contractor name when the reviewed extraction omits `full_name`, while still applying an explicitly supplied replacement name.

Path-component validation now uses a full-string match, rejecting trailing newline/control-character variants that could bypass the previous `$`-anchored regex check.

The consultant keyword-search access layer now redacts restricted fields from stale Meilisearch hits, matching the REST search boundary even if an old index contains C2/C3 data.

Semantic document search now returns only the Qdrant ranking score and PostgreSQL-authoritative document metadata, preventing stale payloads or embedded document text from crossing the access-layer boundary. Added regression coverage for stale sensitive Qdrant fields.

Natural-language compliance searches now cap the matching profile set at 100 before building the response prompt, preventing an unbounded database result and oversized LLM request from a broad staff query.

General document embeddings now use only classification and file-name metadata, excluding C3 extracted evidence from the Qdrant projection. Added a regression test so future semantic-indexing changes cannot reintroduce raw extracted data into the general embedding path.

Rejecting a replacement CV now removes any existing Qdrant point for that document, preventing a prior approved embedding from remaining searchable after the replacement is rejected while the contractor profile stays published.

Document extraction failures and staff-rejected document reviews now remove any existing semantic document projection, preventing a previously searchable revision from surviving a transition to `failed` or `rejected`.

The synchronous Dropbox/Celery extraction path now removes stale semantic projections on rejected or failed transitions too, using a synchronous Qdrant deletion method that does not start a nested event loop.

Source-of-truth search filtering now preserves Meilisearch's estimated total instead of replacing it with the filtered page length, preventing stale projection cleanup from breaking result pagination.

REST search now drops malformed non-object Meilisearch hits before inspecting fields, preventing corrupted projection records from turning a search request into a server error.

Consultant keyword search now applies the same malformed-hit filtering and preserves the provider result estimate, preventing GraphQL keyword searches from crashing or under-reporting pagination after stale-hit cleanup.

Vessel position parsing now rejects non-finite numeric values from the provider, preventing `NaN` and infinity coordinates or navigation readings from reaching API responses and calculations.

Reprocessing a certificate document now clears fields removed from the latest extraction and resets manual verification when evidence changes, preventing stale expiry dates or verification decisions from surviving corrected document data.

Certification status and verification mutations now lock the target row before updating it, preventing concurrent administrator actions from losing one another's state changes.

Manually added medical certifications now reconcile the contractor-level medical expiry, status, and provider projection immediately instead of leaving compliance data stale until document extraction runs.

Malformed extraction confidence values are now treated as review-required and are excluded from persisted aggregate confidence, preventing `NaN`, infinity, boolean, or out-of-range model output from bypassing human review.

LLM extraction now treats non-object JSON payloads and non-object confidence values as review-required instead of crashing or silently accepting malformed output.

Recent-search history now validates persisted localStorage data before rendering, preventing corrupted or manually edited storage values from crashing the search component.

Vessel summary normalization now rejects non-finite length and width values as well as position readings, preventing malformed provider dimensions from entering API responses.

Non-string LLM response bodies now fail into manual review instead of raising a parsing `TypeError` in the extraction worker.

Contractor document pagination now has deterministic upload-time and ID ordering, preventing unstable `LIMIT/OFFSET` pages from skipping or duplicating documents.

All remaining paginated certification, assignment, project, review, report, and pending-document queries now use deterministic secondary-ID ordering, preventing timestamp ties from moving records between pages.

Assignment GraphQL responses now redact the admin-only agreed day rate for staff, and staff cannot submit a commercial rate when creating an assignment.

Compliance reports now exclude certifications with rejected lifecycle or verification status, keeping discarded evidence out of report counts and rows as well as alerts and assignment checks.

Profile and assignment service authorization now fails closed when a non-admin caller has no actor ID, preventing unowned drafts from matching a null identity and bypassing assignment scoping.

Natural-language compliance search now excludes rejected verification records and only reports certifications whose lifecycle status is actually expired or expiring, preventing false compliance issues and discarded evidence from appearing in results.

Manual REST document uploads are now administrator-only for ordinary documents, while staff retain only their own CV draft submission workflow; staff continue to use contractor document requests for other document collection.

Assignment creation and status-update mutation responses now apply the same admin-only commercial-rate redaction as assignment queries, preventing staff from receiving agreed day rates in mutation payloads.

Asynchronous Qdrant indexing now runs its synchronous embedding and client calls off the event loop, preventing semantic indexing from blocking unrelated API requests.

GraphQL depth, complexity, and production introspection guards now fail closed with a generic validation error if their AST inspection encounters an unexpected failure, rather than silently bypassing the security boundary.

Logout now removes the authenticated user’s per-user shortlist from local storage as well as the legacy global key, preventing private bookmarks from reappearing on a later session.

Shortlist rendering now waits for the active user’s storage namespace to load before exposing bookmarked profiles, preventing a transient cross-user bookmark mix-up during account changes.

Updating a medical certification lifecycle status now recomputes the contractor medical projection, so rejecting or replacing evidence cannot leave stale medical expiry or fitness values on the profile.

Vessel position normalization now preserves valid zero-valued latitude, longitude, speed, course, and heading readings instead of treating them as missing during fallback selection. Added a regression test for equatorial and stationary positions.

Dropbox token refresh now validates the provider-supplied expiry value and falls back safely when it is malformed, preventing a successful OAuth response from crashing refresh handling.

The admin Dropbox download endpoint now streams the requested file bytes with a safe `Content-Disposition` header instead of returning only a status and byte count.

The general document download route now uses the asynchronous storage helper, fixing uncached Dropbox downloads that previously attempted to start a nested event loop and failed before retrieving the file.

GraphQL depth and complexity validation now checks every operation in a document, preventing a cheap first operation from bypassing limits when a caller selects a deeper later operation by `operationName`. Added focused validation tests.

GraphQL depth and complexity accounting now follows fragment spreads with cycle protection, preventing deeply nested fields hidden in reusable fragments from bypassing the query guard.

Production GraphQL introspection blocking now follows fragment spreads as well, preventing `__schema` or `__type` fields hidden in reusable fragments from bypassing the restriction.

CV approval now queues semantic indexing after the document becomes searchable, preventing approved CVs from remaining absent from Qdrant when semantic search is enabled.

Manual extraction confirmation now queues semantic indexing when the document enters the searchable `extracted` state, covering the administrator confirmation path as well as background extraction.

Staff document search now restricts Meilisearch to C2 metadata fields before results are returned, preventing C3 extracted evidence from acting as a hidden search/discovery side channel. Administrators retain evidence search.

Medical profile projections now recompute from all current non-rejected medical certificates when certificate evidence is reprocessed, preventing an old later expiry from surviving a corrected earlier expiry.

Explicit rejection of a medical certification now also reconciles the contractor-level medical projection, preventing rejected-but-still-linked evidence from remaining effective.

Certification search, compliance alerts, compliance totals, and assignment checks now also exclude rows whose verification status is rejected, even if a stale lifecycle status still says `valid` or `expiring_soon`.

Natural-language certification searches now exclude explicitly rejected evidence from ordinary name, family, keyword, and validity matching, preventing rejected credentials from acting as qualifications.

Project collection queries now enforce a maximum page size and offset, preventing an unbounded `projects` request from loading the entire project table into one GraphQL response.

Frontend dossier documents and AI summaries now clear on logout and ignore
late responses from the prior session. Shortlists are also namespaced by user
ID, preventing one account's saved contractor IDs from appearing in another
account's workspace.

Document search now rechecks an optional contractor filter against PostgreSQL,
so a stale Meilisearch assignment cannot return a document under its former
contractor after the document is relinked.

Admin document relinking now locks the document, detaches certificate evidence
from the former contractor, and invalidates both contractors' compliance and
summary caches before rebuilding any certificate projection for the new owner.

Direct availability updates now invalidate cached summaries and refresh the
approved contractor's Meilisearch projection, keeping availability consistent
across roster, summary, and keyword-search surfaces.

Upload validation now rejects zero-byte files before storage, rather than
accepting an empty file whose extension happened to be allowed.

CV approval now invalidates the contractor's compliance cache as well as the
summary cache, so newly imported certification evidence cannot remain hidden
behind a stale aggregate.

Document extraction now treats only `pending` and `failed` rows as runnable;
duplicate queued tasks cannot reprocess a row already being processed or a
row awaiting review, avoiding duplicate extraction and certification writes.

Workers now compare the Dropbox revision captured at extraction start with the
locked row before committing results, so an old worker cannot overwrite a newer
file revision.

Manual document reprocessing now clears superseded extracted text, structured
data, and confidence before returning the row to `pending`, preventing stale
evidence from being displayed during the new run.

Rejecting an incoming document now detaches any linked certification evidence
and invalidates compliance and summary caches, preventing rejected documents
from continuing to certify a contractor.

Relinking also removes and refreshes the document's semantic-search point when
enabled, preventing Qdrant metadata from retaining the former contractor ID.

Review decisions now reload the contractor after locking the document, keeping
ownership authorization and cache invalidation consistent if an admin relinks
the document concurrently.

Document-search hits are now rehydrated from PostgreSQL before response
redaction, preventing stale Meilisearch filenames, ownership, statuses, or
administrator-visible extracted evidence from crossing the API boundary.

Enabled semantic-search results now receive the same PostgreSQL rehydration,
so a stale Qdrant payload cannot report a former contractor or classification.

Logout/public-shell transitions now also clear the legacy unscoped shortlist
key, completing the migration to account-scoped saved contractor IDs.

Session expiry now clears the in-memory roster and the full private workspace,
including filters, selection, dialogs, and URL state, matching explicit logout
privacy behavior.

The periodic synchronous compliance task now invalidates profile-summary caches
alongside compliance caches when certification expiry statuses transition.

That task also now keeps the crew-level medical status vocabulary valid: an
expiring certificate remains `fit`, while an actually expired medical
certificate becomes `expired`.

An incoming document approved before its extraction task completes is now still
processed when it has no evidence yet; the worker preserves the human approval
after extraction instead of silently skipping the certificate projection.

Generic document-review routes now reject CV decisions and preserve the
document's awaiting-review state, so CVs can only be resolved through the
structured administrator review workflow.

The async extraction path now creates the durable `CVReview` row when a CV
arrives without one, preventing documents from becoming permanently stuck in
`awaiting_review` without an administrator review target.

Async and Celery extraction failure handlers now lock and recheck terminal
document state before writing `failed`, so a late provider error cannot
overwrite a concurrent administrator approval or rejection.

Document-to-contractor matching now validates the target contractor before
changing the foreign key, returning a domain-level not-found error instead of
an integrity failure for invalid IDs.

Dropbox revision processing now clears superseded extraction evidence and
unlinks certificate projections before reprocessing the replacement binary.
The matching document row is locked while handling a revision so duplicate
webhook deliveries cannot enqueue competing re-extractions.
Revised CVs also reopen terminal `CVReview` records, preventing the worker
from incorrectly reusing the old approval or rejection.

Crew summaries now revalidate publication status in PostgreSQL before reading
the cache, preventing stale cached summaries from surviving profile revocation
when cache invalidation fails.

Performance reports now exclude pending, failed, and rejected document
extractions, so report counts and LLM inputs contain only searchable terminal
evidence.

Automatically detected CVs from contractor upload links now also resolve their
incoming review item as rejected, preventing an unresolvable queue entry from
remaining unread after the CV workflow correctly refuses it.

Certification status edits now invalidate compliance caches, and staff
expiring-certification queries are scoped to approved contractors or drafts
owned by the requesting staff member.

Certification mutations and expiry updates now also invalidate cached profile
summaries, keeping qualification and certification statements synchronized
with the source of truth.

Certification creation now validates the target contractor before inserting,
avoiding a raw foreign-key failure for invalid IDs.

Assignment status transitions now lock the contractor before overlap checks,
closing the concurrent proposed-to-active race that could create overlapping
active assignments.

Project crew-assignment mutations now lock the project row, preventing
concurrent administrator edits from silently losing one assignment list.

Assignment-driven availability changes now invalidate profile summaries and
refresh the Meilisearch profile projection after the PostgreSQL commit,
preventing stale availability results in derived search state.

Document deletion now removes local cache files only after the metadata
transaction commits, preventing a failed database commit from orphaning a
live document record without its content.

The Dropbox deletion webhook now follows the same post-commit local cleanup
ordering, preventing failed webhook transactions from leaving stale extracted
records after cache removal.

Document deletion now invalidates affected compliance and profile-summary
caches when certificate evidence is unlinked, preventing deleted evidence from
remaining visible through cached status or summaries.

Frontend session hydration now ignores an in-flight pre-login `ME` response,
reconciles after login, clears Apollo data on session expiry, and completes
local logout even if cache cleanup fails.

Project assignment mutations now reject unknown or duplicate crew IDs instead
of storing dangling JSON references. Document upload boundaries keep invalid
category and storage errors on safe client-facing messages.

GraphQL JSON and date validation errors now omit parser exception text from
client responses while retaining the structured bad-input code.

The search bar now treats recent query history as authenticated workspace
state: it is not loaded or retained in the public shell after logout, and a
regression test covers the persisted-history boundary.

Natural-language search now rejects non-finite and implausible experience
values from the untrusted intent-classifier payload before they reach SQL
numeric conversion.

Admin-confirmed-distinct CV submissions now remain drafts just like ordinary
CV submissions; the duplicate override no longer bypasses publication gating.

Campaign assignment status transitions now recalculate availability whenever
an assignment leaves an active state, including an active-to-proposed revert.
Assignment creation and status changes also lock the affected rows while
checking overlaps, preventing concurrent updates from bypassing conflict or
availability invariants on PostgreSQL.

Staff project-readiness reports now filter assigned crew IDs through the
publication/ownership scope instead of returning another staff member's draft
identifiers.

That report scope also now fails closed when no staff actor ID is available,
so orphaned drafts with a null submitter are not treated as visible.

Administrator document search continues to include approved/extracted
unassigned documents, while non-admin searches still require an owned crew
record; the source-of-truth recheck no longer drops legitimate orphaned
Dropbox intake records.

Async extraction now stops when the authoritative document disappears and
uses the final locked crew/classification values for certificate linking,
preventing stale worker state from mutating a deleted or relinked document.
Certificate linking also now requires the authoritative document to exist and
belong to the target crew.

The legacy metadata-only GraphQL `uploadDocument` mutation now fails clearly
instead of creating an unbacked pending row; binary uploads use the validated
multipart REST workflow.

General GraphQL crew search no longer matches email or work-history fields
before response redaction, closing a T1 private-data discovery side channel.

All document upload routes now normalize a missing multipart filename to a safe
fallback before persisting metadata, avoiding a nullable filename database
failure.

## 2026-09-12 — Hidden-Bug Pass 9 (Codex)

Document search now revalidates every Meilisearch hit against PostgreSQL for
all roles, excluding deleted, pending, rejected, and stale crew-scope records.
Keyword crew search also corrects its reported count when stale projection
hits are removed. Added regressions for admin document-search leakage and
staff C3 redaction with authoritative document rows.

## 2026-09-12 — Hidden-Bug Pass 8 (Codex)

Closed additional extraction and privacy boundaries: auto-classified CVs now
enter review or are rejected by upload source, extraction workers cannot race
human terminal decisions, and task/request failures no longer return private
provider or storage details. Semantic and keyword search projections are
rechecked against PostgreSQL publication state.

The test harness now completes collection without import-time SQLite setup
deadlock, but runtime async SQLite operations still stall in this environment.
Ruff, compilation, and diff checks pass; mypy is limited by missing Celery and
psycopg2 stubs in the environment.

## 2026-09-11 — Hidden-Bug Pass 7 (Codex)

Fixed the authenticated AI profile-summary path including private contact,
identity, medical, work-history, and raw document-extraction data in the LLM
prompt. Summaries now receive only C1-safe profile context and document
exclusion text, with a regression test for sensitive-value exclusion.

Also fixed logout leaving the backwards-compatible `session` cookie alive;
logout now expires both cookie names accepted by authentication.

Natural-language crew search was also returning email addresses and
work-history aggregates to T1 users, and could match restricted internal notes
or work-history rows as a side channel. Its result and matching fields now
use only the C1 profile allow-list.

T1 natural-language compliance intents are now refused before restricted
certification details reach the query response, while staff/admin callers keep
the operational compliance path.

Staff CV-review listings now redact proposed/approved extraction payloads and
review notes; administrators retain the full review evidence required for
approval.

API-key agent uploads now mark extraction as failed when the broker cannot
accept the task, instead of leaving an unobservable document stuck pending.

General profile roster/detail/search responses no longer enumerate each
account's role. The caller sees their own role via `me` (and admins retain
bulk role visibility for staff management).

Incoming document review resolution now locks the review row before checking
its status, preventing concurrent approve/reject requests from overwriting
each other.

Certificate extraction now links data to canonical certifications only after
automatic review passes; low-confidence results remain document evidence until
an administrator confirms them. Manual certificate confirmation and matching
now update the same certification projection, and explicit CV reprocessing
reopens terminal reviews instead of silently returning the old decision.

Unclassified image uploads now persist the certificate classification used by
vision extraction, and concurrent certificate retries serialize their
document-to-certification upsert on the contractor row.

Deleting a document, including when Dropbox reports it deleted externally,
now unlinks certificate evidence and resets its verification state; enabled
semantic indexes also receive the document deletion.

Deleting an entire contractor now removes each linked semantic document vector
as well, preventing deleted profiles from remaining in the derived index.

Upload handlers now clean up local and Dropbox files if metadata persistence
fails after storage succeeds, preventing untracked files from accumulating.

Uploads without an explicit classification now preserve the unset value so the
extraction worker can classify the document instead of permanently treating it
as `other`.

Semantic Qdrant results now undergo a PostgreSQL publication and extraction
status check before they leave the access layer, preventing stale vectors from
exposing deleted, rejected, draft, or review-gated documents.

The access-layer Meilisearch keyword mode now applies the same PostgreSQL
approved-profile check instead of trusting a stale search projection.

Async document extraction now normalizes classification aliases before pipeline
selection, keeping `resume`/`cert` values on the deterministic CV or canonical
certificate paths rather than sending them through the wrong extractor.

Extraction workers and human review now lock and recheck the document terminal
state, so a late worker cannot overwrite an administrator's approve/reject
decision or create a certification after rejection.

Auto-classified CVs now always create a staged `CVReview`; agent and contractor
upload sources are rejected if their content is identified as a CV, preventing
classification omission from bypassing the staff-only CV workflow.

Extraction task failures now return a generic error string; storage paths and
source filenames remain observable only through safe typed logging.

Request and background-task error results now likewise expose only generic
messages and exception types, preventing provider, path, or input details from
crossing logging/task-result boundaries.

REST crew search now strips legacy index fields such as internal notes, role,
and submitter identifiers in addition to contact and compliance fields.

REST crew search also revalidates returned IDs against PostgreSQL publication
state, preventing stale Meilisearch approval flags from exposing withdrawn
profiles.

**Why:** Prevent review-gated compliance data from affecting certification and
medical fields, and make administrator reprocessing perform a real extraction.

**Follow-up:** Focused pytest execution still hangs during test collection in
this environment; formatting, lint, compilation, and diff checks pass.

## 2026-09-11 — Hidden-Bug Pass 6 (Codex)

Fixed the non-staff operations workspace exposing the vessel search and
mounting staff-only vessel-roster queries. The vessel tab now renders only for
staff/admin users, and non-staff deep links are normalized to contractor
search. Added an E2E regression assertion covering non-staff vessel-tab
visibility.

## 2026-09-11 — Hidden-Bug Pass 4 (Codex)

Fixed two retry/visibility defects found during audit: idempotent upload
recovery now catches PostgreSQL unique-key errors raised by the parent flush,
avoiding 500 responses and stored-file leaks during concurrent retries; staff
document search is scoped from PostgreSQL to approved contractors and the
requesting staff member's drafts, with defense-in-depth filtering of stale
Meilisearch hits.

**Why:** Close concurrent upload leakage and unpublished-draft document
discovery through the search projection.

**Follow-up:** The backend pytest process still hangs during test collection in
this environment, so the new concurrent retry path remains statically checked
but not runtime-verified here.

## 2026-09-11 — Hidden-Bug Pass 5 (Codex)

Restricted GraphQL campaign assignment and vessel roster queries to staff and
administrators. These queries return operational assignment data including
dates, roles, notes, rates, and contractor names and were previously available
to every authenticated user.

**Why:** Enforce the C2 authorization boundary documented for operational
assignment data.

**Follow-up:** Runtime pytest remains blocked during SQLite connection setup;
the authorization regression is statically checked but not executed here.

The assignment queries also now scope non-admin staff to approved contractors
or drafts they submitted; this prevents the staff role from becoming a bypass
around draft ownership.

Assignment compliance evaluation is now admin-only because its response
contains medical-expiry details classified as C3.

Availability, compliance, and performance report data now applies the same
PostgreSQL publication/ownership scope before LLM generation or fallback
serialization, preventing T1 users and staff from receiving unpublished or
unowned draft records.

Staff assignment creation and status updates now enforce the same draft
ownership check, preventing cross-owner operational mutations.

Search rebuilds now reconcile the Meilisearch crew projection against all
authoritative PostgreSQL IDs, removing deleted records while treating an
unavailable index listing as a failed reconciliation rather than an empty
index.

Semantic embedding dispatch now accepts only `extracted`/`approved` documents,
and the worker rechecks the persisted status before indexing, preventing failed
or review-gated documents from entering Qdrant.

Extraction task results marked failed now raise into Celery retry handling
(except for a genuinely missing document), instead of being acknowledged as a
successful task after the processor recorded the failure.

The embedding worker also rechecks the linked contractor publication status,
so delayed tasks cannot index documents attached to unpublished drafts.

## 2026-09-11 — PostgreSQL Verification Fixes (Muse Spark)

Ran the full migration chain (000→017, downgrade, re-upgrade) and the
backend suite against real PostgreSQL via compose. Found and fixed three
PG-only bugs SQLite can never catch: 017 needed `autocommit_block()` —
`transaction_per_migration` alone still wraps each revision, so
`CREATE INDEX CONCURRENTLY` failed live; Document+review single-flush
inserts misorder without an ORM relationship (FK-only graphs), fixed with
explicit parent-first `flush()` in staff/contractor uploads and four review
workflow setups; `reviewed_at` wrote tz-aware datetimes into
`TIMESTAMP WITHOUT TIME ZONE` (asyncpg DataError), now naive UTC like
`document_requests`. Test harness uses `NullPool` for postgres URLs so
per-test event loops don't share loop-bound connections. Full suite:
247 passed on PG and sqlite. Scratch databases dropped; compose `db` left
running.

**Why:** Close the SQLite/PG semantic gap the engineering standards warn
about; prove the deploy-time migration path for real.

**Follow-up:** CI still sqlite-only — promote a PG migration + suite job
per the standards before the next schema change.

## 2026-09-11 — Ops & Migration Fixes (Muse Spark)

Closed four remaining pass-3 items: 017 builds GIN indexes `CONCURRENTLY`
with `IF NOT EXISTS` (env.py runs each revision in its own transaction so
this is legal; single head intact); backups default to `/app/data/backups`
on the persisted volume with portable nullglob retention (no `xargs -r`,
no empty-glob failure) and prod keeps a single 8000 mapping — verified via
merged compose config; `seed_100` refuses `APP_ENV=production` like
`seeds.py`; nginx locations repeat security headers (inheritance wipe
fixed), `/health` uses `default_type`, and the CSP `sed` escapes the origin.

**Why:** Deploy without write locks, backups that survive recreation,
no fake crew in prod, security headers on every response.

**Follow-up:** `CREATE EXTENSION pg_trgm` still needs a privileged role on
managed PG; Gemini CSP host mismatch left as-is (unverified).

## 2026-09-11 — Pass-3 Medium Fixes (Muse Spark)

Hardened four backend mediums: download `Content-Disposition` built via
RFC 6266/5987 helper (sanitized `filename` + `filename*`); Dropbox webhook
recovers `crew_member_id` from `/hydenlyne/<crew_id>/...` paths so rows join
the staff review queue (truly foreign files stay admin-visible via
`pending_reviews`); agent upload accepts an `idempotency_key` with staff-path
409 semantics and stores it as `upload_key` (+ tests); malformed GraphQL
`filters`/`data`/`approved_data`/date strings map to `BAD_USER_INPUT` via
`_parse_json_object`/`_parse_date` helpers instead of 500s (+ test).

**Why:** Close header injection, orphan invisibility, retry duplication, and
unactionable 500s on client input errors.

**Follow-up:** Residual webhook orphans for non-app paths, 017
CONCURRENTLY, backup durability still open.

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
## 2026-09-12 — Hidden-Bug Pass 53 (Codex)

- Continued the derived-state audit across review decisions and document
  lifecycle transitions. Provider methods that return `False` now enqueue
  bounded projection cleanup or search reconciliation, covering rejected CVs,
  recovered document reviews, repeated review actions, reprocessing, and
  terminal extraction paths. This prevents a provider outage from leaving
  stale vectors or search documents after PostgreSQL has already committed the
  source decision.
- Follow-up: run the targeted review/document lifecycle tests when the async
  database fixture is available; the existing fixture can hang during SQLite
  connection setup in this workspace.
## 2026-09-12 — Hidden-Bug Pass 54 (Codex)

- Hardened document relinking against a failed Qdrant delete after the source
  update commits. Searchable documents now receive an embedding retry, while
  unpublished documents receive projection cleanup, preventing either stale
  vectors or accidental cleanup of a newly valid vector.
## 2026-09-12 — Hidden-Bug Pass 55 (Codex)

- Added bounded certificate-projection reconciliation for post-commit linking
  failures. Manual confirmation, document relinking, and synchronous extraction
  now preserve the committed document outcome while enqueueing repair work when
  certification linking cannot complete, instead of returning an error with no
  durable follow-up.
## 2026-09-12 — Hidden-Bug Pass 56 (Codex)

- Prevented asynchronous extraction from converting a successfully committed
  certificate document to `failed` when certificate linking fails afterward.
  The committed extraction remains authoritative and queues the same bounded
  certificate-projection repair used by manual confirmation and relinking.
## 2026-09-12 — Hidden-Bug Pass 57 (Codex)

- Added bounded local-cache cleanup retries for document, Dropbox, and crew
  deletion. Filesystem failures after a successful PostgreSQL deletion are now
  caught and queued instead of surfacing as an unexplained 500 while leaving
  cached document bytes behind.
## 2026-09-12 — Hidden-Bug Pass 58 (Codex)

- Dropbox revision processing now waits for stable local-cache removal before
  extraction. Filesystem cleanup failures enqueue a retry that resumes the
  extraction only after the old cached bytes are gone, preventing stale
  revisions from being parsed or leaving a committed revision permanently
  pending.
## 2026-09-12 — Hidden-Bug Pass 59 (Codex)

- Failed-upload cleanup now catches local filesystem errors and queues cache
  removal instead of masking the original upload failure. This covers both
  local uploads and Dropbox uploads that leave a local cache copy.

## 2026-09-12 — Hidden-Bug Pass 85 (Codex)

- Hardened Dropbox reads, downloads, and deletes to accept only validated paths
  under the managed `/hydenlyne/` hierarchy. A malformed persisted path can no
  longer be forwarded to Dropbox as an arbitrary remote object path.

## 2026-09-12 — Hidden-Bug Pass 86 (Codex)

- Dropbox webhook ingestion now ignores supported files outside the managed
  `/hydenlyne/` root, preventing unrelated account files from becoming
  crew-less document records. Admin downloads also reject malformed persisted
  Dropbox paths before making an upstream request.

## 2026-09-12 — Hidden-Bug Pass 87 (Codex)

- Validated Dropbox webhook file metadata before database binding, rejecting
  oversized, negative, non-integer, overlong, or malformed revision values
  instead of allowing provider payloads to fail ingestion at the ORM layer.

## 2026-09-12 — Hidden-Bug Pass 88 (Codex)

- Compliance reports now count only verified expired or expiring certificates,
  matching assignment readiness and profile compliance rules. Unverified
  evidence can no longer inflate non-compliance totals.

## 2026-09-12 — Hidden-Bug Pass 89 (Codex)

- Document extraction failure handling now treats Meilisearch/Qdrant cleanup as
  derived-state work. Provider exceptions are logged and queued for retry
  instead of escaping after PostgreSQL has already committed `failed`.

## 2026-09-12 — Hidden-Bug Pass 90 (Codex)

- Orphaned-upload cleanup now attempts local-cache removal even when Dropbox
  deletion is unconfirmed, then retries the remote cleanup. A transient local
  failure can no longer permanently strand the cache behind a later remote
  “not found” response.

## 2026-09-12 — Hidden-Bug Pass 91 (Codex)

- Synchronous worker extraction now isolates Qdrant cleanup exceptions after a
  committed failed or rejected document state, queueing projection repair
  instead of causing the Celery task to fail again.

## 2026-09-12 — Hidden-Bug Pass 92 (Codex)

- Synchronous extraction now rolls back a failed SQLAlchemy transaction before
  querying and marking the document failed. Commit errors can no longer leave
  a document stuck in `processing` behind a `PendingRollbackError`.

## 2026-09-12 — Hidden-Bug Pass 93 (Codex)

- CV approval and rejection now isolate post-commit profile, keyword-search,
  and semantic projection failures. Provider outages queue bounded repair work
  instead of turning a committed review decision into a misleading API error.

## 2026-09-12 — Hidden-Bug Pass 94 (Codex)

- Vessel identifier validation no longer depends on an assertion or a blanket
  type-ignore for runtime narrowing; invalid values now follow the explicit
  validation error path in optimized Python builds too.

## 2026-09-12 — Hidden-Bug Pass 95 (Codex)

- Natural-language crew-query filters now escape SQL `LIKE` wildcards from
  classifier output and use literal substring matching. Malformed or
  adversarial `%`, `_`, and backslash values can no longer broaden profile,
  certification, or name searches.

## 2026-09-12 — Hidden-Bug Pass 96 (Codex)

- Applied the same literal `LIKE` matching protection to the ordinary
  roster-search service, closing the parallel wildcard-broadening path used by
  the GraphQL crew search.

## 2026-09-12 — Hidden-Bug Pass 97 (Codex)

- Dropbox deletion webhook processing now ignores paths outside the managed
  `/hydenlyne/` hierarchy, matching ingestion and provider-operation scope so
  unmanaged deletion events cannot remove persisted document rows.

## 2026-09-12 — Hidden-Bug Pass 98 (Codex)

- Campaign assignment inputs now enforce the database-backed limits for role,
  vessel name, and notes at the service boundary. Oversized or malformed
  GraphQL values no longer reach persistence as avoidable database failures.

## 2026-09-12 — Hidden-Bug Pass 99 (Codex)

- `APP_ENV` is now normalized case-insensitively and restricted to the known
  environment modes. Values such as `Production` can no longer bypass
  production secret, cookie, CORS, and health-endpoint controls.

## 2026-09-12 — Hidden-Bug Pass 100 (Codex)

- Document upload-request expiry validation now lives in the request service,
  not only the REST handler. All callers must use a 1–30 day lifetime, so
  invalid or effectively unbounded bearer links cannot be created internally.

## 2026-09-12 — Hidden-Bug Pass 101 (Codex)

- Login and middleware rate-limit counters now repair a missing Redis expiry on
  later increments. A transient failure after `INCR` can no longer turn a
  fixed-window counter into a permanent lockout, while healthy TTLs are left
  unchanged.

## 2026-09-12 — Hidden-Bug Pass 102 (Codex)

- REST, keyword, and natural-language crew searches now trim queries, reject
  whitespace-only input, and cap provider-bound query text at 500 characters.
  Unbounded or blank requests can no longer amplify Meilisearch or Ollama work
  through the search APIs.

## 2026-09-12 — Hidden-Bug Pass 103 (Codex)

- Report compliance filters now cap status lists at 20 values and individual
  values at 100 characters. Unbounded GraphQL filter input can no longer turn
  into an unnecessarily large SQL `IN` clause.

## 2026-09-12 — Hidden-Bug Pass 104 (Codex)

- Certificate projection now validates extracted scalar text against the
  database column bounds. Malformed certificate types no longer reach
  persistence, and oversized optional numbers or issuers are ignored instead
  of repeatedly failing the extraction projection.

## 2026-09-12 — Hidden-Bug Pass 105 (Codex)

- CV extraction now validates model-produced profile and work-history text at
  the persistence boundary. Non-scalar values and strings exceeding their
  database column limits are ignored, preventing malformed CV output from
  aborting otherwise valid profile imports.

## 2026-09-12 — Hidden-Bug Pass 106 (Codex)

- CV certification processing now ignores malformed collection fields and
  non-mapping date evidence instead of raising while iterating model output.
  Valid certification evidence still follows the existing canonical-alias
  path.

## 2026-09-12 — Hidden-Bug Pass 107 (Codex)

- CV list-valued profile fields now accept only bounded scalar strings and a
  bounded item count. Malformed language, tag, geography, system, and training
  output can no longer be persisted as arbitrary JSON values or expand without
  limit during profile import.

## 2026-09-12 — Hidden-Bug Pass 108 (Codex)

- Document classification now validates the classifier's model output before
  normalization in both async API processing and synchronous worker processing.
  A non-string classification can no longer raise while calling `.strip()` and
  strand extraction; it safely falls back to `other`.

## 2026-09-12 — Hidden-Bug Pass 109 (Codex)

- LLM response parsing now rejects non-standard JSON numbers such as `NaN` and
  `Infinity`. Python can parse those tokens by default, but they are not valid
  PostgreSQL JSON values and could otherwise fail extraction persistence.

## 2026-09-12 — Hidden-Bug Pass 110 (Codex)

- Natural-language crew-query entity filters now reject boolean numeric values
  and bound model-produced strings and lists before SQL construction. A
  malformed classifier response can no longer create oversized filters or
  misleading numeric experience/confidence constraints.

## 2026-09-12 — Hidden-Bug Pass 111 (Codex)

- Extraction confidence is now normalized to a dictionary before persistence,
  certificate linking, and audit/reconciliation tasks. Malformed model
  confidence values can still route a document to review without causing a
  later task or audit transaction to fail.

## 2026-09-12 — Hidden-Bug Pass 112 (Codex)

- Report-model responses now require strict JSON and a scalar text summary
  before entering the GraphQL response. Non-standard numbers and object/list
  summaries can no longer produce serialization errors or invalid report text.

## 2026-09-12 — Hidden-Bug Pass 113 (Codex)

- Dropbox OAuth refresh now converts non-object or invalid-JSON provider
  responses into `DropboxAuthError` and safely handles malformed error bodies.
  Upstream payload shape changes can no longer leak raw `AttributeError` or
  `TypeError` failures through token acquisition.

## 2026-09-12 — Hidden-Bug Pass 114 (Codex)

- GraphQL JSON-string inputs now reject non-standard numeric constants before
  filters or approved document data can reach PostgreSQL JSON persistence.

## 2026-09-12 — Hidden-Bug Pass 115 (Codex)

- Login now rejects oversized email and password inputs before rate-limit key
  construction, database lookup, or password verification. This prevents
  unbounded credential payloads from amplifying Redis, SQL, or password-hash
  work.

## 2026-09-12 — Hidden-Bug Pass 116 (Codex)

- Crew and certification GraphQL DTOs now enforce the database column limits
  for optional profile fields, certification evidence, and list-valued
  languages. Oversized mutation inputs are rejected before ORM persistence
  rather than surfacing as database errors.

## 2026-09-12 — Hidden-Bug Pass 117 (Codex)

- Multipart uploads now reject filenames longer than the `documents.file_name`
  database column before storage or database work begins. The same check is
  enforced inside the upload service so callers cannot bypass the HTTP
  validator.

## 2026-09-12 — Hidden-Bug Pass 118 (Codex)

- Upload storage keys now use a separate 180-character bound while preserving
  the original display filename and extension. Managed Dropbox/local paths can
  no longer overflow the 500-character storage-path column because of a valid
  but path-expanding filename.
### Hidden-Bug Pass 119 (Codex)

- Bounded administrator CV review notes and manual extraction/approval JSON at
  the GraphQL boundary before persistence or downstream processing.
- Added focused input-boundary regressions for oversized JSON and review notes.

- Applied the review-note limit consistently to REST review resolution and the
  CV review service, not only the GraphQL resolver.

### Hidden-Bug Pass 120 (Codex)

- Bounded document audit JSON history to the most recent 500 entries across
  access, extraction, and compliance-transition writers.
- Added a regression test for audit-history truncation.

### Hidden-Bug Pass 121 (Codex)

- Restricted direct crew updates to profile fields; protected role and
  publication workflow state now require their dedicated services.
- Added a regression test for rejecting protected update fields before any DB
  access.

### Hidden-Bug Pass 122 (Codex)

- Enforced the project lifecycle status enum in `ProjectService`, protecting
  direct callers from persisting unsupported statuses.
- Added a regression test for invalid status rejection before database access.

### Hidden-Bug Pass 123 (Codex)

- Fixed certificate reprocessing so unchanged verified evidence retains a
  verified lifecycle status, while changed evidence correctly returns to
  pending verification.
- Added lifecycle regression coverage for verified and unverified extraction
  states.

### Hidden-Bug Pass 124 (Codex)

- Moved certification text-length validation into `CertificationService` so
  direct callers cannot bypass database column limits enforced by GraphQL.
- Added pre-database regression tests for oversized certificate fields.

### Hidden-Bug Pass 125 (Codex)

- Added runtime boolean validation to staff-role changes so direct callers
  cannot treat strings such as `"false"` as truthy promotions.
- Added a regression test for non-boolean role-management input.

### Hidden-Bug Pass 126 (Codex)

- Added runtime validation for crew-creation workflow flags, preventing
  truthy strings from bypassing duplicate detection or draft behavior.
- Added a regression test for the duplicate-control flag.

### Hidden-Bug Pass 127 (Codex)

- Certification service text validation now rejects malformed non-string
  optional values with a controlled input error instead of `TypeError`.
- Added malformed-type regression coverage.

### Hidden-Bug Pass 128 (Codex)

- Enforced canonical availability statuses in crew service update paths so
  direct callers cannot persist values outside the GraphQL lifecycle enum.
- Added unknown-status regression coverage.

### Hidden-Bug Pass 129 (Codex)

- Added consistent GraphQL search-input validation for blank and oversized
  keyword and natural-language queries.
- Invalid search input now returns `BAD_USER_INPUT` before service or provider
  work begins.

### Hidden-Bug Pass 130 (Codex)

- Added document metadata validation inside `DocumentService.create_document`,
  covering filename, type, size, storage path, and uploader length limits.
- Added service-boundary regression coverage for invalid metadata.

- Document service creation now rejects Dropbox-looking paths outside the
  managed `/hydenlyne/` path structure.
- Added a regression test for unmanaged remote storage paths.

### Hidden-Bug Pass 131 (Codex)

- Fixed status-only availability updates leaving stale availability dates.
- `on_assignment` updates now require an availability date, while other
  statuses explicitly clear stale dates when no date is supplied.
- Added consistency regression coverage.

### Hidden-Bug Pass 132 (Codex)

- Made synchronous certificate projection inputs explicitly non-null after
  worker checks, preventing nullable document/crew metadata from reaching the
  nested async linker.
- Targeted mypy now reports no application type errors in the touched worker
  and service modules; only unavailable third-party stubs remain.

### Hidden-Bug Pass 133 (Codex)

- Added service-level length and scalar validation for bounded crew update
  fields, closing the DTO bypass for direct callers.
- Added overflow and blank-name regression coverage.

### Hidden-Bug Pass 134 (Codex)

- Applied bounded crew profile validation to raw-model creation as well as
  updates, preventing direct callers from bypassing DTO limits.

### Hidden-Bug Pass 135 (Codex)

- Added service-level bounds and type checks for raw crew `languages` and
  `tags` lists, matching the GraphQL DTO limits.
- Added oversized-list regression coverage.

### Hidden-Bug Pass 136 (Codex)

- Closed a raw crew-creation omission so `languages` and `tags` now actually
  flow through the service-level list bounds.
- Added creation-path regression coverage.

### Hidden-Bug Pass 137 (Codex)

- Added raw-model validation to `ProjectService.create_project`, covering
  required names, bounded text columns, and lifecycle status.
- Added project creation boundary regression coverage.

### Hidden-Bug Pass 138 (Codex)

- Added project-assignment ID validation before database queries, rejecting
  empty, malformed, or overlong crew IDs.
- Added malformed assignment-list regression coverage.

### Hidden-Bug Pass 139 (Codex)

- Prevented raw crew profile creation from provisioning privileged `staff` or
  `admin` roles; role management remains a dedicated authorization path.
- Added privileged-role creation regression coverage.

### Hidden-Bug Pass 140 (Codex)

- Hardened review-queue creation so request/document ownership, request
  activity, expiry, and duplicate review state are checked before insertion.

### Hidden-Bug Pass 141 (Codex)

- Review-note service boundaries now reject non-string values before applying
  length checks, avoiding uncontrolled `TypeError` failures.
- Added contractor-review and CV-review malformed-note regression coverage.

### Hidden-Bug Pass 142 (Codex)

- Lifecycle status validators now reject non-string values before set-membership
  checks, avoiding uncontrolled `TypeError` failures for direct callers.
- Hardened project and assignment status boundaries.

### Hidden-Bug Pass 143 (Codex)

- Certification lifecycle and verification services now reject non-string
  statuses before membership checks, avoiding uncontrolled type errors.
- Added malformed-status regression coverage.

### Hidden-Bug Pass 144 (Codex)

- Assignment creation now rejects malformed status and day-rate types before
  set-membership or numeric validation can raise uncontrolled type errors.
- Added assignment boundary regression coverage.

### Hidden-Bug Pass 145 (Codex)

- Assignment creation now validates date and vessel-ID types before comparison
  or string normalization, avoiding uncontrolled type errors.
- Added malformed date/IMO regression coverage.

### Hidden-Bug Pass 146 (Codex)

- Moved assignment vessel-ID validation ahead of session creation so malformed
  input cannot trigger database work before being rejected.
- Confirmed the focused boundary suite completes without the known DB hang.
### Hidden-Bug Pass 147 (Codex) — 2026-09-12

- Fixed direct service callers passing non-string assignment vessel filters or
  crew search values: both now fail with explicit `ValueError`s before query
  construction instead of raising `AttributeError` from `.strip()`.
- Added regression coverage in `backend/tests/test_input_boundaries.py`.
- Follow-up: continue auditing service pagination and filter boundaries.

### Hidden-Bug Pass 148 (Codex) — 2026-09-12

- Added a shared pagination boundary validator and applied it to assignment,
  crew, project, document, and report listing methods. Non-integer `limit` or
  `offset` values now produce explicit `ValueError`s instead of leaking
  `TypeError` from `min`/`max` during query setup.
- Preserved the existing clamp behavior for negative and oversized values.
- Added regression coverage in `backend/tests/test_input_boundaries.py`.

### Hidden-Bug Pass 149 (Codex) — 2026-09-12

- Hardened VesselAPI string and numeric boundaries. Malformed direct callers
  now receive controlled `ValueError`s before cache/provider access instead of
  leaking `AttributeError` or `TypeError`.
- Added regression coverage in `backend/tests/test_vessel_api.py`.

### Hidden-Bug Pass 150 (Codex) — 2026-09-12

- Fixed compliance alert and natural-language compliance searches to require
  `verification_status == "verified"`; unverified legacy records with an
  expired/expiring lifecycle status can no longer be reported as verified
  compliance evidence.
- Existing database-backed compliance/search tests cover the verified versus
  unverified distinction; the database fixture remains unavailable for a
  reliable rerun in this environment.

### Hidden-Bug Pass 151 (Codex) — 2026-09-12

- Fixed the synchronous compliance alert projection so unverified certificate
  rows may still receive date-based lifecycle maintenance but cannot publish
  operational alerts or sensitive certificate references.
- Added a direct regression test for the unverified-alert boundary.

### Hidden-Bug Pass 152 (Codex) — 2026-09-12

- Added service-level date invariants for projects and certifications. Reversed
  project windows and certification issue/expiry dates now fail before
  persistence, including for non-GraphQL callers.
- Added regression coverage in `backend/tests/test_input_boundaries.py`.

### Hidden-Bug Pass 153 (Codex) — 2026-09-12

- Tightened date validation to reject `datetime` values for SQL `DATE` fields,
  since Python considers `datetime` a `date` subclass.
- Added direct input validation for certification-expiry listing `days`,
  `limit`, and `offset` values before query construction.

### Hidden-Bug Pass 154 (Codex) — 2026-09-12

- Hardened deterministic CV persistence against reversed extracted date ranges:
  invalid work-history end dates are discarded, and invalid certificate expiry
  dates are ignored instead of creating impossible chronology.

### Hidden-Bug Pass 155 (Codex) — 2026-09-12

- Fixed the CV certification-date extraction path so reversed issue/expiry
  dates are normalized consistently with certificate-document linking.
- Added a focused regression test in `backend/tests/test_cv_extraction.py`.

### Hidden-Bug Pass 156 (Codex) — 2026-09-12

- Fixed document reprocessing so an `approved` row with no prior extraction
  evidence cannot silently publish newly extracted content. It now returns to
  `needs_review`, and processing results report the committed database status,
  including CV rows entering `awaiting_review`.
- Added a database-backed regression case for legacy approved rows without
  extraction evidence.

### Hidden-Bug Pass 165 (Codex) — 2026-09-12

- Fixed the document-search rebuild so deleted PostgreSQL documents are also
  removed from Meilisearch, matching the contractor-search rebuild's stale-ID
  cleanup behavior.
- Added batched document-ID listing/deletion support and failure accounting so
  a transient index read cannot be treated as proof that the index is empty.
- Fixed document projection removal to recheck PostgreSQL after deletion and
  restore a newly approved document that raced the delete operation.
- Added a focused projection-race regression test.

### Hidden-Bug Pass 166 (Codex) — 2026-09-12

- Fixed delayed certificate projection workers applying an old extraction after
  the source document was reprocessed.
- Worker reconciliation now verifies that the document data still matches its
  snapshot before creating or updating certification evidence; manual callers
  retain their existing behavior.

### Hidden-Bug Pass 167 (Codex) — 2026-09-12

- Removed C3 extracted evidence from the general Meilisearch document
  projection and its searchable attributes.
- This closes a privacy boundary where raw extracted data could be persisted
  and searched outside the PostgreSQL/T3 evidence path.

### Hidden-Bug Pass 168 (Codex) — 2026-09-12

- Fixed the document-search contract so `file_type` is configured as a
  searchable Meilisearch attribute when the staff search endpoint requests it.
- Centralized the document searchable-attribute list to prevent configuration
  and API drift.

### Hidden-Bug Pass 169 (Codex) — 2026-09-12

- Fixed public contractor uploads to revalidate the bearer request under a
  database lock immediately before creating the document.
- Expired or revoked links can no longer complete a slow upload after the
  initial token check.

### Hidden-Bug Pass 170 (Codex) — 2026-09-12

- Fixed the same public-upload race for rejected contractors: the final
  persistence transaction now locks and rechecks the linked contractor before
  accepting the upload.

### Hidden-Bug Pass 171 (Codex) — 2026-09-12

- Fixed availability reports treating a JSON `null` filter as the literal
  status `"None"`, which silently produced empty results.
- Added allowlist validation for availability statuses and a boundary regression.

### Hidden-Bug Pass 172 (Codex) — 2026-09-12

- Fixed Dropbox webhook ingestion getting permanently stuck on an expired or
  reset cursor.
- HTTP 409 cursor responses now restart a full account listing, with focused
  recovery coverage.

### Hidden-Bug Pass 173 (Codex) — 2026-09-12

- Fixed Qdrant indexing workers dropping the current vector when a newer
  document revision was detected during the write.
- A changed, still-searchable document now queues a fresh embedding pass after
  stale-vector removal.

### Hidden-Bug Pass 174 (Codex) — 2026-09-12

- Fixed delayed projection cleanup deleting a Qdrant vector after the source
  document had become searchable again.
- Cleanup now rechecks source visibility and requeues the current embedding
  revision after removal.

### Hidden-Bug Pass 175 (Codex) — 2026-09-12

- Fixed idempotent contractor-upload retries bypassing the final bearer-link
  expiry/revocation check.
- Existing upload records are now reused only after the request is reloaded
  and locked as active immediately before retry.

### Hidden-Bug Pass 176 (Codex) — 2026-09-12

- Fixed semantic indexing acknowledging success after a document changed during
  the Qdrant write but the replacement task could not be queued.
- The worker now raises into Celery retry handling after removing the stale
  vector, preventing a permanently missing current embedding.

### Hidden-Bug Pass 177 (Codex) — 2026-09-12

- Fixed natural-language certification search dropping legacy records whose
  lifecycle or verification columns are `NULL`.
- `NULL` is now treated as not explicitly rejected, while valid-only searches
  retain their stricter status and verification requirements.
- Added a regression test; the database-backed test remains unconfirmed because
  the workspace async DB fixture stalled during execution.

### Hidden-Bug Pass 178 (Codex) — 2026-09-12

- Fixed repeated approval of an already-resolved contractor certificate review
  being a no-op when the original certificate projection had failed.
- Repeated approval now queues certificate projection repair and clears the
  affected compliance and summary caches while remaining idempotent.
- Added a regression test; the database-backed test remains unconfirmed because
  the workspace async DB fixture stalled during execution.

### Hidden-Bug Pass 179 (Codex) — 2026-09-12

- Fixed document relinking silently losing its Qdrant projection when the
  replacement embedding task could not be dispatched.
- Relinking now queues projection cleanup/retry after the old vector is removed.

### Hidden-Bug Pass 180 (Codex) — 2026-09-12

- Applied the shared pagination validator to the CV review service itself,
  preventing non-GraphQL callers from bypassing review-list bounds.

### Hidden-Bug Pass 181 (Codex) — 2026-09-12

- Fixed logout cleanup erasing a newer account's token and Apollo cache when a
  login completed while server-side logout was still in flight.
- Logout cleanup is now guarded by the session generation that initiated it.

### Hidden-Bug Pass 182 (Codex) — 2026-09-12

- Fixed recent-search suggestions briefly retaining the previous account's
  in-memory history during authentication transitions.
- Search history is now rendered only after the current session's storage
  scope has been loaded; unreadable storage fails closed to an empty list.

### Hidden-Bug Pass 183 (Codex) — 2026-09-12

- Fixed dependency health checks logging raw exception messages.
- Health failures now log only the exception type, preventing connection
  details or configuration values from entering application logs.

### Hidden-Bug Pass 184 (Codex) — 2026-09-12

- Fixed machine-authenticated document uploads accepting files for a contractor
  whose profile was rejected while the upload was in progress.
- Agent uploads now lock and recheck the contractor before idempotent reuse and
  final document persistence; added a rejected-profile regression test.

### Hidden-Bug Pass 185 (Codex) — 2026-09-12

- Fixed Dropbox integration logs recording raw provider error bodies and
  exception messages.
- Cursor, webhook-processing, audit, and download failures now log only safe
  status or exception-type diagnostics.

### Hidden-Bug Pass 186 (Codex) — 2026-09-12

- Fixed Meilisearch outages being returned as successful empty search results.
- Search API endpoints now return a clear 503 service-unavailable response;
  added regression coverage for crew and document search.

### Hidden-Bug Pass 187 (Codex) — 2026-09-12

- Fixed optional semantic-search failures being returned as empty result sets.
- Qdrant and embedding failures now raise an explicit provider-unavailable
  error, preventing enabled semantic search from silently hiding matches.

### Hidden-Bug Pass 188 (Codex) — 2026-09-12

- Fixed stale document-management callbacks running across account switches.
- Document refresh, delete, and review actions now verify the live session
  scope before mutating or applying results.

### Hidden-Bug Pass 189 (Codex) — 2026-09-12

- Extended live-session guards to CV approval/rejection, staff-role changes,
  incoming-document review actions, and campaign mobilization.
- Stale callbacks from a previous account can no longer submit these mutations
  using a newly logged-in account's credentials.

### Hidden-Bug Pass 190 (Codex) — 2026-09-12

- Fixed the top-level contractor deletion callback lacking a live-session
  guard during account switches.
- Fixed `refetchProfiles` discarding Apollo's completion promise, so deletion
  now waits for the refreshed roster before updating local workspace state.

### Hidden-Bug Pass 191 (Codex) — 2026-09-12

- Fixed the incoming-document alert allowing stale approve/reject callbacks to
  run after an account switch.
- Review actions now verify the live session before submitting and applying
  their result.

### Hidden-Bug Pass 192 (Codex) — 2026-09-12

- Fixed certification verification callbacks lacking a live-session guard.
- Dossier verification now refuses stale callbacks after account switching
  and avoids applying their result to the new session.

### Hidden-Bug Pass 193 (Codex) — 2026-09-12

- Fixed the admin contractor-creation modal allowing CV preview, creation,
  upload, and status-polling callbacks to cross account switches.
- The modal now resets when the authenticated session changes and ignores
  stale completions before applying private contractor state.

### Hidden-Bug Pass 194 (Codex) — 2026-09-12

- Fixed the staff CV upload endpoint trusting authorization from before file
  storage completed.
- The draft contractor is now reloaded and locked before document metadata and
  review rows are committed, preventing uploads to drafts changed or removed
  during a slow transfer.

### Hidden-Bug Pass 195 (Codex) — 2026-09-12

- Fixed compliance aggregation dropping legacy certifications whose nullable
  status fields are NULL because SQL `!=` does not match NULL values.
- Such evidence now remains in totals and is correctly counted as pending
  verification.

### Hidden-Bug Pass 196 (Codex) — 2026-09-12

- Extended NULL-safe certification handling to expiry maintenance and
  expiring-certification alerts, so legacy rows are not skipped by compliance
  workers or staff alerts.

### Hidden-Bug Pass 197 (Codex) — 2026-09-12

- Extended legacy-NULL certification handling to medical projections and
  natural-language search result certification lists.

### Hidden-Bug Pass 198 (Codex) — 2026-09-12

- Fixed document preview and upload dialogs retaining prior-session document
  actions across account changes.
- Preview downloads, reviews, deletes, upload-link creation, uploads, and
  polling now verify the live session before applying effects or notifications.

### Hidden-Bug Pass 199 (Codex) — 2026-09-12

- Fixed the legacy mobilization inquiry modal allowing assignment mutations
  and confirmation state to cross account switches.
- Mobilization submission and booking-brief copying now require the live
  session scope, and the modal closes when that scope changes.

### Hidden-Bug Pass 200 (Codex) — 2026-09-12

- Fixed the incoming-document review alert leaving its polling request
  unhandled when the review queue was unavailable.
- Queue failures now stop the loading state and show an actionable error,
  while stale requests remain unable to replace the current session's queue.

### Hidden-Bug Pass 201 (Codex) — 2026-09-12

- Fixed CV-review downloads, pagination, approval, and rejection callbacks
  continuing to affect a dialog after an account switch or close.
- Applied the same request-version guard to staff-access pagination and role
  changes so old account responses cannot overwrite the active dialog state.

### Hidden-Bug Pass 202 (Codex) — 2026-09-12

- Aligned legacy assignment-compliance fixtures with the verified-evidence
  contract so valid-but-unverified certificates are not treated as deployable.
- The focused assignment suite now passes all 33 tests without weakening the
  production verification rule.

### Hidden-Bug Pass 203 (Codex) — 2026-09-12

- Fixed a time-of-check/time-of-use authorization gap in campaign assignment
  mutations.
- Assignment creation and status changes now recheck draft publication and
  submitter ownership while holding the contractor row lock, before commit.

### Hidden-Bug Pass 204 (Codex) — 2026-09-12

- Fixed strict backend type failures in natural-search certificate filters,
  Redis client boundaries, and Meilisearch search-result handling.
- The affected service and GraphQL modules now pass focused mypy and Ruff
  checks without broad type suppressions.

### Hidden-Bug Pass 205 (Codex) — 2026-09-12

- Fixed vessel-search completion and clear actions crossing authenticated
  session changes.
- Search labels and result readiness now require the live session and request
  version that initiated the operation.

### Hidden-Bug Pass 206 (Codex) — 2026-09-12

- Fixed document-request and review authorization checks reading contractor
  ownership/publication state without row locks.
- Request creation, review creation, and review resolution now serialize the
  relevant contractor/document/request rows before authorization and commit.

### Hidden-Bug Pass 207 (Codex) — 2026-09-12

- Fixed CV approval and rejection racing with contractor profile mutations by
  locking the affected contractor row before changing publication state.
- Added row locks to profile and availability updates so concurrent edits do
  not overwrite one another while derived search and summary projections are
  rebuilt from the committed record.
- Applied the same serialization to staff-role and project-status mutations.

### Hidden-Bug Pass 208 (Codex) — 2026-09-12

- Fixed upload queue-failure recovery overwriting newer document or CV-review
  states after a worker or retry had already started processing.
- Recovery now locks the document row and changes only the still-pending state;
  CV review recovery is likewise limited to the processing state.
- Applied the same protection to Dropbox revision/new-file ingestion and
  administrator-triggered document reprocessing.

### Hidden-Bug Pass 209 (Codex) — 2026-09-12

- Fixed stale extraction workers overwriting a newly requeued document with a
  failure state after an exception.
- Synchronous and service extraction paths now mark failure only when the
  locked row is still in the processing state owned by that worker.

### Hidden-Bug Pass 210 (Codex) — 2026-09-12

- Serialized Dropbox-originated deletion and administrator document deletion
  before certification detachment and metadata removal.
- This prevents deletion from acting on a stale document while revision,
  reprocessing, or review workflows are changing the same row.

### Hidden-Bug Pass 211 (Codex) — 2026-09-12

- Fixed document-upload modal state and async callbacks crossing profile
  changes while the same authenticated session remained active.
- Upload operations now require the initiating session and contractor profile;
  changing either resets the form and prevents stale refreshes or toasts.

### Hidden-Bug Pass 212 (Codex) — 2026-09-12

- Fixed CV preview, upload, and status polling callbacks surviving an
  `Add contractor` modal close/reopen cycle in the same session.
- Closing or superseding the modal now invalidates prior async operations.

### Hidden-Bug Pass 213 (Codex) — 2026-09-12

- Fixed crew deletion racing with project assignment updates and leaving an
  orphaned contractor ID in a project's assignment list.
- Project assignment now locks contractor rows before project rows, matching
  deletion's lock order; deletion locks affected projects before cleanup.

### Hidden-Bug Pass 214 (Codex) — 2026-09-12

- Fixed invalid CV selections leaving the previous file selected while an old
  preview request was still in flight.
- New file-selection attempts now invalidate older previews, and invalid files
  clear the stale CV before submission.

### Hidden-Bug Pass 215 (Codex) — 2026-09-12

- Fixed public document uploads reusing an idempotency key after the user
  selected a different file following a failed or ambiguous upload.
- The key now rotates when file identity changes, while retries of the same
  file remain safely idempotent.

### Hidden-Bug Pass 216 (Codex) — 2026-09-12

- Fixed the public upload page retaining the previous token's ready state and
  selected file when its bearer token changed without unmounting.
- Token changes now clear the file and idempotency key and require fresh link
  validation before another upload can be submitted.

### Hidden-Bug Pass 217 (Codex) — 2026-09-12

- Fixed mobilization mutations updating a newly selected vessel or contractor
  when an earlier request completed after the modal target changed.
- Vessel and contractor mobilization requests now require the initiating
  modal scope, session, and target identity before applying results or errors.

### Hidden-Bug Pass 218 (Codex) — 2026-09-12

- Removed an unnecessary database row lock from the read-only document
  download endpoint.
- Slow storage reads no longer block document deletion, review, revision, or
  reprocessing mutations.

### Hidden-Bug Pass 219 (Codex) — 2026-09-12

- Hardened startup failure logging so admin bootstrap and Meilisearch setup
  errors no longer emit raw exception text that could contain configuration or
  connection details.

### Hidden-Bug Pass 220 (Codex) — 2026-09-12

- Fixed profile and search reads failing when profile-access audit persistence
  is temporarily unavailable.
- Audit writes now remain observable but best-effort, matching document-access
  telemetry policy without exposing storage errors to callers.

### Hidden-Bug Pass 221 (Codex) — 2026-09-12

- Hardened Meilisearch, Redis, Qdrant, and Ollama adapter logs against raw
  exception payloads that could contain connection or request details.
- Provider logs retain safe operation, attempt, and exception-type context.

### Hidden-Bug Pass 222 (Codex) — 2026-09-12

- Hardened remaining backend logs across report generation, natural-language
  search, sync-engine fallback, authentication rate limiting, extraction,
  compliance, vessel integration, and upload paths.
- Raw exception text and connection fallback URLs are no longer emitted;
  diagnostics retain operation and exception-type context without exposing
  queries, document content, credentials, or upstream request details.

### Hidden-Bug Pass 223 (Codex) — 2026-09-12

- Fixed a race in manual availability updates: the profile row is now locked
  before changing availability, serializing the update with assignment status
  transitions that derive availability from active assignments.

### Hidden-Bug Pass 224 (Codex) — 2026-09-12

- Serialized the certification-expiration worker against manual certification
  verification/status changes by locking each selected certification batch.
- This prevents a stale expiration read from overwriting a concurrent human
  decision.

### Hidden-Bug Pass 225 (Codex) — 2026-09-12

- Applied the same row-lock protection to the synchronous Celery compliance
  evaluator, which is the production path for daily expiration updates.
- A daily compliance run can no longer overwrite a concurrent certification
  verification/status mutation from a stale read.

### Hidden-Bug Pass 226 (Codex) — 2026-09-12

- Locked the contractor row while the compliance evaluator recomputes the
  denormalized medical projection, preventing concurrent profile/projection
  writes from losing the evaluator's result.

### Hidden-Bug Pass 227 (Codex) — 2026-09-12

- Removed raw Dropbox error response bodies from upload, download, and delete
  logs; provider payloads can contain paths or other request-specific details.
- Retained the HTTP status needed for operational diagnosis.

### Hidden-Bug Pass 228 (Codex) — 2026-09-12

- Removed traceback-based logging from CV preview and document-review
  recovery paths, plus session-cookie setup failures.
- These traces could include exception messages containing uploaded-content or
  provider details; logs now retain only safe exception types and identifiers.

### Hidden-Bug Pass 229 (Codex) — 2026-09-12

- Health endpoints now return the same generic failure detail in development
  and production.
- Public or accidentally exposed development health checks no longer reveal
  database URLs, Redis credentials, internal hostnames, or provider errors.

### Hidden-Bug Pass 230 (Codex) — 2026-09-12

- Vessel health responses now expose only safe exception types instead of raw
  upstream error text, preventing provider URLs or account details from being
  returned through diagnostics.

### Hidden-Bug Pass 231 (Codex) — 2026-09-12

- Removed names, certificate types, expiry dates, and account emails from
  routine compliance and seed logs.
- Operational diagnostics retain status, safe identifiers, and role/configured
  state without unnecessary personal data.

### Hidden-Bug Pass 232 (Codex) — 2026-09-12

- Locked the contractor row during the staff-upload authorization and
  idempotency check.
- A draft cannot be rejected or reassigned between authorization and retry in
  a way that lets staff reuse an old upload key after access has changed.

### Hidden-Bug Pass 233 (Codex) — 2026-09-12

- Public contractor-upload retries now lock and recheck the linked contractor
  before reusing an idempotent document.
- A link cannot continue accepting or requeueing uploads after the contractor
  has been rejected while the link remains technically active.

### Hidden-Bug Pass 234 (Codex) — 2026-09-12

- Moved synchronous Qdrant health probes off the async event loop.
- A slow or unavailable Qdrant service can no longer stall unrelated API
  requests while health checks are running.

### Hidden-Bug Pass 235 (Codex) — 2026-09-12

- Redacted bearer tokens from contractor upload-link URLs before request paths
  enter application logs.
- Added regression coverage while preserving useful non-sensitive paths for
  diagnostics.

### Hidden-Bug Pass 236 (Codex) — 2026-09-12

- Removed uploaded filenames from routine storage logs because filenames can
  contain names, document subjects, or other unnecessary personal data.

### Hidden-Bug Pass 237 (Codex) — 2026-09-12

- Encoded document IDs in frontend status and delete API paths, matching the
  existing download and review helpers.
- Malformed client-side identifiers can no longer alter the intended route
  structure at this boundary.

## Hidden-Bug Pass 238 (Codex) — 2026-09-12

- Normalized document-search classification aliases (for example `cert`) using
  the same shared vocabulary already used by uploads. Added a regression test
  so valid legacy values no longer fail at the REST search boundary.
- Follow-up: rerun the focused search-filter tests and the normal backend
  static checks before the next audit pass.
- Tool: Codex.

## Hidden-Bug Pass 239 (Codex) — 2026-09-12

- Removed the Dropbox OAuth provider error payload from refresh logs and
  raised exceptions. Provider responses can echo credentials or request data;
  diagnostics now retain only the HTTP status.
- Added regression coverage proving `invalid_grant` is not surfaced.
- Transport failures are likewise reduced to a safe generic message.
- Tool: Codex.

## Hidden-Bug Pass 240 (Codex) — 2026-09-12

- Removed raw VesselAPI 403/4xx response bodies from adapter exceptions.
- Added direct adapter coverage proving provider payloads do not cross the
  error boundary.
- Tool: Codex.

## Hidden-Bug Pass 241 (Codex) — 2026-09-12

- Added `Cache-Control: no-store` to GraphQL and REST API responses so private
  roster, dossier, search, and document metadata cannot remain in browser or
  intermediary caches after logout or account switching.
- Added middleware regression coverage for both API styles.
- Tool: Codex.

## 2026-09-13 — Hidden-Bug Pass 278 (Codex)

Fixed blank vessel filters in assignment listing. A staff vessel-roster query
with an empty IMO previously skipped the filter and returned every assignment
visible to that staff member; the service now applies the same strict vessel
key validation to optional list filters and has a regression test.

## 2026-09-13 — Hidden-Bug Pass 279 (Codex)

Fixed natural-language “current medical” matching to require a verified
certificate with a recorded, non-expired date. Certificates marked valid but
missing an expiry date are now excluded, matching the deployment-compliance
rule, with regression coverage.

## 2026-09-13 — Hidden-Bug Pass 280 (Codex)

Aligned certification status and verification mutations with certificate
ingestion lock order: the contractor row is now locked before the certification
row. This prevents concurrent evidence ingestion and manual verification from
deadlocking on opposite row-lock orders.

## 2026-09-13 — Hidden-Bug Pass 281 (Codex)

Fixed compliance evaluation falling back to a stale profile medical expiry
when a verified medical certificate had no expiry date. Verified certificate
evidence now suppresses the denormalized fallback and produces the expected
warning instead of a false deployability result.

## 2026-09-13 — Hidden-Bug Pass 282 (Codex)

Aligned frontend mobilization preflight with backend compliance: a verified
medical certificate with no expiry can no longer fall back to stale profile
medical expiry. Added regression coverage.

## 2026-09-13 — Hidden-Bug Pass 283 (Codex)

Fixed frontend mobilization preflight accepting dated certificates marked
`valid` but still `unverified`. The usable-certificate predicate now matches
the backend’s verified-evidence rule, with regression coverage for mapped
GraphQL certificate data.

## 2026-09-13 — Hidden-Bug Pass 284 (Codex)

Fixed medical projection cleanup skipping expiry-less detached certificates.
Reconciliation now recomputes the root medical fields whenever linked evidence
is detached, preventing stale profile expiry from returning after the last
verified certificate is rejected or deleted. Added regression coverage.

## 2026-09-13 — Hidden-Bug Pass 285 (Codex)

Aligned backend medical-certificate detection with the frontend and canonical
aliases. Manual or imported `ENG1`/`OEUK` evidence now participates in medical
projection, compliance alerts, assignment checks, and natural-language search.
Added regression coverage for the shared detector.

## 2026-09-13 — Hidden-Bug Pass 286 (Codex)

Hardened administrator document downloads against changed or corrupted local
cache and Dropbox content. Downloaded bytes are now revalidated against the
stored filename and magic signature before being served, with regression
coverage for mismatched PDF content.

## 2026-09-13 — Hidden-Bug Pass 287 (Codex)

Applied the same content-integrity validation to the direct Dropbox download
endpoint. Administrator downloads now reject provider bytes whose size or magic
signature does not match the stored document metadata, with regression tests.

## 2026-09-13 — Hidden-Bug Pass 288 (Codex)

Hardened compliance report filters to accept only canonical certification
lifecycle statuses. Unknown status values now return a clear bad-input error
instead of silently generating an empty report, with regression coverage.

## 2026-09-13 — Hidden-Bug Pass 289 (Codex)

Added bounded streaming for Dropbox downloads. Provider responses are now
consumed incrementally and rejected once they exceed the configured file-size
limit, preventing oversized remote content from being fully buffered in memory.
Added focused transport coverage.

## 2026-09-13 — Hidden-Bug Pass 290 (Codex)

Hardened project-readiness report filters to reject unknown project statuses
instead of silently returning an empty report. Validation now uses the existing
project status vocabulary, with regression coverage.

## 2026-09-13 — Hidden-Bug Pass 291 (Codex)

Compliance report filters now reject empty status lists instead of translating
them into an always-empty database predicate. Added regression coverage.

## 2026-09-13 — Hidden-Bug Pass 292 (Codex)

Mapped invalid vessel keys in GraphQL campaign-assignment and vessel-roster
queries to `BAD_USER_INPUT` instead of internal errors. Added regression
coverage for both resolvers.

## 2026-09-13 — Hidden-Bug Pass 293 (Codex)

Bounded VesselAPI response handling. Upstream JSON is now streamed and
rejected above 2 MiB before it can be fully buffered, with regression coverage
for both oversized `Content-Length` and streamed bodies.

## 2026-09-13 — Hidden-Bug Pass 294 (Codex)

Validated runtime duration settings at the configuration boundary. Session
age, VesselAPI timeout, and VesselAPI cache TTL now reject zero, negative, and
non-finite values instead of failing later during request or cookie handling.

## 2026-09-13 — Hidden-Bug Pass 295 (Codex)

Mapped missing or inaccessible profiles in the admin `complianceStatus`
GraphQL query to `NOT_FOUND` instead of exposing a raw internal error. Added
resolver-level regression coverage.

## 2026-09-13 — Hidden-Bug Pass 296 (Codex)

Mapped missing documents in `confirmExtraction` and `confirmDocumentMatch` to
GraphQL `NOT_FOUND` errors instead of raw internal exceptions. Added focused
coverage for both mutations.

## 2026-09-13 — Hidden-Bug Pass 297 (Codex)

Mapped unknown certification IDs in `updateCertification` and
`verifyCertification` to sanitized GraphQL `NOT_FOUND` errors. Validation
failures remain `BAD_USER_INPUT`, and raw certification identifiers are no
longer echoed. Added regression coverage for both mutations.

## 2026-09-13 — Hidden-Bug Pass 298 (Codex)

Mapped missing projects or crew members in `updateProject` and
`assignCrewToProject` to sanitized GraphQL `NOT_FOUND` errors. Project input
validation remains `BAD_USER_INPUT`, with regression coverage for both
mutations.

## 2026-09-13 — Hidden-Bug Pass 299 (Codex)

Mapped invalid `createProject` DTO and persistence input to a sanitized
GraphQL `BAD_USER_INPUT` error instead of exposing a Pydantic or service
exception as an internal error. Added regression coverage for blank names.

## 2026-09-13 — Hidden-Bug Pass 300 (Codex)

Mapped missing or non-reprocessable documents in `reprocessDocument` to
sanitized GraphQL `NOT_FOUND` or `BAD_USER_INPUT` errors instead of exposing
raw service exceptions. Added regression coverage for missing documents.

## 2026-09-13 — Hidden-Bug Pass 301 (Codex)

Mapped unknown crew members and invalid input in `addCertification` to
sanitized GraphQL `NOT_FOUND` or `BAD_USER_INPUT` errors instead of raw DTO or
service exceptions. Added regression coverage for missing crew members.

## 2026-09-13 — Hidden-Bug Pass 302 (Codex)

Mapped invalid DTO input and missing profile IDs in `createCrewMember` and
`updateCrewMember` to sanitized GraphQL `BAD_USER_INPUT` or `NOT_FOUND`
errors. Added regression coverage for both mutations.

## 2026-09-13 — Hidden-Bug Pass 303 (Codex)

Mapped self-delete attempts in `deleteCrewMember` to `FORBIDDEN` and storage
cleanup failures to a sanitized `UPSTREAM_ERROR`. Provider paths and filenames
are no longer returned through GraphQL. Added regression coverage.

## 2026-09-13 — Hidden-Bug Pass 304 (Codex)

Mapped `setStaffRole` service failures to stable GraphQL errors: missing users
return `NOT_FOUND`, protected administrator accounts return `FORBIDDEN`, and
other validation failures return `BAD_USER_INPUT`. Added regression coverage.

## 2026-09-13 — Hidden-Bug Pass 305 (Codex)

Mapped missing, stale, and invalid CV review mutations to stable GraphQL
`NOT_FOUND`, `CONFLICT`, or `BAD_USER_INPUT` errors. Review identifiers are no
longer echoed. Added coverage for missing reviews in approval and rejection.

## 2026-09-13 — Hidden-Bug Pass 306 (Codex)

Mapped terminal or in-progress `confirmExtraction` failures to `CONFLICT`,
and unknown document/crew links to `NOT_FOUND`, instead of leaking raw service
exceptions. Added regression coverage for both document mutation paths.

## 2026-09-13 — Hidden-Bug Pass 307 (Codex)

Mapped invalid vessel identifiers and missing crew members in vessel-record
and assignment-compliance GraphQL queries to sanitized `BAD_USER_INPUT` or
`NOT_FOUND` errors. Added regression coverage for both query paths.

## 2026-09-13 — Hidden-Bug Pass 308 (Codex)

Bounded Dropbox webhook request bodies to 64 KiB. Oversized requests are now
rejected before signature verification or JSON parsing, including chunked
requests without a `Content-Length` header. Added regression coverage.

## 2026-09-13 — Hidden-Bug Pass 309 (Codex)

Bounded Dropbox webhook fan-out to 100 validated account identifiers. Excess
or malformed account entries now receive a `400` response instead of creating
unbounded background processing tasks. Added regression coverage.

## 2026-09-13 — Hidden-Bug Pass 310 (Codex)

Bounded the reflected Dropbox webhook verification challenge to 4 KiB.
Oversized challenge parameters now return `400` instead of producing an
unbounded plain-text response. Added regression coverage.
## Hidden-Bug Pass 341 — prevent fabricated rates and ranking values (2026-09-13)

- Removed invented £800 comparison rates and the £850 default agreed rate from
  vessel mobilization; administrator submissions now require an explicit valid
  rate and reset when the modal opens or candidate changes.
- Missing ratings, rates, and experience no longer receive fabricated fallback
  values in sorting, relevance scoring, skill radar, or cohort insights.
  Tool: Codex.
## Hidden-Bug Pass 342 — stream CV preview uploads (2026-09-13)

- Changed CV preview extraction to stream uploads in bounded chunks while
  writing its temporary parser input, matching the regular upload path and
  avoiding a full 50 MiB in-memory buffer per concurrent request.
  Tool: Codex.
## Hidden-Bug Pass 343 — comparison bar missing-rate label (2026-09-13)

- Replaced the comparison bar's misleading job-title fallback with an explicit
  “Rate on request” label when no day rate is recorded. Also normalized the
  same missing-rate wording in comparison and shortlist copy/export paths.
  Tool: Codex.
## Hidden-Bug Pass 344 — retry search reconciliation exceptions (2026-09-13)

- Fixed document extraction to queue Meilisearch reconciliation when the
  provider raises an exception, not only when it returns `False`; successful
  extraction can no longer leave a stale search projection without a retry.
  Applied the same retry behavior to reprocessing, terminal review, manual
  confirmation, and document relinking paths. Added regression coverage.
  Tool: Codex.

## Hidden-Bug Pass 345 — retry document-review projection failures (2026-09-13)

- Queued search and vector repair tasks when contractor document-review retry
  paths encounter provider exceptions, preventing logged-only failures from
  leaving derived projections stale. Tool: Codex.

## Hidden-Bug Pass 346 — retry reprocessing vector cleanup failures (2026-09-13)

- Reprocessing and terminal document cleanup now enqueue the existing vector
  projection repair task when Qdrant raises, avoiding stale semantic results
  after a provider outage. Tool: Codex.

## Hidden-Bug Pass 347 — keep CV parser errors privacy-safe (2026-09-13)

- Stopped logging raw CV table-parser exception messages, which could contain
  document content or personal data; diagnostics now record only the safe
  exception type. Tool: Codex.

## Hidden-Bug Pass 348 — bound DOCX and email extraction buffers (2026-09-13)

- Bounded DOCX paragraph/table accumulation while parsing and changed EML
  extraction to read only the persisted-text limit, preventing oversized
  uploads from creating avoidable worker-memory spikes. Added regression tests.
  Tool: Codex.

## Hidden-Bug Pass 349 — derive live filter options from loaded contractors (2026-09-13)

- Filter sidebar options and natural-language matching now use the loaded
  contractor roster instead of demo-only skills, locations, and companies.
  This keeps live records selectable without adding a second backend contract.
  Added frontend regression coverage. Tool: Codex.

## Hidden-Bug Pass 350 — expose roster pagination (2026-09-13)

- Added the missing “Load more contractors” control for rosters beyond the
  automatically loaded page bound, so the existing pagination path is usable
  even when current filters have no matches and larger live rosters are not
  silently truncated. Tool: Codex.
## Hidden-Bug Pass 351 — preserve Dropbox cursor failure semantics (2026-09-13)
- Prevented a Redis cursor-read failure from being treated as an absent cursor,
  which could restart a full recursive Dropbox listing during a transient cache
  outage. The account sync now defers that attempt and remains retryable. Added
  a regression test. Tool: Codex.
## Hidden-Bug Pass 352 — preserve AI search experience values (2026-09-13)
- Fixed a frontend/backend natural-search contract mismatch where the backend
  returned `experience_years` but the frontend only parsed
  `experience_months`. Results outside the loaded roster no longer display
  zero experience when the backend supplied an authoritative value. Added
  parser and result-mapping regression coverage. Tool: Codex.
## Hidden-Bug Pass 353 — preserve unknown experience values (2026-09-13)
- Stopped natural-search results and AI-summary inputs from converting missing
  experience data into a misleading confirmed value of `0` years. Missing
  `experience_months` now remains `null`, with regression coverage. Tool:
  Codex.
## Hidden-Bug Pass 354 — distinguish unavailable from available-next-month (2026-09-13)
- Fixed deterministic natural-search parsing so `unavailable next month` no
  longer inherits the date constraint intended only for available contractors.
  Added a regression test. Tool: Codex.
## Hidden-Bug Pass 355 — parse negative availability language (2026-09-13)
- Fixed natural-search normalization so `not available` and `no longer
  available` are treated as unavailable instead of matching the positive
  `available` substring. Added regression coverage. Tool: Codex.
## Hidden-Bug Pass 356 — map live contractor location correctly (2026-09-13)
- Fixed the live roster mapper using nationality as the contractor location.
  Location now comes from `countryOfResidence`, preserving nationality as a
  separate field and making location filters/facets accurate. Added regression
  coverage. Tool: Codex.
## Hidden-Bug Pass 357 — preserve string-form languages (2026-09-13)
- Fixed the frontend mapper silently dropping languages when a compatible API
  response supplied a string or JSON-string representation instead of an array.
  Added regression coverage for the string form. Tool: Codex.
## Hidden-Bug Pass 358 — reject invalid expiry dates in the UI (2026-09-13)
- Fixed document compliance rendering so malformed expiry dates no longer fall
  through as `Valid (NaN mo remaining)`. They now fail closed as unrecorded
  validity, with regression coverage. Tool: Codex.
## Hidden-Bug Pass 359 — guard public upload-link expiry rendering (2026-09-13)
- Fixed malformed contractor upload-link expiry values rendering as
  `Valid for NaN days` and `Invalid Date`. The public page now labels unreadable
  expiry data explicitly, with regression coverage. Tool: Codex.
## Hidden-Bug Pass 360 — validate mobilization compliance dates (2026-09-13)
- Fixed mobilization preflight checks comparing malformed certification or
  availability dates as raw strings. Optional calendar dates are now validated
  before they influence eligibility, sorting, or expiry warnings. Added a
  malformed-medical regression test. Tool: Codex.
## 2026-09-13

- Disabled the development-default mock contractor fallback; demo mode now requires `VITE_ENABLE_DEMO_MODE=true`, preventing empty authenticated rosters from displaying fictional live-looking contractors. Implemented by Codex during the hidden-bug audit.
## 2026-09-13

- Blocked confirmed/on-board assignments when a contractor is still marked on assignment through or beyond the requested start date. Added regression coverage. Implemented by Codex during the hidden-bug audit.
## 2026-09-13

- Rejected certifications can no longer influence assignment blocking or compliance search/report paths when a stale verification flag still says `verified`; added regression coverage for the assignment guard. Implemented by Codex during the hidden-bug audit.
## 2026-09-13

- Prevented confirmed/on-board assignments from mobilizing contractors whose profile publication state is `rejected`, while preserving administrator inspection access. Added regression coverage. Implemented by Codex during the hidden-bug audit.
## 2026-09-13

- Hardened public upload-route token decoding so malformed percent-encoding reaches the normal invalid-link response instead of crashing the frontend during startup. Added focused regression coverage. Implemented by Codex during the hidden-bug audit.
## 2026-09-13

- Prevented the public upload page from reporting completion when the backend persisted the document but failed to dispatch extraction (`status: failed`); the existing idempotency key now remains retryable. Added API regression coverage. Implemented by Codex during the hidden-bug audit.
# 2026-09-13 — Codex hidden-bug audit

Authenticated document uploads now treat a successful HTTP response with a
failed extraction dispatch as an error, preventing the UI from falsely
reporting that processing has started. Added a frontend regression test; retry
the upload after the queue becomes available.

Public idempotent upload retries now return the actual retry outcome when the
broker fails again, instead of returning a stale in-memory `pending` status.
This now applies consistently to public-link, authenticated, and agent upload
origins. Added backend regression coverage for the repeated dispatch failure.

The add-contractor CV flow now stops on terminal extraction failure, polling
timeout, or status-read failure instead of showing “CV submitted for review”
and calling success. Added frontend coverage for the terminal-status decision.

GraphQL model projections now restore safe, fail-closed defaults for legacy
rows whose status fields are null, preventing non-null GraphQL fields from
breaking whole queries or making unknown profiles look published/available.
Added a regression test covering crew, certification, document, and project
projections.
