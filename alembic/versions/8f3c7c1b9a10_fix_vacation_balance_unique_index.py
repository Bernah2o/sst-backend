"""fix vacation balance unique index

Revision ID: 8f3c7c1b9a10
Revises: bb5b16f9fc52
Create Date: 2025-12-01 16:45:00

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '8f3c7c1b9a10'
down_revision = '1628902c0728'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Drop old unique index on worker_id if present
    op.execute('DROP INDEX IF EXISTS ix_vacation_balances_worker_id')
    # Create composite unique index on (worker_id, year)
    op.execute('CREATE UNIQUE INDEX IF NOT EXISTS ux_vacation_balances_worker_year ON vacation_balances (worker_id, year)')


def downgrade() -> None:
    # Drop composite unique index
    op.execute('DROP INDEX IF EXISTS ux_vacation_balances_worker_year')
    # Restore old unique index on worker_id
    op.execute('CREATE UNIQUE INDEX IF NOT EXISTS ix_vacation_balances_worker_id ON vacation_balances (worker_id)')
