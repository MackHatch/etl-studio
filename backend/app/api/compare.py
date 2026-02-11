"""
Compare runs endpoint: compare two runs within a dataset to show impact of schema/rules changes.
"""
from uuid import UUID
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.org_context import require_active_org
from app.db import get_session
from app.models.user import User
from app.models.imports import ImportRun, ImportRunStatus, ImportDataset, ImportRecord


router = APIRouter(prefix="/datasets", tags=["compare"])


def err(code: str, message: str, status_code: int = 400) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message}},
    )


class RunCompareSummary(BaseModel):
    id: str
    status: str
    schema_version: int | None
    finished_at: str | None
    total_rows: int | None
    success_rows: int
    error_rows: int
    spend_total: Decimal
    clicks_total: Decimal
    conversions_total: Decimal


class SpendDiff(BaseModel):
    left: Decimal
    right: Decimal
    delta: Decimal


class CampaignDiff(BaseModel):
    campaign: str
    spend_left: Decimal
    spend_right: Decimal
    delta: Decimal


class CompareDiff(BaseModel):
    total_rows: int | None
    success_rows: int
    error_rows: int
    spend_total: SpendDiff
    clicks_total: SpendDiff
    conversions_total: SpendDiff
    top_changed_campaigns: list[CampaignDiff]


class CompareResponse(BaseModel):
    left_run: RunCompareSummary
    right_run: RunCompareSummary
    diff: CompareDiff


def _decimal_to_float(d: Decimal | None) -> float:
    """Convert Decimal to float for JSON serialization."""
    return float(d) if d is not None else 0.0


