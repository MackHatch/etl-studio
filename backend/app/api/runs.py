import csv
import io
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import get_current_user
from app.core.org_context import require_active_org, require_org_member
from app.core.sse import stream_run_events
from app.core.storage import read_csv_header, read_csv_header_for_run, presign_download_url, resolve_run_file_path
from app.core.celery_app import enqueue_import_run
from app.db import get_session
from app.models.user import User
from app.models.imports import (
    ImportRun,
    ImportRunAttempt,
    ImportRowError,
    ImportRecord,
    ImportDataset,
    ImportRunStatus,
    DatasetSchemaVersion,
)

router = APIRouter(prefix="/runs", tags=["runs"])

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}

MAX_ERRORS = 50


def err(code: str, message: str, status_code: int = 400, details: dict | None = None) -> HTTPException:
    detail = {"error": {"code": code, "message": message}}
    if details is not None:
        detail["error"]["details"] = details
    return HTTPException(status_code=status_code, detail=detail)


class RowErrorResponse(BaseModel):
    id: UUID
    run_id: UUID
    row_number: int
    field: str | None
    message: str
    raw_row: dict | None
    created_at: str

    class Config:
        from_attributes = True


class RunDetailResponse(BaseModel):
    id: UUID
    dataset_id: UUID
    status: str
    progress_percent: int
    total_rows: int | None
    processed_rows: int
    success_rows: int
    error_rows: int
    created_at: str
    started_at: str | None
    finished_at: str | None
    error_summary: str | None
    attempt_count: int
    dlq: bool
    last_error: str | None
    errors: list[RowErrorResponse]

    class Config:
        from_attributes = True


class AttemptResponse(BaseModel):
    id: UUID
    run_id: UUID
    attempt_number: int
    status: str
    started_at: str
    finished_at: str | None
    error_message: str | None
    traceback: str | None
    created_at: str

    class Config:
        from_attributes = True


class AttemptsListResponse(BaseModel):
    items: list[AttemptResponse]


class RecordResponse(BaseModel):
    id: UUID
    run_id: UUID
    row_number: int
    date: str
    campaign: str
    channel: str
    spend: str
    clicks: int
    conversions: int
    created_at: str

    class Config:
        from_attributes = True


class RecordsListResponse(BaseModel):
    items: list[RecordResponse]
    page: int
    page_size: int
    total: int


async def _run_in_active_org(
    session: AsyncSession, run_id: UUID, org_id: UUID
) -> ImportRun | None:
    """Return ImportRun if it belongs to a dataset in the specified org, else None."""
    result = await session.execute(
        select(ImportRun)
        .join(ImportDataset, ImportRun.dataset_id == ImportDataset.id)
        .where(
            ImportRun.id == run_id,
            ImportDataset.org_id == org_id,
        )
    )
    return result.scalar_one_or_none()


class RunHeaderResponse(BaseModel):
    columns: list[str]


class RunDownloadResponse(BaseModel):
    url: str
    expires_in_seconds: int


@router.get("/{run_id}/download", response_model=RunDownloadResponse)
async def get_run_download(
    run_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get presigned download URL for the uploaded CSV (S3) or relative path (disk)."""
    from app.config import settings

    org_id, _ = await require_active_org(current_user, session)
    run = await _run_in_active_org(session, run_id, org_id)
    if not run:
        raise err("not_found", "Run not found", status_code=404)
    if run.file_storage == "s3" and run.s3_bucket and run.s3_key:
        url = presign_download_url(run.s3_bucket, run.s3_key)
        if url:
            return RunDownloadResponse(url=url, expires_in_seconds=settings.PRESIGN_EXPIRES_SECONDS)
        raise err("storage_error", "S3 not configured", status_code=500)
    if run.file_storage == "disk" and run.file_path:
        url = f"/api/runs/{run_id}/download/file"
        return RunDownloadResponse(url=url, expires_in_seconds=3600)
    raise err("no_file", "Run has no file", status_code=400)


@router.get("/{run_id}/download/file")
async def stream_run_download(
    run_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Stream the raw uploaded CSV file (disk storage only)."""
    from fastapi.responses import FileResponse

    org_id, _ = await require_active_org(current_user, session)
    run = await _run_in_active_org(session, run_id, org_id)
    if not run:
        raise err("not_found", "Run not found", status_code=404)
    if run.file_storage != "disk" or not run.file_path:
        raise err("no_file", "Direct download only for disk storage", status_code=400)
    path = resolve_run_file_path(run.file_path)
    if not path.exists():
        raise err("file_not_found", "File not found", status_code=404)
    return FileResponse(
        path,
        media_type="text/csv",
        filename=f"run-{run_id}.csv",
    )


@router.get("/{run_id}/header", response_model=RunHeaderResponse)
async def get_run_header(
    run_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Return CSV header columns for the run's uploaded file."""
    org_id, _ = await require_active_org(current_user, session)
    run = await _run_in_active_org(session, run_id, org_id)
    if not run:
        raise err("not_found", "Run not found", status_code=404)
    if run.file_storage == "disk" and not run.file_path:
        raise err("no_file", "Run has no file", status_code=400)
    if run.file_storage == "s3" and not (run.s3_bucket and run.s3_key):
        raise err("no_file", "Run has no file", status_code=400)
    try:
        columns = read_csv_header_for_run(run)
    except FileNotFoundError as e:
        raise err("file_not_found", str(e), status_code=404)
    except ValueError as e:
        raise err("invalid_file", str(e), status_code=400)
    return RunHeaderResponse(columns=columns)


@router.get("/{run_id}/attempts", response_model=AttemptsListResponse)
async def get_run_attempts(
    run_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """List attempt history for a run. Requires membership in dataset's org."""
    org_id, _ = await require_active_org(current_user, session)
    run = await _run_in_active_org(session, run_id, org_id)
    if not run:
        raise err("not_found", "Run not found", status_code=404)
    result = await session.execute(
        select(ImportRunAttempt)
        .where(ImportRunAttempt.run_id == run_id)
        .order_by(ImportRunAttempt.attempt_number.desc())
    )
    attempts = result.scalars().all()
    return AttemptsListResponse(
        items=[
            AttemptResponse(
                id=a.id,
                run_id=a.run_id,
                attempt_number=a.attempt_number,
                status=a.status.value,
                started_at=a.started_at.isoformat(),
                finished_at=a.finished_at.isoformat() if a.finished_at else None,
                error_message=a.error_message,
                traceback=a.traceback,
                created_at=a.created_at.isoformat(),
            )
            for a in attempts
        ]
    )


@router.post("/{run_id}/retry")
async def retry_run(
    run_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Re-queue a failed or DLQ run. Sets dlq=false, status=QUEUED, enqueues job."""
    org_id, _ = await require_active_org(current_user, session)
    run = await _run_in_active_org(session, run_id, org_id)
    if not run:
        raise err("not_found", "Run not found", status_code=404)
    if run.status != ImportRunStatus.FAILED and not run.dlq:
        raise err(
            "invalid_state",
            "Retry only allowed for runs with status FAILED or in DLQ (dlq=true)",
            status_code=400,
        )
    run.status = ImportRunStatus.QUEUED
    run.dlq = False
    await session.commit()
    enqueue_import_run(str(run.id))
    return {"ok": True, "run_id": str(run.id)}


@router.post("/{run_id}/start")
async def start_run(
    run_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Set run to QUEUED and enqueue Celery task. Run must be DRAFT and dataset must have mapping."""
    org_id, _ = await require_active_org(current_user, session)
    result = await session.execute(
        select(ImportRun)
        .join(ImportDataset, ImportRun.dataset_id == ImportDataset.id)
        .where(
            ImportRun.id == run_id,
            ImportDataset.org_id == org_id,
        )
        .options(selectinload(ImportRun.dataset))
    )
    run = result.scalar_one_or_none()
    if not run:
        raise err("not_found", "Run not found", status_code=404)
    if run.status != ImportRunStatus.DRAFT:
        raise err("invalid_state", f"Run must be DRAFT to start (current: {run.status.value})", status_code=400)
    if not run.dataset.mapping_json:
        raise err("mapping_required", "Dataset mapping is required. Save mapping first.", status_code=400)
    # Set schema_version if not already set
    if run.schema_version is None:
        run.schema_version = run.dataset.active_schema_version
    run.status = ImportRunStatus.QUEUED
    await session.flush()
    await session.commit()
    enqueue_import_run(str(run.id))
    return {"ok": True, "run_id": str(run.id)}


@router.get("/{run_id}/events")
async def stream_run_events_endpoint(
    run_id: UUID,
    current_user: User = Depends(get_current_user),
):
    """Stream SSE events for run progress. Authorization checked in stream_run_events."""
    from fastapi.responses import StreamingResponse

    return StreamingResponse(
        stream_run_events(run_id, current_user.id),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


class RerunRequest(BaseModel):
    schema_version: int | None = None


@router.post("/{run_id}/rerun", response_model=RunSummaryResponse)
async def rerun(
    run_id: UUID,
    body: RerunRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Create a new run from an existing run's file, optionally with a different schema version."""
    org_id, _ = await require_active_org(current_user, session)
    # Get original run
    result = await session.execute(
        select(ImportRun)
        .join(ImportDataset, ImportRun.dataset_id == ImportDataset.id)
        .where(
            ImportRun.id == run_id,
            ImportDataset.org_id == org_id,
        )
        .options(selectinload(ImportRun.dataset))
    )
    original_run = result.scalar_one_or_none()
    if not original_run:
        raise err("not_found", "Run not found", status_code=404)

    has_file = (
        (original_run.file_storage == "s3" and original_run.s3_bucket and original_run.s3_key)
        or (original_run.file_storage == "disk" and original_run.file_path)
    )
    if not has_file:
        raise err("no_file", "Original run has no file", status_code=400)

    # Determine schema version
    schema_version = body.schema_version
    if schema_version is None:
        schema_version = original_run.dataset.active_schema_version

    # Verify schema version exists
    result = await session.execute(
        select(DatasetSchemaVersion).where(
            DatasetSchemaVersion.dataset_id == original_run.dataset_id,
            DatasetSchemaVersion.version == schema_version,
        )
    )
    schema = result.scalar_one_or_none()
    if not schema:
        raise err("schema_not_found", f"Schema version {schema_version} not found", status_code=404)

    # Create new run (copy file metadata for disk or S3)
    new_run = ImportRun(
        dataset_id=original_run.dataset_id,
        status=ImportRunStatus.DRAFT,
        file_storage=original_run.file_storage or "disk",
        file_path=original_run.file_path,
        s3_bucket=original_run.s3_bucket,
        s3_key=original_run.s3_key,
        file_sha256=original_run.file_sha256,
        file_size_bytes=original_run.file_size_bytes,
        schema_version=schema_version,
    )
    session.add(new_run)
    await session.flush()
    await session.commit()
    await session.refresh(new_run)

    return RunSummaryResponse(
        id=new_run.id,
        dataset_id=new_run.dataset_id,
        status=new_run.status.value,
        progress_percent=new_run.progress_percent,
        total_rows=new_run.total_rows,
        processed_rows=new_run.processed_rows,
        success_rows=new_run.success_rows,
        error_rows=new_run.error_rows,
        created_at=new_run.created_at.isoformat(),
        started_at=new_run.started_at.isoformat() if new_run.started_at else None,
        finished_at=new_run.finished_at.isoformat() if new_run.finished_at else None,
        schema_version=new_run.schema_version,
    )


@router.get("/{run_id}", response_model=RunDetailResponse)
async def get_run(
    run_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    org_id, _ = await require_active_org(current_user, session)
    result = await session.execute(
        select(ImportRun)
        .join(ImportDataset, ImportRun.dataset_id == ImportDataset.id)
        .where(
            ImportRun.id == run_id,
            ImportDataset.org_id == org_id,
        )
        .options(selectinload(ImportRun.errors))
    )
    run = result.scalar_one_or_none()
    if not run:
        raise err("not_found", "Run not found", status_code=404)

    errors = sorted(run.errors, key=lambda e: (e.row_number, e.created_at))[:MAX_ERRORS]
    return RunDetailResponse(
        id=run.id,
        dataset_id=run.dataset_id,
        status=run.status.value,
        progress_percent=run.progress_percent,
        total_rows=run.total_rows,
        processed_rows=run.processed_rows,
        success_rows=run.success_rows,
        error_rows=run.error_rows,
        created_at=run.created_at.isoformat(),
        started_at=run.started_at.isoformat() if run.started_at else None,
        finished_at=run.finished_at.isoformat() if run.finished_at else None,
        error_summary=run.error_summary,
        attempt_count=run.attempt_count,
        dlq=run.dlq,
        last_error=run.last_error,
        errors=[
            RowErrorResponse(
                id=e.id,
                run_id=e.run_id,
                row_number=e.row_number,
                field=e.field,
                message=e.message,
                raw_row=e.raw_row,
                created_at=e.created_at.isoformat(),
            )
            for e in errors
        ],
    )


@router.get("/{run_id}/records", response_model=RecordsListResponse)
async def get_run_records(
    run_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    search: str | None = Query(None, alias="search"),
    channel: str | None = Query(None),
    min_spend: float | None = Query(None, alias="minSpend"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
):
    """List import records for a run with optional filters and pagination."""
    org_id, _ = await require_active_org(current_user, session)
    run = await _run_in_active_org(session, run_id, org_id)
    if not run:
        raise err("not_found", "Run not found", status_code=404)

    base = select(ImportRecord).where(ImportRecord.run_id == run_id)
    if search:
        base = base.where(ImportRecord.campaign.ilike(f"%{search}%"))
    if channel:
        base = base.where(ImportRecord.channel == channel)
    if min_spend is not None:
        base = base.where(ImportRecord.spend >= min_spend)

    total = (await session.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0

    q = base.order_by(ImportRecord.row_number).offset((page - 1) * page_size).limit(page_size)
    result = await session.execute(q)
    records = result.scalars().all()

    return RecordsListResponse(
        items=[
            RecordResponse(
                id=r.id,
                run_id=r.run_id,
                row_number=r.row_number,
                date=r.date.isoformat(),
                campaign=r.campaign,
                channel=r.channel,
                spend=str(r.spend),
                clicks=r.clicks,
                conversions=r.conversions,
                created_at=r.created_at.isoformat(),
            )
            for r in records
        ],
        page=page,
        page_size=page_size,
        total=total,
    )


async def _stream_errors_csv(run_id: UUID):
    """Yield CSV lines for run errors. Uses its own session for streaming."""
    from app.db import async_session_factory
    async with async_session_factory() as session:
        result = await session.execute(
            select(ImportRowError)
            .where(ImportRowError.run_id == run_id)
            .order_by(ImportRowError.row_number)
        )
        errors = result.scalars().all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["row_number", "field", "message"])
    yield buf.getvalue()
    buf.seek(0)
    buf.truncate(0)
    for e in errors:
        w.writerow([e.row_number, e.field or "", e.message])
        yield buf.getvalue()
        buf.seek(0)
        buf.truncate(0)


async def _stream_records_csv(run_id: UUID):
    """Yield CSV lines for run records. Uses its own session for streaming."""
    from app.db import async_session_factory
    async with async_session_factory() as session:
        result = await session.execute(
            select(ImportRecord)
            .where(ImportRecord.run_id == run_id)
            .order_by(ImportRecord.row_number)
        )
        records = result.scalars().all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["row_number", "date", "campaign", "channel", "spend", "clicks", "conversions"])
    yield buf.getvalue()
    buf.seek(0)
    buf.truncate(0)
    for r in records:
        w.writerow([r.row_number, r.date.isoformat(), r.campaign, r.channel, str(r.spend), r.clicks, r.conversions])
        yield buf.getvalue()
        buf.seek(0)
        buf.truncate(0)


@router.get("/{run_id}/errors.csv")
async def download_run_errors_csv(
    run_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Stream run validation errors as CSV. Requires membership in dataset's org."""
    org_id, _ = await require_active_org(current_user, session)
    run = await _run_in_active_org(session, run_id, org_id)
    if not run:
        raise err("not_found", "Run not found", status_code=404)
    return StreamingResponse(
        _stream_errors_csv(run_id),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="run-{run_id}-errors.csv"',
        },
    )


@router.get("/{run_id}/records.csv")
async def download_run_records_csv(
    run_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Stream run valid records as CSV. Requires membership in dataset's org."""
    org_id, _ = await require_active_org(current_user, session)
    run = await _run_in_active_org(session, run_id, org_id)
    if not run:
        raise err("not_found", "Run not found", status_code=404)
    return StreamingResponse(
        _stream_records_csv(run_id),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="run-{run_id}-records.csv"',
        },
    )
