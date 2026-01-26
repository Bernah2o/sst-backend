"""Create ocupaciones table

Revision ID: c2a1f4b8d0e1
Revises: b4c5d6e7f809
Create Date: 2026-01-22

"""
from alembic import op
import sqlalchemy as sa


revision = "c2a1f4b8d0e1"
down_revision = "b4c5d6e7f809"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ocupaciones",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(length=100), nullable=False),
        sa.Column("descripcion", sa.String(length=255), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ocupaciones_id"), "ocupaciones", ["id"], unique=False)
    op.create_index(op.f("ix_ocupaciones_nombre"), "ocupaciones", ["nombre"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_ocupaciones_nombre"), table_name="ocupaciones")
    op.drop_index(op.f("ix_ocupaciones_id"), table_name="ocupaciones")
    op.drop_table("ocupaciones")
