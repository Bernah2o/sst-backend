"""Merge migration branches

Revision ID: efc9344c6d31
Revises: 20fba412cfd0, 2a1b3c4d5e6f
Create Date: 2025-09-21 17:54:56.038117

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'efc9344c6d31'
down_revision = ('20fba412cfd0', '2a1b3c4d5e6f')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass