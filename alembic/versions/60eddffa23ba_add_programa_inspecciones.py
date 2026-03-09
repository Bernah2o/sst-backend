"""add_programa_inspecciones

Revision ID: 60eddffa23ba
Revises: 4389729ad81a
Create Date: 2026-03-09 12:44:16.998041

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '60eddffa23ba'
down_revision = '4389729ad81a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'programa_inspecciones',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('año', sa.Integer(), nullable=False),
        sa.Column('empresa_id', sa.Integer(), nullable=True),
        sa.Column('codigo', sa.String(length=50), nullable=True),
        sa.Column('version', sa.String(length=20), nullable=True),
        sa.Column('objetivo', sa.Text(), nullable=True),
        sa.Column('alcance', sa.Text(), nullable=True),
        sa.Column('encargado_sgsst', sa.String(length=200), nullable=True),
        sa.Column('aprobado_por', sa.String(length=200), nullable=True),
        sa.Column('estado', sa.Enum('borrador', 'activo', 'finalizado', name='estadoprogramainspeccion'), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.ForeignKeyConstraint(['empresa_id'], ['empresas.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_programa_inspecciones_id'), 'programa_inspecciones', ['id'], unique=False)

    op.create_table(
        'inspeccion_programada',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('programa_id', sa.Integer(), nullable=False),
        sa.Column('tipo_inspeccion', sa.Enum(
            'locativa', 'equipos', 'herramientas', 'epp', 'extintores',
            'primeros_auxilios', 'orden_aseo', 'electrica', 'emergencias', 'general',
            name='tipoinspeccion',
        ), nullable=False),
        sa.Column('area', sa.String(length=200), nullable=False),
        sa.Column('descripcion', sa.Text(), nullable=False),
        sa.Column('responsable', sa.String(length=300), nullable=True),
        sa.Column('frecuencia', sa.Enum(
            'mensual', 'bimestral', 'trimestral', 'semestral', 'anual',
            name='frecuenciainspeccion',
        ), nullable=True),
        sa.Column('lista_chequeo', sa.String(length=300), nullable=True),
        sa.Column('observaciones', sa.Text(), nullable=True),
        sa.Column('orden', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['programa_id'], ['programa_inspecciones.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_inspeccion_programada_id'), 'inspeccion_programada', ['id'], unique=False)

    op.create_table(
        'inspeccion_seguimiento',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('inspeccion_id', sa.Integer(), nullable=False),
        sa.Column('mes', sa.Integer(), nullable=False),
        sa.Column('programada', sa.Boolean(), nullable=True),
        sa.Column('ejecutada', sa.Boolean(), nullable=True),
        sa.Column('fecha_ejecucion', sa.Date(), nullable=True),
        sa.Column('ejecutado_por', sa.String(length=200), nullable=True),
        sa.Column('hallazgos', sa.Text(), nullable=True),
        sa.Column('accion_correctiva', sa.Text(), nullable=True),
        sa.Column('observacion', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['inspeccion_id'], ['inspeccion_programada.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_inspeccion_seguimiento_id'), 'inspeccion_seguimiento', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_inspeccion_seguimiento_id'), table_name='inspeccion_seguimiento')
    op.drop_table('inspeccion_seguimiento')
    op.drop_index(op.f('ix_inspeccion_programada_id'), table_name='inspeccion_programada')
    op.drop_table('inspeccion_programada')
    op.drop_index(op.f('ix_programa_inspecciones_id'), table_name='programa_inspecciones')
    op.drop_table('programa_inspecciones')
    op.execute("DROP TYPE IF EXISTS estadoprogramainspeccion")
    op.execute("DROP TYPE IF EXISTS tipoinspeccion")
    op.execute("DROP TYPE IF EXISTS frecuenciainspeccion")
