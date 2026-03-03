"""merge lessonstatus uppercase and nav/status lowercase

Revision ID: 4389729ad81a
Revises: g1h2i3j4, i2j3k4l5
Create Date: 2026-03-03 17:02:08.353426

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4389729ad81a'
down_revision = ('g1h2i3j4', 'i2j3k4l5')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass