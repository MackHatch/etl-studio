"""add S3 storage fields: file_storage, s3_bucket, s3_key

Revision ID: 009_s3_storage
Revises: 008_multi_tenant_orgs
Create Date: 2025-02-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "009_s3_storage"
down_revision: Union[str, None] = "008_multi_tenant_orgs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("import_runs", sa.Column("file_storage", sa.String(16), nullable=False, server_default="disk"))
    op.add_column("import_runs", sa.Column("s3_bucket", sa.String(255), nullable=True))
    op.add_column("import_runs", sa.Column("s3_key", sa.String(1024), nullable=True))
    op.create_index("ix_import_runs_s3_bucket_key", "import_runs", ["s3_bucket", "s3_key"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_import_runs_s3_bucket_key", table_name="import_runs")
    op.drop_column("import_runs", "s3_key")
    op.drop_column("import_runs", "s3_bucket")
    op.drop_column("import_runs", "file_storage")
