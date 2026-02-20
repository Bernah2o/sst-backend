"""create_programa_capacitaciones_tables

Revision ID: b2c3d4e5f6a7
Revises: a8b9c0d1e2f3
Create Date: 2026-02-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a7'
down_revision = 'a8b9c0d1e2f3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'programa_capacitaciones',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('año', sa.Integer(), nullable=False),
        sa.Column('empresa_id', sa.Integer(), nullable=True),
        sa.Column('codigo', sa.String(length=50), nullable=True),
        sa.Column('version', sa.String(length=20), nullable=True),
        sa.Column('titulo', sa.String(length=300), nullable=True),
        sa.Column('alcance', sa.Text(), nullable=True),
        sa.Column('objetivo', sa.Text(), nullable=True),
        sa.Column('recursos', sa.Text(), nullable=True),
        sa.Column('meta_cumplimiento', sa.Float(), nullable=True),
        sa.Column('meta_cobertura', sa.Float(), nullable=True),
        sa.Column('meta_eficacia', sa.Float(), nullable=True),
        sa.Column('encargado_sgsst', sa.String(length=200), nullable=True),
        sa.Column('aprobado_por', sa.String(length=200), nullable=True),
        sa.Column('estado', sa.String(length=30), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['empresa_id'], ['empresas.id'], ),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_programa_capacitaciones_id'), 'programa_capacitaciones', ['id'], unique=False)

    op.create_table(
        'capacitacion_actividad',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('programa_id', sa.Integer(), nullable=False),
        sa.Column('ciclo', sa.String(length=30), nullable=False),
        sa.Column('nombre', sa.Text(), nullable=False),
        sa.Column('encargado', sa.String(length=300), nullable=True),
        sa.Column('recursos', sa.String(length=300), nullable=True),
        sa.Column('horas', sa.Float(), nullable=True),
        sa.Column('orden', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['programa_id'], ['programa_capacitaciones.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_capacitacion_actividad_id'), 'capacitacion_actividad', ['id'], unique=False)

    op.create_table(
        'capacitacion_seguimiento',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('actividad_id', sa.Integer(), nullable=False),
        sa.Column('mes', sa.Integer(), nullable=False),
        sa.Column('programada', sa.Boolean(), nullable=True),
        sa.Column('ejecutada', sa.Boolean(), nullable=True),
        sa.Column('observacion', sa.Text(), nullable=True),
        sa.Column('fecha_ejecucion', sa.Date(), nullable=True),
        sa.Column('ejecutado_por', sa.String(length=200), nullable=True),
        sa.Column('trabajadores_programados', sa.Integer(), nullable=True),
        sa.Column('trabajadores_participaron', sa.Integer(), nullable=True),
        sa.Column('personas_evaluadas', sa.Integer(), nullable=True),
        sa.Column('evaluaciones_eficaces', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['actividad_id'], ['capacitacion_actividad.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_capacitacion_seguimiento_id'), 'capacitacion_seguimiento', ['id'], unique=False)

    op.create_table(
        'capacitacion_indicador_mensual',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('programa_id', sa.Integer(), nullable=False),
        sa.Column('tipo_indicador', sa.String(length=20), nullable=False),
        sa.Column('mes', sa.Integer(), nullable=False),
        sa.Column('numerador', sa.Float(), nullable=True),
        sa.Column('denominador', sa.Float(), nullable=True),
        sa.Column('valor_porcentaje', sa.Float(), nullable=True),
        sa.Column('meta', sa.Float(), nullable=True),
        sa.Column('analisis_trimestral', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['programa_id'], ['programa_capacitaciones.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_capacitacion_indicador_mensual_id'), 'capacitacion_indicador_mensual', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_capacitacion_indicador_mensual_id'), table_name='capacitacion_indicador_mensual')
    op.drop_table('capacitacion_indicador_mensual')
    op.drop_index(op.f('ix_capacitacion_seguimiento_id'), table_name='capacitacion_seguimiento')
    op.drop_table('capacitacion_seguimiento')
    op.drop_index(op.f('ix_capacitacion_actividad_id'), table_name='capacitacion_actividad')
    op.drop_table('capacitacion_actividad')
    op.drop_index(op.f('ix_programa_capacitaciones_id'), table_name='programa_capacitaciones')
    op.drop_table('programa_capacitaciones')
