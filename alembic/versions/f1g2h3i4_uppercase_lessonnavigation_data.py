"""uppercase lesson navigation type values

Revision ID: f1g2h3i4
Revises: e9f0g1h2abc
Create Date: 2026-02-26 15:00:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'f1g2h3i4'
down_revision = 'e9f0g1h2abc'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # convert column to text to drop/recreate type safely
    op.execute("ALTER TABLE interactive_lessons ALTER COLUMN navigation_type TYPE text")

    # ensure type has uppercase values (recreate it)
    op.execute("DROP TYPE IF EXISTS lessonnavigationtype")
    op.execute("CREATE TYPE lessonnavigationtype AS ENUM ('SEQUENTIAL','FREE')")

    # update existing rows to uppercase before casting back in case any remain
    op.execute(
        "UPDATE interactive_lessons SET navigation_type = UPPER(navigation_type) "
        "WHERE navigation_type IS NOT NULL AND navigation_type != UPPER(navigation_type)"
    )

    # convert column back to enum
    op.execute(
        "ALTER TABLE interactive_lessons ALTER COLUMN navigation_type TYPE lessonnavigationtype "
        "USING navigation_type::lessonnavigationtype"
    )


def downgrade() -> None:
    # revert to lowercase enum and values
    op.execute("DROP TYPE IF EXISTS lessonnavigationtype")
    op.execute("CREATE TYPE lessonnavigationtype AS ENUM ('sequential','free')")
    op.execute(
        "UPDATE interactive_lessons SET navigation_type = LOWER(navigation_type) "
        "WHERE navigation_type IS NOT NULL AND navigation_type != LOWER(navigation_type)"
    )
    op.execute(
        "ALTER TABLE interactive_lessons ALTER COLUMN navigation_type TYPE lessonnavigationtype "
        "USING navigation_type::lessonnavigationtype"
    )
