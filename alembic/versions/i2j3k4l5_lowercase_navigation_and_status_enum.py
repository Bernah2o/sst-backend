"""lowercase navigation_type and status enums

Revision ID: i2j3k4l5
Revises: a1bc2d3e4f5g
Create Date: 2026-03-03 12:30:00.000000
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "i2j3k4l5"
down_revision = "a1bc2d3e4f5g"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # convert navigation_type to text, normalize to lowercase, recreate enum
    op.execute("ALTER TABLE interactive_lessons ALTER COLUMN navigation_type TYPE text")
    op.execute(
        "UPDATE interactive_lessons SET navigation_type = LOWER(navigation_type) "
        "WHERE navigation_type IS NOT NULL AND navigation_type != LOWER(navigation_type)"
    )
    op.execute("DROP TYPE IF EXISTS lessonnavigationtype")
    op.execute("CREATE TYPE lessonnavigationtype AS ENUM ('sequential','free')")
    op.execute(
        "ALTER TABLE interactive_lessons ALTER COLUMN navigation_type TYPE lessonnavigationtype "
        "USING navigation_type::lessonnavigationtype"
    )

    # convert status to text and lowercase
    op.execute("ALTER TABLE interactive_lessons ALTER COLUMN status TYPE text")
    op.execute(
        "UPDATE interactive_lessons SET status = LOWER(status) "
        "WHERE status IS NOT NULL AND status != LOWER(status)"
    )
    op.execute("DROP TYPE IF EXISTS lessonstatus")
    op.execute("CREATE TYPE lessonstatus AS ENUM ('draft','published','archived')")
    op.execute(
        "ALTER TABLE interactive_lessons ALTER COLUMN status TYPE lessonstatus "
        "USING status::lessonstatus"
    )


def downgrade() -> None:
    # revert status to uppercase enum
    op.execute("ALTER TABLE interactive_lessons ALTER COLUMN status TYPE text")
    op.execute(
        "UPDATE interactive_lessons SET status = UPPER(status) "
        "WHERE status IS NOT NULL AND status != UPPER(status)"
    )
    op.execute("DROP TYPE IF EXISTS lessonstatus")
    op.execute("CREATE TYPE lessonstatus AS ENUM ('DRAFT','PUBLISHED','ARCHIVED')")
    op.execute(
        "ALTER TABLE interactive_lessons ALTER COLUMN status TYPE lessonstatus "
        "USING status::lessonstatus"
    )

    # revert navigation_type to uppercase enum
    op.execute("ALTER TABLE interactive_lessons ALTER COLUMN navigation_type TYPE text")
    op.execute(
        "UPDATE interactive_lessons SET navigation_type = UPPER(navigation_type) "
        "WHERE navigation_type IS NOT NULL AND navigation_type != UPPER(navigation_type)"
    )
    op.execute("DROP TYPE IF EXISTS lessonnavigationtype")
    op.execute("CREATE TYPE lessonnavigationtype AS ENUM ('SEQUENTIAL','FREE')")
    op.execute(
        "ALTER TABLE interactive_lessons ALTER COLUMN navigation_type TYPE lessonnavigationtype "
        "USING navigation_type::lessonnavigationtype"
    )
