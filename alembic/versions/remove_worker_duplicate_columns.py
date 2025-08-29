"""Remove duplicate columns from workers table

Revision ID: remove_worker_duplicates
Revises: 4f5259a15973
Create Date: 2025-08-29 09:50:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'remove_worker_duplicates'
down_revision = '4f5259a15973'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Remove duplicate columns from workers table if they exist
    # These columns conflict with @property definitions in the model
    
    # Check if columns exist before dropping them
    connection = op.get_bind()
    
    # Check for cedula column
    result = connection.execute(
        sa.text("SELECT column_name FROM information_schema.columns WHERE table_name='workers' AND column_name='cedula'")
    )
    if result.fetchone():
        try:
            op.drop_index('ix_workers_cedula', table_name='workers')
        except:
            pass  # Index might not exist
        op.drop_column('workers', 'cedula')
    
    # Check for cargo column
    result = connection.execute(
        sa.text("SELECT column_name FROM information_schema.columns WHERE table_name='workers' AND column_name='cargo'")
    )
    if result.fetchone():
        op.drop_column('workers', 'cargo')
    
    # Check for salario column
    result = connection.execute(
        sa.text("SELECT column_name FROM information_schema.columns WHERE table_name='workers' AND column_name='salario'")
    )
    if result.fetchone():
        op.drop_column('workers', 'salario')


def downgrade() -> None:
    # Add back the duplicate columns if needed for rollback
    op.add_column('workers', sa.Column('cedula', sa.String(50), nullable=True))
    op.add_column('workers', sa.Column('cargo', sa.String(100), nullable=True))
    op.add_column('workers', sa.Column('salario', sa.Numeric(12, 2), nullable=True))
    
    # Recreate index for cedula
    op.create_index('ix_workers_cedula', 'workers', ['cedula'], unique=True)
    
    # Populate the duplicate columns with data from main columns
    connection = op.get_bind()
    connection.execute(
        sa.text("UPDATE workers SET cedula = document_number, cargo = position, salario = salary_ibc")
    )