#!/usr/bin/env python3
"""Reset and seed script: create bootstrap admin (if no users) + seed demo data."""
import asyncio
import os
import sys

# Run from repo root: uv run --package backend python backend/scripts/reset_and_seed.py

# Default env for deterministic demo
os.environ.setdefault("ADMIN_EMAIL", "admin@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "adminpassword")
os.environ.setdefault("SEED_DEMO", "true")


async def main() -> None:
    from sqlalchemy import func, select

    from app.config import settings
    from app.core.demo_seed import seed_demo
    from app.core.org_context import ensure_personal_org
    from app.core.security import hash_password
    from app.db import async_session_factory
    from app.models.user import User, UserRole

    async with async_session_factory() as session:
        result = await session.execute(select(func.count()).select_from(User))
        count = result.scalar() or 0
        if count == 0 and settings.ADMIN_EMAIL and settings.ADMIN_PASSWORD:
            admin = User(
                email=settings.ADMIN_EMAIL,
                name=settings.ADMIN_NAME or "Admin",
                role=UserRole.ADMIN,
                password_hash=hash_password(settings.ADMIN_PASSWORD),
            )
            session.add(admin)
            await session.flush()
            await ensure_personal_org(admin, session)
            await session.commit()
            print(f"Created bootstrap admin: {settings.ADMIN_EMAIL}")

    if settings.SEED_DEMO:
        await seed_demo()
        print("Demo seeded.")


if __name__ == "__main__":
    asyncio.run(main())
