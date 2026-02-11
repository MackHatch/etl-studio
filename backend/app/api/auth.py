from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user, require_admin
from app.core.org_context import ensure_personal_org, get_user_org_role
from app.core.security import create_access_token, hash_password, verify_password
from app.db import get_session
from app.models.user import User, UserRole

router = APIRouter(prefix="/auth", tags=["auth"])


# --- Request/Response schemas ---


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: UUID
    email: str
    name: str
    role: str
    active_org_id: UUID | None = None
    active_org_role: str | None = None

    class Config:
        from_attributes = True


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class CreateUserRequest(BaseModel):
    email: EmailStr
    name: str
    password: str
    role: UserRole = UserRole.MEMBER


# --- Routes ---


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "invalid_credentials",
                    "message": "Invalid email or password",
                }
            },
        )
    token = create_access_token(
        sub=str(user.id),
        role=user.role.value,
        email=user.email,
    )
    return LoginResponse(
        access_token=token,
        user=UserResponse(id=user.id, email=user.email, name=user.name, role=user.role.value),
    )


@router.get("/me", response_model=UserResponse)
async def me(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    # Ensure personal org exists
    await ensure_personal_org(current_user, session)
    await session.refresh(current_user)
    
    # Get active org role
    active_org_role = None
    if current_user.active_org_id:
        active_org_role_obj = await get_user_org_role(current_user.active_org_id, current_user, session)
        if active_org_role_obj:
            active_org_role = active_org_role_obj.value
    
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        role=current_user.role.value,
        active_org_id=current_user.active_org_id,
        active_org_role=active_org_role,
    )


@router.post("/users", response_model=UserResponse)
async def create_user(
    body: CreateUserRequest,
    session: AsyncSession = Depends(get_session),
    _admin: User = Depends(require_admin),
):
    result = await session.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "email_exists",
                    "message": "A user with this email already exists",
                    "details": {"email": body.email},
                }
            },
        )
    user = User(
        email=body.email,
        name=body.name,
        role=body.role,
        password_hash=hash_password(body.password),
    )
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return UserResponse(id=user.id, email=user.email, name=user.name, role=user.role.value)
