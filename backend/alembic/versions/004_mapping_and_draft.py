"""add mapping_json and DRAFT status

Revision ID: 004_mapping_draft
Revises: 003_records
Create Date: 2025-02-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "004_mapping_draft"
down_revision: Union[str, None] = "003_records"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "import_datasets",
        sa.Column("mapping_json", JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.execute("ALTER TYPE importrunstatus ADD VALUE IF NOT EXISTS 'DRAFT'")


def downgrade() -> None:
    op.drop_column("import_datasets", "mapping_json")
    # Note: DRAFT enum value cannot be removed from PostgreSQL without recreating the type.
