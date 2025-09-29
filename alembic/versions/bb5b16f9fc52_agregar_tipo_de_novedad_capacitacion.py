"""Agregar tipo de novedad CAPACITACION

Revision ID: bb5b16f9fc52
Revises: 1b4fe8606608
Create Date: 2025-09-29 02:31:53.178975

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'bb5b16f9fc52'
down_revision = '4bf9958d5e4e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Agregar el nuevo valor 'capacitacion' al enum NovedadType
    op.execute("ALTER TYPE novedadtype ADD VALUE 'capacitacion'")


def downgrade() -> None:
    # Nota: PostgreSQL no permite eliminar valores de un enum directamente
    # Se requeriría recrear el enum completo, lo cual es complejo
    # Por simplicidad, dejamos este downgrade vacío
    pass