"""Remove matrix_carta_check and matrix_plan_accion from occupational_exams

Revision ID: e323456789ad
Revises: e223456789ac
Create Date: 2026-02-23
"""
from alembic import op
import sqlalchemy as sa


revision = "e323456789ad"
down_revision = "e223456789ac"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE occupational_exams DROP COLUMN IF EXISTS matrix_carta_check"
    )
    op.execute(
        "ALTER TABLE occupational_exams DROP COLUMN IF EXISTS matrix_plan_accion"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE occupational_exams ADD COLUMN IF NOT EXISTS matrix_carta_check boolean DEFAULT FALSE"
    )
    op.execute(
        "ALTER TABLE occupational_exams ADD COLUMN IF NOT EXISTS matrix_plan_accion text"
    )

