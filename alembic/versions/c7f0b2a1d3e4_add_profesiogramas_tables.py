"""add profesiogramas tables

Revision ID: c7f0b2a1d3e4
Revises: a1b2c3d4e5f6
Create Date: 2026-01-21

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c7f0b2a1d3e4"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "factores_riesgo",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(length=150), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("nombre"),
    )
    op.create_index(op.f("ix_factores_riesgo_id"), "factores_riesgo", ["id"], unique=False)
    op.create_index(op.f("ix_factores_riesgo_nombre"), "factores_riesgo", ["nombre"], unique=True)

    op.create_table(
        "criterios_exclusion",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(length=200), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("nombre"),
    )
    op.create_index(op.f("ix_criterios_exclusion_id"), "criterios_exclusion", ["id"], unique=False)
    op.create_index(op.f("ix_criterios_exclusion_nombre"), "criterios_exclusion", ["nombre"], unique=True)

    op.create_table(
        "tipos_examen",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(length=150), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("nombre"),
    )
    op.create_index(op.f("ix_tipos_examen_id"), "tipos_examen", ["id"], unique=False)
    op.create_index(op.f("ix_tipos_examen_nombre"), "tipos_examen", ["nombre"], unique=True)

    op.create_table(
        "profesiogramas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cargo_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.String(length=10), nullable=False),
        sa.Column(
            "estado",
            sa.Enum("activo", "inactivo", "borrador", name="profesiogramaestado"),
            nullable=False,
        ),
        sa.Column("posicion_predominante", sa.String(length=50), nullable=False),
        sa.Column("descripcion_actividades", sa.Text(), nullable=False),
        sa.Column("periodicidad_emo_meses", sa.Integer(), nullable=False),
        sa.Column("justificacion_periodicidad_emo", sa.Text(), nullable=True),
        sa.Column("fecha_ultima_revision", sa.Date(), nullable=False),
        sa.Column(
            "nivel_riesgo_cargo",
            sa.Enum("bajo", "medio", "alto", "muy_alto", name="nivelriesgocargo"),
            nullable=False,
        ),
        sa.Column("creado_por", sa.Integer(), nullable=False),
        sa.Column("fecha_creacion", sa.DateTime(), nullable=False),
        sa.Column("modificado_por", sa.Integer(), nullable=True),
        sa.Column("fecha_modificacion", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "periodicidad_emo_meses <= 12 OR justificacion_periodicidad_emo IS NOT NULL",
            name="ck_profesiogramas_justificacion_periodicidad",
        ),
        sa.CheckConstraint(
            "periodicidad_emo_meses IN (6, 12, 24, 36)",
            name="ck_profesiogramas_periodicidad",
        ),
        sa.ForeignKeyConstraint(["cargo_id"], ["cargos.id"]),
        sa.ForeignKeyConstraint(["creado_por"], ["users.id"]),
        sa.ForeignKeyConstraint(["modificado_por"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cargo_id", "version", name="uq_profesiogramas_cargo_id_version"),
    )
    op.create_index(op.f("ix_profesiogramas_cargo_id"), "profesiogramas", ["cargo_id"], unique=False)
    op.create_index(op.f("ix_profesiogramas_id"), "profesiogramas", ["id"], unique=False)

    op.create_table(
        "profesiograma_factor_riesgo",
        sa.Column("profesiograma_id", sa.Integer(), nullable=False),
        sa.Column("factor_riesgo_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["factor_riesgo_id"], ["factores_riesgo.id"]),
        sa.ForeignKeyConstraint(["profesiograma_id"], ["profesiogramas.id"]),
        sa.PrimaryKeyConstraint("profesiograma_id", "factor_riesgo_id"),
    )

    op.create_table(
        "profesiograma_criterio_exclusion",
        sa.Column("profesiograma_id", sa.Integer(), nullable=False),
        sa.Column("criterio_exclusion_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["criterio_exclusion_id"], ["criterios_exclusion.id"]),
        sa.ForeignKeyConstraint(["profesiograma_id"], ["profesiogramas.id"]),
        sa.PrimaryKeyConstraint("profesiograma_id", "criterio_exclusion_id"),
    )

    op.create_table(
        "profesiograma_examenes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profesiograma_id", sa.Integer(), nullable=False),
        sa.Column("tipo_examen_id", sa.Integer(), nullable=False),
        sa.Column("obligatorio", sa.Boolean(), nullable=False),
        sa.Column("observaciones", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["profesiograma_id"], ["profesiogramas.id"]),
        sa.ForeignKeyConstraint(["tipo_examen_id"], ["tipos_examen.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "profesiograma_id",
            "tipo_examen_id",
            name="uq_profesiograma_examenes_profesiograma_tipo",
        ),
    )
    op.create_index(op.f("ix_profesiograma_examenes_id"), "profesiograma_examenes", ["id"], unique=False)
    op.create_index(
        op.f("ix_profesiograma_examenes_profesiograma_id"),
        "profesiograma_examenes",
        ["profesiograma_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_profesiograma_examenes_tipo_examen_id"),
        "profesiograma_examenes",
        ["tipo_examen_id"],
        unique=False,
    )

    op.create_table(
        "profesiograma_inmunizaciones",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profesiograma_id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(length=150), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["profesiograma_id"], ["profesiogramas.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_profesiograma_inmunizaciones_id"),
        "profesiograma_inmunizaciones",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_profesiograma_inmunizaciones_profesiograma_id"),
        "profesiograma_inmunizaciones",
        ["profesiograma_id"],
        unique=False,
    )

    op.create_table(
        "programas_sve",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profesiograma_id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(length=200), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["profesiograma_id"], ["profesiogramas.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_programas_sve_id"), "programas_sve", ["id"], unique=False)
    op.create_index(
        op.f("ix_programas_sve_profesiograma_id"),
        "programas_sve",
        ["profesiograma_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_programas_sve_profesiograma_id"), table_name="programas_sve")
    op.drop_index(op.f("ix_programas_sve_id"), table_name="programas_sve")
    op.drop_table("programas_sve")

    op.drop_index(op.f("ix_profesiograma_inmunizaciones_profesiograma_id"), table_name="profesiograma_inmunizaciones")
    op.drop_index(op.f("ix_profesiograma_inmunizaciones_id"), table_name="profesiograma_inmunizaciones")
    op.drop_table("profesiograma_inmunizaciones")

    op.drop_index(op.f("ix_profesiograma_examenes_tipo_examen_id"), table_name="profesiograma_examenes")
    op.drop_index(op.f("ix_profesiograma_examenes_profesiograma_id"), table_name="profesiograma_examenes")
    op.drop_index(op.f("ix_profesiograma_examenes_id"), table_name="profesiograma_examenes")
    op.drop_table("profesiograma_examenes")

    op.drop_table("profesiograma_criterio_exclusion")
    op.drop_table("profesiograma_factor_riesgo")

    op.drop_index(op.f("ix_profesiogramas_id"), table_name="profesiogramas")
    op.drop_index(op.f("ix_profesiogramas_cargo_id"), table_name="profesiogramas")
    op.drop_table("profesiogramas")

    op.drop_index(op.f("ix_tipos_examen_nombre"), table_name="tipos_examen")
    op.drop_index(op.f("ix_tipos_examen_id"), table_name="tipos_examen")
    op.drop_table("tipos_examen")

    op.drop_index(op.f("ix_criterios_exclusion_nombre"), table_name="criterios_exclusion")
    op.drop_index(op.f("ix_criterios_exclusion_id"), table_name="criterios_exclusion")
    op.drop_table("criterios_exclusion")

    op.drop_index(op.f("ix_factores_riesgo_nombre"), table_name="factores_riesgo")
    op.drop_index(op.f("ix_factores_riesgo_id"), table_name="factores_riesgo")
    op.drop_table("factores_riesgo")

    op.execute("DROP TYPE IF EXISTS profesiogramaestado")
    op.execute("DROP TYPE IF EXISTS nivelriesgocargo")

