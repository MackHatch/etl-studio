"""
Server-Sent Events helpers for streaming ImportRun progress.
"""
import asyncio
import json
import logging
import os
import time
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from threading import Lock
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import async_session_factory
from app.models.imports import ImportRun, ImportRunStatus

logger = logging.getLogger(__name__)

# Per-user SSE connection tracking (thread-safe)
_sse_connections: dict[UUID, int] = {}
_sse_lock = Lock()

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

TERMINAL_STATES = {ImportRunStatus.SUCCEEDED, ImportRunStatus.FAILED}
POLL_INTERVAL = 1.0
HEARTBEAT_INTERVAL = 15.0


def sse_event(event: str, data: dict) -> str:
    """Format a single SSE message: event + data + double newline."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _run_payload(run: ImportRun) -> dict:
    """Build payload dict from run (only fields needed for progress UI)."""
    return {
        "id": str(run.id),
        "dataset_id": str(run.dataset_id),
        "status": run.status.value,
        "progress_percent": run.progress_percent,
        "total_rows": run.total_rows,
        "processed_rows": run.processed_rows,
        "success_rows": run.success_rows,
        "error_rows": run.error_rows,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "error_summary": run.error_summary,
        "created_at": run.created_at.isoformat(),
        "updated_at": run.updated_at.isoformat(),
    }


async def _fetch_run(session: AsyncSession, run_id: UUID) -> ImportRun | None:
    """Load run by id (minimal columns via ORM). Returns None if not found."""
    result = await session.execute(
        select(ImportRun).where(ImportRun.id == run_id)
    )
    return result.scalar_one_or_none()


def _increment_sse_connection(user_id: UUID) -> bool:
    """Increment connection count for user. Returns True if under limit, False if limit exceeded."""
    with _sse_lock:
        count = _sse_connections.get(user_id, 0)
        if count >= settings.SSE_MAX_CONCURRENT_PER_USER:
            return False
        _sse_connections[user_id] = count + 1
        return True


def _decrement_sse_connection(user_id: UUID) -> None:
    """Decrement connection count for user."""
    with _sse_lock:
        count = _sse_connections.get(user_id, 0)
        if count > 0:
            _sse_connections[user_id] = count - 1
        else:
            _sse_connections.pop(user_id, None)


async def stream_run_events(run_id: UUID, user_id: UUID) -> AsyncGenerator[str, None]:
    """
    Async generator that yields SSE-formatted strings for run progress.
    - Checks authorization (user must own run or be admin).
    - Enforces per-user connection limit.
    - Yields run.snapshot immediately.
    - Polls DB every POLL_INTERVAL; yields run.progress when values change.
    - Yields run.completed when status is SUCCEEDED or FAILED, then stops.
    - Yields run.heartbeat every HEARTBEAT_INTERVAL if no progress was sent.
    - Enforces maximum stream duration (10 minutes).
    """
    # Check connection limit
    if not _increment_sse_connection(user_id):
        yield sse_event(
            "run.error",
            {
                "code": "SSE_LIMIT_REACHED",
                "message": f"Maximum concurrent SSE connections ({settings.SSE_MAX_CONCURRENT_PER_USER}) exceeded",
            },
        )
        return

    start_time = time.monotonic()
    max_duration = settings.SSE_MAX_DURATION_SECONDS
    last_sent: dict | None = None
    last_progress_time: float = 0.0
    tracer = _tracer()
    run_id_hash = _hash_id(str(run_id))
    span = tracer.start_span("sse.run.events") if tracer else None
    if span:
        span.set_attribute("run.id_hash", run_id_hash)

    try:
        async with async_session_factory() as session:
            # Check authorization: user must own run or be admin
            from app.models.user import User, UserRole
            from app.models.imports import ImportDataset

            user_result = await session.execute(select(User).where(User.id == user_id))
            user = user_result.scalar_one_or_none()
            if not user:
                if span:
                    span.end()
                yield sse_event("run.error", {"code": "UNAUTHORIZED", "message": "User not found"})
                return

            run_result = await session.execute(
                select(ImportRun)
                .join(ImportDataset, ImportRun.dataset_id == ImportDataset.id)
                .where(ImportRun.id == run_id)
            )
            run = run_result.scalar_one_or_none()
            if not run:
                if span:
                    span.end()
                yield sse_event("run.error", {"code": "NOT_FOUND", "message": "Run not found"})
                return

            # Authorization check: user must be member of dataset's org
            from app.models.orgs import OrganizationMember
            membership_result = await session.execute(
                select(OrganizationMember).where(
                    OrganizationMember.org_id == run.dataset.org_id,
                    OrganizationMember.user_id == user_id,
                )
            )
            if not membership_result.scalar_one_or_none() and user.role != UserRole.ADMIN:
                if span:
                    span.end()
                yield sse_event("run.error", {"code": "FORBIDDEN", "message": "Access denied"})
                return

            if span:
                span.set_attribute("dataset.id_hash", _hash_id(str(run.dataset_id)))
                span.add_event("snapshot")
            payload = _run_payload(run)
            yield sse_event("run.snapshot", payload)
            last_sent = payload
            last_progress_time = time.monotonic()

            if run.status in TERMINAL_STATES:
                if span:
                    span.add_event("completed")
                    span.end()
                yield sse_event("run.completed", payload)
                return

        while True:
            # Check timeout
            elapsed = time.monotonic() - start_time
            if elapsed > max_duration:
                yield sse_event(
                    "run.error",
                    {
                        "code": "SSE_TIMEOUT",
                        "message": f"Stream exceeded maximum duration ({max_duration}s)",
                    },
                )
                break

            await asyncio.sleep(POLL_INTERVAL)

            try:
                async with async_session_factory() as session:
                    run = await _fetch_run(session, run_id)
                    if not run:
                        if span:
                            span.end()
                        yield sse_event("run.error", {"code": "NOT_FOUND", "message": "Run not found"})
                        return
                    payload = _run_payload(run)

                    if run.status in TERMINAL_STATES:
                        if span:
                            span.add_event("completed")
                            span.end()
                        yield sse_event("run.completed", payload)
                        return

                    if payload != last_sent:
                        if span:
                            span.add_event("progress")
                        yield sse_event("run.progress", payload)
                        last_sent = payload
                        last_progress_time = time.monotonic()

                    now = time.monotonic()
                    if now - last_progress_time >= HEARTBEAT_INTERVAL:
                        yield sse_event("run.heartbeat", {"time": datetime.now(timezone.utc).isoformat()})
                        last_progress_time = now

            except asyncio.CancelledError:
                logger.debug("SSE stream cancelled for run_id=%s", run_id)
                break
            except Exception as e:
                logger.exception("SSE stream error for run_id=%s: %s", run_id, e)
                yield sse_event("run.error", {"code": "SSE_ERROR", "message": "Internal error"})
                break

    except asyncio.CancelledError:
        logger.debug("SSE stream cancelled for run_id=%s", run_id)
    except Exception as e:
        logger.exception("SSE stream error for run_id=%s: %s", run_id, e)
        yield sse_event("run.error", {"code": "SSE_ERROR", "message": "Internal error"})
    finally:
        _decrement_sse_connection(user_id)
        if span:
            span.end()
