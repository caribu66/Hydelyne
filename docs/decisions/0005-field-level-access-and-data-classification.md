# ADR 0005: Field-Level Access Tiers and Data Classification

- Status: accepted
- Date: 2026-09-06
- Owners: backend + frontend + security maintainers
- Supersedes: none; complements `docs/AUTHORIZATION.md` and `docs/ARCHITECTURE.md` security boundaries

## Context

Hydenlyne Crew DMS stores three distinct sensitivity classes in one `crew_members` row and its related tables: recruiter-usable profile facts, operational contact/history data, and compliance/identity data with raw documents. The current authorization model (`docs/AUTHORIZATION.md` at `674a1de`) is operation-level only — `user` (any authenticated), `staff` (may submit drafts), `admin` (may publish) — with every read query gated by `@require_auth` / `get_current_user_rest`. Field exposure is uniform for all authenticated users.

Evidence that this is over-broad (verified 2026-09-06):

- `backend/app/graphql/types.py:86-118` `CrewMember` exposes `email`, `phone`, `date_of_birth`, `passport{number,expiry,issuing_country}`, `visa{type,restrictions,expiry}`, `medical{status,expiry,provider}`, `insurance{provider,policy_number,coverage,expiry}`, `work_history`, `certifications{cert_number,issuing_body,document_ref}`, `internal_notes`, and `availability_status` on every `crewMembers`/`crewMember` response. `frontend/src/lib/queries.ts:3-50` `CREW_MEMBERS_QUERY` fetches all of them on every roster load and caches them in Apollo for any authenticated user.
- `backend/app/graphql/schema.py:283-291` `search_crew` delegates to `CrewService.list_crew_members` with only `availability`/`search` filters — no field projection by role. `backend/app/api/search.py:54-83` `GET /api/search/crew` and `GET /api/search/documents` are `get_current_user_rest` (any authenticated) with no tier check.
- Meilisearch general projection `backend/app/services/consultant_knowledge.py:68-80` `_crew_meilisearch_doc` indexes `email` and `phone`; `backend/app/services/meilisearch.py:63-79` `setup_indexes` makes them searchable. No separation between recruiter-safe and compliance projections. `index_crew_members` / `search_crew_members` expose these fields to any authenticated search caller.
- `backend/app/services/audit.py:17-62` document access is logged to mutable `Document.access_log` JSON (`backend/app/models/__init__.py:181`), not an append-only table, and `ProfileAccessEvent` only records `list_profiles`/`keyword_search`/`natural_search` — no sensitive-field read, export, download, permission-change, or review-decision audit with tier provenance.
- Prior audit `docs/AUDIT_2026-09-02.md` P1 #4 required a role/operation matrix with negative authorization tests and auditable sensitive reads. That finding remains open for field-level scope.

Constraints: the product's core use case is cross-specialist search by any authenticated recruiter; removing that would break the system. The fix must preserve recruiter search while removing PII/compliance exposure from the general read path. Search indexes are rebuildable projections (`docs/ARCHITECTURE.md` — PostgreSQL is the sole system of record) and may be rebuilt to a new shape without data loss.

## Decision

Adopt a single, tiered data-classification policy that is the authoritative source for every read path. No GraphQL resolver, REST handler, Celery task, or search projection may expose a field outside its classification without an explicit authorization decision and audit entry.

### 1. Data classifications (single source of truth)

All persisted or derived crew/document/search data belongs to exactly one class:

| Class | Label | Sensitivity | Examples (non-exhaustive, mapped to `backend/app/models/__init__.py` columns) |
|---|---|---|---|
| **C1** | Recruiter-safe profile | Low — required for matching/scheduling | `CrewMember.id`, `full_name`, `nationality`, `country_of_residence`, `gender`, `languages`, `flying_point`, `availability_status`, `availability_date`, `profile_completeness_score`, `experience_months` (→ `yearsOfExperience`), `education`, `professional_summary`, `geographical_experience`, `systems_experience`, `training_qualifications`, `tags`, `created_at`, `updated_at`, `publication_status`; `Certification.cert_type`, `status`, `verification_status`, `expiry_date`, `issue_date` (dates only, no numbers); aggregate `complianceStatus` counts |
| **C2** | Restricted operational | Medium — needed for deployment, but PII/operational | `CrewMember.email`, `phone`, `address`, `emergency_contact_name/relationship/phone`, `WorkHistory.*` (client_name, project_name, location, country, role, responsibilities, dates), `Certification.cert_number`, `issuing_body`, `renewal_date`, `document_ref`, `extracted_confidence`, `internal_notes`, `Document.file_name`, `file_type`, `file_size`, `classification`, `extraction_status`, `uploaded_at`, `version_number`; project `requirements`, `crew_assigned` |
| **C3** | Compliance-only | High — identity, regulated, or raw evidence; strictly need-to-know | `CrewMember.date_of_birth`, `passport_number/expiry/issuing_country`, `visa_type/restrictions/expiry`, `medical_status/expiry/provider`, `insurance_provider/policy_number/coverage/expiry`, `password_hash` (never exposed), `Document.extracted_text`, `extracted_data`, `extraction_confidence`, `storage_path`, `dropbox_path/revision`, `upload_key`, `access_log`, raw binary via `GET /api/documents/{id}/download` and Dropbox; `CVReview.proposed_data/approved_data` pre-publication; `IncomingDocumentReview` queue metadata until resolved |

