from pathlib import Path
from uuid import UUID

from fastapi import UploadFile

from app.config import settings
from app.core.storage_backends import DiskStorage, S3Storage, StoredObject

# Resolve relative to backend package root (backend/storage/uploads)
UPLOAD_ROOT = Path(__file__).resolve().parent.parent.parent / "storage" / "uploads"

ALLOWED_EXTENSIONS = {".csv"}
ALLOWED_CONTENT_TYPES = {"text/csv", "application/csv", "text/plain"}


class InvalidFileError(Exception):
    """Raised when file type is not allowed (e.g. not CSV)."""

    def __init__(self, code: str = "INVALID_FILE", message: str = "Only CSV files are allowed"):
        self.code = code
        self.message = message
        super().__init__(message)


class UploadResult:
    """Result of file upload with metadata."""

    def __init__(self, file_path: str | None, sha256: str, size_bytes: int, storage: str = "disk", s3_bucket: str | None = None, s3_key: str | None = None):
        self.file_path = file_path
        self.sha256 = sha256
        self.size_bytes = size_bytes
        self.storage = storage
        self.s3_bucket = s3_bucket
        self.s3_key = s3_key


def _get_storage_backend():
    if settings.STORAGE_BACKEND == "s3" and settings.S3_ENDPOINT_URL and settings.S3_ACCESS_KEY and settings.S3_SECRET_KEY:
        return S3Storage(
            endpoint_url=settings.S3_ENDPOINT_URL,
            access_key=settings.S3_ACCESS_KEY,
            secret_key=settings.S3_SECRET_KEY,
            bucket=settings.S3_BUCKET,
            region=settings.S3_REGION,
            use_ssl=settings.S3_USE_SSL,
        )
    return DiskStorage()


def presign_download_url(bucket: str, key: str) -> str | None:
    """Generate presigned download URL for S3 object. Returns None if S3 not configured."""
    if settings.STORAGE_BACKEND != "s3":
        return None
    backend = _get_storage_backend()
    if isinstance(backend, S3Storage):
        return backend.presign_download(bucket, key, settings.PRESIGN_EXPIRES_SECONDS)
    return None


async def save_upload(file: UploadFile, org_id: UUID, dataset_id: UUID, run_id: UUID) -> UploadResult:
    """
    Validate CSV, save to configured backend (S3 or disk).
    Enforces size limits and computes SHA256 checksum.
    Returns UploadResult with storage metadata.
    """
    filename = (file.filename or "").strip().lower()
    if not any(filename.endswith(ext) for ext in ALLOWED_EXTENSIONS):
        raise InvalidFileError(
            "INVALID_FILE",
            "File must have .csv extension",
        )
    content_type = (file.content_type or "").strip().lower()
    if content_type and content_type not in ALLOWED_CONTENT_TYPES:
        raise InvalidFileError(
            "INVALID_FILE",
            f"Content-Type must be CSV (got {content_type})",
        )

    backend = _get_storage_backend()
    try:
        stored = await backend.save_upload(
            file, org_id, dataset_id, run_id, settings.MAX_UPLOAD_BYTES
        )
    except ValueError as e:
        raise InvalidFileError("FILE_TOO_LARGE", str(e)) from e

    return UploadResult(
        file_path=stored.file_path,
        sha256=stored.sha256,
        size_bytes=stored.size_bytes,
        storage=stored.storage,
        s3_bucket=stored.bucket,
        s3_key=stored.key,
    )


def resolve_run_file_path(file_path: str) -> Path:
    """Resolve stored file_path (relative to backend root) to absolute Path."""
    backend_root = UPLOAD_ROOT.parent.parent
    return backend_root / file_path


def read_csv_header_for_run(run) -> list[str]:
    """Read CSV header from run, whether stored on disk or S3."""
    import csv

    if run.file_storage == "s3" and run.s3_bucket and run.s3_key:
        backend = _get_storage_backend()
        if hasattr(backend, "client"):
            import io
            resp = backend.client.get_object(Bucket=run.s3_bucket, Key=run.s3_key)
            body = resp["Body"].read(65536)
            first_line = body.split(b"\n")[0].decode("utf-8", errors="replace")
        else:
            raise ValueError("S3 not configured")
    else:
        if not run.file_path:
            raise FileNotFoundError("Run has no file")
        path = resolve_run_file_path(run.file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        with open(path, newline="", encoding="utf-8", errors="replace") as f:
            first_line = f.readline()

    if not first_line:
        raise ValueError("CSV file is empty")
    row = next(csv.reader([first_line.strip()]))
    columns = [c.strip() for c in row] if row else []

    if len(columns) > settings.MAX_COLUMNS:
        raise ValueError(f"Too many columns: {len(columns)} (max {settings.MAX_COLUMNS})")
    max_col_name_len = 200
    for col in columns:
        if len(col) > max_col_name_len:
            raise ValueError(f"Column name too long: {col[:50]}... ({len(col)} chars, max {max_col_name_len})")
    return columns


def read_csv_header(file_path: str) -> list[str]:
    """
    Read first line of CSV and return column names. Raises if file missing or empty.
    Validates column count and field length limits.
    """
    from app.config import settings

    path = resolve_run_file_path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        first = f.readline()
    if not first:
        raise ValueError("CSV file is empty")
    import csv
    row = next(csv.reader([first.strip()]))
    columns = [c.strip() for c in row] if row else []

    # Validate column count
    if len(columns) > settings.MAX_COLUMNS:
        raise ValueError(f"Too many columns: {len(columns)} (max {settings.MAX_COLUMNS})")

    # Validate column name length
    max_col_name_len = 200
    for col in columns:
        if len(col) > max_col_name_len:
            raise ValueError(f"Column name too long: {col[:50]}... ({len(col)} chars, max {max_col_name_len})")

    return columns
