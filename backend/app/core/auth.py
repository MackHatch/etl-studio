from uuid import UUID
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db import get_session
from app.models.user import User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


async def get_current_user(
    session: AsyncSession = Depends(get_session),
    token: str | None = Depends(oauth2_scheme),
) -> User:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "missing_token",
                    "message": "Authorization header with Bearer token is required",
                }
            },
        )
    try:
        payload = decode_access_token(token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "invalid_token",
                    "message": str(e),
                }
            },
        ) from e
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "invalid_token",
                    "message": "Token payload missing subject",
                }
            },
        )
    result = await session.execute(select(User).where(User.id == UUID(sub)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "user_not_found",
                    "message": "User no longer exists",
                }
            },
        )
    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "forbidden",
                    "message": "Admin role required",
                }
            },
        )
    return current_user


async def require_owner_or_admin(
    dataset_id: UUID | None = None,
    run_id: UUID | None = None,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> tuple[ImportDataset | None, ImportRun | None]:
    """
    Verify that the current user owns the dataset/run, or is an admin.
    Returns (dataset, run) tuple. Raises 404 if not found or unauthorized.
    """
    from app.models.imports import ImportDataset, ImportRun
    from sqlalchemy import select

    # Admin bypass
    if current_user.role == UserRole.ADMIN:
        dataset = None
        run = None
        if dataset_id:
            result = await session.execute(select(ImportDataset).where(ImportDataset.id == dataset_id))
            dataset = result.scalar_one_or_none()
            if not dataset:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error": {"code": "not_found", "message": "Dataset not found"}},
                )
        if run_id:
            result = await session.execute(select(ImportRun).where(ImportRun.id == run_id))
            run = result.scalar_one_or_none()
            if not run:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error": {"code": "not_found", "message": "Run not found"}},
                )
        return (dataset, run)

    # Ownership check
    if dataset_id:
        result = await session.execute(
            select(ImportDataset).where(
                ImportDataset.id == dataset_id,
                ImportDataset.created_by_user_id == current_user.id,
            )
        )
        dataset = result.scalar_one_or_none()
        if not dataset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "not_found", "message": "Dataset not found"}},
            )
    else:
        dataset = None

    if run_id:
        result = await session.execute(
            select(ImportRun)
            .join(ImportDataset, ImportRun.dataset_id == ImportDataset.id)
            .where(
                ImportRun.id == run_id,
                ImportDataset.created_by_user_id == current_user.id,
            )
        )
        run = result.scalar_one_or_none()
        if not run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "not_found", "message": "Run not found"}},
            )
    else:
        run = None

    return (dataset, run)