@router.get("/{dataset_id}/runs/compare", response_model=CompareResponse)
async def compare_runs(
    dataset_id: UUID,
    left_run_id: UUID = Query(..., alias="leftRunId"),
    right_run_id: UUID = Query(..., alias="rightRunId"),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Compare two runs within a dataset.
    Both runs must be SUCCEEDED and belong to the dataset.
    Requires membership in dataset's org.
    """
    org_id, _ = await require_active_org(current_user, session)
    
    # Verify dataset belongs to active org
    dataset_result = await session.execute(
        select(ImportDataset).where(
            ImportDataset.id == dataset_id,
            ImportDataset.org_id == org_id,
        )
    )
    dataset = dataset_result.scalar_one_or_none()
    if not dataset:
        raise err("not_found", "Dataset not found", status_code=404)
    
    # Fetch both runs
    runs_result = await session.execute(
        select(ImportRun).where(
            ImportRun.id.in_([left_run_id, right_run_id]),
            ImportRun.dataset_id == dataset_id,
        )
    )
    runs = {r.id: r for r in runs_result.scalars().all()}
    
    left_run = runs.get(left_run_id)
    right_run = runs.get(right_run_id)
    
    if not left_run:
        raise err("not_found", f"Left run {left_run_id} not found", status_code=404)
    if not right_run:
        raise err("not_found", f"Right run {right_run_id} not found", status_code=404)
    
    # Both runs must be SUCCEEDED
    if left_run.status != ImportRunStatus.SUCCEEDED:
        raise err("invalid_status", f"Left run must be SUCCEEDED, got {left_run.status.value}", status_code=400)
    if right_run.status != ImportRunStatus.SUCCEEDED:
        raise err("invalid_status", f"Right run must be SUCCEEDED, got {right_run.status.value}", status_code=400)
    
    # Aggregate totals for left run
    left_totals = await session.execute(
        select(
            func.coalesce(func.sum(ImportRecord.spend), 0).label("spend"),
            func.coalesce(func.sum(ImportRecord.clicks), 0).label("clicks"),
            func.coalesce(func.sum(ImportRecord.conversions), 0).label("conversions"),
        ).where(ImportRecord.run_id == left_run_id)
    )
    left_row = left_totals.one()
    left_spend = left_row.spend or Decimal(0)
    left_clicks = left_row.clicks or Decimal(0)
    left_conversions = left_row.conversions or Decimal(0)
    
    # Aggregate totals for right run
    right_totals = await session.execute(
        select(
            func.coalesce(func.sum(ImportRecord.spend), 0).label("spend"),
            func.coalesce(func.sum(ImportRecord.clicks), 0).label("clicks"),
            func.coalesce(func.sum(ImportRecord.conversions), 0).label("conversions"),
        ).where(ImportRecord.run_id == right_run_id)
    )
    right_row = right_totals.one()
    right_spend = right_row.spend or Decimal(0)
    right_clicks = right_row.clicks or Decimal(0)
    right_conversions = right_row.conversions or Decimal(0)
    
    # Campaign-level aggregation for left run
    left_campaigns_result = await session.execute(
        select(
            ImportRecord.campaign,
            func.sum(ImportRecord.spend).label("spend"),
        )
        .where(ImportRecord.run_id == left_run_id)
        .group_by(ImportRecord.campaign)
    )
    left_campaigns = {row.campaign: row.spend or Decimal(0) for row in left_campaigns_result.all()}
    
    # Campaign-level aggregation for right run
    right_campaigns_result = await session.execute(
        select(
            ImportRecord.campaign,
            func.sum(ImportRecord.spend).label("spend"),
        )
        .where(ImportRecord.run_id == right_run_id)
        .group_by(ImportRecord.campaign)
    )
    right_campaigns = {row.campaign: row.spend or Decimal(0) for row in right_campaigns_result.all()}
    
    # Compute campaign diffs
    all_campaigns = set(left_campaigns.keys()) | set(right_campaigns.keys())
    campaign_diffs = []
    for campaign in all_campaigns:
        left_val = left_campaigns.get(campaign, Decimal(0))
        right_val = right_campaigns.get(campaign, Decimal(0))
        delta = right_val - left_val
        campaign_diffs.append(CampaignDiff(
            campaign=campaign,
            spend_left=left_val,
            spend_right=right_val,
            delta=delta,
        ))
    
    # Sort by absolute delta descending, take top 10
    campaign_diffs.sort(key=lambda x: abs(x.delta), reverse=True)
    top_changed = campaign_diffs[:10]
    
    # Compute row counts
    left_error_rows = left_run.processed_rows - left_run.success_rows
    right_error_rows = right_run.processed_rows - right_run.success_rows
    
    return CompareResponse(
        left_run=RunCompareSummary(
            id=str(left_run.id),
            status=left_run.status.value,
            schema_version=left_run.schema_version,
            finished_at=left_run.finished_at.isoformat() if left_run.finished_at else None,
            total_rows=left_run.total_rows,
            success_rows=left_run.success_rows,
            error_rows=left_error_rows,
            spend_total=left_spend,
            clicks_total=left_clicks,
            conversions_total=left_conversions,
        ),
        right_run=RunCompareSummary(
            id=str(right_run.id),
            status=right_run.status.value,
            schema_version=right_run.schema_version,
            finished_at=right_run.finished_at.isoformat() if right_run.finished_at else None,
            total_rows=right_run.total_rows,
            success_rows=right_run.success_rows,
            error_rows=right_error_rows,
            spend_total=right_spend,
            clicks_total=right_clicks,
            conversions_total=right_conversions,
        ),
        diff=CompareDiff(
            total_rows=(right_run.total_rows or 0) - (left_run.total_rows or 0) if (left_run.total_rows and right_run.total_rows) else None,
            success_rows=right_run.success_rows - left_run.success_rows,
            error_rows=right_error_rows - left_error_rows,
            spend_total=SpendDiff(
                left=left_spend,
                right=right_spend,
                delta=right_spend - left_spend,
            ),
            clicks_total=SpendDiff(
                left=left_clicks,
                right=right_clicks,
                delta=right_clicks - left_clicks,
            ),
            conversions_total=SpendDiff(
                left=left_conversions,
                right=right_conversions,
                delta=right_conversions - left_conversions,
            ),
            top_changed_campaigns=top_changed,
        ),
    )
