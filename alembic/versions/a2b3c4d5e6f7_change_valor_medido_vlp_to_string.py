"""change valor_medido and valor_limite_permisible to string

Permite que valor_medido y valor_limite_permisible acepten texto descriptivo
además de valores numéricos (ej: "No aplica", "Contacto directo con agua")

Revision ID: a2b3c4d5e6f7
Revises: 9c1814cda1dc
Create Date: 2026-01-29 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a2b3c4d5e6f7'
down_revision = '9c1814cda1dc'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Cambiar valor_medido de NUMERIC(10,2) a VARCHAR(255)
    # Primero convertimos los valores existentes a texto
    with op.batch_alter_table("profesiograma_factores") as batch_op:
        batch_op.alter_column(
            "valor_medido",
            existing_type=sa.Numeric(precision=10, scale=2),
            type_=sa.String(length=255),
            existing_nullable=True,
            postgresql_using="valor_medido::text"
        )
        batch_op.alter_column(
            "valor_limite_permisible",
            existing_type=sa.Numeric(precision=10, scale=2),
            type_=sa.String(length=255),
            existing_nullable=True,
            postgresql_using="valor_limite_permisible::text"
        )


def downgrade() -> None:
    # Nota: La reversión puede perder datos si hay valores de texto no numéricos
    with op.batch_alter_table("profesiograma_factores") as batch_op:
        batch_op.alter_column(
            "valor_medido",
            existing_type=sa.String(length=255),
            type_=sa.Numeric(precision=10, scale=2),
            existing_nullable=True,
            postgresql_using="NULLIF(valor_medido, '')::numeric(10,2)"
        )
        batch_op.alter_column(
            "valor_limite_permisible",
            existing_type=sa.String(length=255),
            type_=sa.Numeric(precision=10, scale=2),
            existing_nullable=True,
            postgresql_using="NULLIF(valor_limite_permisible, '')::numeric(10,2)"
        )