`Certification.cert_type`/`status`/`verification_status` remain C1 because a recruiter must see *whether* a BOSIET is valid; the *evidence number and scan* that proves it are C2/C3. This split is intentional and documented here, not inferred per resolver.

Ownership: `backend/app/domain/access_tiers.py` will own the field → class mapping as typed constants. Transport enums/DTOs in `backend/app/graphql/types.py` and `frontend/src/types.ts` derive from it; no second literal list may be maintained. `docs/AUTHORIZATION.md` is the human-readable policy; the domain module is the machine-readable enforcement source.

### 2. Access tiers (who may read which class)

| Tier | Who | May read | Purpose |
|---|---|---|---|
| **T1** | Any authenticated `user`, `staff`, `admin` | **C1 only**, for `publication_status == "approved"` profiles; drafts excluded (drafts remain `submitted_by`/`admin` only per existing publication boundary) | Recruiter search, shortlist, availability planning |
| **T2** | `staff` (scoped) and `admin` (global) | **C1 + C2** | Operations — contacting specialists, verifying work history, managing mobilization. Staff scope: may read C2 only for profiles they submitted (`submitted_by == actor_id`) or for `publication_status == "approved"` profiles when their role explicitly requires it; non-admin staff may not read C2 for another staff member's draft |
| **T3** | `admin` only (future `compliance` role may be split from `admin` without policy change) | **C1 + C2 + C3** | Compliance verification, identity/passport/visa/medical/insurance review, raw document and extracted-evidence review, audit |

No role is widened by this ADR. `user` remains read-only recruiter; `staff` gains no new C3 access; `admin` retains its existing scope. The new `compliance` role is reserved, not created, in this step.

### 3. Enforcement shape (not yet implemented — policy first)

This ADR is the **policy** step. Enforcement (step 2 of the remediation plan) will, in a follow-up change:

- Replace broad `CrewMember` returns on general read paths with tier-scoped DTOs / field-level resolvers and dedicated permissions (e.g. `profile:view:t1`, `profile:view:t2`, `compliance:view:t3`, `document:download:t3`). Every GraphQL field resolver, REST handler, and search projection must consult the tier mapping before returning data; absence of a tier check is a fail-closed denial, not an implicit allow.
- Split Meilisearch projections: the general `crew_members` index carries **C1 only** (`full_name`, `availability_status`, `nationality`, `tags`, `publication_status` and derived C1 text fields). Email, phone, passport-derived values, medical details, and unrestricted `extracted_data` are removed. A separate compliance projection may be introduced only with documented operational need and T3 gating; otherwise C3 is PostgreSQL-only, never indexed.
- Ensure the frontend never fetches or caches C2/C3 for T1 users: split `CREW_MEMBERS_QUERY` / `DocumentsByCrew` into `*_T1` (general roster/search) and `*_T3` (compliance pane) queries, with the dossier only requesting the higher-tier query after an explicit authorization check. Cached C2/C3 must not be readable via Apollo cache by a T1 session.
- Move audit from `Document.access_log` JSON to an append-only table recording actor, tier, class, field set, crew/document id, and outcome for sensitive reads, exports, downloads, permission changes, and review decisions. Existing `ProfileAccessEvent` remains for profile-read counts but is not the compliance audit trail.
- Ensure revocation/role change and subject deletion/anonymisation remove data from **all** projections (general + any future compliance index + Qdrant if enabled).

Search/index deletion propagation, outbox/reconciliation, retention/backup, and performance work (server-side pagination, explicit AI summaries, cookie-only sessions) remain in steps 3-7 and are not changed by this ADR.

## Alternatives considered

