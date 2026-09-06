# Authorization Matrix

This document records the role/operation and field-level authorization policy
enforced by the backend. Roles are: `user` (read-only authenticated),
`staff` (may submit specialists/CVs), and `admin` (may review and publish).
Existing `user` accounts are never promoted automatically. Machine/API-key
access goes through `X-API-Key` for agent uploads (`/api/documents/*`) only.
Administrators promote or demote existing accounts from the **Staff access**
screen; it calls the admin-only `setStaffRole` operation.

The authoritative data-classification and tier definitions live in
**ADR 0005** (`docs/decisions/0005-field-level-access-and-data-classification.md`)
and `backend/app/domain/access_tiers.py` (machine-readable field → class map).
This file is the human-readable enforcement matrix. No resolver, REST handler,
Celery task, or search projection may expose a field outside its classification
without an explicit tier check and audit entry — absence of a check is
fail-closed denial.

## Data classification (single source of truth)

Every persisted or derived crew/document/search field belongs to exactly one
class. Adding a new column requires classifying it here and in
`access_tiers.py` before merge; unmapped fields are deny-by-default.

| Class | Label | Sensitivity | Storage / derivation |
|---|---|---|---|
| **C1** | Recruiter-safe profile | Low — required for matching/scheduling | `crew_members` and derived search/LLM-summary projections |
| **C2** | Restricted operational | Medium — PII/operational, need-to-deploy | `crew_members`, `work_history`, `certifications` PII, document metadata, project assignment |
| **C3** | Compliance-only | High — identity/regulated/raw evidence, need-to-know | `crew_members` identity/medical/insurance, raw documents, `extracted_text`/`extracted_data`, `storage_path`/`dropbox_path`, `access_log`, pre-publication `cv_reviews` |

### Field-level mapping (authoritative, mirrors `access_tiers.py`)

**C1 — Recruiter-safe** (any authenticated `T1` may read for `publication_status == "approved"` profiles):
- `CrewMember`: `id`, `full_name`, `nationality`, `country_of_residence`, `gender`, `languages`, `flying_point`, `availability_status`, `availability_date`, `profile_completeness_score`, `experience_months` → `yearsOfExperience`, `education`, `professional_summary` (verbatim), `geographical_experience`, `systems_experience`, `training_qualifications`, `tags`, `created_at`, `updated_at`, `publication_status`, `role` (own role only via `me`; not enumerated for others)
- `Certification`: `id`, `cert_type`, `status`, `verification_status`, `issue_date`, `expiry_date` (dates only — numbers redacted)
- Aggregates: `complianceStatus` counts (`total`/`valid`/`expired`/`pending_verification`) without row-level PII

**C2 — Restricted operational** (`T2`: `staff` scoped + `admin` global):
- `CrewMember`: `email`, `phone`, `address`, `emergency_contact_name/relationship/phone`, `internal_notes`
- `WorkHistory.*`: `client_name`, `project_name`, `project_type`, `location`, `country`, `role`, `responsibilities`, `start_date`, `end_date`, `status`, `document_ref`
- `Certification`: `cert_number`, `issuing_body`, `renewal_date`, `document_ref`, `extracted_confidence`
- `Document` metadata: `file_name`, `file_type`, `file_size`, `classification`, `extraction_status`, `uploaded_at`, `version_number`, `uploaded_by` (identifier only)
- `Project`: `requirements`, `crew_assigned`, `document_ref`, assignment history

**C3 — Compliance-only** (`T3`: `admin` only; future `compliance` role may be split from `admin` without re-classification):
- `CrewMember`: `date_of_birth`, `passport_number/expiry/issuing_country`, `visa_type/restrictions/expiry`, `medical_status/expiry/provider`, `insurance_provider/policy_number/coverage/expiry`, `password_hash` (never exposed), `submitted_by` (audit use only — not bulk-exposed)
- `Document` evidence: `extracted_text`, `extracted_data`, `extraction_confidence`, `storage_path`, `dropbox_path`, `dropbox_revision`, `upload_key`, `access_log`, raw binary via download paths
- `CVReview`: `proposed_data`, `approved_data`, `review_note` pre-publication
- `IncomingDocumentReview` queue metadata until resolved
- All `C3` fields are **never** written to the general Meilisearch/Qdrant projection; they remain PostgreSQL-only (or a separate `compliance`-gated projection if operational need is proven)

Any field not listed is implicitly **C3 / deny-by-default** until classified.

## Access tiers (who may read which class)

| Tier | Who | May read | Scope rule |
|---|---|---|---|
| **T1** | Any authenticated `user`, `staff`, `admin` | **C1 only** | Only `publication_status == "approved"` profiles. Drafts excluded for all T1 callers except submitter/admin (see publication boundary in `docs/ARCHITECTURE.md`). |
| **T2** | `staff` (scoped) and `admin` (global) | **C1 + C2** | `staff` may read C2 only for profiles they submitted (`submitted_by == actor_id`) or for approved profiles when the operation explicitly requires T2 and the resolver has an audited decision. `staff` may not read C2 for another staff member's draft. `admin` may read C2 for any profile. |
| **T3** | `admin` only (reserved: `compliance` role) | **C1 + C2 + C3** | Identity/passport/visa/medical/insurance, raw document bytes, and extracted evidence require an explicit `T3` permission and an append-only audit entry (actor, tier, class, field set, crew/document id, outcome). No `staff`/`user` path may return C3. |

No role is widened by this classification. `user` remains recruiter-safe read-only; `staff` gains no C3; `admin` scope is unchanged. The future `compliance` role, if created, inherits T3 without re-classifying data.

## GraphQL Mutations

| Operation | Decorator | Required Role | Notes |
|---|---|---|---|
| `login` | none | none | Public |
| `logout` | `@require_auth` | any | User logs themselves out |
| `createCrewMember` | `@require_staff` | staff/admin | Staff must use the CV-led draft path; manual admin creation remains compatible |
| `approveCvReview` / `rejectCvReview` | `@require_admin` | admin | Publishes or rejects staged CV data |
| `setStaffRole` | `@require_admin` | admin | Explicitly promotes/demotes non-admin accounts |
| `updateCrewMember` | `@require_admin` | admin | Admin-only until ownership layer ships |
| `deleteCrewMember` | `@require_admin` | admin | |
| `uploadDocument` | `@require_admin` | admin | Documents are org-sensitive |
| `confirmExtraction` | `@require_admin` | admin | |
| `reprocessDocument` | `@require_admin` | admin | |
| `confirmDocumentMatch` | `@require_admin` | admin | |
| `addCertification` | `@require_admin` | admin | |
| `updateCertification` | `@require_admin` | admin | |
| `verifyCertification` | `@require_admin` | admin | |
| `createProject` | `@require_admin` | admin | |
| `updateProject` | `@require_admin` | admin | |
| `assignCrewToProject` | `@require_admin` | admin | |
| `uploadCvAndExtract` | `@require_admin` | admin | Retired path; still admin-gated |

## GraphQL Queries

Approved profiles remain readable to authenticated users at **T1 (C1 only)** with
field-level enforcement. Draft profiles and their documents remain visible only
to the submitting staff member and admins (T2/T3 as classified).

Field-level scrubbing is enforced in `backend/app/graphql/scrub.py` via
`access_tiers.tier_for_role` — every resolver redacts before return; absence of
a scrub is a fail-closed bug.

| Query field | Current decorator | Policy tier | Class returned | Notes |
|---|---|---|---|---|
| `me` | `@require_auth` | T1 | C1 (own record) | Own `id`/`fullName`/`email`/`role` only |
| `crewMember(id)` | `@require_auth` + tier scrub | T1 → T2/T3 escalated | C1 for T1; C1+C2 for T2; all for T3 | Publication check: `publication_status != approved` hidden from non-owner/non-admin; scrubbed via `scrub_crew_member` |
| `crewMembers` | `@require_auth` + tier scrub | T1 → T3 per tier | C1 for T1; C1+C2 for T2; all for T3 | `limit <= 100` server-side; bulk roster is tier-scoped (C1 for T1, escalated for staff/admin detail via `crewMember`) |
| `searchCrew` | `@require_auth` + tier scrub | T1 → T3 per tier | Same as `crewMembers` | Keyword search surface |
| `queryCrew` | `@require_auth` | T1 | C1 (structured hits + AI summary with provenance) | Natural-language search; approved-only |
| `expiringCertifications` | `@require_staff` | T2 | C1 + C2 cert dates/numbers scoped to T2 | Operational alert; T1 receives `FORBIDDEN` |
| `complianceStatus(crewId)` | `@require_admin` + ownership check | T3 | C1 aggregates + C3 expiry detail | T1/T2 receive `FORBIDDEN` |
| `crewSummary(crewId)` | `@require_auth` | T1 (explicit/on-demand) | C1 summary with provenance | Future: explicit request flag, non-AI fallback when Ollama unavailable |
| `document(id)` | `@require_auth` + tier gate | T2 (metadata) / T3 (evidence) | `null` for T1; C2 metadata for T2 (no `extractedText`/`extractedData`); full for T3 | Never return C3 fields to T1/T2; enforced via `scrub_document` |
| `documentsByCrew(crewId)` | `@require_auth` + tier gate | T2 / T3 | `[]` for T1; C2 list for T2; full for T3 | Same split as `document` |
| `pendingReviews` | `@require_admin` | T3 | C3 queue + C2 metadata | Admin/compliance only |
| `cvReviews` | `@require_staff` | T2/T3 | C3 proposed/approved data only for `admin`; staff sees own submissions only | Already ownership-scoped; C3 payload must enforce T3 for full evidence |
| `project` / `projects` | `@require_auth` + tier scrub | T1 (summary) / T2 (assignment) | C1 project roster for T1; `crew_assigned`/`requirements` is C2/T2 | Via `scrub_project` |
| `generateReport` | `@require_auth` + tier branch | T1 (availability) / T2/T3 (compliance/performance) | C1 aggregates for availability; C3 detail for compliance | `COMPLIANCE`/`PERFORMANCE`/`PROJECT_READINESS` require T2+; `AVAILABILITY` remains T1 |

