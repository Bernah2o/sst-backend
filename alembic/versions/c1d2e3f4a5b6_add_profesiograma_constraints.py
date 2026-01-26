"""add profesiograma constraints

Revision ID: c1d2e3f4a5b6
Revises: a9b8c7d6e5f4
Create Date: 2026-01-21

"""

from alembic import op


revision = "c1d2e3f4a5b6"
down_revision = "a9b8c7d6e5f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    minlen_expr = (
        "periodicidad_emo_meses <= 12 OR char_length(trim(justificacion_periodicidad_emo)) >= 50"
        if dialect_name == "postgresql"
        else "periodicidad_emo_meses <= 12 OR length(trim(justificacion_periodicidad_emo)) >= 50"
    )

    with op.batch_alter_table("profesiogramas") as batch_op:
        batch_op.create_check_constraint(
            "ck_profesiogramas_justificacion_periodicidad_minlen",
            minlen_expr,
        )

    with op.batch_alter_table("profesiograma_examenes") as batch_op:
        batch_op.create_check_constraint(
            "ck_profesiograma_examenes_periodicidad_por_tipo",
            "(tipo_evaluacion = 'periodico' AND periodicidad_meses IS NOT NULL) OR (tipo_evaluacion <> 'periodico' AND periodicidad_meses IS NULL)",
        )
        batch_op.create_check_constraint(
            "ck_profesiograma_examenes_periodicidad_valida",
            "periodicidad_meses IS NULL OR periodicidad_meses IN (6, 12, 24, 36)",
        )


def downgrade() -> None:
    with op.batch_alter_table("profesiograma_examenes") as batch_op:
        batch_op.drop_constraint("ck_profesiograma_examenes_periodicidad_valida", type_="check")
        batch_op.drop_constraint("ck_profesiograma_examenes_periodicidad_por_tipo", type_="check")

    with op.batch_alter_table("profesiogramas") as batch_op:
        batch_op.drop_constraint("ck_profesiogramas_justificacion_periodicidad_minlen", type_="check")

