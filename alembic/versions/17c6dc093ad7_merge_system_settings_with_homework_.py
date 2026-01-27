"""merge system_settings with homework_assessments

Revision ID: 17c6dc093ad7
Revises: a1b2c3d4e5f7, c92a4567f855
Create Date: 2026-01-27 09:28:31.202418

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '17c6dc093ad7'
down_revision = ('a1b2c3d4e5f7', 'c92a4567f855')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass