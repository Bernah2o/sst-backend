"""fix_documentcategory_enum_values_consistency

Revision ID: 7561cd51fec8
Revises: bdf6ef73fe33
Create Date: 2025-09-25 16:54:52.299084

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7561cd51fec8'
down_revision = 'bdf6ef73fe33'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Corregir la inconsistencia en los valores del enum documentcategory
    # Recrear el enum con todos los valores en minúsculas para que coincida con el modelo Python
    
    # 1. Crear un nuevo enum temporal con todos los valores en minúsculas
    op.execute("""
        CREATE TYPE documentcategory_new AS ENUM (
            'identificacion', 
            'contrato', 
            'medico', 
            'capacitacion', 
            'certificacion', 
            'personal', 
            'otrosi', 
            'otro'
        )
    """)
    
    # 2. Actualizar la columna category en worker_documents para usar el nuevo tipo
    # Mapear los valores antiguos a los nuevos
    op.execute("""
        ALTER TABLE worker_documents 
        ALTER COLUMN category TYPE documentcategory_new 
        USING CASE 
            WHEN category = 'IDENTIFICATION' THEN 'identificacion'::documentcategory_new
            WHEN category = 'CONTRACT' THEN 'contrato'::documentcategory_new
            WHEN category = 'MEDICAL' THEN 'medico'::documentcategory_new
            WHEN category = 'TRAINING' THEN 'capacitacion'::documentcategory_new
            WHEN category = 'CERTIFICATION' THEN 'certificacion'::documentcategory_new
            WHEN category = 'PERSONAL' THEN 'personal'::documentcategory_new
            WHEN category = 'otrosi' THEN 'otrosi'::documentcategory_new
            WHEN category = 'OTHER' THEN 'otro'::documentcategory_new
            ELSE 'otro'::documentcategory_new
        END
    """)
    
    # 3. Eliminar el enum anterior
    op.execute("DROP TYPE documentcategory")
    
    # 4. Renombrar el nuevo enum
    op.execute("ALTER TYPE documentcategory_new RENAME TO documentcategory")


def downgrade() -> None:
    # Para revertir, recrear el enum con los valores originales en mayúsculas
    
    # 1. Crear enum temporal con valores en mayúsculas
    op.execute("""
        CREATE TYPE documentcategory_old AS ENUM (
            'IDENTIFICATION', 
            'CONTRACT', 
            'MEDICAL', 
            'TRAINING', 
            'CERTIFICATION', 
            'PERSONAL', 
            'OTHER'
        )
    """)
    
    # 2. Actualizar la columna mapeando de vuelta a mayúsculas
    op.execute("""
        ALTER TABLE worker_documents 
        ALTER COLUMN category TYPE documentcategory_old 
        USING CASE 
            WHEN category = 'identificacion' THEN 'IDENTIFICATION'::documentcategory_old
            WHEN category = 'contrato' THEN 'CONTRACT'::documentcategory_old
            WHEN category = 'medico' THEN 'MEDICAL'::documentcategory_old
            WHEN category = 'capacitacion' THEN 'TRAINING'::documentcategory_old
            WHEN category = 'certificacion' THEN 'CERTIFICATION'::documentcategory_old
            WHEN category = 'personal' THEN 'PERSONAL'::documentcategory_old
            WHEN category = 'otrosi' THEN 'OTHER'::documentcategory_old
            WHEN category = 'otro' THEN 'OTHER'::documentcategory_old
            ELSE 'OTHER'::documentcategory_old
        END
    """)
    
    # 3. Eliminar el enum actual
    op.execute("DROP TYPE documentcategory")
    
    # 4. Renombrar el enum temporal
    op.execute("ALTER TYPE documentcategory_old RENAME TO documentcategory")