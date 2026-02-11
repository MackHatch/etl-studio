"""add security fields: file_sha256, file_size_bytes, row_limit_exceeded

Revision ID: 006_security_fields
Revises: 005_attempts_dlq
Create Date: 2025-02-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "006_security_fields"
down_revision: Union[str, None] = "005_attempts_dlq"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "import_runs",
        sa.Column("file_sha256", sa.String(64), nullable=True),
    )
    op.add_column(
        "import_runs",
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
    )
    op.add_column(
        "import_runs",
        sa.Column("row_limit_exceeded", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index("ix_import_runs_file_sha256", "import_runs", ["file_sha256"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_import_runs_file_sha256", table_name="import_runs")
    op.drop_column("import_runs", "row_limit_exceeded")
    op.drop_column("import_runs", "file_size_bytes")
    op.drop_column("import_runs", "file_sha256")
