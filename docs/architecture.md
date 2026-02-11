# ETL Studio Architecture

## System Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              ETL Studio                                       │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│   ┌─────────────┐         ┌─────────────┐         ┌─────────────┐           │
│   │   Browser   │  HTTP   │   Frontend  │  HTTP   │   Backend   │           │
│   │   (User)    │◄───────►│  (Next.js)  │◄───────►│  (FastAPI)  │           │
│   └─────────────┘   SSE   └─────────────┘         └──────┬──────┘           │
│        │                        │                         │                   │
│        │                        │                         │ enqueue           │
│        │                        │                         ▼                   │
│        │                        │                  ┌─────────────┐            │
│        │                        │                  │   Worker    │            │
│        │                        │                  │  (Celery)   │            │
│        │                        │                  └──────┬──────┘            │
│        │                        │                         │                   │
│        │                        │                         │ read CSV          │
│        │                        │                         │ write records     │
│        │                        │                         ▼                   │
│   ┌────┴────┐             ┌─────┴─────┐             ┌─────────────┐           │
│   │ Postgres │◄────────────│   Redis   │◄────────────│ S3 / Disk   │           │
│   │ (DB)     │             │ (Broker)  │             │ (Uploads)   │           │
│   └──────────┘             └───────────┘             └─────────────┘           │
│                                                                               │
│   Optional: Jaeger (traces), MinIO (S3), Flower (Celery UI)                  │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Data Flow

1. **Upload** → User uploads CSV via frontend. Backend validates (size, type, columns), streams to S3 or disk, stores metadata on `ImportRun` (DRAFT).
2. **Mapping** → User maps CSV columns to canonical fields (date, campaign, channel, spend, clicks, conversions). Stored on `ImportDataset`.
3. **Start** → User clicks "Start import". Backend enqueues Celery task `etl.process_import_run`, sets run status QUEUED.
4. **Worker** → Celery picks up task, loads CSV from S3 or disk, applies mapping and validation rules, writes `ImportRecord` (valid) and `ImportRowError` (invalid). Updates run progress.
5. **SSE** → Frontend connects to `/api/runs/:id/events`, receives `run.snapshot`, `run.progress`, `run.completed`.
6. **Results** → User views records table, exports CSV, checks analytics.

## Key Decisions

### FastAPI + Celery + Redis
- **FastAPI**: Async HTTP, native SSE support, Pydantic validation, OpenAPI docs.
- **Celery**: Proven async job queue, retries with backoff, DLQ, integrates with Redis.
- **Redis**: Lightweight broker, also usable for caching/sessions later.

### S3-Compatible Storage
- **Local dev**: MinIO (S3-compatible). Same code path as production S3.
- **Production**: AWS S3 or any S3-compatible store (e.g., GCS, MinIO).
- **Fallback**: Disk storage when S3 not configured.

### Security
- **Upload limits**: 10MB max, CSV-only, column/field limits (MAX_COLUMNS, MAX_FIELD_CHARS, MAX_ROWS).
- **RBAC**: Org-scoped (OWNER/ADMIN/MEMBER). Dataset/run access filtered by `org_id`.
- **SSE**: Per-user connection cap, timeout, no traceback leakage.
- **Duplicate detection**: SHA256 prevents re-upload of identical files.

### Observability
- **OpenTelemetry**: Optional tracing to Jaeger. Spans for HTTP, Celery, SSE.
- **Flower**: Celery task monitor (dev).
