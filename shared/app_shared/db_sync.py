from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app_shared.config import settings
from app_shared.models.base import Base

sync_engine = create_engine(
    settings.get_sync_database_url(),
    pool_pre_ping=True,
)
SyncSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)


def get_sync_session() -> Session:
    return SyncSessionLocal()
