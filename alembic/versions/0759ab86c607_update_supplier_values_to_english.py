"""update_supplier_values_to_english

Revision ID: 0759ab86c607
Revises: 861b66515785
Create Date: 2025-09-03 20:30:48.660227

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0759ab86c607'
down_revision = '861b66515785'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Actualizar tipos de proveedores de español a inglés
    op.execute("""
        UPDATE suppliers 
        SET supplier_type = CASE 
            WHEN supplier_type = 'centro_medico' THEN 'medical_center'
            WHEN supplier_type = 'laboratorio' THEN 'laboratory'
            WHEN supplier_type = 'clinica' THEN 'clinic'
            WHEN supplier_type = 'hospital' THEN 'hospital'
            WHEN supplier_type = 'ips' THEN 'other'
            WHEN supplier_type = 'otro' THEN 'other'
            ELSE supplier_type
        END
        WHERE supplier_type IN ('centro_medico', 'laboratorio', 'clinica', 'hospital', 'ips', 'otro')
    """)
    
    # Actualizar estados de proveedores de español a inglés
    op.execute("""
        UPDATE suppliers 
        SET status = CASE 
            WHEN status = 'activo' THEN 'active'
            WHEN status = 'inactivo' THEN 'inactive'
            WHEN status = 'suspendido' THEN 'suspended'
            ELSE status
        END
        WHERE status IN ('activo', 'inactivo', 'suspendido')
    """)


def downgrade() -> None:
    # Revertir tipos de proveedores de inglés a español
    op.execute("""
        UPDATE suppliers 
        SET supplier_type = CASE 
            WHEN supplier_type = 'medical_center' THEN 'centro_medico'
            WHEN supplier_type = 'laboratory' THEN 'laboratorio'
            WHEN supplier_type = 'clinic' THEN 'clinica'
            WHEN supplier_type = 'hospital' THEN 'hospital'
            WHEN supplier_type = 'other' THEN 'otro'
            ELSE supplier_type
        END
        WHERE supplier_type IN ('medical_center', 'laboratory', 'clinic', 'hospital', 'other')
    """)
    
    # Revertir estados de proveedores de inglés a español
    op.execute("""
        UPDATE suppliers 
        SET status = CASE 
            WHEN status = 'active' THEN 'activo'
            WHEN status = 'inactive' THEN 'inactivo'
            WHEN status = 'suspended' THEN 'suspendido'
            ELSE status
        END
        WHERE status IN ('active', 'inactive', 'suspended')
    """)