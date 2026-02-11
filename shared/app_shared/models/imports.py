import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from sqlalchemy import Date, DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app_shared.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app_shared.models.orgs import Organization


class ImportRunStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class ImportRunAttemptStatus(str, enum.Enum):
    STARTED = "STARTED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class ImportDataset(Base, TimestampMixin):
    __tablename__ = "import_datasets"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    mapping_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    active_schema_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    runs: Mapped[list["ImportRun"]] = relationship(
        "ImportRun",
        back_populates="dataset",
        cascade="all, delete-orphan",
        order_by="ImportRun.created_at.desc()",
    )
    schema_versions: Mapped[list["DatasetSchemaVersion"]] = relationship(
        "DatasetSchemaVersion",
        back_populates="dataset",
        cascade="all, delete-orphan",
        order_by="DatasetSchemaVersion.version.desc()",
    )
    organization: Mapped["Organization"] = relationship("Organization", back_populates="datasets")


class ImportRun(Base, TimestampMixin):
    __tablename__ = "import_runs"

    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("import_datasets.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[ImportRunStatus] = mapped_column(
        Enum(ImportRunStatus),
        nullable=False,
        default=ImportRunStatus.DRAFT,
    )
    schema_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_storage: Mapped[str] = mapped_column(String(16), default="disk", nullable=False)
    file_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    s3_bucket: Mapped[str | None] = mapped_column(String(255), nullable=True)
    s3_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    file_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    row_limit_exceeded: Mapped[bool] = mapped_column(default=False, nullable=False)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_rows: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processed_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    success_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    dlq: Mapped[bool] = mapped_column(default=False, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_import_runs_dataset_id_created_at", "dataset_id", "created_at"),
        Index("ix_import_runs_status_created_at", "status", "created_at"),
    )

    dataset: Mapped["ImportDataset"] = relationship("ImportDataset", back_populates="runs")
    attempts: Mapped[list["ImportRunAttempt"]] = relationship(
        "ImportRunAttempt",
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="ImportRunAttempt.attempt_number",
    )
    errors: Mapped[list["ImportRowError"]] = relationship(
        "ImportRowError",
        back_populates="run",
        cascade="all, delete-orphan",
    )
    records: Mapped[list["ImportRecord"]] = relationship(
        "ImportRecord",
        back_populates="run",
        cascade="all, delete-orphan",
    )


class ImportRunAttempt(Base):
    __tablename__ = "import_run_attempts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("import_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ImportRunAttemptStatus] = mapped_column(
        Enum(ImportRunAttemptStatus),
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    traceback: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_import_run_attempts_run_id", "run_id"),
        Index("ix_import_run_attempts_attempt_number", "run_id", "attempt_number"),
    )

    run: Mapped[ImportRun] = relationship("ImportRun", back_populates="attempts")


class ImportRowError(Base):
    __tablename__ = "import_row_errors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("import_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    field: Mapped[str | None] = mapped_column(String(255), nullable=True)
    message: Mapped[str] = mapped_column(String(1024), nullable=False)
    raw_row: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (Index("ix_import_row_errors_run_id_row_number", "run_id", "row_number"),)

    run: Mapped["ImportRun"] = relationship("ImportRun", back_populates="errors")


class ImportRecord(Base):
    __tablename__ = "import_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("import_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    campaign: Mapped[str] = mapped_column(String(512), nullable=False)
    channel: Mapped[str] = mapped_column(String(255), nullable=False)
    spend: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    clicks: Mapped[int] = mapped_column(Integer, nullable=False)
    conversions: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_import_records_run_id_row_number", "run_id", "row_number"),
        Index("ix_import_records_run_id_campaign", "run_id", "campaign"),
    )

    run: Mapped["ImportRun"] = relationship("ImportRun", back_populates="records")


class DatasetSchemaVersion(Base, TimestampMixin):
    __tablename__ = "dataset_schema_versions"

    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("import_datasets.id", ondelete="CASCADE"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    mapping_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    rules_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        Index("ix_dataset_schema_versions_dataset_version", "dataset_id", "version", unique=True),
        Index("ix_dataset_schema_versions_dataset_created", "dataset_id", "created_at"),
    )

    dataset: Mapped["ImportDataset"] = relationship("ImportDataset", back_populates="schema_versions")
