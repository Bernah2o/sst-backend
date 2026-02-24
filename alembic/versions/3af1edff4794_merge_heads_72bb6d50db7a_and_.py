"""Merge heads 72bb6d50db7a and e323456789ad

Revision ID: 3af1edff4794
Revises: 72bb6d50db7a, e323456789ad
Create Date: 2026-02-23 20:51:57.726848

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3af1edff4794'
down_revision = ('72bb6d50db7a', 'e323456789ad')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass