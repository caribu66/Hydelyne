# Authorization Matrix

This document records the role/operation authorization policy enforced by the
backend. Roles are: `user` (any authenticated), and `admin`. Machine/API-key
access goes through `X-API-Key` for agent uploads (`/api/documents/*`) only.

## GraphQL Mutations

| Operation | Decorator | Required Role | Notes |
|---|---|---|---|
| `login` | none | none | Public |
| `logout` | `@require_auth` | any | User logs themselves out |
| `createCrewMember` | `@require_admin` | admin | Org-wide personnel record |
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

All queries remain `@require_auth` (any authenticated user). Read access is
not segregated by role in this iteration; tightening it is future work.

## REST

| Endpoint | Dependency | Required | Notes |
|---|---|---|---|
| `GET /api/search/crew` | `get_current_user_rest` | any authenticated | Read; mirrors GraphQL query policy |
| `GET /api/search/documents` | `get_current_user_rest` | any authenticated | Read |
| `POST /api/search/index/crew/{crew_id}` | `require_admin_rest` | admin | State-changing (Meilisearch write) |
| `GET /api/search/health` | none | public | Meilisearch liveness only, no data |
| `POST /api/documents/preview-cv` | `require_admin_rest` | admin | |
| `POST /api/documents/upload` | `require_admin_rest` | admin | |
| `GET /api/documents/{document_id}/download` | `get_current_user_rest` | any authenticated | Read; mirrors GraphQL `document` query policy |
| `GET /api/documents/{document_id}/status` | `get_current_user_rest` | any authenticated | Read |
| `DELETE /api/documents/{document_id}` | `require_admin_rest` | admin | |
| `POST /api/documents/agent/upload` | `require_api_key` | valid `X-API-Key` | Machine/agent access |
| `GET`/`POST /api/dropbox/webhook` | webhook signature | signed payload | Provider-authenticated, not user-authenticated |
| `POST /api/dropbox/download/{document_id}` | `get_current_user_rest` | any authenticated | Read |
| `GET /health/` | none | public | Liveness only; minimal detail |
| `GET /health/services` | `require_admin_rest` | admin | |
| `GET /health/db`, `/redis`, `/ollama`, `/qdrant`, `/all` | `require_api_key` in production, none otherwise | admin/API-key in production; open in dev/test | Dependency diagnostics — gated only when `APP_ENV=production` (see `_is_prod()` in `app/api/health.py`); intentional per docs/ARCHITECTURE.md's "in production" scope, but note it explicitly so a future reader doesn't mistake the dev-mode bypass for a bug |

## Rationale

All mutations and other state-changing operations (document upload/delete,
search-index writes) touch organization-wide state (personnel, documents,
certifications, projects, the search index). They require the `admin` role.

Reads are intentionally open to any authenticated user rather than scoped by
resource ownership: the product's purpose is letting agents browse and search
across all specialists, so per-record read restriction would work against the
core use case. This is a deliberate scope boundary, not an oversight — if that
changes, update this table and the GraphQL/REST dependencies together.

The role check happens in `@require_admin` (`app/auth/decorators.py`) for
GraphQL and `require_admin_rest` for REST. The GraphQL response uses
`extensions.code = "FORBIDDEN"` for failed authz so the frontend can branch
cleanly. REST returns HTTP 403. Every admin-gated GraphQL mutation has a
negative-authorization test in `backend/tests/test_auth.py` asserting a
non-admin caller gets `FORBIDDEN` — add a case there whenever a new mutation
is added to this table.