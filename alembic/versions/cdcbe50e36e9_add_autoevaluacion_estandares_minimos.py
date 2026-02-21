"""add autoevaluacion estandares minimos

Revision ID: cdcbe50e36e9
Revises: b2c3d4e5f6a7
Create Date: 2026-02-21 16:16:07.693144

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'cdcbe50e36e9'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'autoevaluacion_estandares',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('año', sa.Integer(), nullable=False),
        sa.Column('empresa_id', sa.Integer(), nullable=True),
        sa.Column('num_trabajadores', sa.Integer(), nullable=False),
        sa.Column('nivel_riesgo', sa.Enum('I', 'II', 'III', 'IV', 'V', name='nivel_riesgo_empresa_enum'), nullable=False),
        sa.Column('grupo', sa.Enum('GRUPO_7', 'GRUPO_21', 'GRUPO_60', name='grupo_estandar_enum'), nullable=False),
        sa.Column('estado', sa.Enum('borrador', 'en_proceso', 'finalizada', name='estado_autoevaluacion_enum'), nullable=True),
        sa.Column('puntaje_total', sa.Float(), nullable=True),
        sa.Column('puntaje_planear', sa.Float(), nullable=True),
        sa.Column('puntaje_hacer', sa.Float(), nullable=True),
        sa.Column('puntaje_verificar', sa.Float(), nullable=True),
        sa.Column('puntaje_actuar', sa.Float(), nullable=True),
        sa.Column('nivel_cumplimiento', sa.Enum('critico', 'moderadamente_aceptable', 'aceptable', name='nivel_cumplimiento_enum'), nullable=True),
        sa.Column('encargado_sgsst', sa.String(length=200), nullable=True),
        sa.Column('observaciones_generales', sa.Text(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['empresa_id'], ['empresas.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_autoevaluacion_estandares_id'), 'autoevaluacion_estandares', ['id'], unique=False)

    op.create_table(
        'autoevaluacion_respuesta',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('autoevaluacion_id', sa.Integer(), nullable=False),
        sa.Column('estandar_codigo', sa.String(length=20), nullable=False),
        sa.Column('ciclo', sa.Enum('PLANEAR', 'HACER', 'VERIFICAR', 'ACTUAR', name='ciclo_phva_estandares_enum'), nullable=False),
        sa.Column('descripcion', sa.Text(), nullable=False),
        sa.Column('valor_maximo', sa.Float(), nullable=False),
        sa.Column('valor_maximo_ajustado', sa.Float(), nullable=False),
        sa.Column('cumplimiento', sa.Enum('cumple_totalmente', 'no_cumple', 'no_aplica', name='valor_cumplimiento_enum'), nullable=True),
        sa.Column('valor_obtenido', sa.Float(), nullable=True),
        sa.Column('justificacion_no_aplica', sa.Text(), nullable=True),
        sa.Column('observaciones', sa.Text(), nullable=True),
        sa.Column('orden', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['autoevaluacion_id'], ['autoevaluacion_estandares.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_autoevaluacion_respuesta_id'), 'autoevaluacion_respuesta', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_autoevaluacion_respuesta_id'), table_name='autoevaluacion_respuesta')
    op.drop_table('autoevaluacion_respuesta')
    op.drop_index(op.f('ix_autoevaluacion_estandares_id'), table_name='autoevaluacion_estandares')
    op.drop_table('autoevaluacion_estandares')
    op.execute("DROP TYPE IF EXISTS valor_cumplimiento_enum")
    op.execute("DROP TYPE IF EXISTS ciclo_phva_estandares_enum")
    op.execute("DROP TYPE IF EXISTS nivel_cumplimiento_enum")
    op.execute("DROP TYPE IF EXISTS estado_autoevaluacion_enum")
    op.execute("DROP TYPE IF EXISTS grupo_estandar_enum")
    op.execute("DROP TYPE IF EXISTS nivel_riesgo_empresa_enum")
