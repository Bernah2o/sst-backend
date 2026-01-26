"""align profesiograma matrix to gtc45 example

Revision ID: b4c5d6e7f809
Revises: a3b4c5d6e7f8
Create Date: 2026-01-22

"""

from alembic import op
import sqlalchemy as sa


revision = "b4c5d6e7f809"
down_revision = "a3b4c5d6e7f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("profesiogramas", sa.Column("empresa", sa.String(length=150), nullable=True))
    op.add_column("profesiogramas", sa.Column("departamento", sa.String(length=100), nullable=True))
    op.add_column("profesiogramas", sa.Column("codigo_cargo", sa.String(length=50), nullable=True))
    op.add_column("profesiogramas", sa.Column("numero_trabajadores_expuestos", sa.Integer(), nullable=True))
    op.add_column("profesiogramas", sa.Column("fecha_elaboracion", sa.Date(), nullable=True))
    op.add_column("profesiogramas", sa.Column("validado_por", sa.String(length=150), nullable=True))
    op.add_column("profesiogramas", sa.Column("proxima_revision", sa.Date(), nullable=True))

    op.add_column("profesiogramas", sa.Column("elaborado_por", sa.String(length=150), nullable=True))
    op.add_column("profesiogramas", sa.Column("revisado_por", sa.String(length=150), nullable=True))
    op.add_column("profesiogramas", sa.Column("aprobado_por", sa.String(length=150), nullable=True))
    op.add_column("profesiogramas", sa.Column("fecha_aprobacion", sa.Date(), nullable=True))
    op.add_column("profesiogramas", sa.Column("vigencia_meses", sa.Integer(), nullable=True))

    op.add_column("profesiograma_factores", sa.Column("zona_lugar", sa.String(length=150), nullable=True))
    op.add_column("profesiograma_factores", sa.Column("tipo_peligro", sa.String(length=80), nullable=True))
    op.add_column("profesiograma_factores", sa.Column("clasificacion_peligro", sa.String(length=120), nullable=True))

    op.add_column("profesiograma_factores", sa.Column("controles_existentes", sa.Text(), nullable=True))
    op.add_column("profesiograma_factores", sa.Column("fuente", sa.Text(), nullable=True))
    op.add_column("profesiograma_factores", sa.Column("medio", sa.Text(), nullable=True))
    op.add_column("profesiograma_factores", sa.Column("individuo", sa.Text(), nullable=True))

    op.add_column("profesiograma_factores", sa.Column("peor_consecuencia", sa.Text(), nullable=True))
    op.add_column("profesiograma_factores", sa.Column("requisito_legal", sa.Text(), nullable=True))

    op.create_table(
        "profesiograma_controles_esiae",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("profesiograma_id", sa.Integer(), nullable=False),
        sa.Column("factor_riesgo_id", sa.Integer(), nullable=False),
        sa.Column("nivel", sa.String(length=10), nullable=False),
        sa.Column("medida", sa.String(length=150), nullable=True),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.Column("estado_actual", sa.String(length=50), nullable=True),
        sa.Column("meta", sa.String(length=150), nullable=True),
        sa.ForeignKeyConstraint(
            ["profesiograma_id", "factor_riesgo_id"],
            ["profesiograma_factores.profesiograma_id", "profesiograma_factores.factor_riesgo_id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_profesiograma_controles_esiae_pf",
        "profesiograma_controles_esiae",
        ["profesiograma_id", "factor_riesgo_id"],
    )

    op.create_table(
        "profesiograma_intervenciones",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("profesiograma_id", sa.Integer(), nullable=False),
        sa.Column("factor_riesgo_id", sa.Integer(), nullable=False),
        sa.Column("tipo_control", sa.String(length=20), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.Column("responsable", sa.String(length=100), nullable=True),
        sa.Column("plazo", sa.String(length=60), nullable=True),
        sa.ForeignKeyConstraint(
            ["profesiograma_id", "factor_riesgo_id"],
            ["profesiograma_factores.profesiograma_id", "profesiograma_factores.factor_riesgo_id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_profesiograma_intervenciones_pf",
        "profesiograma_intervenciones",
        ["profesiograma_id", "factor_riesgo_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_profesiograma_intervenciones_pf", table_name="profesiograma_intervenciones")
    op.drop_table("profesiograma_intervenciones")

    op.drop_index("ix_profesiograma_controles_esiae_pf", table_name="profesiograma_controles_esiae")
    op.drop_table("profesiograma_controles_esiae")

    op.drop_column("profesiograma_factores", "requisito_legal")
    op.drop_column("profesiograma_factores", "peor_consecuencia")

    op.drop_column("profesiograma_factores", "individuo")
    op.drop_column("profesiograma_factores", "medio")
    op.drop_column("profesiograma_factores", "fuente")
    op.drop_column("profesiograma_factores", "controles_existentes")

    op.drop_column("profesiograma_factores", "clasificacion_peligro")
    op.drop_column("profesiograma_factores", "tipo_peligro")
    op.drop_column("profesiograma_factores", "zona_lugar")

    op.drop_column("profesiogramas", "vigencia_meses")
    op.drop_column("profesiogramas", "fecha_aprobacion")
    op.drop_column("profesiogramas", "aprobado_por")
    op.drop_column("profesiogramas", "revisado_por")
    op.drop_column("profesiogramas", "elaborado_por")

    op.drop_column("profesiogramas", "proxima_revision")
    op.drop_column("profesiogramas", "validado_por")
    op.drop_column("profesiogramas", "fecha_elaboracion")
    op.drop_column("profesiogramas", "numero_trabajadores_expuestos")
    op.drop_column("profesiogramas", "codigo_cargo")
    op.drop_column("profesiogramas", "departamento")
    op.drop_column("profesiogramas", "empresa")

