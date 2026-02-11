"""
OpenTelemetry initialization for backend and worker.
Call init_otel(service_name) before creating app/celery; uses env for config.
"""
import logging
import os

OTEL_ENABLED_ENV = "OTEL_ENABLED"
OTEL_EXPORTER_OTLP_ENDPOINT_ENV = "OTEL_EXPORTER_OTLP_ENDPOINT"
OTEL_SERVICE_NAME_ENV = "OTEL_SERVICE_NAME"
TRACE_ID_HASH_SECRET_ENV = "TRACE_ID_HASH_SECRET"

DEFAULT_OTLP_ENDPOINT = "http://otel-collector:4318"


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.environ.get(name, "").strip().lower()
    if v in ("1", "true", "yes"):
        return True
    if v in ("0", "false", "no"):
        return False
    return default


def init_otel(service_name: str) -> bool:
    """
    Initialize OpenTelemetry TracerProvider with OTLP exporter.
    Uses env: OTEL_ENABLED (default false), OTEL_EXPORTER_OTLP_ENDPOINT, OTEL_SERVICE_NAME, TRACE_ID_HASH_SECRET.
    Returns True if tracing was initialized, False otherwise.
    """
    if not _env_bool(OTEL_ENABLED_ENV, False):
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError as e:
        logging.getLogger(__name__).warning("OpenTelemetry dependencies missing: %s", e)
        return False

    endpoint = os.environ.get(OTEL_EXPORTER_OTLP_ENDPOINT_ENV, DEFAULT_OTLP_ENDPOINT).strip()
    name = os.environ.get(OTEL_SERVICE_NAME_ENV, service_name).strip() or service_name

    resource = Resource.create({"service.name": name})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=f"{endpoint.rstrip('/')}/v1/traces")
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    logging.getLogger(__name__).info("OpenTelemetry initialized: service=%s endpoint=%s", name, endpoint)
    return True
