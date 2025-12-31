"""make_course_id_nullable_in_certificates

Revision ID: 106e441ffcc4
Revises: a09d02d6b9c0
Create Date: 2025-10-08 20:42:31.577955

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '106e441ffcc4'
down_revision = 'a09d02d6b9c0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Make course_id nullable in certificates table
    op.alter_column('certificates', 'course_id',
                    existing_type=sa.INTEGER(),
                    nullable=True)


def downgrade() -> None:
    # Revert course_id to not nullable in certificates table
    op.alter_column('certificates', 'course_id',
                    existing_type=sa.INTEGER(),
                    nullable=False)