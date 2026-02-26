"""uppercase lessonstatus enum values

Revision ID: g1h2i3j4
Revises: f1g2h3i4
Create Date: 2026-02-26 15:10:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'g1h2i3j4'
down_revision = 'f1g2h3i4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # convert column to text to allow enum recreation
    op.execute("ALTER TABLE interactive_lessons ALTER COLUMN status TYPE text")

    # recreate uppercase enum
    op.execute("DROP TYPE IF EXISTS lessonstatus")
    op.execute("CREATE TYPE lessonstatus AS ENUM ('DRAFT','PUBLISHED','ARCHIVED')")

    # update data to uppercase
    op.execute(
        "UPDATE interactive_lessons SET status = UPPER(status) "
        "WHERE status IS NOT NULL AND status != UPPER(status)"
    )

    # convert back to enum
    op.execute(
        "ALTER TABLE interactive_lessons ALTER COLUMN status TYPE lessonstatus "
        "USING status::lessonstatus"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE interactive_lessons ALTER COLUMN status TYPE text")
    op.execute("DROP TYPE IF EXISTS lessonstatus")
    op.execute("CREATE TYPE lessonstatus AS ENUM ('draft','published','archived')")
    op.execute(
        "UPDATE interactive_lessons SET status = LOWER(status) "
        "WHERE status IS NOT NULL AND status != LOWER(status)"
    )
    op.execute(
        "ALTER TABLE interactive_lessons ALTER COLUMN status TYPE lessonstatus "
        "USING status::lessonstatus"
    )
