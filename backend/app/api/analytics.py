"""
Analytics endpoints: summary and anomalies for imported marketing data.
Owner-only: dataset must belong to current user.
"""
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.org_context import require_active_org
from app.db import get_session
from app.models.imports import (
    ImportDataset,
    ImportRecord,
    ImportRun,
    ImportRunStatus,
)
from app.models.user import User

router = APIRouter(prefix="/analytics", tags=["analytics"])

RANGE_DAYS = {"7d": 7, "30d": 30, "90d": 90}
ANOMALIES_CAP = 50


def err(code: str, message: str, status_code: int = 400) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message}},
    )


async def _ensure_dataset_in_active_org(
    session: AsyncSession, dataset_id: UUID, org_id: UUID
) -> None:
    result = await session.execute(
        select(ImportDataset).where(
            ImportDataset.id == dataset_id,
            ImportDataset.org_id == org_id,
        )
    )
    if not result.scalar_one_or_none():
        raise err("not_found", "Dataset not found", status_code=404)


def _records_base(dataset_id: UUID):
    """Base select for ImportRecord joined to runs that are SUCCEEDED and belong to dataset."""
    return (
        select(ImportRecord)
        .join(ImportRun, ImportRecord.run_id == ImportRun.id)
        .join(ImportDataset, ImportRun.dataset_id == ImportDataset.id)
        .where(
            ImportRun.dataset_id == dataset_id,
            ImportRun.status == ImportRunStatus.SUCCEEDED,
        )
    )


class TotalsSchema(BaseModel):
    spend: float
    clicks: int
    conversions: int


class ByChannelRow(BaseModel):
    channel: str
    spend: float
    clicks: int
    conversions: int


class ByDayRow(BaseModel):
    date: str
    spend: float
    clicks: int
    conversions: int


class TopCampaignRow(BaseModel):
    campaign: str
    spend: float
    clicks: int
    conversions: int


class SummaryResponse(BaseModel):
    range: str
    totals: TotalsSchema
    by_channel: list[ByChannelRow] = Field(alias="byChannel")
    by_day: list[ByDayRow] = Field(alias="byDay")
    top_campaigns: list[TopCampaignRow] = Field(alias="topCampaigns")

    class Config:
        populate_by_name = True


def _decimal_to_float(v) -> float:
    if v is None:
        return 0.0
    if isinstance(v, Decimal):
        return float(v)
    return float(v)


