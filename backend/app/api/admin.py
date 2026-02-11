"""
Admin-only API: list runs across datasets, SSE for run list updates.
Org-scoped: shows runs for active org only. Requires ADMIN or OWNER role.
"""
import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import get_current_user
from app.core.org_context import require_active_org, require_org_admin_or_owner
from app.core.sse import sse_event
from app.db import get_session, async_session_factory
from app.models.imports import ImportRun, ImportDataset
from app.models.user import User


def _hash_id(value: str) -> str:
    try:
        from app_shared.hash import hash_id
        return hash_id(value, os.environ.get("TRACE_ID_HASH_SECRET"))
    except Exception:
        return ""


def _tracer():
    try:
        from opentelemetry import trace
        return trace.get_tracer("etl-backend", "0.1.0")
    except Exception:
        return None

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

ADMIN_RUNS_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}

ADMIN_POLL_INTERVAL = 2.0
ADMIN_HEARTBEAT_INTERVAL = 20.0
ADMIN_CHANGED_CAP = 50


class AdminRunItem(BaseModel):
    id: str
    dataset_id: str
    dataset_name: str
    status: str
    progress_percent: int
    processed_rows: int
    total_rows: int | None
    attempt_count: int
    dlq: bool
    updated_at: str
    last_error: str | None

    class Config:
        from_attributes = True


class AdminRunsListResponse(BaseModel):
    items: list[AdminRunItem]
    page: int
    page_size: int
    total: int


def _run_to_item(run: ImportRun, dataset_name: str) -> dict:
    return {
        "id": str(run.id),
        "dataset_id": str(run.dataset_id),
        "dataset_name": dataset_name,
        "status": run.status.value,
        "progress_percent": run.progress_percent,
        "processed_rows": run.processed_rows,
        "total_rows": run.total_rows,
        "attempt_count": run.attempt_count,
        "dlq": run.dlq,
        "updated_at": run.updated_at.isoformat(),
        "last_error": run.last_error,
    }


@router.get("/runs", response_model=AdminRunsListResponse)
async def list_admin_runs(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    status: str | None = Query(None),
    dlq: bool | None = Query(None),
    dataset_id: UUID | None = Query(None, alias="datasetId"),
    q: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
):
    """
    List recent runs across datasets in active org.
    Requires ADMIN or OWNER role in active org.
    Supports filters.
    """
    org_id, _ = await require_active_org(current_user, session)
    await require_org_admin_or_owner(org_id, current_user, session)
    
    base = (
        select(ImportRun)
        .join(ImportDataset, ImportRun.dataset_id == ImportDataset.id)
        .where(ImportDataset.org_id == org_id)
        .options(selectinload(ImportRun.dataset))
    )
    if status:
        base = base.where(ImportRun.status == status)
    if dlq is not None:
        base = base.where(ImportRun.dlq == dlq)
    if dataset_id is not None:
        base = base.where(ImportRun.dataset_id == dataset_id)
    if q and q.strip():
        base = base.where(ImportDataset.name.ilike(f"%{q.strip()}%"))

    base_count = (
        select(ImportRun)
        .join(ImportDataset, ImportRun.dataset_id == ImportDataset.id)
        .where(ImportDataset.org_id == org_id)
    )
    if status:
        base_count = base_count.where(ImportRun.status == status)
    if dlq is not None:
        base_count = base_count.where(ImportRun.dlq == dlq)
    if dataset_id is not None:
        base_count = base_count.where(ImportRun.dataset_id == dataset_id)
    if q and q.strip():
        base_count = base_count.where(ImportDataset.name.ilike(f"%{q.strip()}%"))
    total = (await session.execute(select(func.count()).select_from(base_count.subquery()))).scalar() or 0

    base = base.order_by(ImportRun.updated_at.desc())
    base = base.offset((page - 1) * page_size).limit(page_size)
    result = await session.execute(base)
    runs = result.unique().scalars().all()

    items = [
        AdminRunItem(**_run_to_item(run, run.dataset.name))
        for run in runs
    ]
    return AdminRunsListResponse(items=items, page=page, page_size=page_size, total=total)


async def _fetch_runs_updated_after(
    session: AsyncSession,
    org_id: UUID,
    updated_after: datetime | None,
    limit: int = ADMIN_CHANGED_CAP,
) -> list[tuple[ImportRun, str]]:
    """Return list of (run, dataset_name) updated after given time, newest first, scoped to org."""
    base = (
        select(ImportRun)
        .join(ImportDataset, ImportRun.dataset_id == ImportDataset.id)
        .where(ImportDataset.org_id == org_id)
        .options(selectinload(ImportRun.dataset))
        .order_by(ImportRun.updated_at.desc())
        .limit(limit)
    )
    if updated_after is not None:
        base = base.where(ImportRun.updated_at > updated_after)
    result = await session.execute(base)
    runs = result.unique().scalars().all()
    return [(r, r.dataset.name) for r in runs]


def _admin_sse_tracer():
    try:
        from opentelemetry import trace
        return trace.get_tracer("etl-backend", "0.1.0")
    except Exception:
        return None


async def stream_admin_runs_events(org_id: UUID):
    """SSE stream: initial runs.snapshot (first 50), then poll for runs.changed, heartbeat. Org-scoped."""
    last_seen: datetime | None = None
    last_heartbeat: float = 0.0
    tracer = _admin_sse_tracer()
    span = tracer.start_span("sse.admin.runs.events") if tracer else None
    if span:
        span.set_attribute("org.id_hash", _hash_id(str(org_id)))
    try:
        async with async_session_factory() as session:
            runs_data = await _fetch_runs_updated_after(session, org_id, None, limit=50)
        items = [_run_to_item(run, name) for run, name in runs_data]
        if span:
            span.add_event("snapshot")
        yield sse_event("runs.snapshot", {"items": items})
        if runs_data:
            last_seen = runs_data[0][0].updated_at
        last_heartbeat = time.monotonic()
    except asyncio.CancelledError:
        if span:
            span.end()
        return
    except Exception as e:
        logger.exception("Admin runs SSE initial snapshot: %s", e)
        if span:
            span.end()
        yield sse_event("runs.error", {"message": str(e)})
        return

    try:
        while True:
            await asyncio.sleep(ADMIN_POLL_INTERVAL)
            try:
                async with async_session_factory() as session:
                    changed = await _fetch_runs_updated_after(session, org_id, last_seen, limit=ADMIN_CHANGED_CAP)
                if changed:
                    items = [_run_to_item(run, name) for run, name in changed]
                    if span:
                        span.add_event("changed")
                    yield sse_event("runs.changed", {"items": items})
                    last_seen = changed[0][0].updated_at
                now_sec = time.monotonic()
                if now_sec - last_heartbeat >= ADMIN_HEARTBEAT_INTERVAL:
                    if span:
                        span.add_event("heartbeat")
                    yield sse_event("runs.heartbeat", {"time": datetime.now(timezone.utc).isoformat()})
                    last_heartbeat = now_sec
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("Admin runs SSE poll: %s", e)
                yield sse_event("runs.error", {"message": str(e)})
                break
    finally:
        if span:
            span.end()


@router.get("/runs/events")
async def admin_runs_events(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """SSE stream for admin runs list updates (org-scoped). Requires ADMIN or OWNER role in active org."""
    org_id, _ = await require_active_org(current_user, session)
    await require_org_admin_or_owner(org_id, current_user, session)
    return StreamingResponse(
        stream_admin_runs_events(org_id),
        media_type="text/event-stream",
        headers=ADMIN_RUNS_SSE_HEADERS,
    )
