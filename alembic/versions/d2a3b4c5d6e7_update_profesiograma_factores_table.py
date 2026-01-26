"""update profesiograma factores table

Revision ID: d2a3b4c5d6e7
Revises: c7f0b2a1d3e4
Create Date: 2026-01-21

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d2a3b4c5d6e7"
down_revision = "c7f0b2a1d3e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.rename_table("profesiograma_factor_riesgo", "profesiograma_factores")

    nivel_exposicion_enum = sa.Enum(
        "bajo",
        "medio",
        "alto",
        "muy_alto",
        name="nivelexposicion",
    )
    nivel_exposicion_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "profesiograma_factores",
        sa.Column(
            "nivel_exposicion",
            nivel_exposicion_enum,
            nullable=False,
        ),
    )
    op.add_column(
        "profesiograma_factores",
        sa.Column("tiempo_exposicion_horas", sa.Numeric(4, 2), nullable=False),
    )
    op.add_column(
        "profesiograma_factores",
        sa.Column("valor_medido", sa.Numeric(10, 2), nullable=True),
    )
    op.add_column(
        "profesiograma_factores",
        sa.Column("valor_limite_permisible", sa.Numeric(10, 2), nullable=True),
    )
    op.add_column(
        "profesiograma_factores",
        sa.Column("unidad_medida", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "profesiograma_factores",
        sa.Column("controles_ingenieria", sa.Text(), nullable=True),
    )
    op.add_column(
        "profesiograma_factores",
        sa.Column("controles_administrativos", sa.Text(), nullable=True),
    )
    op.add_column(
        "profesiograma_factores",
        sa.Column("epp_requerido", sa.Text(), nullable=True),
    )
    op.add_column(
        "profesiograma_factores",
        sa.Column(
            "fecha_registro",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.add_column(
        "profesiograma_factores",
        sa.Column("registrado_por", sa.Integer(), nullable=False),
    )
    op.create_foreign_key(
        "fk_profesiograma_factores_registrado_por_users",
        "profesiograma_factores",
        "users",
        ["registrado_por"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_profesiograma_factores_registrado_por_users",
        "profesiograma_factores",
        type_="foreignkey",
    )
    op.drop_column("profesiograma_factores", "registrado_por")
    op.drop_column("profesiograma_factores", "fecha_registro")
    op.drop_column("profesiograma_factores", "epp_requerido")
    op.drop_column("profesiograma_factores", "controles_administrativos")
    op.drop_column("profesiograma_factores", "controles_ingenieria")
    op.drop_column("profesiograma_factores", "unidad_medida")
    op.drop_column("profesiograma_factores", "valor_limite_permisible")
    op.drop_column("profesiograma_factores", "valor_medido")
    op.drop_column("profesiograma_factores", "tiempo_exposicion_horas")
    op.drop_column("profesiograma_factores", "nivel_exposicion")

    op.rename_table("profesiograma_factores", "profesiograma_factor_riesgo")
    op.execute("DROP TYPE IF EXISTS nivelexposicion")
