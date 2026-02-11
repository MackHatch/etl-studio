"""
Process an ImportRun: read CSV, apply dataset mapping, validate rows, write errors and valid records.
Only processes runs with status QUEUED. Requires dataset.mapping_json.
Uses retries with backoff for transient errors; DLQ for repeated failures.
"""
import csv
import logging
import re
import traceback as tb_module
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app_shared.config import settings
from app_shared.db_sync import get_sync_session
from app_shared.models.imports import (
    ImportDataset,
    ImportRun,
    ImportRunAttempt,
    ImportRunAttemptStatus,
    ImportRunStatus,
    ImportRowError,
    ImportRecord,
    DatasetSchemaVersion,
)

# Security limits
MAX_ROWS = settings.MAX_ROWS
MAX_FIELD_CHARS = settings.MAX_FIELD_CHARS

from worker_main import celery_app

logger = logging.getLogger(__name__)

# Exception taxonomy: deterministic = no retry; transient = retry with backoff
class DeterministicFailure(Exception):
    """Validation/mapping/config errors — fail fast, do not retry."""


class TransientFailure(Exception):
    """DB connection, file read, etc. — retry; after exhaustion set dlq=true."""


TRACEBACK_MAX_LEN = 8000
MAX_RETRIES = 3

CANONICAL_REQUIRED = {"date", "campaign", "channel", "spend"}
CANONICAL_OPTIONAL = {"clicks", "conversions"}
CANONICAL_FIELDS = CANONICAL_REQUIRED | CANONICAL_OPTIONAL

PROGRESS_BATCH_SIZE = 200
RECORDS_BATCH_SIZE = 500


def _truncate_traceback(s: str, max_len: int = TRACEBACK_MAX_LEN) -> str:
    if not s or len(s) <= max_len:
        return s or ""
    return s[: max_len - 50] + "\n... (truncated)\n" + s[-50:]


def _upload_root() -> Path:
    if settings.UPLOAD_ROOT:
        return Path(settings.UPLOAD_ROOT)
    return Path(__file__).resolve().parent.parent.parent / "backend"


def _resolve_file_path(file_path: str) -> Path:
    root = _upload_root()
    return root / file_path


def _get_csv_path_for_run(run) -> tuple[Path, bool]:
    """Return (Path to CSV file, is_temp). Downloads from S3 to temp if needed."""
    storage = getattr(run, "file_storage", "disk") or "disk"
    if storage == "s3" and getattr(run, "s3_bucket", None) and getattr(run, "s3_key", None):
        if not (settings.S3_ENDPOINT_URL and settings.S3_ACCESS_KEY and settings.S3_SECRET_KEY):
            raise DeterministicFailure("S3 not configured; cannot read S3-stored run")
        import boto3
        import tempfile
        client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name=getattr(settings, "S3_REGION", "us-east-1"),
            use_ssl=False,
        )
        tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
        tmp.close()
        try:
            client.download_file(run.s3_bucket, run.s3_key, tmp.name)
            return (Path(tmp.name), True)
        except Exception as e:
            Path(tmp.name).unlink(missing_ok=True)
            raise TransientFailure(f"S3 download failed: {e}") from e
    if not run.file_path:
        raise DeterministicFailure("No file_path set for run")
    return (_resolve_file_path(run.file_path), False)


def _get_value(row: dict, source: str, header_lookup: dict) -> str | None:
    """Get value from row by source column name (case-insensitive match)."""
    if not (source or "").strip():
        return None
    key = header_lookup.get(source.strip().lower())
    if key is not None:
        val = row.get(key)
    else:
        val = row.get(source.strip())
    if val is None or (isinstance(val, str) and not val.strip()):
        return None
    return str(val).strip() if isinstance(val, str) else str(val)


def _apply_mapping(
    row: dict,
    row_number: int,
    mapping: dict,
    header_lookup: dict,
) -> tuple[dict, list[tuple[str, str]]]:
    """
    Build canonical dict from raw row using mapping. Apply transforms.
    Returns (canonical_dict, list of (field, error_message)).
    """
    canonical = {}
    errors = []
    for field in ["date", "campaign", "channel", "spend", "clicks", "conversions"]:
        config = mapping.get(field) or {}
        source = (config.get("source") or "").strip()
        default = config.get("default")
        raw = _get_value(row, source, header_lookup) if source else None
        if raw is None and default is not None:
            if field in ("clicks", "conversions"):
                try:
                    canonical[field] = int(default)
                except (TypeError, ValueError):
                    canonical[field] = 0
                continue
        if raw is None or (isinstance(raw, str) and not raw):
            if field in CANONICAL_REQUIRED:
                errors.append((field, f"Missing or empty value for mapped column '{source or field}'"))
            else:
                canonical[field] = 0 if field in ("clicks", "conversions") else ""
            continue
        if field == "date":
            fmt = (config.get("format") or "YYYY-MM-DD").strip().upper()
            try:
                if "MM/DD" in fmt or "MM-DD" in fmt:
                    dt = datetime.strptime(raw, "%m/%d/%Y")
                else:
                    dt = datetime.strptime(raw, "%Y-%m-%d")
                canonical["date"] = dt.date()
            except ValueError:
                try:
                    dt = datetime.strptime(raw, "%m/%d/%Y")
                    canonical["date"] = dt.date()
                except ValueError:
                    errors.append((field, f"Invalid date: {raw!r}"))
            continue
        if field in ("campaign", "channel"):
            canonical[field] = raw
            continue
        if field == "spend":
            s = raw
            if config.get("currency"):
                s = re.sub(r"[$,\s]", "", s)
            try:
                v = Decimal(s)
                if v < 0:
                    errors.append((field, "Spend must be >= 0"))
                else:
                    canonical["spend"] = v
            except Exception:
                errors.append((field, f"Invalid number for spend: {raw!r}"))
            continue
        if field in ("clicks", "conversions"):
            try:
                v = int(Decimal(raw.replace(",", "")))
                if v < 0:
                    errors.append((field, f"{field} must be >= 0"))
                else:
                    canonical[field] = v
            except Exception:
                errors.append((field, f"Invalid integer for {field}: {raw!r}"))
    return canonical, errors


def _validate_canonical(canonical: dict, row_number: int, rules: dict | None = None) -> list[tuple[str, str]]:
    """
    Validate canonical row. Returns list of (field, message).
    Applies rules if provided.
    """
    from datetime import date as date_type
    errors = []
    for field in CANONICAL_REQUIRED:
        if field not in canonical:
            errors.append((field, f"Missing {field}"))
    if "date" in canonical and not isinstance(canonical.get("date"), date_type):
        errors.append(("date", "Invalid date"))
    if "spend" in canonical and (not isinstance(canonical["spend"], Decimal) or canonical["spend"] < 0):
        errors.append(("spend", "Spend must be >= 0"))
    for field in ("clicks", "conversions"):
        if field in canonical and (not isinstance(canonical.get(field), int) or canonical[field] < 0):
            errors.append((field, f"{field} must be >= 0"))

    # Apply rules if provided
    if rules:
        errors.extend(_apply_rules(canonical, rules))

    return errors


