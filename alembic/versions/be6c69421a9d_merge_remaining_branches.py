"""Merge remaining branches

Revision ID: be6c69421a9d
Revises: 7a68cc80eff9_v2, efc9344c6d31
Create Date: 2025-09-21 17:56:32.220688

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'be6c69421a9d'
down_revision = ('7a68cc80eff9_v2', 'efc9344c6d31')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass