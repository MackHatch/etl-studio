from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str
    REDIS_URL: str
    JWT_SECRET: str
    BACKEND_PORT: int = 8000
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    ENV: str = "dev"
    JWT_ACCESS_EXPIRES_MINUTES: int = 30
    # Bootstrap admin (optional): create admin user on startup if no users exist
    ADMIN_EMAIL: str | None = None
    ADMIN_PASSWORD: str | None = None
    ADMIN_NAME: str | None = None
    # Demo seed: create demo dataset and run when true
    SEED_DEMO: bool = False
    # Security limits
    MAX_UPLOAD_BYTES: int = 10 * 1024 * 1024  # 10MB
    MAX_COLUMNS: int = 200
    MAX_FIELD_CHARS: int = 10000
    MAX_ROWS: int = 500000
    # SSE limits
    SSE_MAX_CONCURRENT_PER_USER: int = 3
    SSE_MAX_DURATION_SECONDS: int = 600  # 10 minutes
    # Storage backend: "s3" or "disk"
    STORAGE_BACKEND: str = "disk"
    # S3 / MinIO
    S3_ENDPOINT_URL: str | None = None
    S3_ACCESS_KEY: str | None = None
    S3_SECRET_KEY: str | None = None
    S3_BUCKET: str = "etl-uploads"
    S3_REGION: str = "us-east-1"
    S3_USE_SSL: bool = False
    PRESIGN_EXPIRES_SECONDS: int = 900


def _resolve_storage_backend() -> str:
    import os
    explicit = os.environ.get("STORAGE_BACKEND")
    if explicit in ("s3", "disk"):
        return explicit
    if os.environ.get("S3_ENDPOINT_URL") and os.environ.get("S3_ACCESS_KEY"):
        return "s3"
    return "disk"


settings = Settings()
settings.STORAGE_BACKEND = _resolve_storage_backend()