This is enforced automatically for operation-level auth:
`test_all_queries_require_auth_decorator` in `backend/tests/test_auth.py`
introspects every `Query` field and fails if one isn't wrapped by
`@require_auth`/`@require_admin`/`@require_staff`. Field-level tier checks are
covered by `backend/tests/test_field_level_auth.py` — T1 callers receive
`null`/`[]` or `FORBIDDEN` for every C2/C3 field — and by
`test_meilisearch_doc_is_C1_only` for the projection.

## REST

| Endpoint | Dependency | Required | Policy tier | Notes |
|---|---|---|---|---|
| `GET /api/search/crew` | `get_current_user_rest` | any authenticated | **T1 / C1 only** | Returns C1 projection; general index is C1-only and hits are stripped of denied fields (`MEILISEARCH_CREW_DENIED_FIELDS`) |
| `GET /api/search/documents` | `require_staff_rest` | staff/admin | **T2 (metadata) / T3 (evidence)** | Metadata list is T2; `extracted_data`/`extracted_text` stripped for T2, full for T3. Excludes `pending`/`failed`/`rejected` via `SEARCHABLE_DOCUMENTS_FILTER`. |
| `POST /api/search/index/crew/{crew_id}` | `require_admin_rest` | admin | T3 (write) | State-changing (Meilisearch write) — admin-only |
| `GET /api/search/health` | none | public | public | Meilisearch liveness only, no data |
| `POST /api/documents/preview-cv` | `require_staff_rest` | staff/admin | T2 | Deterministic CV preview only |
| `POST /api/documents/upload` | `require_staff_rest` | staff/admin | T2 (metadata) | Staff may upload only to their own draft; creates C3 evidence gated to T3 on read |
| `GET /api/documents/{document_id}/download` | `require_admin_rest` | admin | **T3 / C3** | Raw bytes are C3; T1/T2 receive 403. Audited via `audit_service.log_access`. |
| `GET /api/documents/{document_id}/status` | `require_staff_rest` | staff/admin | **T2** | C2 metadata only; T1 receives 403; must not leak C3 evidence or storage paths |
| `DELETE /api/documents/{document_id}` | `require_admin_rest` | admin | T3 (destructive) | |
| `POST /api/documents/requests` | `require_staff_rest` | staff/admin | T2 | Creates bearer link; token returned once, HMAC stored |
| `GET /api/documents/request/{token}` | none (bearer) | bearer | public (minimal) | Returns only `status`/`expires_at`, never identity/history |
| `POST /api/documents/request/{token}/upload` | bearer | bearer | T3 (ingest) | Contractor upload; CV classification rejected (review gate) |
| `GET /api/documents/review-queue` | `require_staff_rest` | staff/admin | T3 | Durable queue; scoped to `submitted_by`/`approved` for non-admin staff |
| `POST /api/documents/review-queue/{id}/action` | `require_staff_rest` | staff/admin | T3 | Approve/reject with audit |
| `POST /api/documents/{id}/review` | `require_staff_rest` | staff/admin | T3 | Direct compliance review |
| `POST /api/documents/agent/upload` | `require_api_key` | valid `X-API-Key` | T2 (ingest) | Machine/agent access; CV classification rejected |
| `GET`/`POST /api/dropbox/webhook` | webhook signature | signed payload | provider | Provider-authenticated, not user-authenticated |
| `POST /api/dropbox/download/{document_id}` | `require_admin_rest` | admin | **T3 / C3** | Same tier as document download — T1/T2 receive 403 |
| `GET /health/` | none | public | public | Liveness only; minimal detail |
| `GET /health/services` | `require_admin_rest` | admin | admin | |
| `GET /health/db`, `/redis`, `/ollama`, `/qdrant`, `/all` | `require_api_key` in production, none otherwise | admin/API-key in production; open in dev/test | admin in prod | Gated only when `APP_ENV=production` (see `_is_prod()` in `app/api/health.py`) |

## Search and projection policy

