"""backfill_duration_months_for_occupational_exams

Revision ID: b7c9d1e2f3a4
Revises: a9d4e6f8b1c2
Create Date: 2026-04-01 11:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "b7c9d1e2f3a4"
down_revision = "a9d4e6f8b1c2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE occupational_exams oe
            SET duracion_cargo_actual_meses = GREATEST(
                0,
                (
                    (EXTRACT(YEAR FROM oe.exam_date) - EXTRACT(YEAR FROM w.fecha_de_ingreso)) * 12
                    + (EXTRACT(MONTH FROM oe.exam_date) - EXTRACT(MONTH FROM w.fecha_de_ingreso))
                    - CASE
                        WHEN EXTRACT(DAY FROM oe.exam_date) < EXTRACT(DAY FROM w.fecha_de_ingreso) THEN 1
                        ELSE 0
                      END
                )::int
            )
            FROM workers w
            WHERE oe.worker_id = w.id
              AND oe.duracion_cargo_actual_meses IS NULL
              AND w.fecha_de_ingreso IS NOT NULL
            """
        )
    )


def downgrade() -> None:
    pass
