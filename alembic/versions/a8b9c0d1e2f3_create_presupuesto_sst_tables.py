"""create_presupuesto_sst_tables

Revision ID: a8b9c0d1e2f3
Revises: fee1d228404b
Create Date: 2026-02-20 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'a8b9c0d1e2f3'
down_revision = 'a1b2c3d4e5f8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'presupuesto_sst',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('año', sa.Integer(), nullable=False),
        sa.Column('empresa_id', sa.Integer(), sa.ForeignKey('empresas.id'), nullable=True),
        sa.Column('codigo', sa.String(50), nullable=True, server_default='AN-SST-03'),
        sa.Column('version', sa.String(20), nullable=True, server_default='1'),
        sa.Column('titulo', sa.String(300), nullable=True),
        sa.Column('encargado_sgsst', sa.String(200), nullable=True),
        sa.Column('aprobado_por', sa.String(200), nullable=True),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
    )

    op.create_table(
        'presupuesto_categoria',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            'presupuesto_id', sa.Integer(),
            sa.ForeignKey('presupuesto_sst.id', ondelete='CASCADE'), nullable=False
        ),
        sa.Column('categoria', sa.String(40), nullable=False),
        sa.Column('orden', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
    )

    op.create_table(
        'presupuesto_item',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            'categoria_id', sa.Integer(),
            sa.ForeignKey('presupuesto_categoria.id', ondelete='CASCADE'), nullable=False
        ),
        sa.Column('actividad', sa.Text(), nullable=False),
        sa.Column('es_default', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('orden', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
    )

    op.create_table(
        'presupuesto_mensual',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            'item_id', sa.Integer(),
            sa.ForeignKey('presupuesto_item.id', ondelete='CASCADE'), nullable=False
        ),
        sa.Column('mes', sa.Integer(), nullable=False),
        sa.Column('proyectado', sa.Numeric(14, 2), nullable=True, server_default='0'),
        sa.Column('ejecutado', sa.Numeric(14, 2), nullable=True, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
    )


def downgrade() -> None:
    op.drop_table('presupuesto_mensual')
    op.drop_table('presupuesto_item')
    op.drop_table('presupuesto_categoria')
    op.drop_table('presupuesto_sst')
