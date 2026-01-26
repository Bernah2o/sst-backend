"""add gtc45 fields to profesiograma factores

Revision ID: a3b4c5d6e7f8
Revises: f0a1b2c3d4e5
Create Date: 2026-01-22

"""

from alembic import op
import sqlalchemy as sa


revision = "a3b4c5d6e7f8"
down_revision = "f0a1b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("profesiograma_factores", sa.Column("proceso", sa.String(length=100), nullable=True))
    op.add_column("profesiograma_factores", sa.Column("actividad", sa.String(length=150), nullable=True))
    op.add_column("profesiograma_factores", sa.Column("tarea", sa.String(length=150), nullable=True))
    op.add_column("profesiograma_factores", sa.Column("rutinario", sa.Boolean(), nullable=True))

    op.add_column("profesiograma_factores", sa.Column("descripcion_peligro", sa.Text(), nullable=True))
    op.add_column("profesiograma_factores", sa.Column("efectos_posibles", sa.Text(), nullable=True))

    op.add_column("profesiograma_factores", sa.Column("nd", sa.Integer(), nullable=True))
    op.add_column("profesiograma_factores", sa.Column("ne", sa.Integer(), nullable=True))
    op.add_column("profesiograma_factores", sa.Column("nc", sa.Integer(), nullable=True))

    op.add_column("profesiograma_factores", sa.Column("eliminacion", sa.Text(), nullable=True))
    op.add_column("profesiograma_factores", sa.Column("sustitucion", sa.Text(), nullable=True))
    op.add_column("profesiograma_factores", sa.Column("senalizacion", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("profesiograma_factores", "senalizacion")
    op.drop_column("profesiograma_factores", "sustitucion")
    op.drop_column("profesiograma_factores", "eliminacion")

    op.drop_column("profesiograma_factores", "nc")
    op.drop_column("profesiograma_factores", "ne")
    op.drop_column("profesiograma_factores", "nd")

    op.drop_column("profesiograma_factores", "efectos_posibles")
    op.drop_column("profesiograma_factores", "descripcion_peligro")

    op.drop_column("profesiograma_factores", "rutinario")
    op.drop_column("profesiograma_factores", "tarea")
    op.drop_column("profesiograma_factores", "actividad")
    op.drop_column("profesiograma_factores", "proceso")
