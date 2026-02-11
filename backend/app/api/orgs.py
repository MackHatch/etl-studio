from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.org_context import (
    require_active_org,
    require_org_member,
    require_org_role,
    get_active_org_id,
)
from app.core.permissions import require_org_admin_or_owner, require_org_owner
from app.db import get_session
from app.models.user import User
from app.models.orgs import Organization, OrganizationMember, OrganizationInvite, OrgMemberRole

router = APIRouter(prefix="/orgs", tags=["orgs"])


def err(code: str, message: str, status_code: int = 400) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message}},
    )


# --- Schemas ---


class OrganizationResponse(BaseModel):
    id: UUID
    name: str
    created_at: str

    class Config:
        from_attributes = True


class OrganizationListResponse(BaseModel):
    items: list[OrganizationResponse]


class CreateOrgRequest(BaseModel):
    name: str


class UpdateOrgRequest(BaseModel):
    name: str


class MemberResponse(BaseModel):
    id: UUID
    org_id: UUID
    user_id: UUID
    role: str
    user_email: str
    user_name: str
    created_at: str

    class Config:
        from_attributes = True


class MembersListResponse(BaseModel):
    items: list[MemberResponse]


class UpdateMemberRequest(BaseModel):
    role: OrgMemberRole


class InviteResponse(BaseModel):
    id: UUID
    org_id: UUID
    email: str
    role: str
    expires_at: str
    created_at: str
    accepted_at: str | None

    class Config:
        from_attributes = True


class InvitesListResponse(BaseModel):
    items: list[InviteResponse]


class CreateInviteRequest(BaseModel):
    email: EmailStr
    role: OrgMemberRole = OrgMemberRole.MEMBER


# --- Routes ---


