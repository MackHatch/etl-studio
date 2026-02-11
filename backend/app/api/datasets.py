from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import get_current_user
from app.core.org_context import require_active_org
from app.core.storage import save_upload, InvalidFileError
from app.db import get_session
from app.models.user import User
from app.models.imports import ImportDataset, ImportRun, ImportRunStatus

router = APIRouter(prefix="/datasets", tags=["datasets"])


def err(code: str, message: str, status_code: int = 400, details: dict | None = None) -> HTTPException:
    detail = {"error": {"code": code, "message": message}}
    if details is not None:
        detail["error"]["details"] = details
    return HTTPException(status_code=status_code, detail=detail)


# --- Schemas ---


class CreateDatasetRequest(BaseModel):
    name: str
    description: str | None = None


class DatasetResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    created_at: str

    class Config:
        from_attributes = True


class RunSummaryResponse(BaseModel):
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
    schema_version: int | None = None

    class Config:
        from_attributes = True


class DatasetWithRunsResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    created_at: str
    mapping: dict | None
    runs: list[RunSummaryResponse]

    class Config:
        from_attributes = True


# --- Routes ---


@router.post("", response_model=DatasetResponse)
async def create_dataset(
    body: CreateDatasetRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    org_id, _ = await require_active_org(current_user, session)
    dataset = ImportDataset(
        name=body.name,
        description=body.description,
        org_id=org_id,
        created_by_user_id=current_user.id,
    )
    session.add(dataset)
    await session.flush()
    await session.refresh(dataset)
    return DatasetResponse(
        id=dataset.id,
        name=dataset.name,
        description=dataset.description,
        created_at=dataset.created_at.isoformat(),
    )


@router.get("", response_model=list[DatasetResponse])
async def list_datasets(
    skip: int = 0,
    take: int = 100,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    org_id, _ = await require_active_org(current_user, session)
    result = await session.execute(
        select(ImportDataset)
        .where(ImportDataset.org_id == org_id)
        .order_by(ImportDataset.created_at.desc())
        .offset(skip)
        .limit(take)
    )
    rows = result.scalars().all()
    return [
        DatasetResponse(
            id=d.id,
            name=d.name,
            description=d.description,
            created_at=d.created_at.isoformat(),
        )
        for d in rows
    ]


@router.get("/{dataset_id}", response_model=DatasetWithRunsResponse)
async def get_dataset(
    dataset_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    org_id, _ = await require_active_org(current_user, session)
    result = await session.execute(
        select(ImportDataset)
        .where(ImportDataset.id == dataset_id, ImportDataset.org_id == org_id)
        .options(selectinload(ImportDataset.runs))
    )
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise err("not_found", "Dataset not found", status_code=404)
    runs = dataset.runs[:20]  # recent 20
    return DatasetWithRunsResponse(
        id=dataset.id,
        name=dataset.name,
        description=dataset.description,
        created_at=dataset.created_at.isoformat(),
        mapping=dataset.mapping_json,
        runs=[
            RunSummaryResponse(
                id=r.id,
                dataset_id=r.dataset_id,
                status=r.status.value,
                progress_percent=r.progress_percent,
                total_rows=r.total_rows,
                processed_rows=r.processed_rows,
                success_rows=r.success_rows,
                error_rows=r.error_rows,
                created_at=r.created_at.isoformat(),
                started_at=r.started_at.isoformat() if r.started_at else None,
                finished_at=r.finished_at.isoformat() if r.finished_at else None,
                schema_version=r.schema_version,
            )
            for r in runs
        ],
    )


# Mapping schema: canonical field -> { source: str, format?: str, currency?: bool, default?: number }
CANONICAL_REQUIRED = {"date", "campaign", "channel", "spend"}
CANONICAL_OPTIONAL = {"clicks", "conversions"}
CANONICAL_FIELDS = CANONICAL_REQUIRED | CANONICAL_OPTIONAL


class MappingFieldSchema(BaseModel):
    source: str
    format: str | None = None  # e.g. YYYY-MM-DD, MM/DD/YYYY
    currency: bool | None = None
    default: int | float | None = None


class PutMappingRequest(BaseModel):
    mapping: dict[str, MappingFieldSchema]


def _validate_mapping(mapping: dict) -> None:
    """Raise HTTPException if mapping is invalid."""
    if not mapping or not isinstance(mapping, dict):
        raise err("invalid_mapping", "Mapping must be a non-empty object", status_code=400)
    for key in CANONICAL_REQUIRED:
        if key not in mapping:
            raise err("invalid_mapping", f"Required field '{key}' is missing", status_code=400)
        m = mapping.get(key)
        if not isinstance(m, dict) or not (m.get("source") or "").strip():
            raise err("invalid_mapping", f"Field '{key}' must have a non-empty 'source' column", status_code=400)
    for key in list(mapping.keys()):
        if key not in CANONICAL_FIELDS:
            raise err("invalid_mapping", f"Unknown field '{key}'", status_code=400)
    for key in CANONICAL_OPTIONAL:
        if key in mapping:
            m = mapping[key]
            if not isinstance(m, dict):
                raise err("invalid_mapping", f"Field '{key}' must be an object", status_code=400)
            if m.get("source") is not None and not str(m.get("source", "")).strip():
                raise err("invalid_mapping", f"Field '{key}' source cannot be empty if set", status_code=400)


@router.put("/{dataset_id}/mapping")
async def put_dataset_mapping(
    dataset_id: UUID,
    body: PutMappingRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Set dataset column mapping. Validates required canonical fields."""
    org_id, _ = await require_active_org(current_user, session)
    result = await session.execute(
        select(ImportDataset).where(
            ImportDataset.id == dataset_id,
            ImportDataset.org_id == org_id,
        )
    )
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise err("not_found", "Dataset not found", status_code=404)
    _validate_mapping(body.mapping)
    dataset.mapping_json = body.mapping
    await session.flush()
    await session.commit()
    return {"ok": True}


@router.post("/{dataset_id}/uploads", response_model=RunSummaryResponse)
async def upload_csv(
    dataset_id: UUID,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    org_id, _ = await require_active_org(current_user, session)
    result = await session.execute(
        select(ImportDataset).where(
            ImportDataset.id == dataset_id,
            ImportDataset.org_id == org_id,
        )
    )
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise err("not_found", "Dataset not found", status_code=404)

    # Check for duplicate upload (same SHA256, same dataset, SUCCEEDED status)
    # We'll compute SHA256 during upload, but first create the run
    run = ImportRun(
        dataset_id=dataset_id,
        status=ImportRunStatus.DRAFT,
        file_path=None,
    )
    session.add(run)
    await session.flush()

    try:
        upload_result = await save_upload(file, org_id, dataset_id, run.id)
    except InvalidFileError as e:
        await session.rollback()
        raise err(e.code, e.message, status_code=400) from e

    # Check for duplicate upload
    existing_run = await session.execute(
        select(ImportRun)
        .join(ImportDataset)
        .where(
            ImportRun.file_sha256 == upload_result.sha256,
            ImportDataset.id == dataset_id,
            ImportRun.status == ImportRunStatus.SUCCEEDED,
        )
        .order_by(ImportRun.created_at.desc())
        .limit(1)
    )
    duplicate = existing_run.scalar_one_or_none()
    if duplicate:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "DUPLICATE_UPLOAD",
                    "message": "A run with the same file content already exists",
                    "details": {"existing_run_id": str(duplicate.id)},
                }
            },
        )

    run.file_storage = upload_result.storage
    run.file_path = upload_result.file_path
    run.s3_bucket = upload_result.s3_bucket
    run.s3_key = upload_result.s3_key
    run.file_sha256 = upload_result.sha256
    run.file_size_bytes = upload_result.size_bytes
    await session.flush()
    await session.commit()

    await session.refresh(run)
    return RunSummaryResponse(
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
        schema_version=run.schema_version,
    )
