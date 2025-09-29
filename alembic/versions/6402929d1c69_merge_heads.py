"""Merge heads

Revision ID: 6402929d1c69
Revises: 1b4fe8606608, bb5b16f9fc52
Create Date: 2025-09-28 20:46:13.967849

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6402929d1c69'
down_revision = ('1b4fe8606608', 'bb5b16f9fc52')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass