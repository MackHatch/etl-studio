"""
Permission helpers for org role-based access control.
"""
from uuid import UUID
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.org_context import require_org_member, get_user_org_role
from app.db import get_session
from app.models.user import User
from app.models.orgs import OrgMemberRole


async def require_org_owner(
    org_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Require user is OWNER of the org. Returns membership."""
    membership = await require_org_member(org_id, current_user, session)
    if membership.role != OrgMemberRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "insufficient_permissions",
                    "message": "OWNER role required",
                }
            },
        )
    return membership


async def require_org_admin_or_owner(
    org_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Require user is ADMIN or OWNER of the org. Returns membership."""
    membership = await require_org_member(org_id, current_user, session)
    if membership.role not in (OrgMemberRole.ADMIN, OrgMemberRole.OWNER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "insufficient_permissions",
                    "message": "ADMIN or OWNER role required",
                }
            },
        )
    return membership


async def require_dataset_org_admin_or_owner(
    dataset_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> tuple[UUID, OrgMemberRole]:
    """
    Require user is ADMIN or OWNER of the dataset's org.
    Returns (org_id, user_role).
    """
    from app.models.imports import ImportDataset
    from sqlalchemy import select

    result = await session.execute(select(ImportDataset).where(ImportDataset.id == dataset_id))
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "Dataset not found"}},
        )

    membership = await require_org_admin_or_owner(dataset.org_id, current_user, session)
    return (dataset.org_id, membership.role)


def is_owner(role: OrgMemberRole) -> bool:
    """Check if role is OWNER."""
    return role == OrgMemberRole.OWNER


def is_admin_or_owner(role: OrgMemberRole) -> bool:
    """Check if role is ADMIN or OWNER."""
    return role in (OrgMemberRole.ADMIN, OrgMemberRole.OWNER)


def can_manage_members(role: OrgMemberRole) -> bool:
    """Check if role can manage members (OWNER only)."""
    return role == OrgMemberRole.OWNER


def can_invite(role: OrgMemberRole) -> bool:
    """Check if role can invite members (OWNER/ADMIN)."""
    return role in (OrgMemberRole.OWNER, OrgMemberRole.ADMIN)


def can_publish_schema(role: OrgMemberRole) -> bool:
    """Check if role can publish schema versions (OWNER/ADMIN)."""
    return role in (OrgMemberRole.OWNER, OrgMemberRole.ADMIN)
