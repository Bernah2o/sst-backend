"""make_course_id_nullable_in_evaluations

Revision ID: a1b2c3d4e5f9
Revises: 9ab4c6d8e0f1
Create Date: 2026-04-23

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f9'
down_revision = '9ab4c6d8e0f1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column('evaluations', 'course_id',
                    existing_type=sa.INTEGER(),
                    nullable=True)


def downgrade() -> None:
    op.alter_column('evaluations', 'course_id',
                    existing_type=sa.INTEGER(),
                    nullable=False)
