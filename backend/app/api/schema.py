from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.org_context import require_active_org
from app.core.permissions import require_dataset_org_admin_or_owner
from app.db import get_session
from app.models.user import User
from app.models.imports import ImportDataset, DatasetSchemaVersion

router = APIRouter(prefix="/datasets/{dataset_id}/schema", tags=["schema"])


def err(code: str, message: str, status_code: int = 400) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message}},
    )


class SchemaVersionResponse(BaseModel):
    id: UUID
    dataset_id: UUID
    version: int
    mapping: dict
    rules: dict
    created_by_user_id: UUID | None
    created_at: str

    class Config:
        from_attributes = True


class ActiveSchemaResponse(BaseModel):
    version: int
    mapping: dict
    rules: dict


class PublishSchemaRequest(BaseModel):
    mapping: dict
    rules: dict


class SchemaVersionsListResponse(BaseModel):
    items: list[SchemaVersionResponse]


@router.get("/active", response_model=ActiveSchemaResponse)
async def get_active_schema(
    dataset_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get the active schema version for a dataset."""
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

    # Get active schema version
    result = await session.execute(
        select(DatasetSchemaVersion).where(
            DatasetSchemaVersion.dataset_id == dataset_id,
            DatasetSchemaVersion.version == dataset.active_schema_version,
        )
    )
    schema = result.scalar_one_or_none()
    if not schema:
        raise err("no_schema", "No schema version found", status_code=404)

    return ActiveSchemaResponse(
        version=schema.version,
        mapping=schema.mapping_json,
        rules=schema.rules_json,
    )


@router.get("/versions", response_model=SchemaVersionsListResponse)
async def list_schema_versions(
    dataset_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """List all schema versions for a dataset (latest first)."""
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

    # Get all versions
    result = await session.execute(
        select(DatasetSchemaVersion)
        .where(DatasetSchemaVersion.dataset_id == dataset_id)
        .order_by(DatasetSchemaVersion.version.desc())
    )
    versions = result.scalars().all()

    return SchemaVersionsListResponse(
        items=[
            SchemaVersionResponse(
                id=v.id,
                dataset_id=v.dataset_id,
                version=v.version,
                mapping=v.mapping_json,
                rules=v.rules_json,
                created_by_user_id=v.created_by_user_id,
                created_at=v.created_at.isoformat(),
            )
            for v in versions
        ]
    )


@router.post("/publish", response_model=SchemaVersionResponse)
async def publish_schema(
    dataset_id: UUID,
    body: PublishSchemaRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Publish a new schema version. Creates version max+1 and sets it as active. Requires ADMIN or OWNER role."""
    await require_dataset_org_admin_or_owner(dataset_id, current_user, session)
    result = await session.execute(
        select(ImportDataset).where(ImportDataset.id == dataset_id)
    )
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise err("not_found", "Dataset not found", status_code=404)

    # Validate mapping (basic check)
    if not body.mapping or not isinstance(body.mapping, dict):
        raise err("invalid_mapping", "Mapping must be a non-empty object")

    # Validate rules (basic check)
    if not body.rules or not isinstance(body.rules, dict):
        raise err("invalid_rules", "Rules must be a non-empty object")

    # Get max version
    result = await session.execute(
        select(func.max(DatasetSchemaVersion.version)).where(
            DatasetSchemaVersion.dataset_id == dataset_id
        )
    )
    max_version = result.scalar() or 0
    new_version = max_version + 1

    # Create new schema version
    schema_version = DatasetSchemaVersion(
        dataset_id=dataset_id,
        version=new_version,
        mapping_json=body.mapping,
        rules_json=body.rules,
        created_by_user_id=current_user.id,
    )
    session.add(schema_version)

    # Update dataset active_schema_version
    dataset.active_schema_version = new_version
    # Also update mapping_json for backward compatibility
    dataset.mapping_json = body.mapping

    await session.flush()
    await session.commit()
    await session.refresh(schema_version)

    return SchemaVersionResponse(
        id=schema_version.id,
        dataset_id=schema_version.dataset_id,
        version=schema_version.version,
        mapping=schema_version.mapping_json,
        rules=schema_version.rules_json,
        created_by_user_id=schema_version.created_by_user_id,
        created_at=schema_version.created_at.isoformat(),
    )
