"""
Demo seed: create Demo Workspace org, demo user, dataset, schema v1/v2, Run A (clean) and Run B (with errors).
Idempotent: upserts by email (users) and name (org, datasets).
Runs when SEED_DEMO=true.
"""
import logging
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select

from app.core.org_context import ensure_personal_org
from app.core.security import hash_password
from app.db import async_session_factory
from app.models.imports import (
    ImportDataset,
    ImportRun,
    ImportRunAttempt,
    ImportRunAttemptStatus,
    ImportRecord,
    ImportRowError,
    ImportRunStatus,
    DatasetSchemaVersion,
)
from app.models.orgs import Organization, OrganizationMember, OrgMemberRole
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)

ORG_NAME = "Demo Workspace"
DATASET_NAME = "Demo: Marketing Spend"
DEMO_EMAIL = "demo@etl.com"
DEMO_PASSWORD = "DemoPass123!"

# Schema v1: baseline rules (empty = no extra validation)
MAPPING_V1 = {
    "date": {"source": "date", "format": "YYYY-MM-DD"},
    "campaign": {"source": "campaign"},
    "channel": {"source": "channel"},
    "spend": {"source": "spend", "currency": True},
    "clicks": {"source": "clicks", "default": 0},
    "conversions": {"source": "conversions", "default": 0},
}
RULES_V1 = {}

# Schema v2: spend min 100 - causes rows with spend < 100 to fail
RULES_V2 = {"spend": {"min": 100}}


