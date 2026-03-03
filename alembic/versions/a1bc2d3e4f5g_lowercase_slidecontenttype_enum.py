"""lowercase slidecontenttype enum values

Revision ID: a1bc2d3e4f5g
Revises: e9f0g1h2abc
Create Date: 2026-03-03 12:00:00.000000
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "a1bc2d3e4f5g"
down_revision = "e9f0g1h2abc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # convert slide_type column to text to allow enum recreation
    op.execute("ALTER TABLE lesson_slides ALTER COLUMN slide_type TYPE text")

    # normalise existing data to lowercase (should already be but safe)
    op.execute(
        "UPDATE lesson_slides SET slide_type = LOWER(slide_type) "
        "WHERE slide_type IS NOT NULL AND slide_type != LOWER(slide_type)"
    )

    # drop and recreate enum with lowercase labels
    op.execute("DROP TYPE IF EXISTS slidecontenttype")
    op.execute(
        "CREATE TYPE slidecontenttype AS ENUM ('text','image','video','text_image','quiz','interactive')"
    )

    # convert column back to enum type
    op.execute(
        "ALTER TABLE lesson_slides ALTER COLUMN slide_type TYPE slidecontenttype "
        "USING slide_type::slidecontenttype"
    )


def downgrade() -> None:
    # revert to uppercase values (mirror earlier migrations)
    op.execute("ALTER TABLE lesson_slides ALTER COLUMN slide_type TYPE text")
    op.execute(
        "UPDATE lesson_slides SET slide_type = UPPER(slide_type) "
        "WHERE slide_type IS NOT NULL AND slide_type != UPPER(slide_type)"
    )
    op.execute("DROP TYPE IF EXISTS slidecontenttype")
    op.execute(
        "CREATE TYPE slidecontenttype AS ENUM ('TEXT','IMAGE','VIDEO','TEXT_IMAGE','QUIZ','INTERACTIVE')"
    )
    op.execute(
        "ALTER TABLE lesson_slides ALTER COLUMN slide_type TYPE slidecontenttype "
        "USING slide_type::slidecontenttype"
    )
