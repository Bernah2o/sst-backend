"""add_end_date_to_virtual_sessions

Revision ID: f4a7bc6c9bb6
Revises: 6f894a3d47af
Create Date: 2025-11-01 17:19:58.795203

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f4a7bc6c9bb6'
down_revision = '6f894a3d47af'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add end_date column to virtual_sessions table
    op.add_column('virtual_sessions', sa.Column('end_date', sa.DateTime(), nullable=True))
    
    # Update existing records to set end_date based on session_date + 2 hours
    op.execute("""
        UPDATE virtual_sessions 
        SET end_date = session_date + INTERVAL '2 hours'
        WHERE end_date IS NULL
    """)
    
    # Make end_date not nullable after setting default values
    op.alter_column('virtual_sessions', 'end_date', nullable=False)


def downgrade() -> None:
    # Remove end_date column from virtual_sessions table
    op.drop_column('virtual_sessions', 'end_date')