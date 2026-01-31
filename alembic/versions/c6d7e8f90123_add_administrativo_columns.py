"""add administrativo columns to empresas and matriz_legal_normas

Agrega las columnas para la característica de trabajo administrativo
si no existen (para bases de datos que corrieron la migración anterior
antes de que se agregaran estas columnas):
- empresas.tiene_trabajo_administrativo
- matriz_legal_normas.aplica_trabajo_administrativo

Revision ID: c6d7e8f90123
Revises: b5c6d7e8f901
Create Date: 2026-01-30 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = 'c6d7e8f90123'
down_revision = 'b5c6d7e8f901'
branch_labels = None
depends_on = None


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in the specified table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [c['name'] for c in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    # Add tiene_trabajo_administrativo to empresas if not exists
    if not column_exists('empresas', 'tiene_trabajo_administrativo'):
        op.add_column('empresas',
            sa.Column('tiene_trabajo_administrativo', sa.Boolean(), nullable=False, server_default='false')
        )

    # Add aplica_trabajo_administrativo to matriz_legal_normas if not exists
    if not column_exists('matriz_legal_normas', 'aplica_trabajo_administrativo'):
        op.add_column('matriz_legal_normas',
            sa.Column('aplica_trabajo_administrativo', sa.Boolean(), nullable=False, server_default='false')
        )


def downgrade() -> None:
    # Only drop if columns exist
    if column_exists('matriz_legal_normas', 'aplica_trabajo_administrativo'):
        op.drop_column('matriz_legal_normas', 'aplica_trabajo_administrativo')
    if column_exists('empresas', 'tiene_trabajo_administrativo'):
        op.drop_column('empresas', 'tiene_trabajo_administrativo')
