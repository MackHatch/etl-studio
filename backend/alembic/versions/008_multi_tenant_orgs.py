"""add multi-tenant organizations: Organization, OrganizationMember, OrganizationInvite, org_id on datasets, active_org_id on users

Revision ID: 008_multi_tenant_orgs
Revises: 007_schema_versioning
Create Date: 2025-02-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "008_multi_tenant_orgs"
down_revision: Union[str, None] = "007_schema_versioning"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create orgmemberrole enum
    orgmemberrole = postgresql.ENUM(
        "OWNER",
        "ADMIN",
        "MEMBER",
        name="orgmemberrole",
        create_type=True,
    )
    orgmemberrole.create(op.get_bind(), checkfirst=True)

    # Create organizations table
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_organizations_name", "organizations", ["name"], unique=False)

    # Create organization_members table
    op.create_table(
        "organization_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", orgmemberrole, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_organization_members_org_user",
        "organization_members",
        ["org_id", "user_id"],
        unique=True,
    )
    op.create_index("ix_organization_members_user", "organization_members", ["user_id"], unique=False)

    # Create organization_invites table
    op.create_table(
        "organization_invites",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("role", orgmemberrole, nullable=False),
        sa.Column("token", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_organization_invites_email", "organization_invites", ["email"], unique=False)
    op.create_index("ix_organization_invites_token", "organization_invites", ["token"], unique=True)
    op.create_index("ix_organization_invites_org", "organization_invites", ["org_id"], unique=False)
    op.create_index("ix_organization_invites_expires", "organization_invites", ["expires_at"], unique=False)

    # Add active_org_id to users
    op.add_column(
        "users",
        sa.Column("active_org_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_users_active_org_id",
        "users",
        "organizations",
        ["active_org_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Add org_id to import_datasets (nullable first for migration)
    op.add_column(
        "import_datasets",
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    # Backfill: create personal orgs for existing users with datasets
    # This is a data migration - we'll create orgs and assign datasets
    connection = op.get_bind()
    
    # Get all users who have datasets
    result = connection.execute(
        sa.text("""
            SELECT DISTINCT created_by_user_id 
            FROM import_datasets 
            WHERE created_by_user_id IS NOT NULL
        """)
    )
    user_ids = [row[0] for row in result]
    
    for user_id in user_ids:
        # Get user name
        user_result = connection.execute(
            sa.text("SELECT name FROM users WHERE id = :user_id"),
            {"user_id": user_id}
        )
        user_row = user_result.fetchone()
        if not user_row:
            continue
        user_name = user_row[0]
        
        # Create personal org
        import uuid
        org_id = uuid.uuid4()
        connection.execute(
            sa.text("""
                INSERT INTO organizations (id, name, created_at, updated_at)
                VALUES (:org_id, :name, NOW(), NOW())
            """),
            {"org_id": org_id, "name": f"{user_name} Workspace"}
        )
        
        # Add user as OWNER
        connection.execute(
            sa.text("""
                INSERT INTO organization_members (id, org_id, user_id, role, created_at)
                VALUES (:id, :org_id, :user_id, 'OWNER', NOW())
            """),
            {"id": uuid.uuid4(), "org_id": org_id, "user_id": user_id}
        )
        
        # Update user's active_org_id
        connection.execute(
            sa.text("UPDATE users SET active_org_id = :org_id WHERE id = :user_id"),
            {"org_id": org_id, "user_id": user_id}
        )
        
        # Assign datasets to org
        connection.execute(
            sa.text("UPDATE import_datasets SET org_id = :org_id WHERE created_by_user_id = :user_id"),
            {"org_id": org_id, "user_id": user_id}
        )
    
    # Create orgs for users without datasets
    result = connection.execute(
        sa.text("SELECT id, name FROM users WHERE active_org_id IS NULL")
    )
    for row in result:
        user_id, user_name = row
        import uuid
        org_id = uuid.uuid4()
        connection.execute(
            sa.text("""
                INSERT INTO organizations (id, name, created_at, updated_at)
                VALUES (:org_id, :name, NOW(), NOW())
            """),
            {"org_id": org_id, "name": f"{user_name} Workspace"}
        )
        connection.execute(
            sa.text("""
                INSERT INTO organization_members (id, org_id, user_id, role, created_at)
                VALUES (:id, :org_id, :user_id, 'OWNER', NOW())
            """),
            {"id": uuid.uuid4(), "org_id": org_id, "user_id": user_id}
        )
        connection.execute(
            sa.text("UPDATE users SET active_org_id = :org_id WHERE id = :user_id"),
            {"org_id": org_id, "user_id": user_id}
        )

    # Now make org_id NOT NULL
    op.alter_column("import_datasets", "org_id", nullable=False)
    op.create_foreign_key(
        "fk_import_datasets_org_id",
        "import_datasets",
        "organizations",
        ["org_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_import_datasets_org_id", "import_datasets", ["org_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_import_datasets_org_id", table_name="import_datasets")
    op.drop_constraint("fk_import_datasets_org_id", "import_datasets", type_="foreignkey")
    op.drop_column("import_datasets", "org_id")
    op.drop_constraint("fk_users_active_org_id", "users", type_="foreignkey")
    op.drop_column("users", "active_org_id")
    op.drop_index("ix_organization_invites_expires", table_name="organization_invites")
    op.drop_index("ix_organization_invites_org", table_name="organization_invites")
    op.drop_index("ix_organization_invites_token", table_name="organization_invites")
    op.drop_index("ix_organization_invites_email", table_name="organization_invites")
    op.drop_table("organization_invites")
    op.drop_index("ix_organization_members_user", table_name="organization_members")
    op.drop_index("ix_organization_members_org_user", table_name="organization_members")
    op.drop_table("organization_members")
    op.drop_index("ix_organizations_name", table_name="organizations")
    op.drop_table("organizations")
    postgresql.ENUM(name="orgmemberrole").drop(op.get_bind(), checkfirst=True)
