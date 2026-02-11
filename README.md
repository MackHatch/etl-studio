# ETL Studio

A production-ready ETL pipeline for importing and analyzing marketing data. Upload CSV files, map columns to canonical fields, process with retries and DLQ, and view analytics dashboards.

## Features

- **CSV Import Pipeline**: Upload CSV → map columns → process → view results
- **Column Mapping**: Configure mappings from CSV columns to canonical fields (date, campaign, channel, spend, clicks, conversions)
- **Robust Processing**: Retries with exponential backoff, dead-letter queue (DLQ) for failed runs, attempt history
- **Real-time Progress**: Server-Sent Events (SSE) for live run progress updates
- **Analytics Dashboard**: Summaries by day/channel/campaign, spend anomalies detection
- **Admin Dashboard**: Monitor all runs across datasets, filter by status/DLQ, live updates
- **OpenTelemetry Tracing**: Distributed tracing across backend, worker, and SSE streams (optional)
- **Type Safety**: Full TypeScript frontend, Python type hints, mypy checks
- **Security Hardening**: Upload validation, size limits, duplicate detection, RBAC, SSE rate limiting

## Architecture

See [docs/architecture.md](docs/architecture.md) for a detailed system diagram, data flow, and key decisions.

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│   Browser   │──────│   Frontend  │──────│   Backend   │
│  (Next.js)  │ SSE  │  (Next.js)  │ HTTP │  (FastAPI)  │
└─────────────┘      └─────────────┘      └─────────────┘
                                                      │
                                                      │ enqueue
                                                      ▼
                                              ┌─────────────┐
                                              │   Worker    │
                                              │  (Celery)   │
                                              └─────────────┘
                                                      │
                                                      │
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│  Postgres   │◄─────│   Redis     │◄─────│  Jaeger    │
│  (Database) │      │  (Broker)   │      │  (Traces)  │
└─────────────┘      └─────────────┘      └─────────────┘
```

**Flow:**
1. User uploads CSV → backend creates run (DRAFT)
2. User configures mapping → backend saves mapping
3. User starts run → backend enqueues Celery task
4. Worker processes CSV → writes records/errors to DB
5. Frontend streams progress via SSE
6. User views results, exports CSV, checks analytics

## Structure

- `backend/` – FastAPI application (Python 3.12) using SQLAlchemy 2.0 (async), Alembic, Postgres, and JWT auth.
- `worker/` – Celery worker using Redis as a broker, sharing models with the backend.
- `shared/` – Shared Python package for database models and common logic (used by both backend and worker).
- `frontend/` – Next.js (App Router, TypeScript) frontend with Tailwind CSS and TanStack Query.

## Tech Stack

- **Backend**
  - Python 3.12
  - FastAPI + Pydantic
  - SQLAlchemy 2.0 (async) + Alembic
  - Postgres
  - Server-Sent Events (SSE) endpoints for job progress
  - JWT auth (email/password) for MVP

- **Worker**
  - Celery
  - Redis broker
  - Shared database models from the `python/` package

- **Frontend**
  - Next.js (App Router) + TypeScript
  - Tailwind CSS
  - TanStack Query
  - SSE client for streaming job progress

## Quickstart

### Prerequisites

- **Docker** and **Docker Compose** (easiest path)
- **Node.js** 20+ (for frontend, if running locally)
- **Python** 3.12 + **uv** (for migrations/seeding, if not using Docker)

### Option A: Docker (recommended)

**First-time setup:** Reset the database, run migrations, and seed an admin user plus demo data:

```bash
git clone <repo-url>
cd etl-studio
make reset
```

This will:

1. Start Postgres and Redis
2. Run database migrations
3. Create admin user (`admin@example.com` / `adminpassword`) and demo dataset

**Start the full stack:**

```bash
make dev
```

This brings up backend, frontend, worker, MinIO, Flower, and optional tracing (Jaeger).

**Open the app:** http://localhost:3000

**Login:** `admin@example.com` / `adminpassword`

---

**Skip `make reset`?** If Postgres/Redis are already running and migrations are applied, you can run `make dev` directly. Without `make reset`, you may need to create a user manually or ensure your database has seed data.

### Option B: Docker Compose (no Makefile)

```bash
git clone <repo-url>
cd etl-studio
docker compose up -d postgres redis
# Wait ~5 seconds for Postgres to be ready
docker compose run --rm backend alembic upgrade head
DATABASE_URL=postgresql+asyncpg://etl_user:etl_password@localhost:5432/etl_db \
REDIS_URL=redis://localhost:6379/0 \
JWT_SECRET=dev-secret \
uv run --package backend python backend/scripts/reset_and_seed.py
docker compose up --build
```

Then open http://localhost:3000 and log in with `admin@example.com` / `adminpassword`.

### Key URLs

| Service       | URL                          |
|---------------|------------------------------|
| App           | http://localhost:3000        |
| API docs      | http://localhost:8000/docs   |
| Flower (Celery)| http://localhost:5555        |
| MinIO console | http://localhost:9001        |
| Jaeger (traces)| http://localhost:16686      |

### Demo credentials

- **Admin:** `admin@example.com` / `adminpassword` (created by `make reset` or bootstrap)
- **Demo user:** `demo@example.com` / `demo123` (created when `SEED_DEMO=true`)

### What to try first

1. Log in → **Datasets** → Create a dataset
2. Upload `frontend/public/sample.csv` (or any CSV with date, campaign, channel, spend)
3. Map columns → Save → Start import
4. Watch progress → View results → Check **Analytics**
5. Compare runs: use **Compare runs** on a dataset with multiple completed runs

### Local Development (without Docker)

See [Local Development](#local-development) for running backend, worker, and frontend locally with `uv` and `npm`.

## Prerequisites

- **Node.js**: 20.x (see `.nvmrc`)
- **npm**: latest (for the frontend)
- **Python**: 3.12 (for backend, worker, and shared package)
- **Docker & Docker Compose** (optional, for full stack)

## Environment Configuration

Copy the root `.env.example` to `.env` and adjust values as needed:

```bash
cp .env.example .env
```

### Environment Variables Reference

**Database:**
- `POSTGRES_USER` – Postgres username (default: `etl_user`)
- `POSTGRES_PASSWORD` – Postgres password (**required in production**)
- `POSTGRES_DB` – Database name (default: `etl_db`)
- `DATABASE_URL` – Full async SQLAlchemy URL (e.g. `postgresql+asyncpg://user:password@postgres:5432/db`). If not set, constructed from POSTGRES_* vars.

