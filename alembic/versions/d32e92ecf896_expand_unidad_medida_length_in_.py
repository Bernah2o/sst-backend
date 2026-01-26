"""expand unidad_medida length in profesiograma_factores

Revision ID: d32e92ecf896
Revises: d0c1b2a3e4f5
Create Date: 2026-01-22 18:07:18.235117

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd32e92ecf896'
down_revision = 'd0c1b2a3e4f5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("profesiograma_factores") as batch_op:
        batch_op.alter_column(
            "unidad_medida",
            existing_type=sa.String(length=20),
            type_=sa.String(length=50),
            existing_nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("profesiograma_factores") as batch_op:
        batch_op.alter_column(
            "unidad_medida",
            existing_type=sa.String(length=50),
            type_=sa.String(length=20),
            existing_nullable=True,
        )