@router.get("", response_model=OrganizationListResponse)
async def list_orgs(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """List all organizations the current user belongs to."""
    result = await session.execute(
        select(Organization)
        .join(OrganizationMember, Organization.id == OrganizationMember.org_id)
        .where(OrganizationMember.user_id == current_user.id)
        .order_by(Organization.created_at.desc())
    )
    orgs = result.scalars().all()
    return OrganizationListResponse(
        items=[
            OrganizationResponse(id=o.id, name=o.name, created_at=o.created_at.isoformat())
            for o in orgs
        ]
    )


@router.post("", response_model=OrganizationResponse)
async def create_org(
    body: CreateOrgRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Create a new organization. Creator becomes OWNER."""
    from uuid import uuid4

    org = Organization(
        id=uuid4(),
        name=body.name,
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
    await session.commit()
    await session.refresh(org)

    return OrganizationResponse(id=org.id, name=org.name, created_at=org.created_at.isoformat())


@router.get("/{org_id}", response_model=OrganizationResponse)
async def get_org(
    org_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Get organization details. Requires membership."""
    await require_org_member(org_id, current_user, session)
    result = await session.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    if not org:
        raise err("not_found", "Organization not found", status_code=404)
    return OrganizationResponse(id=org.id, name=org.name, created_at=org.created_at.isoformat())


@router.patch("/{org_id}", response_model=OrganizationResponse)
async def update_org(
    org_id: UUID,
    body: UpdateOrgRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Update organization name. Requires OWNER or ADMIN role."""
    await require_org_role(org_id, [OrgMemberRole.OWNER, OrgMemberRole.ADMIN], current_user, session)
    result = await session.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    if not org:
        raise err("not_found", "Organization not found", status_code=404)
    org.name = body.name
    await session.commit()
    await session.refresh(org)
    return OrganizationResponse(id=org.id, name=org.name, created_at=org.created_at.isoformat())


@router.post("/{org_id}/activate")
async def activate_org(
    org_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Set this organization as the user's active org. Requires membership."""
    await require_org_member(org_id, current_user, session)
    current_user.active_org_id = org_id
    await session.commit()
    await session.refresh(current_user)
    return {"ok": True, "active_org_id": str(org_id)}


@router.get("/{org_id}/members", response_model=MembersListResponse)
async def list_members(
    org_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """List organization members. Requires membership."""
    await require_org_member(org_id, current_user, session)
    result = await session.execute(
        select(OrganizationMember, User)
        .join(User, OrganizationMember.user_id == User.id)
        .where(OrganizationMember.org_id == org_id)
        .order_by(OrganizationMember.created_at.desc())
    )
    rows = result.all()
    return MembersListResponse(
        items=[
            MemberResponse(
                id=m.id,
                org_id=m.org_id,
                user_id=m.user_id,
                role=m.role.value,
                user_email=u.email,
                user_name=u.name,
                created_at=m.created_at.isoformat(),
            )
            for m, u in rows
        ]
    )


@router.patch("/{org_id}/members/{user_id}", response_model=MemberResponse)
async def update_member(
    org_id: UUID,
    user_id: UUID,
    body: UpdateMemberRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Update member role. Requires OWNER role."""
    await require_org_owner(org_id, current_user, session)
    result = await session.execute(
        select(OrganizationMember).where(
            OrganizationMember.org_id == org_id,
            OrganizationMember.user_id == user_id,
        )
    )
    membership = result.scalar_one_or_none()
    if not membership:
        raise err("not_found", "Member not found", status_code=404)
    membership.role = body.role
    await session.commit()
    await session.refresh(membership)
    user_result = await session.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one()
    return MemberResponse(
        id=membership.id,
        org_id=membership.org_id,
        user_id=membership.user_id,
        role=membership.role.value,
        user_email=user.email,
        user_name=user.name,
        created_at=membership.created_at.isoformat(),
    )


@router.delete("/{org_id}/members/{user_id}")
async def remove_member(
    org_id: UUID,
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Remove member from organization. Requires OWNER role. Cannot remove last OWNER."""
    await require_org_owner(org_id, current_user, session)
    
    # Check if this is the last OWNER
    result = await session.execute(
        select(func.count()).select_from(OrganizationMember).where(
            OrganizationMember.org_id == org_id,
            OrganizationMember.role == OrgMemberRole.OWNER,
        )
    )
    owner_count = result.scalar() or 0
    if owner_count <= 1:
        result = await session.execute(
            select(OrganizationMember).where(
                OrganizationMember.org_id == org_id,
                OrganizationMember.user_id == user_id,
            )
        )
        membership = result.scalar_one_or_none()
        if membership and membership.role == OrgMemberRole.OWNER:
            raise err("cannot_remove_last_owner", "Cannot remove the last OWNER", status_code=400)
    
    result = await session.execute(
        select(OrganizationMember).where(
            OrganizationMember.org_id == org_id,
            OrganizationMember.user_id == user_id,
        )
    )
    membership = result.scalar_one_or_none()
    if not membership:
        raise err("not_found", "Member not found", status_code=404)
    
    await session.delete(membership)
    await session.commit()
    return {"ok": True}


@router.post("/{org_id}/invites", response_model=InviteResponse)
async def create_invite(
    org_id: UUID,
    body: CreateInviteRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Create an organization invite. Requires OWNER or ADMIN role."""
    await require_org_role(org_id, [OrgMemberRole.OWNER, OrgMemberRole.ADMIN], current_user, session)
    
    from uuid import uuid4
    import secrets
    from datetime import datetime, timedelta, timezone

    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)

    invite = OrganizationInvite(
        id=uuid4(),
        org_id=org_id,
        email=body.email,
        role=body.role,
        token=token,
        expires_at=expires_at,
        created_by_user_id=current_user.id,
    )
    session.add(invite)
    await session.commit()
    await session.refresh(invite)

    return InviteResponse(
        id=invite.id,
        org_id=invite.org_id,
        email=invite.email,
        role=invite.role.value,
        expires_at=invite.expires_at.isoformat(),
        created_at=invite.created_at.isoformat(),
        accepted_at=invite.accepted_at.isoformat() if invite.accepted_at else None,
    )


@router.get("/{org_id}/invites", response_model=InvitesListResponse)
async def list_invites(
    org_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """List organization invites. Requires OWNER or ADMIN role."""
    await require_org_admin_or_owner(org_id, current_user, session)
    result = await session.execute(
        select(OrganizationInvite)
        .where(OrganizationInvite.org_id == org_id)
        .order_by(OrganizationInvite.created_at.desc())
    )
    invites = result.scalars().all()
    return InvitesListResponse(
        items=[
            InviteResponse(
                id=i.id,
                org_id=i.org_id,
                email=i.email,
                role=i.role.value,
                expires_at=i.expires_at.isoformat(),
                created_at=i.created_at.isoformat(),
                accepted_at=i.accepted_at.isoformat() if i.accepted_at else None,
            )
            for i in invites
        ]
    )


@router.delete("/{org_id}/invites/{invite_id}")
async def revoke_invite(
    org_id: UUID,
    invite_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Revoke an organization invite. Requires OWNER or ADMIN role."""
    await require_org_admin_or_owner(org_id, current_user, session)
    result = await session.execute(
        select(OrganizationInvite).where(
            OrganizationInvite.id == invite_id,
            OrganizationInvite.org_id == org_id,
        )
    )
    invite = result.scalar_one_or_none()
    if not invite:
        raise err("not_found", "Invite not found", status_code=404)
    await session.delete(invite)
    await session.commit()
    return {"ok": True}
