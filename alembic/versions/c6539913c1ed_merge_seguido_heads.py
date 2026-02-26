"""merge seguido heads

Revision ID: c6539913c1ed
Revises: bc7eeb3a5de3, c5d6e7f809a1
Create Date: 2026-02-26 08:53:59.049176

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c6539913c1ed'
down_revision = ('bc7eeb3a5de3', 'c5d6e7f809a1')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass