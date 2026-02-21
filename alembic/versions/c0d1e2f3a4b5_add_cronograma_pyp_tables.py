"""add_cronograma_pyp_tables

Revision ID: c0d1e2f3a4b5
Revises: cdcbe50e36e9
Create Date: 2026-02-21 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "c0d1e2f3a4b5"
down_revision = "cdcbe50e36e9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cronograma_pyp",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "plan_trabajo_anual_id",
            sa.Integer(),
            sa.ForeignKey("plan_trabajo_anual.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("año", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), sa.ForeignKey("empresas.id"), nullable=True),
        sa.Column("codigo", sa.String(length=50), nullable=True, default="CR-PYP-01"),
        sa.Column("version", sa.String(length=20), nullable=True, default="1"),
        sa.Column("objetivo", sa.Text(), nullable=True),
        sa.Column("alcance", sa.Text(), nullable=True),
        sa.Column("encargado_sgsst", sa.String(length=200), nullable=True),
        sa.Column("aprobado_por", sa.String(length=200), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    op.create_table(
        "cronograma_pyp_actividad",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "cronograma_id",
            sa.Integer(),
            sa.ForeignKey("cronograma_pyp.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("actividad", sa.Text(), nullable=False),
        sa.Column("poblacion_objetivo", sa.String(length=500), nullable=True),
        sa.Column("responsable", sa.String(length=300), nullable=True),
        sa.Column("indicador", sa.String(length=500), nullable=True),
        sa.Column("recursos", sa.String(length=500), nullable=True),
        sa.Column("observaciones", sa.Text(), nullable=True),
        sa.Column("orden", sa.Integer(), nullable=True, default=0),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    op.create_table(
        "cronograma_pyp_seguimiento",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "actividad_id",
            sa.Integer(),
            sa.ForeignKey("cronograma_pyp_actividad.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("mes", sa.Integer(), nullable=False),
        sa.Column("programada", sa.Boolean(), nullable=True, default=False),
        sa.Column("ejecutada", sa.Boolean(), nullable=True, default=False),
        sa.Column("observacion", sa.Text(), nullable=True),
        sa.Column("fecha_ejecucion", sa.Date(), nullable=True),
        sa.Column("ejecutado_por", sa.String(length=200), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint("actividad_id", "mes", name="uq_cronograma_pyp_actividad_mes"),
    )


def downgrade() -> None:
    op.drop_table("cronograma_pyp_seguimiento")
    op.drop_table("cronograma_pyp_actividad")
    op.drop_table("cronograma_pyp")

