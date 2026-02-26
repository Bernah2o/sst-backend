"""lowercase lessonnavigationtype enum values

Revision ID: e9f0g1h2abc
Revises: d7e8f901234
Create Date: 2026-02-26 14:50:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e9f0g1h2abc'
down_revision = 'd7e8f901234'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ensure the column can be updated
    op.execute("ALTER TABLE interactive_lessons ALTER COLUMN navigation_type TYPE text")

    # normalise data to uppercase (to match enum names)
    op.execute(
        "UPDATE interactive_lessons SET navigation_type = UPPER(navigation_type) "
        "WHERE navigation_type IS NOT NULL AND navigation_type != UPPER(navigation_type)"
    )

    # recreate enum type with uppercase labels
    op.execute("DROP TYPE IF EXISTS lessonnavigationtype")
    op.execute("CREATE TYPE lessonnavigationtype AS ENUM ('SEQUENTIAL','FREE')")

    # convert column back to enum
    op.execute(
        "ALTER TABLE interactive_lessons ALTER COLUMN navigation_type TYPE lessonnavigationtype "
        "USING navigation_type::lessonnavigationtype"
    )


def downgrade() -> None:
    # convert to text to allow changes
    op.execute("ALTER TABLE interactive_lessons ALTER COLUMN navigation_type TYPE text")
    # recreate lowercase enum and cast back
    op.execute("DROP TYPE IF EXISTS lessonnavigationtype")
    op.execute("CREATE TYPE lessonnavigationtype AS ENUM ('sequential','free')")
    op.execute(
        "ALTER TABLE interactive_lessons ALTER COLUMN navigation_type TYPE lessonnavigationtype "
        "USING navigation_type::lessonnavigationtype"
    )
