"""add import_records table

Revision ID: 003_records
Revises: 002_imports
Create Date: 2025-02-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "003_records"
down_revision: Union[str, None] = "002_imports"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "import_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("campaign", sa.String(length=512), nullable=False),
        sa.Column("channel", sa.String(length=255), nullable=False),
        sa.Column("spend", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("clicks", sa.Integer(), nullable=False),
        sa.Column("conversions", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["import_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_import_records_run_id_row_number", "import_records", ["run_id", "row_number"], unique=False)
    op.create_index("ix_import_records_run_id_campaign", "import_records", ["run_id", "campaign"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_import_records_run_id_campaign", table_name="import_records")
    op.drop_index("ix_import_records_run_id_row_number", table_name="import_records")
    op.drop_table("import_records")
