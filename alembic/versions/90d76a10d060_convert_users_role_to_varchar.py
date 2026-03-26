"""convert_users_role_to_varchar

Revision ID: 90d76a10d060
Revises: 61ec3396563f
Create Date: 2026-03-26 11:58:47.427247

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '90d76a10d060'
down_revision = '61ec3396563f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    role_column = conn.execute(
        sa.text(
            """
            SELECT data_type
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'users'
              AND column_name = 'role'
            """
        )
    ).fetchone()

    if not role_column:
        return

    if role_column[0] != "character varying":
        op.execute(
            "ALTER TABLE users ALTER COLUMN role TYPE VARCHAR(50) USING role::text"
        )

    op.execute("UPDATE users SET role = LOWER(role) WHERE role IS NOT NULL")
    op.execute("ALTER TABLE users ALTER COLUMN role SET DEFAULT 'employee'")


def downgrade() -> None:
    conn = op.get_bind()
    role_column = conn.execute(
        sa.text(
            """
            SELECT data_type
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'users'
              AND column_name = 'role'
            """
        )
    ).fetchone()

    if not role_column:
        return

    userrole_type_exists = conn.execute(
        sa.text(
            """
            SELECT 1
            FROM pg_type
            WHERE typname = 'userrole'
            """
        )
    ).fetchone()

    if not userrole_type_exists:
        op.execute(
            "CREATE TYPE userrole AS ENUM ('admin', 'trainer', 'employee', 'supervisor')"
        )
    else:
        op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'admin'")
        op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'trainer'")
        op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'employee'")
        op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'supervisor'")

    op.execute("UPDATE users SET role = LOWER(role) WHERE role IS NOT NULL")

    if role_column[0] == "character varying":
        op.execute(
            "ALTER TABLE users ALTER COLUMN role TYPE userrole USING LOWER(role)::userrole"
        )

    op.execute("ALTER TABLE users ALTER COLUMN role SET DEFAULT 'employee'::userrole")