- **General `crew_members` Meilisearch index is C1-only.** It contains `id`, `full_name`, `availability_status`, `nationality`, `country_of_residence`, `gender`, `languages`, `flying_point`, `tags`, `publication_status`, and derived C1 text (`education`, `systems_experience`, `training_qualifications`, `geographical_experience`, `professional_summary` as text) — and **must not** contain `email`, `phone`, `passport`/`visa`/`medical`/`insurance`-derived values, or unrestricted `extracted_data`. Enforced in `backend/app/services/consultant_knowledge.py:_crew_meilisearch_doc` (allow-list `MEILISEARCH_CREW_C1_FIELDS`) and `backend/app/services/meilisearch.py:setup_indexes` (searchable attributes C1-only); hits are additionally stripped of `MEILISEARCH_CREW_DENIED_FIELDS` in `GET /api/search/crew` as defense-in-depth for pre-migration indexes. General index rebuild via `reindex_all_crew` keyset path produces C1-only docs.
- **Document `documents` index** searchable filter `SEARCHABLE_DOCUMENTS_FILTER = 'extraction_status IN ["approved", "extracted"]'` remains; `extracted_data`/`extracted_text` in hits is C3 and is stripped for T2 callers in `GET /api/search/documents` (full for T3).
- **Future compliance projection** (`compliance_crew` or Qdrant payload) may be created only with documented operational need and T3 gating. Its existence, retention, and deletion propagation must be proven before it ships.
- **Deletion / revocation propagation**: `deleteCrewMember`, `remove_from_index`, role demotion (`setStaffRole`), and subject deletion/anonymisation must remove the crew/document from **all** projections (general + any compliance index + Qdrant). Verified by `reindex_all_crew` keyset rebuild and a revocation test (downgrade `admin` → `user` then assert C2/C3 absent from search hits and Apollo cache).

## Enforcement status

Least-privilege enforcement for the general read path is **implemented** in this
revision (policy + code):

- GraphQL field-level scrubbing (`backend/app/graphql/scrub.py`) on `crewMembers`,
  `crewMember`, `searchCrew`, `document`, `documentsByCrew`, `project`/`projects`;
  decorator tightening on `expiringCertifications` (`@require_staff`), `complianceStatus`
  (`@require_admin`), and tier branching on `generateReport`.
- REST tier gates on `GET /api/documents/{id}/download` (`@require_admin_rest`),
  `GET /api/documents/{id}/status` (`@require_staff_rest`),
  `GET /api/search/documents` (`@require_staff_rest` with C3 stripping),
  `POST /api/dropbox/download/{id}` (`@require_admin_rest`), and C1-only
  projection + hit stripping on `GET /api/search/crew`.
- Meilisearch general projection C1-only (`_crew_meilisearch_doc` + `setup_indexes`).
- Frontend roster query `CREW_MEMBERS_QUERY` split to C1-only; detail query
  `CREW_MEMBER_DETAIL_QUERY` (C1+C2+C3) is available for T2/T3 dossier views
  (`frontend/src/lib/queries.ts`). `DocumentsByCrew` remains tier-scrubbed
  server-side; full detail requires `CREW_MEMBER_DETAIL_QUERY` or a future
  compliance pane query. Negative tests in
  `backend/tests/test_field_level_auth.py` cover every tier (T1 null/`[]`/
  `FORBIDDEN`, T2 C2 without C3, T3 full) for roster/detail/documents/reports
  and every restricted REST route plus `test_meilisearch_doc_is_C1_only`.

Remaining follow-up within the same security release: wire `CREW_MEMBER_DETAIL_QUERY`
into the dossier pane for selected profiles (so staff/admin see full detail via
explicit fetch rather than roster), and move audit from `Document.access_log` JSON
to an append-only table. Search-index deletion on role revocation and full
retention/retention enforcement remain steps 3–4.

## Rationale

All mutations and other state-changing operations (document upload/delete,
search-index writes) touch organization-wide state (personnel, documents,
certifications, projects, the search index). They require the `admin` role.

Confirmed profiles' **C1** remains open to any authenticated user because
cross-specialist search is the product's core use case — but only C1. C2/C3
requires least privilege and audit. Unpublished drafts are ownership-scoped
so a submission cannot leak before review, regardless of tier.

The role check happens in `@require_admin` (`app/auth/decorators.py`) for
GraphQL and `require_admin_rest` for REST. The GraphQL response uses
`extensions.code = "FORBIDDEN"` for failed authz so the frontend can branch
cleanly. REST returns HTTP 403. Every admin-gated GraphQL mutation has a
negative-authorization test in `backend/tests/test_auth.py` asserting a
non-admin caller gets `FORBIDDEN` — add a case there whenever a new mutation
is added to this table. Enforcement PR must extend that file with
`test_c2_requires_t2` / `test_c3_requires_t3` cases for every field and
download route.