def _apply_rules(canonical: dict, rules: dict) -> list[tuple[str, str]]:
    """Apply validation rules to canonical row. Returns list of (field, message)."""
    errors = []
    from datetime import date as date_type
    from decimal import Decimal

    for field, rule_config in rules.items():
        if field not in canonical:
            continue

        value = canonical[field]

        # Numeric rules (spend, clicks, conversions)
        if field in ("spend", "clicks", "conversions"):
            if not isinstance(value, (int, Decimal)):
                continue
            num_val = float(value) if isinstance(value, Decimal) else value
            if "min" in rule_config:
                if num_val < rule_config["min"]:
                    errors.append((field, f"{field} must be >= {rule_config['min']}"))
            if "max" in rule_config:
                if num_val > rule_config["max"]:
                    errors.append((field, f"{field} must be <= {rule_config['max']}"))

        # String rules (campaign, channel)
        elif field in ("campaign", "channel"):
            if not isinstance(value, str):
                continue
            if "minLength" in rule_config:
                if len(value) < rule_config["minLength"]:
                    errors.append((field, f"{field} must be at least {rule_config['minLength']} characters"))
            if "maxLength" in rule_config:
                if len(value) > rule_config["maxLength"]:
                    errors.append((field, f"{field} must be at most {rule_config['maxLength']} characters"))
            if "allowed" in rule_config:
                allowed_list = rule_config["allowed"]
                if isinstance(allowed_list, list) and value not in allowed_list:
                    errors.append((field, f"{field} must be one of: {', '.join(allowed_list)}"))

        # Date rules
        elif field == "date":
            if not isinstance(value, date_type):
                continue
            if "minDate" in rule_config:
                try:
                    min_date = datetime.strptime(rule_config["minDate"], "%Y-%m-%d").date()
                    if value < min_date:
                        errors.append((field, f"date must be >= {rule_config['minDate']}"))
                except (ValueError, TypeError):
                    pass
            if "maxDate" in rule_config:
                try:
                    max_date = datetime.strptime(rule_config["maxDate"], "%Y-%m-%d").date()
                    if value > max_date:
                        errors.append((field, f"date must be <= {rule_config['maxDate']}"))
                except (ValueError, TypeError):
                    pass

    return errors


def _canonical_to_record(run_uuid: UUID, canonical: dict, row_number: int) -> ImportRecord:
    return ImportRecord(
        run_id=run_uuid,
        row_number=row_number,
        date=canonical["date"],
        campaign=str(canonical.get("campaign", "")),
        channel=str(canonical.get("channel", "")),
        spend=canonical["spend"],
        clicks=int(canonical.get("clicks", 0)),
        conversions=int(canonical.get("conversions", 0)),
    )


def _mark_attempt_failed(
    session: Session,
    run: ImportRun,
    attempt: ImportRunAttempt,
    error_message: str,
    traceback_str: str | None,
    set_dlq: bool = False,
) -> None:
    now = datetime.now(timezone.utc)
    msg = (error_message or "")[:2000]
    attempt.status = ImportRunAttemptStatus.FAILED
    attempt.finished_at = now
    attempt.error_message = msg or None
    attempt.traceback = _truncate_traceback(traceback_str) if traceback_str else None
    run.status = ImportRunStatus.FAILED
    run.finished_at = now
    run.error_summary = msg or None
    run.last_error = msg or None
    if set_dlq:
        run.dlq = True
    session.commit()


@celery_app.task(name="etl.process_import_run", bind=True, max_retries=MAX_RETRIES)
def process_import_run(self, run_id: str, **kwargs) -> None:
    """Process an import run. Accepts _trace_ctx in kwargs for trace correlation."""
    trace_ctx = kwargs.pop("_trace_ctx", None)
    if trace_ctx:
        try:
            from opentelemetry import propagate
            from opentelemetry.context import attach, detach
            ctx = propagate.extract(carrier=trace_ctx)
            token = attach(ctx)
            try:
                _process_import_run_impl(self, run_id)
            finally:
                detach(token)
        except ImportError:
            _process_import_run_impl(self, run_id)
    else:
        _process_import_run_impl(self, run_id)