**Redis:**
- `REDIS_URL` – Redis connection URL (default: `redis://redis:6379/0`)

**Backend:**
- `JWT_SECRET` – Secret for JWT token signing (**required in production**)
- `BACKEND_PORT` – Backend port (default: `8000`, dev only)
- `CORS_ORIGINS` – Comma-separated allowed origins (default: `http://localhost:3000`)
- `ADMIN_EMAIL`, `ADMIN_PASSWORD` – Bootstrap admin user (created if no users exist)
- `ADMIN_NAME` – Admin display name (optional)
- `SEED_DEMO` – `true` to seed demo dataset and run (default: `false`)

**Frontend:**
- `FRONTEND_PORT` – Frontend port (default: `3000`, dev only)
- `NEXT_PUBLIC_API_URL` – Public API URL for frontend (default: `http://localhost:8000`). In production, set to your public backend URL.

**OpenTelemetry (optional):**
- `OTEL_ENABLED` – `true` to enable tracing (default: `false`)
- `OTEL_EXPORTER_OTLP_ENDPOINT` – OTLP HTTP endpoint (default: `http://otel-collector:4318`)
- `OTEL_SERVICE_NAME` – Service name (defaults: `etl-backend`, `etl-worker`)
- `TRACE_ID_HASH_SECRET` – Secret for hashing IDs in traces (optional)

**Storage (S3 / MinIO):**
- `STORAGE_BACKEND` – `"s3"` or `"disk"` (default: `s3` if S3 vars present, else `disk`)
- `S3_ENDPOINT_URL` – MinIO: `http://minio:9000` (compose) / `http://localhost:9000` (local)
- `S3_ACCESS_KEY`, `S3_SECRET_KEY` – MinIO: same as `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD`
- `S3_BUCKET` – Bucket name (default: `etl-uploads`)
- `S3_REGION` – AWS region (default: `us-east-1`, dummy for MinIO)
- `PRESIGN_EXPIRES_SECONDS` – Presigned download URL expiry (default: `900` = 15 min)

