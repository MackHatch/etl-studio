from celery import Celery

from app.config import settings

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

# Task name used by worker (must match worker task name)
IMPORT_RUN_TASK_NAME = "etl.process_import_run"


def enqueue_import_run(run_id: str) -> str:
    """Enqueue Celery task to process an import run. Returns task id. Injects trace context when OTEL enabled."""
    kwargs = {}
    try:
        from opentelemetry import propagate
        carrier = {}
        propagate.inject(carrier)
        if carrier:
            kwargs["_trace_ctx"] = carrier
    except Exception:
        pass
    result = celery_app.send_task(IMPORT_RUN_TASK_NAME, args=[run_id], kwargs=kwargs)
    return result.id
