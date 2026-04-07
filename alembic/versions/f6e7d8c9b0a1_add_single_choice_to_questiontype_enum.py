"""add_single_choice_to_questiontype_enum

Revision ID: f6e7d8c9b0a1
Revises: d9f1e2a3b4c5
Create Date: 2026-04-07 20:15:00.000000
"""

from alembic import op


revision = "f6e7d8c9b0a1"
down_revision = "d9f1e2a3b4c5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE questiontype ADD VALUE IF NOT EXISTS 'SINGLE_CHOICE'")


def downgrade() -> None:
    pass
