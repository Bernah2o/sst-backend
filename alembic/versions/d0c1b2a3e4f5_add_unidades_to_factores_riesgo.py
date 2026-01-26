"""Add unidades to factores_riesgo

Revision ID: d0c1b2a3e4f5
Revises: c2a1f4b8d0e1
Create Date: 2026-01-22

"""

from alembic import op
import sqlalchemy as sa


revision = "d0c1b2a3e4f5"
down_revision = "c2a1f4b8d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("factores_riesgo") as batch_op:
        batch_op.add_column(sa.Column("unidad_medida", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("simbolo_unidad", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("instrumento_medida", sa.String(length=80), nullable=True))

    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        lower_fn = "lower"
        like_op = "ILIKE"
    else:
        lower_fn = "lower"
        like_op = "LIKE"

    def _set_if_null(pattern: str, unidad: str, simbolo: str, instrumento: str) -> None:
        conn = op.get_bind()
        conn.execute(
            sa.text(
                f"""
                UPDATE factores_riesgo
                SET
                  unidad_medida = COALESCE(unidad_medida, :unidad),
                  simbolo_unidad = COALESCE(simbolo_unidad, :simbolo),
                  instrumento_medida = COALESCE(instrumento_medida, :instrumento)
                WHERE unidad_medida IS NULL
                  AND {lower_fn}(nombre) {like_op} {lower_fn}(:pattern)
                """
            ),
            {"unidad": unidad, "simbolo": simbolo, "instrumento": instrumento, "pattern": pattern},
        )

    _set_if_null("%ruido%", "Decibelios", "dB", "Sonómetro")
    _set_if_null("%presi%acust%", "Pascales", "Pa", "Sonómetro")
    _set_if_null("%polvo%", "mg/m³", "mg/m³", "Muestreador de aire")
    _set_if_null("%quimic%", "ppm (partes/millón)", "ppm", "Detector gas/líquido")
    _set_if_null("%ilumin%", "Luxes", "lux", "Luxómetro")
    _set_if_null("%temperatura%", "Grados Celsius", "°C", "Termómetro")
    _set_if_null("%vibraci%", "m/s²", "m/s²", "Vibrómetro")
    _set_if_null("%radiaci%", "µSv/h", "µSv/h", "Dosímetro")
    _set_if_null("%humedad%", "Porcentaje", "%", "Higrómetro")
    _set_if_null("%velocidad%aire%", "m/s", "m/s", "Anemómetro")
    _set_if_null("%carga%mental%", "Puntos escala", "pts", "Test/Encuesta")
    _set_if_null("%estrés%", "Score PSS", "0-56", "Escala Cohen")
    _set_if_null("%estres%", "Score PSS", "0-56", "Escala Cohen")
    _set_if_null("%horas%trabajo%", "Horas/día", "h", "Cronómetro")


def downgrade() -> None:
    with op.batch_alter_table("factores_riesgo") as batch_op:
        batch_op.drop_column("instrumento_medida")
        batch_op.drop_column("simbolo_unidad")
        batch_op.drop_column("unidad_medida")
