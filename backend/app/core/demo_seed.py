"""
Demo seed: create demo dataset and a completed run with sample records and errors.
Idempotent: checks if demo dataset exists before creating.
Runs only when SEED_DEMO=true.
"""
import logging
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from uuid import UUID

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
)
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)

DEMO_DATASET_NAME = "Demo: Marketing Spend"
DEMO_ADMIN_EMAIL = "demo@example.com"
DEMO_ADMIN_PASSWORD = "demo123"


async def seed_demo() -> None:
    """Seed demo dataset and run if SEED_DEMO is enabled. Idempotent."""
    async with async_session_factory() as session:
        # Ensure demo admin exists
        result = await session.execute(select(User).where(User.email == DEMO_ADMIN_EMAIL))
        demo_admin = result.scalar_one_or_none()
        if not demo_admin:
            demo_admin = User(
                email=DEMO_ADMIN_EMAIL,
                name="Demo User",
                role=UserRole.ADMIN,
                password_hash=hash_password(DEMO_ADMIN_PASSWORD),
            )
            session.add(demo_admin)
            await session.flush()
            logger.info("Created demo admin user: %s", DEMO_ADMIN_EMAIL)
        else:
            logger.debug("Demo admin already exists: %s", DEMO_ADMIN_EMAIL)

        # Ensure demo admin has personal org
        await ensure_personal_org(demo_admin, session)
        await session.refresh(demo_admin)
        if not demo_admin.active_org_id:
            raise RuntimeError("Failed to create personal org for demo admin")

        # Check if demo dataset exists
        result = await session.execute(
            select(ImportDataset)
            .where(ImportDataset.name == DEMO_DATASET_NAME)
            .where(ImportDataset.org_id == demo_admin.active_org_id)
        )
        demo_dataset = result.scalar_one_or_none()
        if not demo_dataset:
            demo_dataset = ImportDataset(
                name=DEMO_DATASET_NAME,
                description="Sample marketing spend data for demo purposes",
                org_id=demo_admin.active_org_id,
                created_by_user_id=demo_admin.id,
                mapping_json={
                    "date": {"source": "date", "format": "YYYY-MM-DD"},
                    "campaign": {"source": "campaign"},
                    "channel": {"source": "channel"},
                    "spend": {"source": "spend", "currency": True},
                    "clicks": {"source": "clicks", "default": 0},
                    "conversions": {"source": "conversions", "default": 0},
                },
            )
            session.add(demo_dataset)
            await session.flush()
            logger.info("Created demo dataset: %s", DEMO_DATASET_NAME)
        else:
            logger.debug("Demo dataset already exists: %s", DEMO_DATASET_NAME)

        # Check if demo run exists
        result = await session.execute(
            select(ImportRun)
            .where(ImportRun.dataset_id == demo_dataset.id)
            .where(ImportRun.status == ImportRunStatus.SUCCEEDED)
        )
        existing_run = result.scalar_one_or_none()
        if existing_run:
            logger.debug("Demo run already exists, skipping seed")
            await session.commit()
            return

        # Create demo run
        now = datetime.now(timezone.utc)
        started = now - timedelta(minutes=5)
        finished = now - timedelta(minutes=2)
        demo_run = ImportRun(
            dataset_id=demo_dataset.id,
            status=ImportRunStatus.SUCCEEDED,
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
        session.add(demo_run)
        await session.flush()

        # Create attempt
        attempt = ImportRunAttempt(
            run_id=demo_run.id,
            attempt_number=1,
            status=ImportRunAttemptStatus.SUCCEEDED,
            started_at=started,
            finished_at=finished,
        )
        session.add(attempt)

        # Create sample records (3 valid rows)
        records = [
            ImportRecord(
                run_id=demo_run.id,
                row_number=1,
                date=date(2024, 1, 15),
                campaign="Campaign A",
                channel="Paid Search",
                spend=Decimal("150.00"),
                clicks=320,
                conversions=12,
            ),
            ImportRecord(
                run_id=demo_run.id,
                row_number=2,
                date=date(2024, 1, 15),
                campaign="Campaign B",
                channel="Social",
                spend=Decimal("85.50"),
                clicks=180,
                conversions=5,
            ),
            ImportRecord(
                run_id=demo_run.id,
                row_number=3,
                date=date(2024, 1, 16),
                campaign="Campaign A",
                channel="Paid Search",
                spend=Decimal("200.00"),
                clicks=410,
                conversions=18,
            ),
        ]
        session.add_all(records)

        # Create sample errors (2 invalid rows)
        errors = [
            ImportRowError(
                run_id=demo_run.id,
                row_number=4,
                field="date",
                message="Invalid date: 2024-13-45",
                raw_row={"date": "2024-13-45", "campaign": "Campaign C", "channel": "Email", "spend": "50.00"},
            ),
            ImportRowError(
                run_id=demo_run.id,
                row_number=5,
                field="spend",
                message="Invalid number for spend: 'abc'",
                raw_row={"date": "2024-01-17", "campaign": "Campaign D", "channel": "Display", "spend": "abc"},
            ),
        ]
        session.add_all(errors)

        await session.commit()
        logger.info("Demo seed completed: dataset=%s, run=%s", demo_dataset.id, demo_run.id)
