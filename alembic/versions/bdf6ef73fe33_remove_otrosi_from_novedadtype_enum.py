"""remove_otrosi_from_novedadtype_enum

Revision ID: bdf6ef73fe33
Revises: 161bd49b6aab
Create Date: 2025-09-25 16:20:05.172926

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'bdf6ef73fe33'
down_revision = '161bd49b6aab'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Eliminar 'otrosi' del enum NovedadType
    # En PostgreSQL, no se puede eliminar directamente un valor de un enum
    # Necesitamos recrear el enum sin el valor 'otrosi'
    
    # 1. Crear un nuevo enum temporal sin 'otrosi'
    op.execute("CREATE TYPE novedadtype_new AS ENUM ('PERMISO_DIA_FAMILIA', 'LICENCIA_PATERNIDAD', 'INCAPACIDAD_MEDICA', 'PERMISO_DIA_NO_REMUNERADO', 'AUMENTO_SALARIO', 'LICENCIA_MATERNIDAD', 'HORAS_EXTRAS', 'RECARGOS')")
    
    # 2. Actualizar la columna para usar el nuevo tipo
    op.execute("ALTER TABLE worker_novedades ALTER COLUMN tipo TYPE novedadtype_new USING tipo::text::novedadtype_new")
    
    # 3. Eliminar el enum anterior
    op.execute("DROP TYPE novedadtype")
    
    # 4. Renombrar el nuevo enum
    op.execute("ALTER TYPE novedadtype_new RENAME TO novedadtype")


def downgrade() -> None:
    # Para revertir, agregamos 'otrosi' de vuelta al enum
    op.execute("ALTER TYPE novedadtype ADD VALUE 'otrosi'")