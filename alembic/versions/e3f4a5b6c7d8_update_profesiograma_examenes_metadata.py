"""update profesiograma examenes metadata

Revision ID: e3f4a5b6c7d8
Revises: d2a3b4c5d6e7
Create Date: 2026-01-21

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e3f4a5b6c7d8"
down_revision = "d2a3b4c5d6e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    op.create_table(
        "profesiograma_examenes_new",
        sa.Column("profesiograma_id", sa.Integer(), nullable=False),
        sa.Column("tipo_examen_id", sa.Integer(), nullable=False),
        sa.Column(
            "tipo_evaluacion",
            sa.Enum(
                "ingreso",
                "periodico",
                "retiro",
                "cambio_cargo",
                "post_incapacidad",
                "reincorporacion",
                name="tipoevaluacionexamen",
            ),
            nullable=False,
        ),
        sa.Column("periodicidad_meses", sa.Integer(), nullable=True),
        sa.Column("justificacion_periodicidad", sa.Text(), nullable=True),
        sa.Column("obligatorio", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("orden_realizacion", sa.Integer(), nullable=True),
        sa.Column("normativa_base", sa.String(length=200), nullable=True),
        sa.ForeignKeyConstraint(["profesiograma_id"], ["profesiogramas.id"]),
        sa.ForeignKeyConstraint(["tipo_examen_id"], ["tipos_examen.id"]),
        sa.PrimaryKeyConstraint("profesiograma_id", "tipo_examen_id", "tipo_evaluacion"),
    )
    op.create_index(
        op.f("ix_profesiograma_examenes_new_profesiograma_id"),
        "profesiograma_examenes_new",
        ["profesiograma_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_profesiograma_examenes_new_tipo_examen_id"),
        "profesiograma_examenes_new",
        ["tipo_examen_id"],
        unique=False,
    )

    tipo_eval_literal = "'periodico'::tipoevaluacionexamen" if dialect_name == "postgresql" else "'periodico'"
    op.execute(
        f"""
        INSERT INTO profesiograma_examenes_new (
            profesiograma_id,
            tipo_examen_id,
            tipo_evaluacion,
            periodicidad_meses,
            justificacion_periodicidad,
            obligatorio,
            orden_realizacion,
            normativa_base
        )
        SELECT
            profesiograma_id,
            tipo_examen_id,
            {tipo_eval_literal},
            NULL,
            observaciones,
            obligatorio,
            NULL,
            NULL
        FROM profesiograma_examenes
        """
    )

    op.drop_index(op.f("ix_profesiograma_examenes_tipo_examen_id"), table_name="profesiograma_examenes")
    op.drop_index(op.f("ix_profesiograma_examenes_profesiograma_id"), table_name="profesiograma_examenes")
    op.drop_index(op.f("ix_profesiograma_examenes_id"), table_name="profesiograma_examenes")
    op.drop_table("profesiograma_examenes")

    op.rename_table("profesiograma_examenes_new", "profesiograma_examenes")
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


def downgrade() -> None:
    op.create_table(
        "profesiograma_examenes_old",
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
    op.create_index(op.f("ix_profesiograma_examenes_old_id"), "profesiograma_examenes_old", ["id"], unique=False)
    op.create_index(
        op.f("ix_profesiograma_examenes_old_profesiograma_id"),
        "profesiograma_examenes_old",
        ["profesiograma_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_profesiograma_examenes_old_tipo_examen_id"),
        "profesiograma_examenes_old",
        ["tipo_examen_id"],
        unique=False,
    )

    op.execute(
        """
        INSERT INTO profesiograma_examenes_old (
            id,
            profesiograma_id,
            tipo_examen_id,
            obligatorio,
            observaciones
        )
        SELECT
            row_number() OVER () AS id,
            profesiograma_id,
            tipo_examen_id,
            obligatorio,
            justificacion_periodicidad
        FROM profesiograma_examenes
        WHERE tipo_evaluacion = 'periodico'
        """
    )

    op.drop_index(op.f("ix_profesiograma_examenes_tipo_examen_id"), table_name="profesiograma_examenes")
    op.drop_index(op.f("ix_profesiograma_examenes_profesiograma_id"), table_name="profesiograma_examenes")
    op.drop_table("profesiograma_examenes")

    op.rename_table("profesiograma_examenes_old", "profesiograma_examenes")
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
    op.execute("DROP TYPE IF EXISTS tipoevaluacionexamen")
