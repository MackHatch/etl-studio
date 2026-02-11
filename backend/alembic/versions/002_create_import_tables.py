"""create import_datasets, import_runs, import_row_errors

Revision ID: 002_imports
Revises: 001_users
Create Date: 2025-02-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "002_imports"
down_revision: Union[str, None] = "001_users"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "import_datasets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=1024), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_import_datasets_name"), "import_datasets", ["name"], unique=False)

    op.execute("CREATE TYPE importrunstatus AS ENUM ('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED')")
    op.create_table(
        "import_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("dataset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.Enum("QUEUED", "RUNNING", "SUCCEEDED", "FAILED", name="importrunstatus"), nullable=False),
        sa.Column("file_path", sa.String(length=1024), nullable=True),
        sa.Column("progress_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_rows", sa.Integer(), nullable=True),
        sa.Column("processed_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["dataset_id"], ["import_datasets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_import_runs_dataset_id_created_at", "import_runs", ["dataset_id", "created_at"], unique=False)
    op.create_index("ix_import_runs_status_created_at", "import_runs", ["status", "created_at"], unique=False)

    op.create_table(
        "import_row_errors",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("field", sa.String(length=255), nullable=True),
        sa.Column("message", sa.String(length=1024), nullable=False),
        sa.Column("raw_row", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["import_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_import_row_errors_run_id_row_number", "import_row_errors", ["run_id", "row_number"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_import_row_errors_run_id_row_number", table_name="import_row_errors")
    op.drop_table("import_row_errors")
    op.drop_index("ix_import_runs_status_created_at", table_name="import_runs")
    op.drop_index("ix_import_runs_dataset_id_created_at", table_name="import_runs")
    op.drop_table("import_runs")
    op.execute("DROP TYPE importrunstatus")
    op.drop_index(op.f("ix_import_datasets_name"), table_name="import_datasets")
    op.drop_table("import_datasets")
