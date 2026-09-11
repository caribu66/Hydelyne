# Hydenlyne Crew Document Management Platform

A crew document management platform for Hydenlyne's internal team to manage their global consultant workforce.

## Quick Start

### Prerequisites

- Podman + `podman-compose` (Docker + `docker compose` works too)
- Optional: an NVIDIA GPU with CDI configured (`/etc/cdi/nvidia.yaml`). The
  launcher automatically enables GPU acceleration only on external power when
  it can verify the device and CDI runtime; otherwise it uses CPU safely.

Every service, including Ollama, runs in a container. Nothing needs to be
installed on the host.

### Configure

```bash
cp .env.example .env
# then edit .env — at minimum SESSION_SECRET_KEY, ADMIN_EMAIL/ADMIN_PASSWORD,
# MEILI_MASTER_KEY, and the DROPBOX_* credentials
```

`OLLAMA_MODELS_PATH` points the Ollama container at an existing model store
(default `${HOME}/.ollama/models`), so models already on disk are reused
instead of re-downloaded. The extraction models are `qwen2.5:14b` (text) and
`llama3.2-vision:latest` (images); pull them once with `ollama pull` on the
host, or into the container with
`podman exec <ollama-container> ollama pull qwen2.5:14b`.

### Run the Platform

```bash
podman-compose build          # builds one image per service with a `build:` key
podman-compose up -d
podman-compose logs -f backend

# Access points:
# - Frontend: http://localhost:5173
# - Backend API: http://localhost:8000
# - GraphQL Playground: http://localhost:8000/graphql
# - Flower (Celery): http://localhost:5555/flower
```

Schema migrations run as a discrete deployment step: the backend container's
entrypoint invokes `alembic upgrade head` before `uvicorn` starts. There is
no `create_all` fallback in the production path; the API will not start if the
schema is out of date.

### Services

| Service | Port | Description |
|---------|------|-------------|
| PostgreSQL | 5433 (host) → 5432 (container) | Primary database; host port overridable via `POSTGRES_HOST_PORT` |
| Redis | 6379 | Task queue broker + rate limiting |
| Qdrant | 6333/6334 | Vector search (the app talks to the REST port, 6333) |
| Meilisearch | 7700 | Keyword search index |
| Ollama | — | LLM inference; internal to the compose network |
| Backend | 8000 | FastAPI + GraphQL |
| Celery Worker | — | Async task processing (`high_priority`, `default` queues) |
| Celery Compute Worker | — | Async task processing (`heavy_compute`, `indexing` queues) |
| Celery Beat | — | Scheduled tasks |
| Frontend | 5173 | React + Vite, served by nginx |

> Flower (Celery monitoring) and the GPU worker are excluded from
> `docker-compose.prod.yml` by default. Enable them only from a trusted network
> and when GPU hardware is available.

## How This Fits Together

Eleven containers sound like a lot, but they are four groups and you only ever
look at two of them.

| Group | Services | Do you touch it? |
|---|---|---|
| The app | `frontend`, `backend` | Yes — the two URLs above |
| Data stores | `db`, `redis`, `qdrant`, `meilisearch` | No, they just have to be up |
| Background work | `celery_worker`, `celery_compute_worker`, `celery_beat` | Only when an upload does not process |
| Inference | `ollama` | No |

The Celery workers are what make document uploads process on their own. Without
them an upload is accepted and then simply never extracted.

### Always build every service, never one

`podman-compose` builds a **separate image per service**. `backend`,
`celery_worker`, `celery_compute_worker`, and `celery_beat` are four
images produced from the same `backend/Dockerfile`. Building one of them leaves
the other three on stale code, which shows up as a change that works through the
API but not through a background task:

```bash
podman-compose build          # correct
podman-compose build backend  # rebuilds 1 of 4 — the workers keep the old code
```

### There are two .env files and they are not interchangeable

- **`.env` at the root** is the one compose reads. Hostnames in it are compose
  *service names*: `db`, `redis`, `ollama`.
- **`backend/.env`** applies only when uvicorn runs directly on the host.
  Hostnames in it are `127.0.0.1`.

The `environment:` block in `docker-compose.yml` overrides both, because a real
environment variable beats a value read from a file. If you change a setting and
nothing happens, check whether you edited `backend/.env` while running in
containers.

### Backend changes restart, frontend changes rebuild

`./backend` is bind-mounted into the containers, so the source is live — but
uvicorn runs without `--reload`, so a change needs a restart:

```bash
podman restart hydenlyne-crew-dms_backend_1 hydenlyne-crew-dms_celery_worker_1
```

That only covers source edits. A change to `requirements.txt` needs a rebuild,
same as the frontend, because the dependency is installed into the image, not
read from the bind mount:

```bash
podman-compose build backend
podman-compose up -d --force-recreate backend celery_worker celery_compute_worker celery_beat
```

The frontend is compiled into an nginx image at build time (the dev bind mount
is commented out in `docker-compose.yml`), so a frontend change needs a rebuild.
`up -d` alone can leave the old container running on the old image if nothing
else in the compose file changed, so force the recreate:

```bash
podman-compose build frontend
podman-compose up -d --force-recreate frontend
```

### Nothing else may hold the ports

The stack binds 5433 (Postgres), 6379, 5173, and 8000. Anything already on
those ports — a host Postgres, a `npm run dev` server, a stray uvicorn — makes
the corresponding container fail to start. Postgres defaults to 5433 rather
than the standard 5432 specifically because a rootless-podman host commonly
also runs its own general-purpose Postgres as a systemd/Quadlet unit on 5432;
check for one before assuming the port is free:

```bash
systemctl --user list-units --type=service | grep -i postgres
```

If a compose `db` container ever does fail with "address already in use" on
5433 too, set `POSTGRES_HOST_PORT` in `.env` to another free port.

### Checking the stack

```bash
curl -s localhost:8000/health/all | python3 -m json.tool
```

All five entries should read `healthy`. A `degraded` result names the failing
dependency, and `podman-compose logs <service>` explains why.

## Production Deployment

Production uses `docker-compose.prod.yml` as an override on top of the base
`docker-compose.yml`. It removes internal port publishes, sets `APP_ENV=production`
on every service, adds restart policies, and applies resource limits.

```bash
# Build production images
docker compose -f docker-compose.yml -f docker-compose.prod.yml build

# Deploy
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Verify
curl -s http://localhost:8000/health/
curl -s http://localhost:5173/health
```

### Production environment variables

At minimum, override these from their development defaults before deploying:

| Variable | Requirement |
|----------|-------------|
| `APP_ENV` | `production` (the override sets this, but verify) |
| `SESSION_SECRET_KEY` | >= 32 chars, never the default |
| `POSTGRES_PASSWORD` | Strong random value |
| `REDIS_PASSWORD` | Strong random value |
| `MEILI_MASTER_KEY` | Strong random value |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | Bootstrap admin credentials |
| `CORS_ORIGINS` | Comma-separated list of allowed frontend origins |
| `SENTRY_DSN` | Error tracking (leave empty to disable) |

The backend validates critical secrets on startup and refuses to start if a
default or missing value would weaken security.

### Backups

Database backups are handled by `backend/scripts/backup.sh`. The script produces
a compressed, timestamped `pg_dump` and retains the last 7 daily backups.

**Host cron example** (run from any host with network access to Postgres and
`pg_dump` installed):

```cron
0 2 * * * DATABASE_URL=postgresql://hydenlyne:${POSTGRES_PASSWORD}@db:5432/hydenlyne BACKUP_DIR=/backups /path/to/repo/backend/scripts/backup.sh
```

For cloud deployments, prefer the provider's automated snapshot feature (RDS
automated backups, managed PostgreSQL continuous archiving, etc.) and treat the
script as a manual recovery option.

### Observability

- **Health checks**: `/health/` (public liveness), `/health/all` (admin-only
  readiness with dependency details)
- **Logging**: JSON-structured logs on stdout in production
- **Error tracking**: Sentry (enable with `SENTRY_DSN`)
- **Task monitoring**: Flower is excluded from `docker-compose.prod.yml` by
  default; enable it only from a trusted network if needed

### Restart and resource policies

`docker-compose.prod.yml` applies `restart: unless-stopped` and memory/CPU
limits to every service. Adjust the `deploy.resources.limits` blocks to match
your host capacity.

## Project Structure

```
hydenlyne-crew-dms/
├── backend/
│   ├── app/
│   │   ├── graphql/        # GraphQL schema and types
│   │   ├── models/         # SQLAlchemy models
│   │   ├── services/       # Business logic (Ollama, extraction, matching)
│   │   ├── tasks/          # Celery async tasks
│   │   └── auth/           # Session management
│   ├── tests/              # Test suite
│   ├── requirements.txt    # Runtime dependencies
│   ├── requirements-dev.txt # Development and test dependencies
│   └── requirements-prod.txt # Production-optimised runtime dependencies
├── frontend/                  # React + Vite, served by nginx (part of this repo)
│   ├── src/
│   │   ├── components/     # Reusable UI components
│   │   ├── hooks/          # Data-fetching and UI hooks
│   │   ├── lib/            # Apollo client, GraphQL queries, mappers
│   │   └── App.tsx
│   └── package.json
├── docker-compose.yml
├── docker-compose.prod.yml  # Production overrides
└── .env.example
```

## Development

The containerised stack is the supported way to run this. Always start it from
the repository root with the checked launcher:

```bash
./scripts/local-stack.sh start
```

It stops only this checkout's containers, refuses to run when another process
owns the frontend or backend port, waits for both health endpoints, and then
prints the usable URL. This avoids a browser silently talking to a stale
frontend or backend from another worktree. Use `./scripts/local-stack.sh stop`
or `./scripts/local-stack.sh status` to manage it. The default stack is
CPU-safe by default. At each `start` or `status`, the launcher prints the
selected compute mode and reason. In automatic mode, GPU acceleration is used
only on external power when `nvidia-smi`, `/dev/nvidia0`, and the CDI
specification are available; battery mode stays on CPU. Use
`HYDENLYNE_COMPUTE_MODE=cpu ./scripts/local-stack.sh start` to force CPU, or
`HYDENLYNE_COMPUTE_MODE=gpu ./scripts/local-stack.sh start` to require GPU and
fail visibly if it cannot be used.

Running a service directly on the host is only worth it for a fast edit loop
on one component, and it needs the matching container stopped first so the
port is free.

### Backend on the host

Reads `backend/.env`, not the root `.env`, so it expects Postgres, Redis, and
Ollama on `127.0.0.1`.

```bash
podman-compose stop backend
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend on the host

Vite serves on 5173, the same port as the frontend container, so stop that
first. Requires Node 20+.

```bash
podman-compose stop frontend
cd frontend
npm install
npm run dev
```

### Tests
The backend test suite runs against SQLite via `aiosqlite`. Install development
dependencies and run them on the host or in CI:

```bash
cd backend && pip install -r requirements-dev.txt && python -m pytest tests -q
cd frontend && npm run lint && npm run test && npm run build
```

## Documentation

- [AI engineering contract](AGENTS.md) — mandatory rules for AI-assisted work,
  read automatically by Claude Code via `CLAUDE.md`, and directly by Codex and
  Kilo Code. This is the single source of truth for project rules — don't fork
  them into a tool-specific file.
- [Changelog](docs/CHANGELOG.md) — running log of what was built, by which
  tool, and why. Read this first when picking up work in a new session.
- [Secret Rotation](SECRET_ROTATION.md) — what each secret protects and the
  blast radius of rotating it
- [Architecture](docs/ARCHITECTURE.md) — system ownership, dependency direction,
  data flows, and known legacy exceptions
- [Engineering standards](docs/ENGINEERING_STANDARDS.md) — quality gates,
  security, testing, review, and definition of done
- [Architecture audit](docs/AUDIT_2026-09-02.md) — prioritized current-state
  findings and remediation sequence
- [ADR template](docs/decisions/0000-template.md) — record consequential
  architecture decisions
- [Consultant knowledge core](backend/docs/consultant-knowledge-core.md) —
  consultant ingestion, retrieval, indexing, and semantic-search decisions
