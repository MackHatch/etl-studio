"""add run attempts and DLQ fields

Revision ID: 005_attempts_dlq
Revises: 004_mapping_draft
Create Date: 2025-02-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "005_attempts_dlq"
down_revision: Union[str, None] = "004_mapping_draft"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "import_runs",
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "import_runs",
        sa.Column("dlq", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "import_runs",
        sa.Column("last_error", sa.Text(), nullable=True),
    )

    importrunattemptstatus = postgresql.ENUM(
        "STARTED",
        "SUCCEEDED",
        "FAILED",
        name="importrunattemptstatus",
        create_type=True,
    )
    importrunattemptstatus.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "import_run_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", importrunattemptstatus, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("traceback", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["import_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_import_run_attempts_run_id", "import_run_attempts", ["run_id"], unique=False)
    op.create_index("ix_import_run_attempts_attempt_number", "import_run_attempts", ["run_id", "attempt_number"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_import_run_attempts_attempt_number", table_name="import_run_attempts")
    op.drop_index("ix_import_run_attempts_run_id", table_name="import_run_attempts")
    op.drop_table("import_run_attempts")
    postgresql.ENUM(name="importrunattemptstatus").drop(op.get_bind(), checkfirst=True)

    op.drop_column("import_runs", "last_error")
    op.drop_column("import_runs", "dlq")
    op.drop_column("import_runs", "attempt_count")