def _process_import_run_impl(self, run_id: str) -> None:
    run_uuid = UUID(run_id)
    session: Session = get_sync_session()
    attempt: ImportRunAttempt | None = None
    run: ImportRun | None = None
    csv_path: Path | None = None
    is_temp = False
    try:
        run = session.get(ImportRun, run_uuid)
        if not run:
            logger.error("ImportRun not found: %s", run_id)
            return
        if run.status != ImportRunStatus.QUEUED:
            logger.warning("ImportRun %s not QUEUED (status=%s), skipping", run_id, run.status)
            return
        csv_path, is_temp = _get_csv_path_for_run(run)

        dataset = session.get(ImportDataset, run.dataset_id)
        if not dataset:
            raise DeterministicFailure("Dataset not found")

        # Load schema version
        schema_version = run.schema_version
        if schema_version is None:
            schema_version = dataset.active_schema_version

        from sqlalchemy import select as sync_select
        result = session.execute(
            sync_select(DatasetSchemaVersion).where(
                DatasetSchemaVersion.dataset_id == run.dataset_id,
                DatasetSchemaVersion.version == schema_version,
            )
        )
        schema = result.scalar_one_or_none()

        if not schema:
            raise DeterministicFailure(f"Schema version {schema_version} not found")

        mapping = schema.mapping_json
        rules = schema.rules_json
        run.attempt_count += 1
        attempt_number = run.attempt_count
        now = datetime.now(timezone.utc)
        attempt = ImportRunAttempt(
            run_id=run_uuid,
            attempt_number=attempt_number,
            status=ImportRunAttemptStatus.STARTED,
            started_at=now,
        )
        session.add(attempt)
        run.status = ImportRunStatus.RUNNING
        run.started_at = now
        session.commit()

        session.execute(delete(ImportRowError).where(ImportRowError.run_id == run_uuid))
        session.execute(delete(ImportRecord).where(ImportRecord.run_id == run_uuid))
        session.commit()

        full_path = csv_path
        if not full_path.exists():
            raise TransientFailure(f"File not found: {full_path}")

        try:
            with open(full_path, newline="", encoding="utf-8", errors="replace") as f:
                reader = csv.DictReader(f)
                raw_headers = reader.fieldnames or []
                header_lookup = {h.strip().lower(): h for h in raw_headers}
                row_count = sum(1 for _ in reader)
        except (OSError, IOError) as e:
            raise TransientFailure(f"Failed to read CSV: {e}") from e

        # Enforce row limit
        if row_count > MAX_ROWS:
            raise DeterministicFailure(
                f"File exceeds maximum row limit: {row_count} rows (max {MAX_ROWS})"
            )

        run = session.get(ImportRun, run_uuid)
        run.total_rows = row_count
        run.processed_rows = 0
        run.success_rows = 0
        run.error_rows = 0
        run.row_limit_exceeded = False
        session.commit()

        pending_errors: list[ImportRowError] = []
        pending_records: list[ImportRecord] = []
        processed = 0
        success = 0
        errors_count = 0

        with open(full_path, newline="", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row_num, row in enumerate(reader, start=1):
                # Validate field lengths in raw row before processing
                field_too_long = False
                for key, val in row.items():
                    if val and len(str(val)) > MAX_FIELD_CHARS:
                        pending_errors.append(
                            ImportRowError(
                                run_id=run_uuid,
                                row_number=row_num,
                                field=key,
                                message=f"Field value exceeds maximum length: {len(str(val))} chars (max {MAX_FIELD_CHARS})",
                                raw_row=None,  # Don't store oversized raw row
                            )
                        )
                        field_too_long = True
                if field_too_long:
                    errors_count += 1
                    processed += 1
                    if len(pending_errors) >= 100:
                        session.bulk_save_objects(pending_errors)
                        pending_errors.clear()
                        session.commit()
                    if processed % PROGRESS_BATCH_SIZE == 0:
                        run = session.get(ImportRun, run_uuid)
                        run.processed_rows = processed
                        run.success_rows = success
                        run.error_rows = errors_count
                        run.progress_percent = min(100, int(100 * processed / row_count)) if row_count else 100
                        session.commit()
                    continue
                canonical, map_errors = _apply_mapping(row, row_num, mapping, header_lookup)
                if map_errors:
                    for field, message in map_errors:
                        pending_errors.append(
                            ImportRowError(
                                run_id=run_uuid,
                                row_number=row_num,
                                field=field,
                                message=message,
                                raw_row=dict(row),
                            )
                        )
                    errors_count += 1
                    processed += 1
                    continue
                val_errors = _validate_canonical(canonical, row_num, rules)
                if val_errors:
                    for field, message in val_errors:
                        pending_errors.append(
                            ImportRowError(
                                run_id=run_uuid,
                                row_number=row_num,
                                field=field,
                                message=message,
                                raw_row=dict(row),
                            )
                        )
                    errors_count += 1
                else:
                    rec = _canonical_to_record(run_uuid, canonical, row_num)
                    pending_records.append(rec)
                    success += 1
                processed += 1

                if len(pending_errors) >= 100:
                    session.bulk_save_objects(pending_errors)
                    pending_errors.clear()
                    session.commit()
                if len(pending_records) >= RECORDS_BATCH_SIZE:
                    session.bulk_save_objects(pending_records)
                    pending_records.clear()
                    session.commit()

                if processed % PROGRESS_BATCH_SIZE == 0:
                    run = session.get(ImportRun, run_uuid)
                    run.processed_rows = processed
                    run.success_rows = success
                    run.error_rows = errors_count
                    run.progress_percent = min(100, int(100 * processed / row_count)) if row_count else 100
                    session.commit()

        if pending_errors:
            session.bulk_save_objects(pending_errors)
            session.commit()
        if pending_records:
            session.bulk_save_objects(pending_records)
            session.commit()

        run = session.get(ImportRun, run_uuid)
        run.processed_rows = processed
        run.success_rows = success
        run.error_rows = errors_count
        run.status = ImportRunStatus.SUCCEEDED
        run.progress_percent = 100
        run.finished_at = datetime.now(timezone.utc)
        if attempt:
            attempt.status = ImportRunAttemptStatus.SUCCEEDED
            attempt.finished_at = run.finished_at
        session.commit()
        logger.info("ImportRun %s completed: %d rows, %d success, %d errors", run_id, processed, success, errors_count)

    except DeterministicFailure as e:
        logger.warning("ImportRun %s deterministic failure: %s", run_id, e)
        try:
            run = session.get(ImportRun, run_uuid) if not run else run
            attempt_obj = session.get(ImportRunAttempt, attempt.id) if (attempt and getattr(attempt, "id", None)) else None
            if run and attempt_obj:
                _mark_attempt_failed(
                    session, run, attempt_obj, str(e), tb_module.format_exc(), set_dlq=False
                )
            elif run:
                now = datetime.now(timezone.utc)
                msg = str(e)[:2000]
                run.status = ImportRunStatus.FAILED
                run.finished_at = now
                run.error_summary = msg
                run.last_error = msg
                session.commit()
            else:
                session.rollback()
        except Exception:
            session.rollback()
        raise

    except (TransientFailure, Exception) as e:
        logger.exception("ImportRun %s failed: %s", run_id, e)
        exc_tb = tb_module.format_exc()
        run = session.get(ImportRun, run_uuid) if not run else run
        attempt_obj = session.get(ImportRunAttempt, attempt.id) if (attempt and getattr(attempt, "id", None)) else None
        if run and attempt_obj:
            exhausted = self.request.retries >= self.max_retries
            _mark_attempt_failed(
                session, run, attempt_obj, str(e), exc_tb, set_dlq=exhausted
            )
            if not exhausted:
                run.status = ImportRunStatus.QUEUED
                session.commit()
                raise self.retry(countdown=2 ** self.request.retries)
        else:
            try:
                session.rollback()
            except Exception:
                pass
        raise e
    finally:
        session.close()
        if csv_path and is_temp and csv_path.exists():
            try:
                csv_path.unlink(missing_ok=True)
            except OSError:
                pass
