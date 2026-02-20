"""create_plan_trabajo_anual_tables

Revision ID: a1b2c3d4e5f8
Revises: 74410b4f386d
Create Date: 2026-02-20 12:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f8'
down_revision = '15de284399be'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Crear enums de PostgreSQL
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE estadoplan AS ENUM ('borrador', 'aprobado', 'en_ejecucion', 'finalizado');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE cloophva AS ENUM ('I_PLANEAR', 'II_HACER', 'III_VERIFICAR', 'IV_ACTUAR');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE categoriaactividad AS ENUM (
                'RECURSOS', 'GESTION_INTEGRAL', 'GESTION_SALUD',
                'GESTION_PELIGROS', 'GESTION_AMENAZAS', 'VERIFICACION', 'MEJORAMIENTO'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # Tabla plan_trabajo_anual
    op.create_table(
        'plan_trabajo_anual',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('año', sa.Integer(), nullable=False),
        sa.Column('empresa_id', sa.Integer(), sa.ForeignKey('empresas.id'), nullable=True),
        sa.Column('codigo', sa.String(50), nullable=True, default='PL-SST-02'),
        sa.Column('version', sa.String(20), nullable=True, default='1'),
        sa.Column('objetivo', sa.Text(), nullable=True),
        sa.Column('alcance', sa.Text(), nullable=True),
        sa.Column('meta', sa.String(500), nullable=True),
        sa.Column('meta_porcentaje', sa.Float(), nullable=True, default=90.0),
        sa.Column('indicador', sa.String(500), nullable=True),
        sa.Column('formula', sa.String(500), nullable=True),
        sa.Column('encargado_sgsst', sa.String(200), nullable=True),
        sa.Column('aprobado_por', sa.String(200), nullable=True),
        sa.Column('estado', sa.String(30), nullable=True, default='borrador'),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
    )

    # Tabla plan_trabajo_actividad
    op.create_table(
        'plan_trabajo_actividad',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('plan_id', sa.Integer(), sa.ForeignKey('plan_trabajo_anual.id', ondelete='CASCADE'), nullable=False),
        sa.Column('ciclo', sa.String(30), nullable=False),
        sa.Column('categoria', sa.String(50), nullable=False),
        sa.Column('estandar', sa.String(200), nullable=True),
        sa.Column('descripcion', sa.Text(), nullable=False),
        sa.Column('frecuencia', sa.String(100), nullable=True),
        sa.Column('responsable', sa.String(300), nullable=True),
        sa.Column('recurso_financiero', sa.Boolean(), nullable=True, default=False),
        sa.Column('recurso_tecnico', sa.Boolean(), nullable=True, default=False),
        sa.Column('costo', sa.Numeric(12, 2), nullable=True),
        sa.Column('observaciones', sa.Text(), nullable=True),
        sa.Column('orden', sa.Integer(), nullable=True, default=0),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
    )

    # Tabla plan_trabajo_seguimiento (tracking mensual P/E)
    op.create_table(
        'plan_trabajo_seguimiento',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('actividad_id', sa.Integer(), sa.ForeignKey('plan_trabajo_actividad.id', ondelete='CASCADE'), nullable=False),
        sa.Column('mes', sa.Integer(), nullable=False),
        sa.Column('programada', sa.Boolean(), nullable=True, default=False),
        sa.Column('ejecutada', sa.Boolean(), nullable=True, default=False),
        sa.Column('observacion', sa.Text(), nullable=True),
        sa.Column('fecha_ejecucion', sa.Date(), nullable=True),
        sa.Column('ejecutado_por', sa.String(200), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
    )


def downgrade() -> None:
    op.drop_table('plan_trabajo_seguimiento')
    op.drop_table('plan_trabajo_actividad')
    op.drop_table('plan_trabajo_anual')
    op.execute("DROP TYPE IF EXISTS categoriaactividad")
    op.execute("DROP TYPE IF EXISTS cloophva")
    op.execute("DROP TYPE IF EXISTS estadoplan")
