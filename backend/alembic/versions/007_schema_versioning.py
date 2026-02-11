"""add schema versioning: DatasetSchemaVersion table, active_schema_version, schema_version

Revision ID: 007_schema_versioning
Revises: 006_security_fields
Create Date: 2025-02-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "007_schema_versioning"
down_revision: Union[str, None] = "006_security_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add active_schema_version to import_datasets
    op.add_column(
        "import_datasets",
        sa.Column("active_schema_version", sa.Integer(), nullable=False, server_default="1"),
    )

    # Add schema_version to import_runs
    op.add_column(
        "import_runs",
        sa.Column("schema_version", sa.Integer(), nullable=True),
    )

    # Create dataset_schema_versions table
    op.create_table(
        "dataset_schema_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dataset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("mapping_json", postgresql.JSONB(), nullable=False),
        sa.Column("rules_json", postgresql.JSONB(), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["dataset_id"], ["import_datasets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_dataset_schema_versions_dataset_version",
        "dataset_schema_versions",
        ["dataset_id", "version"],
        unique=True,
    )
    op.create_index(
        "ix_dataset_schema_versions_dataset_created",
        "dataset_schema_versions",
        ["dataset_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_dataset_schema_versions_dataset_created", table_name="dataset_schema_versions")
    op.drop_index("ix_dataset_schema_versions_dataset_version", table_name="dataset_schema_versions")
    op.drop_table("dataset_schema_versions")
    op.drop_column("import_runs", "schema_version")
    op.drop_column("import_datasets", "active_schema_version")
