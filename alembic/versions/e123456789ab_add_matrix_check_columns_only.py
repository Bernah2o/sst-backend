"""Add matrix check columns to occupational_exams (focused migration)

Revision ID: e123456789ab
Revises: d3f4e5a6b7c8
Create Date: 2026-02-23
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "e123456789ab"
down_revision = "d3f4e5a6b7c8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add only the four matrix check columns; avoid unrelated schema changes
    op.execute(
        "ALTER TABLE occupational_exams ADD COLUMN IF NOT EXISTS matrix_i_check boolean"
    )
    op.execute(
        "ALTER TABLE occupational_exams ADD COLUMN IF NOT EXISTS matrix_p_check boolean"
    )
    op.execute(
        "ALTER TABLE occupational_exams ADD COLUMN IF NOT EXISTS matrix_e_check boolean"
    )
    op.execute(
        "ALTER TABLE occupational_exams ADD COLUMN IF NOT EXISTS matrix_carta_check boolean"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE occupational_exams DROP COLUMN IF EXISTS matrix_carta_check"
    )
    op.execute("ALTER TABLE occupational_exams DROP COLUMN IF EXISTS matrix_e_check")
    op.execute("ALTER TABLE occupational_exams DROP COLUMN IF EXISTS matrix_p_check")
    op.execute("ALTER TABLE occupational_exams DROP COLUMN IF EXISTS matrix_i_check")

