"""
Elimina course_id y agrega course_name a attendances

Revision ID: 20250917_remove_course_id_add_course_name
Revises: 7a68cc80eff9
Create Date: 2025-09-17
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20250917_remove_course_id_add_course_name"
down_revision = "7a68cc80eff9"
branch_labels = None
depends_on = None


def upgrade():
    # Eliminar FK y columna course_id
    with op.batch_alter_table("attendances") as batch_op:
        batch_op.drop_constraint("attendances_course_id_fkey", type_="foreignkey")
        batch_op.drop_column("course_id")
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
