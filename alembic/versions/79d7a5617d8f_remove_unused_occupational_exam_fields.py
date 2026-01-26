"""remove unused occupational exam fields

Revision ID: 79d7a5617d8f
Revises: d32e92ecf896
Create Date: 2026-01-22 21:30:45.711036

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '79d7a5617d8f'
down_revision = 'd32e92ecf896'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("occupational_exams") as batch_op:
        batch_op.drop_constraint(
            "ck_occupational_exams_duracion_minima",
            type_="check",
        )
        batch_op.drop_column("antecedentes_ocupacionales")
        batch_op.drop_column("antecedentes_familiares")
        batch_op.drop_column("antecedentes_personales")
        batch_op.drop_column("historia_ocupacional")
        batch_op.drop_column("duracion_minutos")
        batch_op.drop_column("exam_time")


def downgrade() -> None:
    with op.batch_alter_table("occupational_exams") as batch_op:
        batch_op.add_column(sa.Column("exam_time", sa.Time(), nullable=True))
        batch_op.add_column(sa.Column("duracion_minutos", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("historia_ocupacional", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("antecedentes_personales", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("antecedentes_familiares", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("antecedentes_ocupacionales", sa.Text(), nullable=True))
        batch_op.create_check_constraint(
            "ck_occupational_exams_duracion_minima",
            "duracion_minutos IS NULL OR duracion_minutos >= 20",
        )
