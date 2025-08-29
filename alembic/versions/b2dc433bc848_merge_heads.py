"""merge_heads

Revision ID: b2dc433bc848
Revises: 162f680b5a53, 20250829_090327_create_user_progress_tables
Create Date: 2025-08-29 09:09:51.952635

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2dc433bc848'
down_revision = ('162f680b5a53', '20250829_090327_create_user_progress_tables')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass