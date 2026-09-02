# Hydenlyne Crew Document Management Platform

A crew document management platform for Hydenlyne's internal team to manage their global consultant workforce.

## Quick Start

### Prerequisites

- Podman + `podman-compose` (Docker + `docker compose` works too)
- Optional: an NVIDIA GPU with CDI configured (`/etc/cdi/nvidia.yaml`) — the
  Ollama container claims `nvidia.com/gpu=all` and falls back to CPU without it

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

Schema migrations run automatically on backend startup (`alembic upgrade head`
from the FastAPI lifespan hook); there is no separate migration step.

### Services

| Service | Port | Description |
|---------|------|-------------|
| PostgreSQL | 5432 | Primary database |
| Redis | 6379 | Task queue broker + rate limiting |
| Qdrant | 6333/6334 | Vector search (the app talks to the REST port, 6333) |
| Meilisearch | 7700 | Keyword search index |
| Ollama | — | LLM inference; internal to the compose network |
| Backend | 8000 | FastAPI + GraphQL |
| Celery Worker | — | Async task processing (`default` queue) |
| Celery GPU Worker | — | Async task processing (`gpu` queue) |
| Celery Beat | — | Scheduled tasks |
| Flower | 5555 | Celery monitoring |
| Frontend | 5173 | React + Vite, served by nginx |

## How This Fits Together

Eleven containers sound like a lot, but they are four groups and you only ever
look at two of them.

| Group | Services | Do you touch it? |
|---|---|---|
| The app | `frontend`, `backend` | Yes — the two URLs above |
| Data stores | `db`, `redis`, `qdrant`, `meilisearch` | No, they just have to be up |
| Background work | `celery_worker`, `celery_gpu_worker`, `celery_beat`, `flower` | Only when an upload does not process |
| Inference | `ollama` | No |

The Celery workers are what make document uploads process on their own. Without
them an upload is accepted and then simply never extracted.

### Always build every service, never one

`podman-compose` builds a **separate image per service**. `backend`,
`celery_worker`, `celery_gpu_worker`, `celery_beat`, and `flower` are five
images produced from the same `backend/Dockerfile`. Building one of them leaves
the other four on stale code, which shows up as a change that works through the
API but not through a background task:

```bash
podman-compose build          # correct
podman-compose build backend  # rebuilds 1 of 5 — the workers keep the old code
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

The frontend is compiled into an nginx image at build time (the dev bind mount
is commented out in `docker-compose.yml`), so a frontend change needs
`podman-compose build && podman-compose up -d`.

### Nothing else may hold the ports

The stack binds 5432, 6379, 5173, and 8000. Anything already on those ports — a
host Postgres, a `npm run dev` server, a stray uvicorn — makes the
corresponding container fail to start. On a rootless-podman host, check for a
systemd user unit holding the database port:

```bash
systemctl --user list-units --type=service | grep -i postgres
```

### Checking the stack

```bash
curl -s localhost:8000/health/all | python3 -m json.tool
```

All five entries should read `healthy`. A `degraded` result names the failing
dependency, and `podman-compose logs <service>` explains why.

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
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/     # Reusable UI components
│   │   ├── pages/          # Route pages
│   │   ├── lib/            # Utilities (Apollo client, etc.)
│   │   └── generated/      # GraphQL codegen output
│   └── package.json
├── docker-compose.yml
└── .env.example
```

## Development

The containerised stack above is the supported way to run this. Running a
service directly on the host is only worth it for a fast edit loop on one
component, and it needs the matching container stopped first so the port is
free.

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

The backend test suite runs against SQLite via `aiosqlite`. That package is not
listed in `requirements.txt` and there is no dev-requirements file, so the tests
only run where it happens to be installed — `pip install aiosqlite` first, and
run them on the host rather than inside a container.

```bash
cd backend && python -m pytest tests -q
cd frontend && npm run lint && npm run build
```

## Documentation

- [Secret Rotation](SECRET_ROTATION.md) — what each secret protects and the
  blast radius of rotating it

The architecture and data-model plan lives outside this repository, at
`~/.local/share/kilo/plans/1788202713989-hydenlyne-crew-dms.md`, so it does not
travel with a clone. `AI_BUILD_GUIDE.md` and `EXTRACTION_PROMPTS.md` were
previously linked here but have never existed in the tree.