@router.get("/summary", response_model=SummaryResponse)
async def get_analytics_summary(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    dataset_id: UUID | None = Query(None, alias="datasetId"),
    range_param: str = Query("30d", alias="range"),
):
    """
    Aggregated analytics. If datasetId provided: for that dataset.
    If omitted: org-wide totals across all datasets in active org.
    Requires membership in org. Only SUCCEEDED runs.
    """
    org_id, _ = await require_active_org(current_user, session)
    
    days = RANGE_DAYS.get(range_param)
    if not days:
        raise err("invalid_range", "range must be 7d, 30d, or 90d")
    start_date = date.today() - timedelta(days=days)

    # Build base query with org filter
    base_join = (
        select(ImportRecord)
        .join(ImportRun, ImportRecord.run_id == ImportRun.id)
        .join(ImportDataset, ImportRun.dataset_id == ImportDataset.id)
        .where(
            ImportDataset.org_id == org_id,
            ImportRun.status == ImportRunStatus.SUCCEEDED,
            ImportRecord.date >= start_date,
        )
    )
    
    # If dataset_id specified, add filter and verify ownership
    if dataset_id:
        await _ensure_dataset_in_active_org(session, dataset_id, org_id)
        base_join = base_join.where(ImportRun.dataset_id == dataset_id)

    # Totals
    totals_q = (
        select(
            func.coalesce(func.sum(ImportRecord.spend), 0).label("spend"),
            func.coalesce(func.sum(ImportRecord.clicks), 0).label("clicks"),
            func.coalesce(func.sum(ImportRecord.conversions), 0).label("conversions"),
        )
        .select_from(ImportRecord)
        .join(ImportRun, ImportRecord.run_id == ImportRun.id)
        .join(ImportDataset, ImportRun.dataset_id == ImportDataset.id)
        .where(
            ImportDataset.org_id == org_id,
            ImportRun.status == ImportRunStatus.SUCCEEDED,
            ImportRecord.date >= start_date,
        )
    )
    if dataset_id:
        totals_q = totals_q.where(ImportRun.dataset_id == dataset_id)
    totals_row = (await session.execute(totals_q)).one()
    totals = TotalsSchema(
        spend=_decimal_to_float(totals_row.spend),
        clicks=int(totals_row.clicks or 0),
        conversions=int(totals_row.conversions or 0),
    )

    # By channel
    channel_q = (
        select(
            ImportRecord.channel,
            func.sum(ImportRecord.spend).label("spend"),
            func.sum(ImportRecord.clicks).label("clicks"),
            func.sum(ImportRecord.conversions).label("conversions"),
        )
        .select_from(ImportRecord)
        .join(ImportRun, ImportRecord.run_id == ImportRun.id)
        .join(ImportDataset, ImportRun.dataset_id == ImportDataset.id)
        .where(
            ImportDataset.org_id == org_id,
            ImportRun.status == ImportRunStatus.SUCCEEDED,
            ImportRecord.date >= start_date,
        )
    )
    if dataset_id:
        channel_q = channel_q.where(ImportRun.dataset_id == dataset_id)
    channel_q = channel_q.group_by(ImportRecord.channel)
    channel_rows = (await session.execute(channel_q)).all()
    by_channel = [
        ByChannelRow(
            channel=row.channel or "",
            spend=_decimal_to_float(row.spend),
            clicks=int(row.clicks or 0),
            conversions=int(row.conversions or 0),
        )
        for row in channel_rows
    ]

    # By day
    day_q = (
        select(
            ImportRecord.date,
            func.sum(ImportRecord.spend).label("spend"),
            func.sum(ImportRecord.clicks).label("clicks"),
            func.sum(ImportRecord.conversions).label("conversions"),
        )
        .select_from(ImportRecord)
        .join(ImportRun, ImportRecord.run_id == ImportRun.id)
        .join(ImportDataset, ImportRun.dataset_id == ImportDataset.id)
        .where(
            ImportDataset.org_id == org_id,
            ImportRun.status == ImportRunStatus.SUCCEEDED,
            ImportRecord.date >= start_date,
        )
    )
    if dataset_id:
        day_q = day_q.where(ImportRun.dataset_id == dataset_id)
    day_q = day_q.group_by(ImportRecord.date).order_by(ImportRecord.date)
    day_rows = (await session.execute(day_q)).all()
    by_day = [
        ByDayRow(
            date=row.date.isoformat(),
            spend=_decimal_to_float(row.spend),
            clicks=int(row.clicks or 0),
            conversions=int(row.conversions or 0),
        )
        for row in day_rows
    ]

    # Top campaigns
    camp_q = (
        select(
            ImportRecord.campaign,
            func.sum(ImportRecord.spend).label("spend"),
            func.sum(ImportRecord.clicks).label("clicks"),
            func.sum(ImportRecord.conversions).label("conversions"),
        )
        .select_from(ImportRecord)
        .join(ImportRun, ImportRecord.run_id == ImportRun.id)
        .join(ImportDataset, ImportRun.dataset_id == ImportDataset.id)
        .where(
            ImportDataset.org_id == org_id,
            ImportRun.status == ImportRunStatus.SUCCEEDED,
            ImportRecord.date >= start_date,
        )
    )
    if dataset_id:
        camp_q = camp_q.where(ImportRun.dataset_id == dataset_id)
    camp_q = camp_q.group_by(ImportRecord.campaign).order_by(func.sum(ImportRecord.spend).desc()).limit(10)
    camp_rows = (await session.execute(camp_q)).all()
    top_campaigns = [
        TopCampaignRow(
            campaign=row.campaign or "",
            spend=_decimal_to_float(row.spend),
            clicks=int(row.clicks or 0),
            conversions=int(row.conversions or 0),
        )
        for row in camp_rows
    ]

    return SummaryResponse(
        range=range_param,
        totals=totals,
        by_channel=by_channel,
        by_day=by_day,
        top_campaigns=top_campaigns,
    )


class AnomalyRow(BaseModel):
    date: str
    channel: str
    spend: float
    channel_mean: float
    channel_std: float
    z_score: float


class AnomaliesResponse(BaseModel):
    range: str
    items: list[AnomalyRow]


@router.get("/anomalies", response_model=AnomaliesResponse)
async def get_analytics_anomalies(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    dataset_id: UUID | None = Query(None, alias="datasetId"),
    range_param: str = Query("30d", alias="range"),
):
    """
    Spend anomalies: day+channel where spend > mean + 3*std for that channel.
    If datasetId provided: for that dataset. If omitted: org-wide.
    Requires membership in org.
    """
    org_id, _ = await require_active_org(current_user, session)
    
    if dataset_id:
        await _ensure_dataset_in_active_org(session, dataset_id, org_id)
    
    days = RANGE_DAYS.get(range_param)
    if not days:
        raise err("invalid_range", "range must be 7d, 30d, or 90d")
    start_date = date.today() - timedelta(days=days)

    # Daily spend by (channel, date)
    daily_q = (
        select(
            ImportRecord.channel,
            ImportRecord.date,
            func.sum(ImportRecord.spend).label("spend"),
        )
        .select_from(ImportRecord)
        .join(ImportRun, ImportRecord.run_id == ImportRun.id)
        .join(ImportDataset, ImportRun.dataset_id == ImportDataset.id)
        .where(
            ImportDataset.org_id == org_id,
            ImportRun.status == ImportRunStatus.SUCCEEDED,
            ImportRecord.date >= start_date,
        )
    )
    if dataset_id:
        daily_q = daily_q.where(ImportRun.dataset_id == dataset_id)
    daily_q = daily_q.group_by(ImportRecord.channel, ImportRecord.date)
    rows = (await session.execute(daily_q)).all()

    # Group by channel: list of (date, spend)
    from collections import defaultdict
    by_channel: dict[str, list[tuple[date, float]]] = defaultdict(list)
    for r in rows:
        by_channel[r.channel or ""].append((r.date, _decimal_to_float(r.spend)))

    # For each channel compute mean, std; flag (date, channel, spend) where spend > mean + 3*std
    anomalies: list[tuple[date, str, float, float, float, float]] = []
    for channel, points in by_channel.items():
        if len(points) < 2:
            continue
        spends = [p[1] for p in points]
        n = len(spends)
        mean = sum(spends) / n
        variance = sum((x - mean) ** 2 for x in spends) / n
        std = (variance ** 0.5) if variance > 0 else 0.0
        if std <= 0:
            continue
        threshold = mean + 3 * std
        for d, spend in points:
            if spend > threshold:
                z = (spend - mean) / std
                anomalies.append((d, channel, spend, mean, std, z))

    anomalies.sort(key=lambda x: -x[5])
    anomalies = anomalies[:ANOMALIES_CAP]

    items = [
        AnomalyRow(
            date=d.isoformat(),
            channel=channel,
            spend=spend,
            channel_mean=round(mean, 2),
            channel_std=round(std, 2),
            z_score=round(z_score, 2),
        )
        for d, channel, spend, mean, std, z_score in anomalies
    ]

    return AnomaliesResponse(range=range_param, items=items)


# Pydantic model config for response with by_channel etc. (snake_case in JSON)
# SummaryResponse uses by_channel, by_day - FastAPI will serialize as-is by default.
# If we want camelCase we'd set alias; prompt says byChannel, byDay - so let's use alias for JSON
class SummaryResponseCamel(BaseModel):
    range: str
    totals: TotalsSchema
    byChannel: list[ByChannelRow]
    byDay: list[ByDayRow]
    topCampaigns: list[TopCampaignRow]

    class Config:
        populate_by_name = True
