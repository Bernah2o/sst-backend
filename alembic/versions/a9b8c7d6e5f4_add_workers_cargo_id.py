"""add workers cargo_id

Revision ID: a9b8c7d6e5f4
Revises: f1a2b3c4d5e6
Create Date: 2026-01-21

"""

from alembic import op
import sqlalchemy as sa


revision = "a9b8c7d6e5f4"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    with op.batch_alter_table("workers") as batch_op:
        batch_op.add_column(sa.Column("cargo_id", sa.Integer(), nullable=True))
        batch_op.create_index("ix_workers_cargo_id", ["cargo_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_workers_cargo_id_cargos",
            "cargos",
            ["cargo_id"],
            ["id"],
        )

    if dialect_name == "postgresql":
        op.execute(
            """
            UPDATE workers w
            SET cargo_id = c.id
            FROM cargos c
            WHERE w.cargo_id IS NULL
              AND w.position = c.nombre_cargo
            """
        )
    else:
        op.execute(
            """
            UPDATE workers
            SET cargo_id = (
                SELECT c.id
                FROM cargos c
                WHERE c.nombre_cargo = workers.position
                LIMIT 1
            )
            WHERE cargo_id IS NULL
            """
        )


def downgrade() -> None:
    with op.batch_alter_table("workers") as batch_op:
        batch_op.drop_constraint("fk_workers_cargo_id_cargos", type_="foreignkey")
        batch_op.drop_index("ix_workers_cargo_id")
        batch_op.drop_column("cargo_id")

