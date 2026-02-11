from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str
    REDIS_URL: str
    # Root directory for uploads (e.g. "backend" or "/app/backend"); file_path is relative to this
    UPLOAD_ROOT: str | None = None
    # Security limits (shared between backend and worker)
    MAX_ROWS: int = 500000
    MAX_FIELD_CHARS: int = 10000
    # S3 / MinIO (worker reads from S3 when file_storage=s3)
    S3_ENDPOINT_URL: str | None = None
    S3_ACCESS_KEY: str | None = None
    S3_SECRET_KEY: str | None = None
    S3_BUCKET: str = "etl-uploads"
    S3_REGION: str = "us-east-1"

    def get_sync_database_url(self) -> str:
        """Return a sync driver URL for SQLAlchemy (worker)."""
        url = self.DATABASE_URL
        if "+asyncpg" in url:
            return url.replace("postgresql+asyncpg", "postgresql", 1)
        return url


settings = Settings()
