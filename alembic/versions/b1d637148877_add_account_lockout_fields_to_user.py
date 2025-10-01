"""add_account_lockout_fields_to_user

Revision ID: b1d637148877
Revises: 95a56ca27c44
Create Date: 2025-10-01 13:30:35.857515

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b1d637148877'
down_revision = '95a56ca27c44'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add account lockout fields to users table
    op.add_column('users', sa.Column('failed_login_attempts', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('account_locked_until', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('last_failed_login', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    # Remove account lockout fields from users table
    op.drop_column('users', 'last_failed_login')
    op.drop_column('users', 'account_locked_until')
    op.drop_column('users', 'failed_login_attempts')