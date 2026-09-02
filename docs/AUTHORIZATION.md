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

| Endpoint | Dependency | Required |
|---|---|---|
| `/api/documents/*` upload | `require_admin_rest` / `require_api_key` | admin or valid `X-API-Key` |
| `/api/dropbox/webhook` | webhook signature | signed payload |
| `/health/`, `/health/all` | none | public |

## Rationale

All mutations mutate organization-wide state (personnel, documents,
certifications, projects). They require the `admin` role. Queries are safe to
expose to any authenticated user; further segmentation is deferred.

The role check happens in `@require_admin` (`app/auth/decorators.py`). The
GraphQL response uses `extensions.code = "FORBIDDEN"` for failed authz so the
frontend can branch cleanly. REST returns HTTP 403.