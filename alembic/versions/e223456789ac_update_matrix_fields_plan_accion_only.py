"""Update occupational_exams matrix fields: drop I/P/E, add matrix_plan_accion

Revision ID: e223456789ac
Revises: e123456789ab
Create Date: 2026-02-23
"""
from alembic import op
import sqlalchemy as sa


revision = "e223456789ac"
down_revision = "e123456789ab"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add matrix_plan_accion if it does not exist
    op.execute(
        "ALTER TABLE occupational_exams ADD COLUMN IF NOT EXISTS matrix_plan_accion text"
    )

    # Drop unused I/P/E columns if they exist
    op.execute(
        "ALTER TABLE occupational_exams DROP COLUMN IF EXISTS matrix_i_check"
    )
    op.execute(
        "ALTER TABLE occupational_exams DROP COLUMN IF EXISTS matrix_p_check"
    )
    op.execute(
        "ALTER TABLE occupational_exams DROP COLUMN IF EXISTS matrix_e_check"
    )


def downgrade() -> None:
    # Recreate I/P/E columns (without data) if needed
    op.execute(
        "ALTER TABLE occupational_exams ADD COLUMN IF NOT EXISTS matrix_i_check boolean"
    )
    op.execute(
        "ALTER TABLE occupational_exams ADD COLUMN IF NOT EXISTS matrix_p_check boolean"
    )
    op.execute(
        "ALTER TABLE occupational_exams ADD COLUMN IF NOT EXISTS matrix_e_check boolean"
    )

    # Drop matrix_plan_accion
    op.execute(
        "ALTER TABLE occupational_exams DROP COLUMN IF EXISTS matrix_plan_accion"
    )