**MinIO console:** http://localhost:9001 — login with `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` (default: `minioadmin` / `minioadmin`).

**Security Limits:**
- `MAX_UPLOAD_BYTES` – Maximum file upload size in bytes (default: `10485760` = 10MB)
- `MAX_COLUMNS` – Maximum CSV columns allowed (default: `200`)
- `MAX_FIELD_CHARS` – Maximum characters per field value (default: `10000`)
- `MAX_ROWS` – Maximum rows per import run (default: `500000`)
- `SSE_MAX_CONCURRENT_PER_USER` – Maximum concurrent SSE streams per user (default: `3`)
- `SSE_MAX_DURATION_SECONDS` – Maximum SSE stream duration in seconds (default: `600` = 10 minutes)

Each of `backend/`, `worker/`, and `frontend/` will also have an `.env.example` with a subset of these values relevant to that service.

## Security

### Upload Protection

- **File Size Limits**: Enforced at FastAPI level (default: 10MB). Files exceeding limit are rejected before processing.
- **File Validation**: Extension and content-type checks ensure only CSV files are accepted.
- **Column Limits**: Maximum 200 columns per CSV. Column names limited to 200 characters.
- **Field Length Limits**: Individual field values limited to 10,000 characters to prevent CSV "bombs".
- **Row Limits**: Maximum 500,000 rows per run to prevent runaway jobs.
- **Duplicate Detection**: SHA256 checksums prevent duplicate uploads (same file content, same dataset). Returns 409 Conflict with existing run ID.

### Authorization

- **RBAC**: All dataset/run endpoints verify ownership (`dataset.created_by_user_id == current_user.id`).
- **Admin Bypass**: ADMIN role users can access all datasets/runs.
- **Admin Endpoints**: Admin-only endpoints (e.g., `/api/admin/runs`) require ADMIN role.
- **404 on Unauthorized**: Unauthorized access returns 404 (not 403) to prevent information leakage.

### SSE Safety

- **Connection Limits**: Maximum 3 concurrent SSE streams per user (configurable).
- **Timeouts**: SSE streams automatically close after 10 minutes (configurable).
- **Authorization**: SSE endpoints verify ownership before streaming (404 if unauthorized).
- **Heartbeats**: Regular heartbeat messages keep connections alive and detect disconnects.

### Error Handling

- **No Traceback Leakage**: API responses never include internal tracebacks. Only user-friendly error messages.
- **Truncated Tracebacks**: Full tracebacks stored only in `ImportRunAttempt` table (for debugging), truncated to 8000 characters.
- **Error Sanitization**: All error messages are sanitized before returning to clients.

### Best Practices

- Set strong `JWT_SECRET` and `POSTGRES_PASSWORD` in production.
- Configure `CORS_ORIGINS` to your frontend domain(s).
- Review security limits (`MAX_*` env vars) based on your use case.
- Monitor SSE connection counts and adjust `SSE_MAX_CONCURRENT_PER_USER` if needed.
- Regularly audit dataset ownership and admin users.

## Local Development

### 1. Python dependencies (uv workspace)

