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

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Documentation

- [Full Plan](.local/share/kilo/plans/1788202713989-hydenlyne-crew-dms.md) — Architecture, data model, API schema
- [AI Build Guide](AI_BUILD_GUIDE.md) — Coding standards and conventions
- [Extraction Prompts](EXTRACTION_PROMPTS.md) — LLM extraction prompts
