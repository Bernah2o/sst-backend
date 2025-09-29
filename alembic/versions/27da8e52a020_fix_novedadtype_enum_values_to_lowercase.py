"""Fix novedadtype enum values to lowercase

Revision ID: 27da8e52a020
Revises: 6402929d1c69
Create Date: 2025-09-28 20:51:30.539711

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '27da8e52a020'
down_revision = '6402929d1c69'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # First, convert the column to text to allow updates
    op.execute("ALTER TABLE worker_novedades ALTER COLUMN tipo TYPE text")
    
    # Update existing data to use lowercase values
    op.execute("UPDATE worker_novedades SET tipo = 'permiso_dia_familia' WHERE tipo = 'PERMISO_DIA_FAMILIA'")
    op.execute("UPDATE worker_novedades SET tipo = 'licencia_paternidad' WHERE tipo = 'LICENCIA_PATERNIDAD'")
    op.execute("UPDATE worker_novedades SET tipo = 'incapacidad_medica' WHERE tipo = 'INCAPACIDAD_MEDICA'")
    op.execute("UPDATE worker_novedades SET tipo = 'permiso_dia_no_remunerado' WHERE tipo = 'PERMISO_DIA_NO_REMUNERADO'")
    op.execute("UPDATE worker_novedades SET tipo = 'aumento_salario' WHERE tipo = 'AUMENTO_SALARIO'")
    op.execute("UPDATE worker_novedades SET tipo = 'licencia_maternidad' WHERE tipo = 'LICENCIA_MATERNIDAD'")
    op.execute("UPDATE worker_novedades SET tipo = 'horas_extras' WHERE tipo = 'HORAS_EXTRAS'")
    op.execute("UPDATE worker_novedades SET tipo = 'recargos' WHERE tipo = 'RECARGOS'")
    # capacitacion is already lowercase, no need to update
    
    # Drop the old enum
    op.execute("DROP TYPE novedadtype")
    
    # Create a new enum with all lowercase values
    op.execute("CREATE TYPE novedadtype AS ENUM ('permiso_dia_familia', 'licencia_paternidad', 'incapacidad_medica', 'permiso_dia_no_remunerado', 'aumento_salario', 'licencia_maternidad', 'horas_extras', 'recargos', 'capacitacion')")
    
    # Convert the column back to the new enum
    op.execute("ALTER TABLE worker_novedades ALTER COLUMN tipo TYPE novedadtype USING tipo::novedadtype")


def downgrade() -> None:
    # Convert the column to text to allow updates
    op.execute("ALTER TABLE worker_novedades ALTER COLUMN tipo TYPE text")
    
    # Update data back to original case
    op.execute("UPDATE worker_novedades SET tipo = 'PERMISO_DIA_FAMILIA' WHERE tipo = 'permiso_dia_familia'")
    op.execute("UPDATE worker_novedades SET tipo = 'LICENCIA_PATERNIDAD' WHERE tipo = 'licencia_paternidad'")
    op.execute("UPDATE worker_novedades SET tipo = 'INCAPACIDAD_MEDICA' WHERE tipo = 'incapacidad_medica'")
    op.execute("UPDATE worker_novedades SET tipo = 'PERMISO_DIA_NO_REMUNERADO' WHERE tipo = 'permiso_dia_no_remunerado'")
    op.execute("UPDATE worker_novedades SET tipo = 'AUMENTO_SALARIO' WHERE tipo = 'aumento_salario'")
    op.execute("UPDATE worker_novedades SET tipo = 'LICENCIA_MATERNIDAD' WHERE tipo = 'licencia_maternidad'")
    op.execute("UPDATE worker_novedades SET tipo = 'HORAS_EXTRAS' WHERE tipo = 'horas_extras'")
    op.execute("UPDATE worker_novedades SET tipo = 'RECARGOS' WHERE tipo = 'recargos'")
    # capacitacion stays the same
    
    # Drop the current enum
    op.execute("DROP TYPE novedadtype")
    
    # Create the old enum with mixed case values
    op.execute("CREATE TYPE novedadtype AS ENUM ('PERMISO_DIA_FAMILIA', 'LICENCIA_PATERNIDAD', 'INCAPACIDAD_MEDICA', 'PERMISO_DIA_NO_REMUNERADO', 'AUMENTO_SALARIO', 'LICENCIA_MATERNIDAD', 'HORAS_EXTRAS', 'RECARGOS', 'capacitacion')")
    
    # Convert the column back to the old enum
    op.execute("ALTER TABLE worker_novedades ALTER COLUMN tipo TYPE novedadtype USING tipo::novedadtype")