This repo uses [uv](https://docs.astral.sh/uv/) for Python dependency management. From the repo root:

```bash
uv sync
```

This will install dependencies for the workspace projects (`python/`, `backend/`, `worker/`).

**Backend (run from `backend/` directory):**

```bash
cd backend
uv run uvicorn app.main:app --reload --port 8000   # or: uv run dev
uv run alembic upgrade head                         # or: uv run migrate
uv run alembic revision --autogenerate -m "..."    # or: uv run revision "message"
```

**Worker (from repo root):**

```bash
uv run --package worker celery -A worker_main.celery_app worker --loglevel=info --concurrency=2
```

### How it works

**SSE (Server-Sent Events):**
- Backend exposes `/api/runs/:id/events` that streams progress updates
- Frontend connects via `fetch()` streaming and parses SSE messages
- Updates include: `run.snapshot`, `run.progress`, `run.completed`, `run.heartbeat`
- Automatically reconnects on disconnect with exponential backoff

**Worker Processing:**
- Backend enqueues Celery task `etl.process_import_run` when user starts a run
- Worker picks up task, reads CSV, applies mapping, validates rows
- Writes `ImportRecord` for valid rows, `ImportRowError` for invalid rows
- Updates run progress (`processed_rows`, `success_rows`, `error_rows`) periodically
- On completion: sets run status to `SUCCEEDED` or `FAILED`
- Retries transient errors (DB/file issues) up to 3 times with exponential backoff
- Failed runs after retries go to DLQ (dead-letter queue) for manual review

### 2. Frontend dependencies

From `frontend/`:

```bash
cd frontend
npm install
npm run dev
```

The Next.js dev server will run on `http://localhost:3000` by default.

**E2E tests (Playwright):**

With the full stack running (frontend, backend, worker), run Playwright E2E tests from the frontend directory:

```bash
cd frontend
npx playwright install chromium   # first time: install browser
npm run test:e2e
```

Use `E2E_LOGIN_EMAIL` and `E2E_LOGIN_PASSWORD` env vars to override credentials (default: `admin@example.com` / `adminpassword` to match CI bootstrap).

### 3. Running with Docker

Build and start the full stack with Docker Compose:

```bash
docker compose up --build
```

Services:

- `backend` – FastAPI app on `http://localhost:8000`
- `frontend` – Next.js app on `http://localhost:3000`
- `postgres` – Postgres database on port `5432`
- `redis` – Redis broker on port `6379`
- `worker` – Celery worker
- `flower` – Celery monitoring UI on `http://localhost:5555`
- `otel-collector` – OpenTelemetry collector (if tracing enabled) on ports `4318` (HTTP), `4317` (gRPC)
- `jaeger` – Jaeger UI (if tracing enabled) on `http://localhost:16686`

Postgres and Redis services will have health checks defined in `docker-compose.yml`, and application services will depend on them.

**Flower (Celery UI):**
- View active tasks, task history, worker status
- Access at: http://localhost:5555
- No auth required (dev only; secure in production)

## Production Deployment

### Docker Compose Production

Use `docker-compose.prod.yml` for production deployments:

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

**Services:**
- `postgres` – Postgres database with persistent volume
- `redis` – Redis broker with persistent volume
- `migrate` – One-time migration job (runs `alembic upgrade head` before backend starts)
- `backend` – FastAPI app (healthcheck: `/api/health`)
- `worker` – Celery worker (shares upload volume with backend)
- `frontend` – Next.js server (production build)
- `flower` – Celery monitoring UI (optional, port 5555)
- `nginx` – Reverse proxy (port 80) routing `/api/*` to backend, `/*` to frontend

**Key differences from dev:**
- Nginx reverse proxy as single entrypoint
- SSE endpoints configured with `proxy_buffering off` for real-time streaming
- Persistent volumes for postgres, redis, and uploads
- Healthchecks on all services
- Non-root users in containers
- Migration runs automatically before backend starts

**Migration Strategy:**
The `migrate` service runs `alembic upgrade head` before the backend starts. The backend depends on `migrate` with `condition: service_completed_successfully`, ensuring migrations complete before the API accepts requests.

**Upload Storage:**
Uploads are stored in a Docker volume `upload_data` mounted at `/app/backend/storage` in both backend and worker containers. This ensures worker can read CSV files uploaded by the backend.

**Environment Variables (Production):**

Required:
- `POSTGRES_PASSWORD` – Postgres password (no default)
- `JWT_SECRET` – Secret for JWT signing (no default)
- `DATABASE_URL` – Full asyncpg URL (or set POSTGRES_USER/POSTGRES_PASSWORD/POSTGRES_DB)
- `REDIS_URL` – Redis connection URL
- `NEXT_PUBLIC_API_URL` – Public URL for frontend API calls (e.g. `https://api.example.com`)

Optional:
- `ADMIN_EMAIL`, `ADMIN_PASSWORD` – Bootstrap admin user
- `SEED_DEMO` – `true` to seed demo dataset
- `CORS_ORIGINS` – Comma-separated allowed origins (default: `http://localhost:3000`)
- `OTEL_ENABLED`, `OTEL_EXPORTER_OTLP_ENDPOINT`, etc. – OpenTelemetry config

**Nginx Configuration:**
- Routes `/api/*` → backend:8000
- Routes `/*` → frontend:3000
- Disables buffering for SSE endpoints (`/api/*/events`)
- Sets appropriate headers for proxying

**Access:**
- Application: http://localhost (via nginx)
- Flower: http://localhost:5555 (if enabled)
- Backend direct: http://localhost:8000 (internal only, via nginx)

### Production Checklist

- [ ] Set strong `POSTGRES_PASSWORD` and `JWT_SECRET`
- [ ] Configure `NEXT_PUBLIC_API_URL` to your public domain
- [ ] Set `CORS_ORIGINS` to your frontend domain(s)
- [ ] Review nginx config (`ops/nginx.conf`) for your domain/SSL
- [ ] Ensure volumes are backed up (postgres_data, redis_data, upload_data)
- [ ] Set up SSL/TLS (add certs to nginx or use external load balancer)
- [ ] Configure firewall rules (expose only port 80/443)
- [ ] Set up monitoring/alerting for healthchecks
- [ ] Review worker concurrency based on load
- [ ] Configure log rotation for containers

## OpenTelemetry tracing (optional)

When enabled, the backend and worker export traces via OTLP to an OpenTelemetry Collector, which forwards them to Jaeger for viewing.

### Enable tracing

Set these environment variables (e.g. in `.env` or in docker-compose `environment`):

- **`OTEL_ENABLED`** – `true` to enable tracing (default: `false`).
- **`OTEL_EXPORTER_OTLP_ENDPOINT`** – OTLP HTTP endpoint. In Docker: `http://otel-collector:4318`. For local dev with a collector on the host: `http://localhost:4318`.
- **`OTEL_SERVICE_NAME`** – Optional. Defaults to `etl-backend` (backend) or `etl-worker` (worker).
- **`TRACE_ID_HASH_SECRET`** – Optional. Secret used to hash run/dataset IDs in span attributes (no raw IDs in traces). Set to a stable secret in production.

Example for local development with Docker collector and Jaeger:

```bash
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
TRACE_ID_HASH_SECRET=your-secret-here
```

### Jaeger UI

With `docker compose up`, the stack includes:

- **otel-collector** – receives OTLP on port **4318** (HTTP) and **4317** (gRPC), forwards traces to Jaeger.
- **jaeger** – all-in-one with OTLP enabled; UI on port **16686**.

Open the Jaeger UI at:

**http://localhost:16686**

### What to look for in Jaeger

1. **Service** – Select `etl-backend` or `etl-worker`.
2. **Trace flow** – Upload CSV → create run (DRAFT) → configure mapping → **Start import** (run goes QUEUED, task enqueued). The backend span for `POST /api/runs/:id/start` and the worker span for `etl.process_import_run` can be correlated when trace context is propagated (same trace ID).
3. **SSE** – Subscribing to run progress (`GET /api/runs/:id/events`) creates spans named `sse.run.events` with attributes `run.id_hash` and `dataset.id_hash` (hashed). Events: snapshot, progress, completed.
4. **Admin** – Admin runs list SSE (`GET /api/admin/runs/events`) creates spans named `sse.admin.runs.events` with events snapshot, changed, heartbeat.

Use **Find Traces** and filter by service or operation to see the full request → enqueue → task → SSE flow.

## Demo Walkthrough

When running in development mode, the frontend shows a **Demo Walkthrough** panel with:

- Demo credentials: `demo@example.com` / `demo123`
- Step-by-step guide: Create dataset → Upload CSV → Configure mapping → Start run → Watch progress → View results → Analytics
- Quick copy buttons for curl commands (login, create dataset, upload)
- Download sample CSV button

To seed demo data automatically, set `SEED_DEMO=true` in your `.env` file. This creates:
- Demo dataset: "Demo: Marketing Spend"
- A completed run with 3 valid records and 2 row errors

## API Examples

**Login:**
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@example.com","password":"demo123"}'
```

**Create dataset:**
```bash
curl -X POST http://localhost:8000/api/datasets \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"name":"My Dataset","description":"Description"}'
```

**Upload CSV:**
```bash
curl -X POST http://localhost:8000/api/datasets/DATASET_ID/uploads \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@sample.csv"
```

See the Demo Walkthrough panel in the UI for more examples.

## Screenshots

See [docs/screenshots/README.md](docs/screenshots/README.md) for screenshots and capture instructions.

