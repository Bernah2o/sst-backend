"""add art15 fields to occupational exams

Revision ID: e7f8a9b0c1d2
Revises: d4e5f6a7b8c9
Create Date: 2026-01-21

"""

from alembic import op
import sqlalchemy as sa


revision = "e7f8a9b0c1d2"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("occupational_exams") as batch_op:
        batch_op.add_column(sa.Column("exam_time", sa.Time(), nullable=True))
        batch_op.add_column(sa.Column("departamento", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("ciudad", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("duracion_minutos", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("afiliacion_eps_momento", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("afiliacion_afp_momento", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("afiliacion_arl_momento", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("historia_ocupacional", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("duracion_cargo_actual_meses", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("antecedentes_personales", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("antecedentes_familiares", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("antecedentes_ocupacionales", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("factores_riesgo_evaluados", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("cargo_id_momento_examen", sa.Integer(), nullable=True))
        batch_op.create_index("ix_occupational_exams_cargo_id_momento_examen", ["cargo_id_momento_examen"], unique=False)
        batch_op.create_foreign_key(
            "fk_occupational_exams_cargo_id_momento_examen_cargos",
            "cargos",
            ["cargo_id_momento_examen"],
            ["id"],
        )
        batch_op.create_check_constraint(
            "ck_occupational_exams_duracion_minima",
            "duracion_minutos IS NULL OR duracion_minutos >= 20",
        )


def downgrade() -> None:
    with op.batch_alter_table("occupational_exams") as batch_op:
        batch_op.drop_constraint("ck_occupational_exams_duracion_minima", type_="check")
        batch_op.drop_constraint("fk_occupational_exams_cargo_id_momento_examen_cargos", type_="foreignkey")
        batch_op.drop_index("ix_occupational_exams_cargo_id_momento_examen")
        batch_op.drop_column("cargo_id_momento_examen")
        batch_op.drop_column("factores_riesgo_evaluados")
        batch_op.drop_column("antecedentes_ocupacionales")
        batch_op.drop_column("antecedentes_familiares")
        batch_op.drop_column("antecedentes_personales")
        batch_op.drop_column("duracion_cargo_actual_meses")
        batch_op.drop_column("historia_ocupacional")
        batch_op.drop_column("afiliacion_arl_momento")
        batch_op.drop_column("afiliacion_afp_momento")
        batch_op.drop_column("afiliacion_eps_momento")
        batch_op.drop_column("duracion_minutos")
        batch_op.drop_column("ciudad")
        batch_op.drop_column("departamento")
        batch_op.drop_column("exam_time")