- **Per-field ad-hoc checks without a classification table**: each resolver decides its own allow-list. Rejected — duplicates the pre-remediation failure mode ("every resolver must remember to deny"), no single source of truth, untestable coverage.
- **Create `recruiter` and `compliance` roles immediately and assign fields to roles**: rejected for this step because it conflates data sensitivity (what the data *is*) with authorization (who *holds* a role). Classification (C1/C2/C3) is stable; role mapping (T1/T2/T3) can evolve (e.g. splitting `compliance` from `admin`) without re-classifying data. The ADR adopts classification-first, then tier-to-role mapping.
- **Keep a single Meilisearch index and filter by role at query time**: rejected for C3 — a single index containing C3 fields is a data-at-rest exposure; deletion or replica misconfiguration leaks compliance data. Separation enforces least privilege even if query filters are misapplied, and aligns with `docs/ARCHITECTURE.md`'s "rebuildable projection" principle.
- **Defer classification and go straight to code enforcement**: rejected — without an agreed C1/C2/C3 table, each enforcement PR would re-litigate field ownership, produce divergent literal lists, and lack a testable contract. Policy must precede enforcement (this ADR's purpose).

## Consequences

- **Positive**: one authoritative field → class map eliminates scattered literal lists; recruiter functionality (search, shortlist, availability) retains exactly the C1 data it needs; compliance/identity data gains explicit, auditable gating; Meilisearch general index shrinks, reducing blast radius; the `compliance` role can be introduced later without re-reviewing every resolver.
- **Cost**: follow-up enforcement requires touching every read path listed below; some resolvers currently return full `CrewMember` models and must be split into tier-scoped DTOs; frontend query splitting adds Apollo cache complexity; compliance workflows that previously relied on broad reads must request the higher-tier view explicitly.
- **Operational burden**: any new `CrewMember`/`Document`/`Certification`/`WorkHistory` column must be classified in `access_tiers.py` and `docs/AUTHORIZATION.md` before merge; review checklist must include "is this field classified?" — enforced by a test that fails on unmapped fields.
- **Risk if not followed**: a new field added without classification silently falls through to the most permissive path; mitigated by the fail-closed rule (unmapped = deny) and a CI check enumerating model columns against the classification map.

## Migration and rollback

This ADR is **policy-only** — it introduces no schema migration, no runtime behavior change, and no data migration. The change is additive documentation plus a domain constants module. Rolling back means reverting the docs and deleting the constants module; no stored data is affected.

Subsequent enforcement work will be contract changes and will follow an expand/migrate/contract pattern:

- **Expand**: introduce tier-scoped GraphQL types/queries (`CrewMemberPublic`, `CrewMemberOperational`, `CrewMemberCompliance` or field-level directives) alongside the existing `CrewMember` type; add a domain `access_tiers` mapping and a compliance-only audit table (additive migrations with downgrade).
- **Migrate**: update resolvers/REST handlers/search indexing to consult the tier map, split frontend queries, and rebuild Meilisearch general index to C1-only (using existing `reindex_all_crew` keyset path `backend/app/services/consultant_knowledge.py:242-301`). Dual-write to old + new shapes during cutover where needed.
- **Contract**: deprecate broad `CrewMember` field exposure on general queries, remove C2/C3 fields from the general Meilisearch index, and enforce fail-closed on unmapped fields. Announce GraphQL field deprecation per `docs/ENGINEERING_STANDARDS.md` compatibility rules.

Verification before merging enforcement (not this ADR):

- `pytest backend/tests/test_auth.py` — negative authorization tests for every C2/C3 field, every document classification, and every download route (T1 caller receives `FORBIDDEN`/403 or `null`, never the field).
- Migration `alembic upgrade head` / `alembic downgrade -1` round-trip for the audit table and any DTO/projection changes.
- Meilisearch reindex proof: `reindex_all_crew` followed by `search_crew_members` asserting no `email`/`phone`/`passport`/`medical` in hits.
- Role-revocation propagation test: downgrade `admin` → `user` and assert C2/C3 disappears from general projections and caches.

## Validation

- **This ADR**: human review of the C1/C2/C3 table against `backend/app/models/__init__.py` columns, `backend/app/graphql/types.py` `CrewMember`/`DocumentType`/`Certification` shapes, and `backend/app/services/consultant_knowledge.py` `_crew_meilisearch_doc` fields; `docs/AUTHORIZATION.md` updated in the same commit per `AGENTS.md`.
- **Follow-up enforcement**: the test/migration/reindex checklist above, plus `mypy app` / `ruff check app tests` / `pytest -q` and frontend `npm run lint && npm run build && npm run ui:audit:strict` gates. No `any`/`cast`/`type:ignore` in the classification module.

