"""
Celery app for ETL Studio worker.
Run: uv run celery -A worker_main.celery_app worker --loglevel=INFO --concurrency=2
"""
from app_shared.otel import init_otel

init_otel("etl-worker")

from celery import Celery

from app_shared.config import settings

celery_app = Celery(
    "etl_studio",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

try:
    from opentelemetry.instrumentation.celery import CeleryInstrumentor
    CeleryInstrumentor().instrument()
except ImportError:
    pass

try:
    from app_shared.db_sync import sync_engine
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    SQLAlchemyInstrumentor().instrument(engine=sync_engine)
except ImportError:
    pass

# Register tasks so they are discovered
celery_app.autodiscover_tasks(["tasks"])