async def seed_demo() -> None:
    """Seed Demo Workspace with demo user, dataset, schema v1/v2, Run A (clean), Run B (errors). Idempotent."""
    async with async_session_factory() as session:
        # Ensure demo user exists (bootstrap may have created)
        result = await session.execute(select(User).where(User.email == DEMO_EMAIL))
        demo_user = result.scalar_one_or_none()
        if not demo_user:
            demo_user = User(
                email=DEMO_EMAIL,
                name="Demo User",
                role=UserRole.ADMIN,
                password_hash=hash_password(DEMO_PASSWORD),
            )
            session.add(demo_user)
            await session.flush()
            logger.info("Created demo user: %s", DEMO_EMAIL)
        await ensure_personal_org(demo_user, session)
        await session.refresh(demo_user)

        # Create or get "Demo Workspace" org
        result = await session.execute(select(Organization).where(Organization.name == ORG_NAME))
        org = result.scalar_one_or_none()
        if not org:
            org = Organization(id=uuid4(), name=ORG_NAME)
            session.add(org)
            await session.flush()
            logger.info("Created org: %s", ORG_NAME)
        # Ensure demo user is member (idempotent)
        member_result = await session.execute(
            select(OrganizationMember).where(
                OrganizationMember.org_id == org.id,
                OrganizationMember.user_id == demo_user.id,
            )
        )
        if not member_result.scalar_one_or_none():
            session.add(
                OrganizationMember(
                    id=uuid4(),
                    org_id=org.id,
                    user_id=demo_user.id,
                    role=OrgMemberRole.OWNER,
                )
            )
            await session.flush()
        demo_user.active_org_id = org.id

        await session.flush()

        # Create dataset
        result = await session.execute(
            select(ImportDataset).where(
                ImportDataset.name == DATASET_NAME,
                ImportDataset.org_id == org.id,
            )
        )
        dataset = result.scalar_one_or_none()
        if not dataset:
            dataset = ImportDataset(
                name=DATASET_NAME,
                description="Sample marketing spend for 2-minute demo",
                org_id=org.id,
                created_by_user_id=demo_user.id,
                mapping_json=MAPPING_V1,
            )
            session.add(dataset)
            await session.flush()
            logger.info("Created dataset: %s", DATASET_NAME)
        else:
            dataset.mapping_json = MAPPING_V1
            dataset.active_schema_version = 2
            await session.flush()

        # Schema v1
        result = await session.execute(
            select(DatasetSchemaVersion).where(
                DatasetSchemaVersion.dataset_id == dataset.id,
                DatasetSchemaVersion.version == 1,
            )
        )
        if not result.scalar_one_or_none():
            session.add(
                DatasetSchemaVersion(
                    dataset_id=dataset.id,
                    version=1,
                    mapping_json=MAPPING_V1,
                    rules_json=RULES_V1,
                    created_by_user_id=demo_user.id,
                )
            )
            await session.flush()

        # Schema v2 (slightly different rules)
        result = await session.execute(
            select(DatasetSchemaVersion).where(
                DatasetSchemaVersion.dataset_id == dataset.id,
                DatasetSchemaVersion.version == 2,
            )
        )
        if not result.scalar_one_or_none():
            session.add(
                DatasetSchemaVersion(
                    dataset_id=dataset.id,
                    version=2,
                    mapping_json=MAPPING_V1,
                    rules_json=RULES_V2,
                    created_by_user_id=demo_user.id,
                )
            )
            await session.flush()
        dataset.active_schema_version = 2
        await session.flush()

        now = datetime.now(timezone.utc)

        # Run A: SUCCEEDED, schema v1, all records clean (meaningful totals for compare)
        run_a_result = await session.execute(
            select(ImportRun).where(
                ImportRun.dataset_id == dataset.id,
                ImportRun.schema_version == 1,
                ImportRun.status == ImportRunStatus.SUCCEEDED,
            )
        )
        run_a = run_a_result.scalar_one_or_none()
        if not run_a:
            started = now - timedelta(hours=2)
            finished = now - timedelta(hours=2) + timedelta(seconds=30)
            run_a = ImportRun(
                dataset_id=dataset.id,
                status=ImportRunStatus.SUCCEEDED,
                schema_version=1,
                file_path="demo/sample.csv",
                progress_percent=100,
                total_rows=5,
                processed_rows=5,
                success_rows=5,
                error_rows=0,
                started_at=started,
                finished_at=finished,
                attempt_count=1,
                dlq=False,
            )
            session.add(run_a)
            await session.flush()
            session.add(
                ImportRunAttempt(
                    run_id=run_a.id,
                    attempt_number=1,
                    status=ImportRunAttemptStatus.SUCCEEDED,
                    started_at=started,
                    finished_at=finished,
                )
            )
            # 5 records: totals for compare (spend: 150+85+200+60+100 = 595)
            for i, (d, camp, ch, sp, cl, cv) in enumerate(
                [
                    (date(2024, 1, 15), "Campaign A", "Paid Search", Decimal("150.00"), 320, 12),
                    (date(2024, 1, 15), "Campaign B", "Social", Decimal("85.50"), 180, 5),
                    (date(2024, 1, 16), "Campaign A", "Paid Search", Decimal("200.00"), 410, 18),
                    (date(2024, 1, 16), "Campaign C", "Email", Decimal("60.00"), 90, 3),
                    (date(2024, 1, 17), "Campaign B", "Display", Decimal("100.00"), 150, 7),
                ],
                start=1,
            ):
                session.add(
                    ImportRecord(
                        run_id=run_a.id,
                        row_number=i,
                        date=d,
                        campaign=camp,
                        channel=ch,
                        spend=sp,
                        clicks=cl,
                        conversions=cv,
                    )
                )
            await session.flush()

        # Run B: SUCCEEDED, schema v2, has row errors (spend<50 rejected)
        run_b_result = await session.execute(
            select(ImportRun).where(
                ImportRun.dataset_id == dataset.id,
                ImportRun.schema_version == 2,
                ImportRun.status == ImportRunStatus.SUCCEEDED,
            )
        )
        run_b = run_b_result.scalar_one_or_none()
        if not run_b:
            started = now - timedelta(hours=1)
            finished = now - timedelta(hours=1) + timedelta(seconds=25)
            run_b = ImportRun(
                dataset_id=dataset.id,
                status=ImportRunStatus.SUCCEEDED,
                schema_version=2,
                file_path="demo/sample.csv",
                progress_percent=100,
                total_rows=5,
                processed_rows=5,
                success_rows=3,
                error_rows=2,
                started_at=started,
                finished_at=finished,
                attempt_count=1,
                dlq=False,
            )
            session.add(run_b)
            await session.flush()
            session.add(
                ImportRunAttempt(
                    run_id=run_b.id,
                    attempt_number=1,
                    status=ImportRunAttemptStatus.SUCCEEDED,
                    started_at=started,
                    finished_at=finished,
                )
            )
            # 3 valid (spend>=50), 2 rejected by rules (Campaign C spend 60 is valid, but we'll reject lower)
            # Run B: only 3 records with spend >= 50: 150, 85, 200 (Campaign C 60, Campaign B 100 - 100 is valid)
            # Actually RULES_V2 says spend min 50. So 60 and 100 both pass. Let me use min 100 to get 2 errors.
            # Records that pass (spend >= 100)
            for i, (d, camp, ch, sp, cl, cv) in enumerate(
                [
                    (date(2024, 1, 15), "Campaign A", "Paid Search", Decimal("150.00"), 320, 12),
                    (date(2024, 1, 16), "Campaign A", "Paid Search", Decimal("200.00"), 410, 18),
                    (date(2024, 1, 17), "Campaign B", "Display", Decimal("100.00"), 150, 7),
                ],
                start=1,
            ):
                session.add(
                    ImportRecord(
                        run_id=run_b.id,
                        row_number=i,
                        date=d,
                        campaign=camp,
                        channel=ch,
                        spend=sp,
                        clicks=cl,
                        conversions=cv,
                    )
                )
            session.add_all(
                [
                    ImportRowError(
                        run_id=run_b.id,
                        row_number=2,
                        field="spend",
                        message="spend must be >= 100",
                        raw_row={"date": "2024-01-15", "campaign": "Campaign B", "channel": "Social", "spend": "85.50"},
                    ),
                    ImportRowError(
                        run_id=run_b.id,
                        row_number=4,
                        field="spend",
                        message="spend must be >= 100",
                        raw_row={"date": "2024-01-16", "campaign": "Campaign C", "channel": "Email", "spend": "60.00"},
                    ),
                ]
            )
            await session.flush()

        await session.commit()
        logger.info("Demo seed completed: %s, Run A=%s, Run B=%s", DATASET_NAME, run_a.id if run_a else "n/a", run_b.id if run_b else "n/a")
