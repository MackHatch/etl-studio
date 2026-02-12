"""
Demo seed: create Acme Marketing org, demo users, datasets, and runs.
Idempotent: upserts by email (users) and name (org, datasets).
Runs when SEED_DEMO=true.
"""
import logging
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select

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

# Acme Marketing demo
ACME_ORG_NAME = "Acme Marketing"
DEMO_PASSWORD = "DemoPass123!"

DEMO_USERS = [
    {"email": "admin@acme.com", "name": "Admin", "role": UserRole.ADMIN, "org_role": OrgMemberRole.OWNER},
    {"email": "analyst@acme.com", "name": "Analyst", "role": UserRole.ADMIN, "org_role": OrgMemberRole.ADMIN},
    {"email": "member@acme.com", "name": "Member", "role": UserRole.MEMBER, "org_role": OrgMemberRole.MEMBER},
]

DEFAULT_MAPPING = {
    "date": {"source": "date", "format": "YYYY-MM-DD"},
    "campaign": {"source": "campaign"},
    "channel": {"source": "channel"},
    "spend": {"source": "spend", "currency": True},
    "clicks": {"source": "clicks", "default": 0},
    "conversions": {"source": "conversions", "default": 0},
}


async def _get_or_create_user(session, email: str, name: str, role: UserRole) -> User:
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user:
        return user
    user = User(
        email=email,
        name=name,
        role=role,
        password_hash=hash_password(DEMO_PASSWORD),
    )
    session.add(user)
    await session.flush()
    logger.info("Created demo user: %s", email)
    return user


async def _get_or_create_acme_org(session) -> Organization:
    result = await session.execute(select(Organization).where(Organization.name == ACME_ORG_NAME))
    org = result.scalar_one_or_none()
    if org:
        return org
    org = Organization(id=uuid4(), name=ACME_ORG_NAME)
    session.add(org)
    await session.flush()
    logger.info("Created org: %s", ACME_ORG_NAME)
    return org


async def _ensure_member(session, org_id, user_id, role: OrgMemberRole) -> None:
    result = await session.execute(
        select(OrganizationMember).where(
            OrganizationMember.org_id == org_id,
            OrganizationMember.user_id == user_id,
        )
    )
    if result.scalar_one_or_none():
        return
    session.add(
        OrganizationMember(
            id=uuid4(),
            org_id=org_id,
            user_id=user_id,
            role=role,
        )
    )
    await session.flush()


async def _get_or_create_dataset(
    session, org_id, created_by_id, name: str, description: str, mapping: dict
) -> ImportDataset:
    result = await session.execute(
        select(ImportDataset).where(
            ImportDataset.name == name,
            ImportDataset.org_id == org_id,
        )
    )
    ds = result.scalar_one_or_none()
    if ds:
        return ds
    ds = ImportDataset(
        name=name,
        description=description,
        org_id=org_id,
        created_by_user_id=created_by_id,
        mapping_json=mapping,
    )
    session.add(ds)
    await session.flush()

    # Create schema version 1 for mapping
    schema = DatasetSchemaVersion(
        dataset_id=ds.id,
        version=1,
        mapping_json=mapping,
        rules_json={},
        created_by_user_id=created_by_id,
    )
    session.add(schema)
    await session.flush()
    return ds


