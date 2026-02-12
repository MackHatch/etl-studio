"""
Demo metadata endpoint: returns dataset and run IDs for the seeded demo.
Public, no auth required.
"""
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from app.db import async_session_factory
from app.models.imports import ImportDataset, ImportRun, ImportRunStatus

router = APIRouter(prefix="/demo", tags=["demo"])

DATASET_NAME = "Demo: Marketing Spend"
ORG_NAME = "Demo Workspace"


class DemoMetadata(BaseModel):
    dataset_id: str
    run_a_id: str
    run_b_id: str
    org_name: str
    dataset_name: str


@router.get("", response_model=DemoMetadata | None)
async def get_demo_metadata() -> DemoMetadata | None:
    """
    Return demo dataset and run IDs if seeded.
    Used by /demo page for deep links to compare, results, etc.
    """
    from app.models.orgs import Organization

    async with async_session_factory() as session:
        result = await session.execute(
            select(ImportDataset)
            .join(Organization, ImportDataset.org_id == Organization.id)
            .where(
                ImportDataset.name == DATASET_NAME,
                Organization.name == ORG_NAME,
            )
        )
        dataset = result.scalar_one_or_none()
        if not dataset:
            return None

        # Get Run A (schema v1) and Run B (schema v2) - both SUCCEEDED
        runs_result = await session.execute(
            select(ImportRun)
            .where(
                ImportRun.dataset_id == dataset.id,
                ImportRun.status == ImportRunStatus.SUCCEEDED,
            )
            .order_by(ImportRun.schema_version.asc())
        )
        runs = list(runs_result.scalars().all())
        run_a = next((r for r in runs if r.schema_version == 1), None)
        run_b = next((r for r in runs if r.schema_version == 2), None)
        if not run_a or not run_b:
            return None

        return DemoMetadata(
            dataset_id=str(dataset.id),
            run_a_id=str(run_a.id),
            run_b_id=str(run_b.id),
            org_name=ORG_NAME,
            dataset_name=DATASET_NAME,
        )
