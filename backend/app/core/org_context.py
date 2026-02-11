"""
Organization context helpers for multi-tenant scoping.
"""
from uuid import UUID
from fastapi import Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.db import get_session
from app.models.user import User
from app.models.orgs import Organization, OrganizationMember, OrgMemberRole


async def get_active_org_id(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> UUID | None:
    """
    Get the user's active org ID. If null, pick first membership and set it.
    Returns None if user has no org memberships.
    """
    if current_user.active_org_id:
        return current_user.active_org_id

    # Find first membership
    result = await session.execute(
        select(OrganizationMember.org_id)
        .where(OrganizationMember.user_id == current_user.id)
        .limit(1)
    )
    first_org_id = result.scalar_one_or_none()
    if first_org_id:
        current_user.active_org_id = first_org_id
        await session.commit()
        await session.refresh(current_user)
        return first_org_id

    return None


async def require_active_org(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> tuple[UUID, Organization]:
    """
    Require that user has an active org. Returns (org_id, org).
    Raises 403 if no active org.
    """
    org_id = await get_active_org_id(current_user, session)
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "no_active_org", "message": "No active organization"}},
        )

    result = await session.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "org_not_found", "message": "Organization not found"}},
        )

    return (org_id, org)


async def require_org_member(
    org_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> OrganizationMember:
    """
    Require that user is a member of the specified org.
    Returns the membership. Raises 404 if not a member.
    """
    result = await session.execute(
        select(OrganizationMember).where(
            OrganizationMember.org_id == org_id,
            OrganizationMember.user_id == current_user.id,
        )
    )
    membership = result.scalar_one_or_none()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_member", "message": "Not a member of this organization"}},
        )
    return membership


async def require_org_role(
    org_id: UUID,
    required_roles: list[OrgMemberRole],
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> OrganizationMember:
    """
    Require that user has one of the specified roles in the org.
    Returns the membership. Raises 403 if insufficient permissions.
    """
    membership = await require_org_member(org_id, current_user, session)
    if membership.role not in required_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "insufficient_permissions",
                    "message": f"Requires one of: {', '.join(r.value for r in required_roles)}",
                }
            },
        )
    return membership


async def get_user_org_role(
    org_id: UUID,
    current_user: User,
    session: AsyncSession,
) -> OrgMemberRole | None:
    """Get user's role in an org, or None if not a member."""
    result = await session.execute(
        select(OrganizationMember.role).where(
            OrganizationMember.org_id == org_id,
            OrganizationMember.user_id == current_user.id,
        )
    )
    return result.scalar_one_or_none()


async def ensure_personal_org(
    current_user: User,
    session: AsyncSession,
) -> Organization:
    """
    Ensure user has a personal org. Creates one if needed.
    Called during login/bootstrap.
    """
    # Check if user has any memberships
    result = await session.execute(
        select(func.count()).select_from(OrganizationMember).where(
            OrganizationMember.user_id == current_user.id
        )
    )
    count = result.scalar() or 0

    if count > 0:
        # User has orgs, ensure active_org_id is set
        if not current_user.active_org_id:
            first_result = await session.execute(
                select(OrganizationMember.org_id)
                .where(OrganizationMember.user_id == current_user.id)
                .limit(1)
            )
            first_org_id = first_result.scalar_one_or_none()
            if first_org_id:
                current_user.active_org_id = first_org_id
                await session.commit()
                await session.refresh(current_user)
                result = await session.execute(select(Organization).where(Organization.id == first_org_id))
                return result.scalar_one()

    # Create personal org
    from uuid import uuid4

    org = Organization(
        id=uuid4(),
        name=f"{current_user.name} Workspace",
    )
    session.add(org)
    await session.flush()

    membership = OrganizationMember(
        id=uuid4(),
        org_id=org.id,
        user_id=current_user.id,
        role=OrgMemberRole.OWNER,
    )
    session.add(membership)

    current_user.active_org_id = org.id
    await session.commit()
    await session.refresh(org)

    return org
