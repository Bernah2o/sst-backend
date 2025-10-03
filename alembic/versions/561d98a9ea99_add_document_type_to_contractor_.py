"""add_document_type_to_contractor_documents

Revision ID: 561d98a9ea99
Revises: fee1d228404b
Create Date: 2025-10-02 19:57:04.060766

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '561d98a9ea99'
down_revision = 'fee1d228404b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add document_type column to contractor_documents table
    op.add_column('contractor_documents', sa.Column('document_type', sa.String(100), nullable=True))
    
    # Update existing records with a default value
    # We'll set a default value based on document_name patterns or set to 'otros'
    op.execute("""
        UPDATE contractor_documents 
        SET document_type = CASE 
            WHEN LOWER(document_name) LIKE '%arl%' THEN 'arl'
            WHEN LOWER(document_name) LIKE '%eps%' THEN 'eps'
            WHEN LOWER(document_name) LIKE '%afp%' THEN 'afp'
            WHEN LOWER(document_name) LIKE '%cedula%' THEN 'cedula'
            WHEN LOWER(document_name) LIKE '%rut%' THEN 'rut'
            WHEN LOWER(document_name) LIKE '%bancario%' THEN 'certificado_bancario'
            ELSE 'otros'
        END
    """)
    
    # Make the column non-nullable after setting default values
    op.alter_column('contractor_documents', 'document_type', nullable=False)


def downgrade() -> None:
    # Remove document_type column
    op.drop_column('contractor_documents', 'document_type')