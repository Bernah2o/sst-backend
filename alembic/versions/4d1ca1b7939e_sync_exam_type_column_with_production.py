"""sync_exam_type_column_with_production

Migración correctiva para sincronizar la BD local con producción.
- Agrega columna exam_type si no existe (en producción ya existe desde la migración inicial)
- Asegura que tipo_examen_id sea nullable (en producción es nullable)

Revision ID: 4d1ca1b7939e
Revises: e8f90123abcd
Create Date: 2026-02-06 13:53:28.675506

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = '4d1ca1b7939e'
down_revision = 'e8f90123abcd'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('occupational_exams')]

    # 1. Crear el tipo ENUM si no existe
    examtype_enum = postgresql.ENUM('INGRESO', 'PERIODICO', 'REINTEGRO', 'RETIRO', name='examtype', create_type=False)
    examtype_enum.create(conn, checkfirst=True)

    # 2. Agregar columna exam_type si no existe
    if 'exam_type' not in columns:
        op.add_column('occupational_exams', sa.Column(
            'exam_type',
            postgresql.ENUM('INGRESO', 'PERIODICO', 'REINTEGRO', 'RETIRO', name='examtype', create_type=False),
            nullable=True
        ))

    # 3. Asegurar que tipo_examen_id sea nullable
    op.alter_column('occupational_exams', 'tipo_examen_id',
                     existing_type=sa.INTEGER(),
                     nullable=True)


def downgrade() -> None:
    pass
