# Authorization Matrix

This document records the role/operation authorization policy enforced by the
backend. Roles are: `user` (read-only authenticated), `staff` (may submit
specialists/CVs), and `admin` (may review and publish). Existing `user`
accounts are never promoted automatically. Machine/API-key
access goes through `X-API-Key` for agent uploads (`/api/documents/*`) only.
Administrators promote or demote existing accounts from the **Staff access**
screen; it calls the admin-only `setStaffRole` operation.

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

Approved profiles remain readable to authenticated users. Draft profiles and
their documents are visible only to the submitting staff member and admins.
`cvReviews` requires staff and returns all reviews to admins or only the
caller's submissions to staff.

This is enforced automatically, not just documented here:
`test_all_queries_require_auth_decorator` in `backend/tests/test_auth.py`
introspects every `Query` field and fails if one isn't wrapped by
`@require_auth`/`@require_admin`. A future intentionally-public query field
must be added to that test's `_PUBLIC_QUERIES` allow-list with a stated
reason — the test starts from an empty allow-list, so a new field is
auth-required by default.

## REST

| Endpoint | Dependency | Required | Notes |
|---|---|---|---|
| `GET /api/search/crew` | `get_current_user_rest` | any authenticated | Read; mirrors GraphQL query policy |
| `GET /api/search/documents` | `get_current_user_rest` | any authenticated | Read |
| `POST /api/search/index/crew/{crew_id}` | `require_admin_rest` | admin | State-changing (Meilisearch write) |
| `GET /api/search/health` | none | public | Meilisearch liveness only, no data |
| `POST /api/documents/preview-cv` | `require_staff_rest` | staff/admin | Deterministic CV preview only |
| `POST /api/documents/upload` | `require_staff_rest` | staff/admin | Staff may upload only to their own draft |
| `GET /api/documents/{document_id}/download` | `get_current_user_rest` | any authenticated | Read; mirrors GraphQL `document` query policy |
| `GET /api/documents/{document_id}/status` | `get_current_user_rest` | any authenticated | Read |
| `DELETE /api/documents/{document_id}` | `require_admin_rest` | admin | |
| `POST /api/documents/agent/upload` | `require_api_key` | valid `X-API-Key` | Machine/agent access; CV classification is rejected so review cannot be bypassed |
| `GET`/`POST /api/dropbox/webhook` | webhook signature | signed payload | Provider-authenticated, not user-authenticated |
| `POST /api/dropbox/download/{document_id}` | `get_current_user_rest` | any authenticated | Read |
| `GET /health/` | none | public | Liveness only; minimal detail |
| `GET /health/services` | `require_admin_rest` | admin | |
| `GET /health/db`, `/redis`, `/ollama`, `/qdrant`, `/all` | `require_api_key` in production, none otherwise | admin/API-key in production; open in dev/test | Dependency diagnostics — gated only when `APP_ENV=production` (see `_is_prod()` in `app/api/health.py`); intentional per docs/ARCHITECTURE.md's "in production" scope, but note it explicitly so a future reader doesn't mistake the dev-mode bypass for a bug |

## Rationale

All mutations and other state-changing operations (document upload/delete,
search-index writes) touch organization-wide state (personnel, documents,
certifications, projects, the search index). They require the `admin` role.

Confirmed profiles remain open to authenticated users because cross-specialist
search is the product's core use case. Unpublished drafts are ownership-scoped
so a submission cannot leak before review.

The role check happens in `@require_admin` (`app/auth/decorators.py`) for
GraphQL and `require_admin_rest` for REST. The GraphQL response uses
`extensions.code = "FORBIDDEN"` for failed authz so the frontend can branch
cleanly. REST returns HTTP 403. Every admin-gated GraphQL mutation has a
negative-authorization test in `backend/tests/test_auth.py` asserting a
non-admin caller gets `FORBIDDEN` — add a case there whenever a new mutation
is added to this table.
