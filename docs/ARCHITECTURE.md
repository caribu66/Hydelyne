# Hydenlyne Crew DMS architecture

Status: current-state architecture and target boundaries, 2026-09-02.

## Purpose and scope

Hydenlyne Crew DMS is an internal platform for managing specialists, their CVs
and supporting documents, compliance information, search, matching, and
operational workflows. It contains sensitive personal and employment data.

The system is a modular monolith with asynchronous workers. PostgreSQL is the
authoritative transactional store. Redis supports caching, rate limiting, and
Celery. Meilisearch and Qdrant are rebuildable search projections. Dropbox is
an external document store; the local document directory is a runtime cache or
fallback according to configuration. Ollama performs local inference.

## Runtime context

```text
Browser
  -> React/Vite frontend
       -> FastAPI REST + Strawberry GraphQL
            -> PostgreSQL (system of record)
            -> Redis (cache, rate limits, Celery broker)
            -> Meilisearch (keyword projection)
            -> Qdrant (optional semantic projection)
            -> Dropbox (document storage/integration)
            -> Celery workers -> Ollama (extraction/inference)
```

Only the backend may communicate with data stores and external providers. The
frontend consumes documented HTTP/GraphQL contracts.

## Source ownership

| Area | Owns | Must not own |
|---|---|---|
| `frontend/src` | presentation, interaction state, typed API consumption | authorization policy, canonical business rules, direct infrastructure access |
| `backend/app/api` | REST boundary, validation, auth dependency, response mapping | reusable business logic or transaction orchestration |
| `backend/app/graphql` | GraphQL contract, mapping, validation, auth decoration | persistent domain rules or vendor integration |
| `backend/app/domain` | pure vocabulary, normalization, invariants | framework, ORM, queue, HTTP, or vendor dependencies |
| `backend/app/services` | use cases and owned infrastructure adapters | presentation concerns or undocumented cross-module APIs |
| `backend/app/models` | persistence schema and relationships | transport schemas or workflow orchestration |
| `backend/app/tasks` | idempotent asynchronous entry points | duplicated service logic |
| `backend/alembic` | ordered schema evolution | runtime fallback schema creation |

## Dependency direction

New code follows this direction:

```text
REST / GraphQL / Celery
          |
          v
 application services
       |        |
       v        v
    domain    ports/contracts
                  ^
                  |
        infrastructure adapters
```

The domain imports no outer layer. Transport layers may map to and from domain
types, but domain types do not know about GraphQL, FastAPI, Celery, SQLAlchemy,
or React. Infrastructure details remain behind a service or port owned by the
use case.

### Dual-transport maintenance (GraphQL + REST)

The system exposes two external transport boundaries:
- **Strawberry GraphQL** (`/graphql`): for hierarchical entity querying, mutations, reviews, and interactive UI views.
- **FastAPI REST** (`/api/documents/*`, `/api/search/*`, `/dropbox/*`): for multipart file uploads, chunked binary streaming, webhooks, and health probes.

To prevent divergent business logic, both transports strictly follow the **Thin Transport Rule**:
- **Zero Invariant Logic in Transport**: Handlers and resolvers authenticate and validate DTOs/parameters, then call the owning application service (`crew_service`, `document_service`, `consultant_knowledge_service`, etc.).
- **Zero Direct ORM Mutation in Transport**: Neither REST routes nor GraphQL resolvers may construct raw database mutation statements or commit transactions directly.
- **Canonical Exceptions**: Application services raise domain exceptions (`PermissionError`, `ValueError`, `KeyError`, etc.) which transports map to their respective HTTP status codes or GraphQL error extensions.

### Asynchronous worker queue topology

Background processing is segregated across dedicated queues to protect interactive responsiveness:
- `high_priority` / `default`: Latency-sensitive periodic and interactive tasks (compliance checks, alerts, webhooks). Handled by `celery_worker`.
- `heavy_compute`: CPU/GPU bound operations (OCR, PDF extraction, Ollama vision inference). Handled by `celery_compute_worker` (or `celery_gpu_worker`).
- `indexing`: Search projection sync and embedding generation (`index_document_embeddings`). Prevented from starving interactive operations.


## Data ownership and consistency

- PostgreSQL owns specialists, certifications, projects, document metadata,
  extraction state, and audit records.
- Meilisearch and Qdrant contain derived documents and must be rebuildable from
  authoritative data. Failed indexing must be observable and retryable.
- Redis data is disposable except where it temporarily carries queue messages
  or security state. Security behavior during Redis failure must be explicit.
- Uploaded binary ownership depends on `REQUIRE_DROPBOX_STORAGE`. A successful
  operation must not claim durable storage unless the configured durability
  requirement was met.
- Provider calls and database commits are separate failure domains. Important
  multi-system workflows require idempotent operations and durable recovery.

## Primary flows

### Authentication

The login mutation verifies a stored password hash and issues a signed,
HttpOnly session cookie/token. Authorization decorators/dependencies resolve
the user for GraphQL and REST. Redis is currently used for login throttling and
token revocation. Role policy must be defined per operation; `require_auth`
must never be used as an accidental substitute for resource authorization.

### Document ingestion

```text
authorized upload/webhook
  -> validate type, magic bytes, size, and path
  -> persist binary according to storage policy
  -> record PostgreSQL metadata
  -> enqueue stable document identifier
  -> worker extracts and validates data (deterministic parsers for CVs;
     Ollama for other classifications — see below)
  -> transactionally update authoritative records
  -> update rebuildable search projections
```

CV extraction does not call an LLM at all: a deterministic PDF-table/text
parser handles the fixed template this system's CVs come from, and a CV that
doesn't fit it is flagged for manual review rather than falling back to AI.
Other classifications (certificates, identity, etc.) still use Ollama. Details
and rationale live in `backend/docs/cv-ingestion-pipeline.md` and
`docs/decisions/0003-deterministic-cv-extraction.md`. Do not reintroduce an
LLM call into the CV extraction path without a new ADR.

CV-led specialist creation is review-gated. Deterministic extraction is stored
as a `CVReview` proposal; it does not mutate the canonical profile. Only an
administrator-approved proposal changes the profile to `approved` and enters
keyword/natural-language search. Drafts are visible only to their submitting
staff member and administrators.

Tasks may be delivered more than once. Every transition must tolerate retries,
record failure safely, and avoid duplicate domain records.

### Consultant retrieval

`ConsultantKnowledgeService` is the entry point for consultant profile lookup,
structured/keyword search, summaries, and optional semantic retrieval. Details
and feature-flag status live in
`backend/docs/consultant-knowledge-core.md`. Do not add a parallel retrieval
path.

## Security boundaries

- All specialist and document data is private by default.
- Health liveness may be public but must reveal minimal detail. Dependency
  diagnostics require administrator or API-key access in production.
- Webhooks authenticate using the provider signature before side effects.
- Mutation authorization must distinguish ordinary user, administrator,
  machine/API key, and resource ownership where applicable.
- Audit events must exist for sensitive reads, exports, downloads, destructive
  actions, permission changes, and administrative operations.
- Logs and telemetry contain identifiers only when operationally necessary and
  must not contain document bodies, session tokens, passwords, secrets,
  passport data, or medical details.
- The backend is the authorization boundary (see `docs/AUTHORIZATION.md`);
  frontend gating is a UX convenience only. Within the frontend, state that
  can reveal gated UI (search results, filters, saved-only view) must be
  authentication-derived at one render-time checkpoint, not imperatively
  guarded per entry point — a new entry point that forgets its own check must
  fail closed, not silently render. `isSearchActive` in
  `frontend/src/hooks/useSearchWorkspace.ts` is that checkpoint; every
  result-bearing block in `frontend/src/App.tsx` keys off it, so folding
  `isAuthenticated` into its computation closes all of them at once.
  `frontend/tests/auth-gate.spec.ts` is the regression test for this class of
  bug — extend it, don't just re-verify by hand, whenever a new mechanism
  that can seed search/filter state is added (URL params today; a future
  deep link or restored session state would be the same class of risk).

## Deployment invariants

- Schema migration is a controlled deployment step executed once per release,
  not an opportunistic fallback in every API replica.
- The application runs as a non-root container user.
- Production sets `APP_ENV=production`, uses non-default secrets, restricts
  internal service ports, and terminates TLS at a documented trusted proxy.
- Every external call has finite timeouts. Health checks distinguish liveness
  from readiness.
- Worker queue routing must match available hardware. GPU-only routing cannot
  be required on a host where the GPU worker cannot start.

## Known legacy exceptions

These are debt to reduce, not approved examples for new code:

- GraphQL schema and several services contain direct database orchestration.
- `sync_processor.py` creates a separate synchronous SQLAlchemy engine.
- Backend services rely heavily on global singleton clients/settings.
- Application startup runs Alembic and may fall back to `create_all` after an
  Alembic failure on PostgreSQL.
- Several external dependency failures are swallowed or fail open.
- Large backend and frontend files mix multiple responsibilities.
- The frontend and backend live in separate, non-atomic Git histories.

See `docs/AUDIT_2026-09-02.md` for evidence and remediation priorities.