async def seed_demo() -> None:
    """Seed Acme Marketing org with users, datasets, and runs. Idempotent."""
    async with async_session_factory() as session:
        # Create or get users
        admin = await _get_or_create_user(session, "admin@acme.com", "Admin", UserRole.ADMIN)
        analyst = await _get_or_create_user(session, "analyst@acme.com", "Analyst", UserRole.ADMIN)
        member = await _get_or_create_user(session, "member@acme.com", "Member", UserRole.MEMBER)

        # Create or get Acme Marketing org
        acme = await _get_or_create_acme_org(session)

        # Add members to Acme
        await _ensure_member(session, acme.id, admin.id, OrgMemberRole.OWNER)
        await _ensure_member(session, acme.id, analyst.id, OrgMemberRole.ADMIN)
        await _ensure_member(session, acme.id, member.id, OrgMemberRole.MEMBER)

        # Set active_org to Acme for all demo users (so they see Acme datasets first)
        for u in (admin, analyst, member):
            if u.active_org_id != acme.id:
                u.active_org_id = acme.id

        await session.flush()

        # Create datasets
        ds1 = await _get_or_create_dataset(
            session,
            acme.id,
            admin.id,
            "Q1 Marketing Spend",
            "Q1 2024 campaign spend across channels",
            DEFAULT_MAPPING,
        )

        ds2 = await _get_or_create_dataset(
            session,
            acme.id,
            analyst.id,
            "Demo: Marketing Spend",
            "Sample marketing spend for demo purposes",
            DEFAULT_MAPPING,
        )

        now = datetime.now(timezone.utc)

        # Dataset 1: Multiple runs in mixed statuses (idempotent: check count)
        ds1_run_count = (
            await session.execute(select(ImportRun).where(ImportRun.dataset_id == ds1.id))
        )
        ds1_runs = list(ds1_run_count.scalars().all())
        ds1_statuses = {r.status for r in ds1_runs}

        ds1_runs_to_create = [
            (ImportRunStatus.SUCCEEDED, 12, 2, now - timedelta(days=5), now - timedelta(days=5)),
            (ImportRunStatus.SUCCEEDED, 8, 0, now - timedelta(days=3), now - timedelta(days=3)),
            (ImportRunStatus.SUCCEEDED, 15, 1, now - timedelta(days=1), now - timedelta(days=1)),
            (ImportRunStatus.DRAFT, 0, 0, None, None),
        ]
        for status, success_rows, error_rows, started, finished in ds1_runs_to_create:
            # Idempotent: skip if we already have a run with this profile
            existing = next(
                (r for r in ds1_runs if r.status == status and r.success_rows == success_rows),
                None,
            )
            if existing:
                continue

            run = ImportRun(
                dataset_id=ds1.id,
                status=status,
                file_path="demo/sample.csv" if status == ImportRunStatus.SUCCEEDED else None,
                progress_percent=100 if status == ImportRunStatus.SUCCEEDED else 0,
                total_rows=success_rows + error_rows if status == ImportRunStatus.SUCCEEDED else None,
                processed_rows=success_rows + error_rows if status == ImportRunStatus.SUCCEEDED else 0,
                success_rows=success_rows,
                error_rows=error_rows,
                started_at=started,
                finished_at=finished,
                attempt_count=1,
                dlq=False,
                schema_version=1,
            )
            session.add(run)
            await session.flush()

            if status == ImportRunStatus.SUCCEEDED:
                attempt = ImportRunAttempt(
                    run_id=run.id,
                    attempt_number=1,
                    status=ImportRunAttemptStatus.SUCCEEDED,
                    started_at=started,
                    finished_at=finished,
                )
                session.add(attempt)

                # Add sample records for first succeeded run
                if success_rows >= 3:
                    for i, (d, camp, ch, sp, cl, cv) in enumerate(
                        [
                            (date(2024, 1, 15), "Campaign A", "Paid Search", Decimal("150.00"), 320, 12),
                            (date(2024, 1, 15), "Campaign B", "Social", Decimal("85.50"), 180, 5),
                            (date(2024, 1, 16), "Campaign A", "Paid Search", Decimal("200.00"), 410, 18),
                        ],
                        start=1,
                    ):
                        session.add(
                            ImportRecord(
                                run_id=run.id,
                                row_number=i,
                                date=d,
                                campaign=camp,
                                channel=ch,
                                spend=sp,
                                clicks=cl,
                                conversions=cv,
                            )
                        )
                    if error_rows > 0:
                        session.add(
                            ImportRowError(
                                run_id=run.id,
                                row_number=4,
                                field="date",
                                message="Invalid date: 2024-13-45",
                                raw_row={"date": "2024-13-45", "campaign": "C", "channel": "Email", "spend": "50"},
                            )
                        )

        # Dataset 2: Demo dataset with one completed run (legacy demo compatibility)
        result = await session.execute(
            select(ImportRun).where(
                ImportRun.dataset_id == ds2.id,
                ImportRun.status == ImportRunStatus.SUCCEEDED,
            )
        )
        if not result.scalar_one_or_none():
            started = now - timedelta(minutes=5)
            finished = now - timedelta(minutes=2)
            run = ImportRun(
                dataset_id=ds2.id,
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
                schema_version=1,
            )
            session.add(run)
            await session.flush()

            attempt = ImportRunAttempt(
                run_id=run.id,
                attempt_number=1,
                status=ImportRunAttemptStatus.SUCCEEDED,
                started_at=started,
                finished_at=finished,
            )
            session.add(attempt)

            for i, (d, camp, ch, sp, cl, cv) in enumerate(
                [
                    (date(2024, 1, 15), "Campaign A", "Paid Search", Decimal("150.00"), 320, 12),
                    (date(2024, 1, 15), "Campaign B", "Social", Decimal("85.50"), 180, 5),
                    (date(2024, 1, 16), "Campaign A", "Paid Search", Decimal("200.00"), 410, 18),
                ],
                start=1,
            ):
                session.add(
                    ImportRecord(
                        run_id=run.id,
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
                        run_id=run.id,
                        row_number=4,
                        field="date",
                        message="Invalid date: 2024-13-45",
                        raw_row={"date": "2024-13-45", "campaign": "C", "channel": "Email", "spend": "50.00"},
                    ),
                    ImportRowError(
                        run_id=run.id,
                        row_number=5,
                        field="spend",
                        message="Invalid number for spend: 'abc'",
                        raw_row={"date": "2024-01-17", "campaign": "D", "channel": "Display", "spend": "abc"},
                    ),
                ]
            )

        await session.commit()
        logger.info("Demo seed completed: Acme Marketing org with datasets and runs")
