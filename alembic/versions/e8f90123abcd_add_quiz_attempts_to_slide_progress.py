"""add quiz_attempts to user_slide_progress

Agrega el campo quiz_attempts para permitir múltiples intentos en quizzes.

Revision ID: e8f90123abcd
Revises: d7e8f90123ab
Create Date: 2026-02-05 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e8f90123abcd'
down_revision = 'd7e8f90123ab'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Agregar columna quiz_attempts a user_slide_progress
    op.add_column('user_slide_progress',
        sa.Column('quiz_attempts', sa.Integer(), nullable=False, server_default='0')
    )


def downgrade() -> None:
    # Eliminar columna quiz_attempts
    op.drop_column('user_slide_progress', 'quiz_attempts')
