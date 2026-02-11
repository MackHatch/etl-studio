import logging
from sqlalchemy import select, func
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app_shared.otel import init_otel

init_otel("etl-backend")

from app.config import settings
from app.api.router import api_router
from app.core.demo_seed import seed_demo
from app.core.logging import LoggingMiddleware
from app.core.org_context import ensure_personal_org
from app.core.security import hash_password
from app.db import async_session_factory
from app.models.user import User, UserRole

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="ETL Studio API",
    version="0.1.0",
)


@app.on_event("startup")
async def bootstrap_admin() -> None:
    """Create admin user from env if no users exist (for initial provisioning)."""
    if not settings.ADMIN_EMAIL or not settings.ADMIN_PASSWORD:
        return
    async with async_session_factory() as session:
        result = await session.execute(select(func.count()).select_from(User))
        count = result.scalar() or 0
        if count > 0:
            return
        admin = User(
            email=settings.ADMIN_EMAIL,
            name=settings.ADMIN_NAME or "Admin",
            role=UserRole.ADMIN,
            password_hash=hash_password(settings.ADMIN_PASSWORD),
        )
        session.add(admin)
        await session.flush()
        await ensure_personal_org(admin, session)
        await session.commit()
        await session.refresh(admin)
        logger.info(
            "Bootstrap admin user created: %s (role=ADMIN, active_org_id=%s)",
            settings.ADMIN_EMAIL,
            admin.active_org_id,
        )

    # Seed demo data if enabled
    if settings.SEED_DEMO:
        try:
            await seed_demo()
        except Exception as e:
            logger.exception("Demo seed failed: %s", e)


app.add_middleware(LoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

try:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    FastAPIInstrumentor.instrument_app(app)
except ImportError:
    pass

app.include_router(api_router)
