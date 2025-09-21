"""
Elimina course_id y agrega course_name a attendances

Revision ID: 20250917_remove_course_id_add_course_name
Revises: 7a68cc80eff9
Create Date: 2025-09-17
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "7a68cc80eff9_v2"
down_revision = "7a68cc80eff9"
branch_labels = None
depends_on = None


def upgrade():
    # Verificar si la restricción existe antes de eliminarla
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    foreign_keys = inspector.get_foreign_keys("attendances")
    
    # Verificar si la columna course_id existe
    columns = [col['name'] for col in inspector.get_columns("attendances")]
    
    with op.batch_alter_table("attendances") as batch_op:
        # Solo eliminar la FK si existe
        if any(fk['name'] == 'attendances_course_id_fkey' for fk in foreign_keys):
            batch_op.drop_constraint("attendances_course_id_fkey", type_="foreignkey")
        
        # Solo eliminar la columna si existe
        if "course_id" in columns:
            batch_op.drop_column("course_id")
        
        # Solo agregar course_name si no existe
        if "course_name" not in columns:
            batch_op.add_column(
                sa.Column("course_name", sa.String(length=255), nullable=True)
            )


def downgrade():
    # Restaurar columna course_id y eliminar course_name
    with op.batch_alter_table("attendances") as batch_op:
        batch_op.add_column(sa.Column("course_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "attendances_course_id_fkey", "courses", ["course_id"], ["id"]
        )
        batch_op.drop_column("course_name")
