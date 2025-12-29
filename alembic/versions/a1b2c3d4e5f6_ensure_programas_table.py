"""ensure_programas_table

Revision ID: a1b2c3d4e5f6
Revises: 8f3c7c1b9a10
Create Date: 2025-12-30 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '8f3c7c1b9a10'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()
    
    if 'programas' not in tables:
        op.create_table('programas',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('nombre_programa', sa.String(length=200), nullable=False),
            sa.Column('activo', sa.Boolean(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_programas_id'), 'programas', ['id'], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()
    
    if 'programas' in tables:
        op.drop_index(op.f('ix_programas_id'), table_name='programas')
        op.drop_table('programas')
