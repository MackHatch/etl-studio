from datetime import datetime, timezone
from fastapi import APIRouter, Response
from app.db import check_db

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=dict,
    summary="Health check",
)
async def health(response: Response):
    """Return service and DB health. No-store to avoid caching."""
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    db_ok, latency_ms = await check_db()
    return {
        "ok": True,
        "db": {"ok": db_ok, "latency_ms": round(latency_ms, 2)},
        "time": datetime.now(timezone.utc).isoformat(),
    }
