"""add restricciones medicas

Revision ID: d4e5f6a7b8c9
Revises: c1d2e3f4a5b6
Create Date: 2026-01-21

"""

from alembic import op
import sqlalchemy as sa


revision = "d4e5f6a7b8c9"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("workers") as batch_op:
        batch_op.add_column(sa.Column("tiene_restricciones_activas", sa.Boolean(), nullable=False, server_default=sa.text("false")))
        batch_op.create_index("ix_workers_tiene_restricciones_activas", ["tiene_restricciones_activas"], unique=False)

    op.create_table(
        "restricciones_medicas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("worker_id", sa.Integer(), nullable=False),
        sa.Column("occupational_exam_id", sa.Integer(), nullable=True),
        sa.Column(
            "tipo_restriccion",
            sa.Enum("temporal", "permanente", "condicional", name="tiporestriccion"),
            nullable=False,
        ),
        sa.Column("descripcion", sa.Text(), nullable=False),
        sa.Column("actividades_restringidas", sa.Text(), nullable=True),
        sa.Column("recomendaciones", sa.Text(), nullable=True),
        sa.Column("fecha_inicio", sa.Date(), nullable=False),
        sa.Column("fecha_fin", sa.Date(), nullable=True),
        sa.Column("activa", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("fecha_limite_implementacion", sa.Date(), nullable=False),
        sa.Column("fecha_implementacion", sa.Date(), nullable=True),
        sa.Column(
            "estado_implementacion",
            sa.Enum(
                "pendiente",
                "en_proceso",
                "implementada",
                "vencida",
                name="estadoimplementacionrestriccion",
            ),
            nullable=False,
            server_default="pendiente",
        ),
        sa.Column("implementada", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("responsable_implementacion_id", sa.Integer(), nullable=True),
        sa.Column("observaciones_implementacion", sa.Text(), nullable=True),
        sa.Column("creado_por", sa.Integer(), nullable=True),
        sa.Column("fecha_creacion", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("modificado_por", sa.Integer(), nullable=True),
        sa.Column("fecha_modificacion", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "(tipo_restriccion = 'permanente' AND fecha_fin IS NULL) OR (tipo_restriccion <> 'permanente')",
            name="ck_restricciones_medicas_permanente_sin_fecha_fin",
        ),
        sa.ForeignKeyConstraint(["occupational_exam_id"], ["occupational_exams.id"]),
        sa.ForeignKeyConstraint(["worker_id"], ["workers.id"]),
        sa.ForeignKeyConstraint(["responsable_implementacion_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["creado_por"], ["users.id"]),
        sa.ForeignKeyConstraint(["modificado_por"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_restricciones_medicas_id"), "restricciones_medicas", ["id"], unique=False)
    op.create_index(op.f("ix_restricciones_medicas_worker_id"), "restricciones_medicas", ["worker_id"], unique=False)
    op.create_index(op.f("ix_restricciones_medicas_occupational_exam_id"), "restricciones_medicas", ["occupational_exam_id"], unique=False)
    op.create_index(op.f("ix_restricciones_medicas_activa"), "restricciones_medicas", ["activa"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_restricciones_medicas_activa"), table_name="restricciones_medicas")
    op.drop_index(op.f("ix_restricciones_medicas_occupational_exam_id"), table_name="restricciones_medicas")
    op.drop_index(op.f("ix_restricciones_medicas_worker_id"), table_name="restricciones_medicas")
    op.drop_index(op.f("ix_restricciones_medicas_id"), table_name="restricciones_medicas")
    op.drop_table("restricciones_medicas")

    with op.batch_alter_table("workers") as batch_op:
        batch_op.drop_index("ix_workers_tiene_restricciones_activas")
        batch_op.drop_column("tiene_restricciones_activas")

    op.execute("DROP TYPE IF EXISTS tiporestriccion")
    op.execute("DROP TYPE IF EXISTS estadoimplementacionrestriccion")

