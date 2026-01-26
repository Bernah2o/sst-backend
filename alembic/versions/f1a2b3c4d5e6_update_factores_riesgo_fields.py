"""update factores_riesgo fields

Revision ID: f1a2b3c4d5e6
Revises: e3f4a5b6c7d8
Create Date: 2026-01-21

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f1a2b3c4d5e6"
down_revision = "e3f4a5b6c7d8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    categoria_enum = sa.Enum(
        "fisico",
        "quimico",
        "biologico",
        "ergonomico",
        "psicosocial",
        "seguridad",
        name="categoriafactorriesgo",
    )

    if dialect_name == "postgresql":
        categoria_enum.create(bind, checkfirst=True)

    if dialect_name == "postgresql":
        op.execute("ALTER TABLE factores_riesgo DROP CONSTRAINT IF EXISTS factores_riesgo_nombre_key")
        op.execute("DROP INDEX IF EXISTS ix_factores_riesgo_nombre")

    with op.batch_alter_table("factores_riesgo") as batch_op:
        batch_op.add_column(sa.Column("codigo", sa.String(length=20), nullable=True))
        batch_op.add_column(
            sa.Column(
                "categoria",
                categoria_enum,
                nullable=True,
            )
        )
        batch_op.add_column(sa.Column("nivel_accion", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("periodicidad_sugerida_meses", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("normativa_aplicable", sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column("examenes_sugeridos", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("requiere_sve", sa.Boolean(), nullable=False, server_default=sa.text("false")))
        batch_op.add_column(sa.Column("tipo_sve", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("true")))

        batch_op.alter_column(
            "nombre",
            existing_type=sa.String(length=150),
            type_=sa.String(length=100),
            existing_nullable=False,
            nullable=True,
        )

    if dialect_name == "postgresql":
        op.execute(
            "UPDATE factores_riesgo SET codigo = CONCAT('FR_', id) WHERE codigo IS NULL"
        )
    else:
        op.execute(
            "UPDATE factores_riesgo SET codigo = 'FR_' || id WHERE codigo IS NULL"
        )

    with op.batch_alter_table("factores_riesgo") as batch_op:
        batch_op.alter_column("codigo", existing_type=sa.String(length=20), nullable=False)
        batch_op.create_index("ix_factores_riesgo_codigo", ["codigo"], unique=True)
        batch_op.create_index("ix_factores_riesgo_nombre", ["nombre"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    with op.batch_alter_table("factores_riesgo") as batch_op:
        batch_op.drop_index("ix_factores_riesgo_nombre")
        batch_op.drop_index("ix_factores_riesgo_codigo")

        batch_op.drop_column("activo")
        batch_op.drop_column("tipo_sve")
        batch_op.drop_column("requiere_sve")
        batch_op.drop_column("examenes_sugeridos")
        batch_op.drop_column("normativa_aplicable")
        batch_op.drop_column("periodicidad_sugerida_meses")
        batch_op.drop_column("nivel_accion")
        batch_op.drop_column("categoria")
        batch_op.drop_column("codigo")

        batch_op.alter_column(
            "nombre",
            existing_type=sa.String(length=100),
            type_=sa.String(length=150),
            existing_nullable=True,
            nullable=False,
        )

    if dialect_name == "postgresql":
        op.execute("DROP TYPE IF EXISTS categoriafactorriesgo")
