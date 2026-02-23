"""add master documents table

Revision ID: d3f4e5a6b7c8
Revises: c0d1e2f3a4b5
Create Date: 2026-02-23

"""

from alembic import op
import sqlalchemy as sa


revision = "d3f4e5a6b7c8"
down_revision = "c0d1e2f3a4b5"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "master_documents",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("empresa_id", sa.Integer(), sa.ForeignKey("empresas.id"), nullable=True),
        sa.Column("tipo_documento", sa.String(length=120), nullable=False),
        sa.Column("nombre_documento", sa.String(length=300), nullable=False),
        sa.Column("version", sa.String(length=20), nullable=True),
        sa.Column("codigo", sa.String(length=50), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=True),
        sa.Column("fecha_texto", sa.String(length=20), nullable=True),
        sa.Column("ubicacion", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("empresa_id", "codigo", name="uq_master_documents_empresa_codigo"),
    )

    op.create_index("ix_master_documents_codigo", "master_documents", ["codigo"], unique=False)
    op.create_index(
        "ix_master_documents_tipo_documento",
        "master_documents",
        ["tipo_documento"],
        unique=False,
    )
    op.create_index("ix_master_documents_empresa_id", "master_documents", ["empresa_id"], unique=False)
    op.create_index("ix_master_documents_id", "master_documents", ["id"], unique=False)


def downgrade():
    op.drop_index("ix_master_documents_id", table_name="master_documents")
    op.drop_index("ix_master_documents_empresa_id", table_name="master_documents")
    op.drop_index("ix_master_documents_tipo_documento", table_name="master_documents")
    op.drop_index("ix_master_documents_codigo", table_name="master_documents")
    op.drop_table("master_documents")

