"""add_ciclo_recursos_legislacion_to_inspecciones

Revision ID: 756dfa14a956
Revises: 60eddffa23ba
Create Date: 2026-03-09 12:53:53.552392

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '756dfa14a956'
down_revision = '60eddffa23ba'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Crear el tipo enum cicloinspeccion
    cicloinspeccion = sa.Enum('planear', 'hacer', 'verificar', 'actuar', name='cicloinspeccion')
    cicloinspeccion.create(op.get_bind(), checkfirst=True)

    # Agregar columna ciclo a inspeccion_programada (nullable para registros existentes)
    op.add_column('inspeccion_programada', sa.Column(
        'ciclo',
        sa.Enum('planear', 'hacer', 'verificar', 'actuar', name='cicloinspeccion'),
        nullable=True,
        server_default='hacer',
    ))

    # Agregar columnas de condiciones peligrosas a inspeccion_seguimiento
    op.add_column('inspeccion_seguimiento', sa.Column(
        'condiciones_peligrosas_reportadas', sa.Integer(), nullable=True, server_default='0'
    ))
    op.add_column('inspeccion_seguimiento', sa.Column(
        'condiciones_peligrosas_intervenidas', sa.Integer(), nullable=True, server_default='0'
    ))

    # Agregar campos al programa
    op.add_column('programa_inspecciones', sa.Column(
        'recursos', sa.String(length=500), nullable=True
    ))
    op.add_column('programa_inspecciones', sa.Column(
        'legislacion_aplicable', sa.Text(), nullable=True
    ))

    # Actualizar registros existentes con valor por defecto
    op.execute("UPDATE inspeccion_programada SET ciclo = 'hacer' WHERE ciclo IS NULL")


def downgrade() -> None:
    op.drop_column('programa_inspecciones', 'legislacion_aplicable')
    op.drop_column('programa_inspecciones', 'recursos')
    op.drop_column('inspeccion_seguimiento', 'condiciones_peligrosas_intervenidas')
    op.drop_column('inspeccion_seguimiento', 'condiciones_peligrosas_reportadas')
    op.drop_column('inspeccion_programada', 'ciclo')
    op.execute("DROP TYPE IF EXISTS cicloinspeccion")
