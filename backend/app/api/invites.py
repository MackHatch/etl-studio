from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from app.core.auth import get_current_user
from app.db import get_session
from app.models.user import User
from app.models.orgs import Organization, OrganizationInvite, OrganizationMember, OrgMemberRole

router = APIRouter(prefix="/invites", tags=["invites"])


def err(code: str, message: str, status_code: int = 400) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message}},
    )


# --- Schemas ---


class InviteDetailResponse(BaseModel):
    id: UUID
    org_id: UUID
    org_name: str
    email: str
    role: str
    expires_at: str
    created_at: str
    accepted_at: str | None

    class Config:
        from_attributes = True


# --- Routes ---


@router.get("/{token}", response_model=InviteDetailResponse)
async def get_invite(
    token: str,
    session: AsyncSession = Depends(get_session),
):
    """Get invite details by token. Public endpoint."""
    result = await session.execute(
        select(OrganizationInvite, Organization)
        .join(Organization, OrganizationInvite.org_id == Organization.id)
        .where(OrganizationInvite.token == token)
    )
    row = result.first()
    if not row:
        raise err("not_found", "Invite not found", status_code=404)
    invite, org = row

    # Check expiry
    if invite.expires_at < datetime.now(timezone.utc):
        raise err("expired", "Invite has expired", status_code=400)

    # Check if already accepted
    if invite.accepted_at:
        raise err("already_accepted", "Invite has already been accepted", status_code=400)

    return InviteDetailResponse(
        id=invite.id,
        org_id=invite.org_id,
        org_name=org.name,
        email=invite.email,
        role=invite.role.value,
        expires_at=invite.expires_at.isoformat(),
        created_at=invite.created_at.isoformat(),
        accepted_at=invite.accepted_at.isoformat() if invite.accepted_at else None,
    )


@router.post("/{token}/accept")
async def accept_invite(
    token: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Accept an organization invite. Requires authentication."""
    result = await session.execute(
        select(OrganizationInvite).where(OrganizationInvite.token == token)
    )
    invite = result.scalar_one_or_none()
    if not invite:
        raise err("not_found", "Invite not found", status_code=404)

    # Check expiry
    if invite.expires_at < datetime.now(timezone.utc):
        raise err("expired", "Invite has expired", status_code=400)

    # Check if already accepted
    if invite.accepted_at:
        raise err("already_accepted", "Invite has already been accepted", status_code=400)

    # Check email matches
    if invite.email.lower() != current_user.email.lower():
        raise err(
            "email_mismatch",
            f"Invite is for {invite.email}, but you are logged in as {current_user.email}",
            status_code=400,
        )

    # Check if already a member
    existing_result = await session.execute(
        select(OrganizationMember).where(
            OrganizationMember.org_id == invite.org_id,
            OrganizationMember.user_id == current_user.id,
        )
    )
    if existing_result.scalar_one_or_none():
        raise err("already_member", "You are already a member of this organization", status_code=400)

    # Create membership
    from uuid import uuid4

    membership = OrganizationMember(
        id=uuid4(),
        org_id=invite.org_id,
        user_id=current_user.id,
        role=invite.role,
    )
    session.add(membership)

    # Mark invite as accepted
    invite.accepted_at = datetime.now(timezone.utc)

    # Set as active org if user has no active org
    if not current_user.active_org_id:
        current_user.active_org_id = invite.org_id

    await session.commit()
    await session.refresh(membership)

    return {"ok": True, "org_id": str(invite.org_id)}
