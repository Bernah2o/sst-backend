"""create matriz legal tables

Crea las tablas para el módulo de Matriz Legal SST:
- sectores_economicos: Catálogo de sectores económicos
- empresas: Configuración de empresas con características
- matriz_legal_importaciones: Registro de importaciones de Excel
- matriz_legal_normas: Normas legales importadas
- matriz_legal_normas_historial: Historial de versiones de normas
- matriz_legal_cumplimientos: Seguimiento de cumplimiento por empresa
- matriz_legal_cumplimientos_historial: Auditoría de cambios

Revision ID: b5c6d7e8f901
Revises: a2b3c4d5e6f7
Create Date: 2026-01-30 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b5c6d7e8f901'
down_revision = 'a2b3c4d5e6f7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ===================== SECTORES ECONÓMICOS =====================
    op.create_table('sectores_economicos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('codigo', sa.String(length=20), nullable=True),
        sa.Column('nombre', sa.String(length=200), nullable=False),
        sa.Column('descripcion', sa.Text(), nullable=True),
        sa.Column('es_todos_los_sectores', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('activo', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_sectores_economicos_id', 'sectores_economicos', ['id'], unique=False)
    op.create_index('ix_sectores_economicos_nombre', 'sectores_economicos', ['nombre'], unique=True)
    op.create_index('ix_sectores_economicos_codigo', 'sectores_economicos', ['codigo'], unique=True)

    # ===================== EMPRESAS =====================
    op.create_table('empresas',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nombre', sa.String(length=200), nullable=False),
        sa.Column('nit', sa.String(length=20), nullable=True),
        sa.Column('razon_social', sa.String(length=300), nullable=True),
        sa.Column('direccion', sa.String(length=300), nullable=True),
        sa.Column('telefono', sa.String(length=50), nullable=True),
        sa.Column('email', sa.String(length=150), nullable=True),
        sa.Column('sector_economico_id', sa.Integer(), nullable=True),
        # Características para filtrado automático
        sa.Column('tiene_trabajadores_independientes', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('tiene_teletrabajo', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('tiene_trabajo_alturas', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('tiene_trabajo_espacios_confinados', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('tiene_trabajo_caliente', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('tiene_sustancias_quimicas', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('tiene_radiaciones', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('tiene_trabajo_nocturno', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('tiene_menores_edad', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('tiene_mujeres_embarazadas', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('tiene_conductores', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('tiene_manipulacion_alimentos', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('tiene_maquinaria_pesada', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('tiene_riesgo_electrico', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('tiene_riesgo_biologico', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('tiene_trabajo_excavaciones', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('tiene_trabajo_administrativo', sa.Boolean(), nullable=False, server_default='false'),
        # Metadatos
        sa.Column('activo', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('creado_por', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['sector_economico_id'], ['sectores_economicos.id'], ),
        sa.ForeignKeyConstraint(['creado_por'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_empresas_id', 'empresas', ['id'], unique=False)
    op.create_index('ix_empresas_nombre', 'empresas', ['nombre'], unique=True)
    op.create_index('ix_empresas_nit', 'empresas', ['nit'], unique=True)

    # ===================== IMPORTACIONES =====================
    op.create_table('matriz_legal_importaciones',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nombre_archivo', sa.String(length=255), nullable=False),
        sa.Column('fecha_importacion', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('estado', sa.String(length=20), nullable=False, server_default='en_proceso'),
        sa.Column('total_filas', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('normas_nuevas', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('normas_actualizadas', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('normas_sin_cambios', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('errores', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('log_errores', sa.Text(), nullable=True),
        sa.Column('creado_por', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['creado_por'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_matriz_legal_importaciones_id', 'matriz_legal_importaciones', ['id'], unique=False)

    # ===================== NORMAS =====================
    op.create_table('matriz_legal_normas',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ambito_aplicacion', sa.String(length=20), nullable=False, server_default='nacional'),
        sa.Column('sector_economico_id', sa.Integer(), nullable=True),
        sa.Column('sector_economico_texto', sa.String(length=200), nullable=True),
        sa.Column('clasificacion_norma', sa.String(length=150), nullable=False),
        sa.Column('tema_general', sa.String(length=200), nullable=False),
        sa.Column('subtema_riesgo_especifico', sa.String(length=300), nullable=True),
        sa.Column('anio', sa.Integer(), nullable=False),
        sa.Column('tipo_norma', sa.String(length=100), nullable=False),
        sa.Column('numero_norma', sa.String(length=50), nullable=False),
        sa.Column('fecha_expedicion', sa.Date(), nullable=True),
        sa.Column('expedida_por', sa.String(length=200), nullable=True),
        sa.Column('descripcion_norma', sa.Text(), nullable=True),
        sa.Column('articulo', sa.String(length=100), nullable=True),
        sa.Column('estado', sa.String(length=20), nullable=False, server_default='vigente'),
        sa.Column('info_adicional', sa.Text(), nullable=True),
        sa.Column('descripcion_articulo_exigencias', sa.Text(), nullable=True),
        # Campos de aplicabilidad
        sa.Column('aplica_trabajadores_independientes', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('aplica_teletrabajo', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('aplica_trabajo_alturas', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('aplica_espacios_confinados', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('aplica_trabajo_caliente', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('aplica_sustancias_quimicas', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('aplica_radiaciones', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('aplica_trabajo_nocturno', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('aplica_menores_edad', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('aplica_mujeres_embarazadas', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('aplica_conductores', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('aplica_manipulacion_alimentos', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('aplica_maquinaria_pesada', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('aplica_riesgo_electrico', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('aplica_riesgo_biologico', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('aplica_trabajo_excavaciones', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('aplica_trabajo_administrativo', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('aplica_general', sa.Boolean(), nullable=False, server_default='true'),
        # Versionado
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('importacion_id', sa.Integer(), nullable=True),
        sa.Column('hash_contenido', sa.String(length=64), nullable=True),
        sa.Column('activo', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['sector_economico_id'], ['sectores_economicos.id'], ),
        sa.ForeignKeyConstraint(['importacion_id'], ['matriz_legal_importaciones.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tipo_norma', 'numero_norma', 'articulo', name='uq_matriz_legal_norma_tipo_numero_articulo')
    )
    op.create_index('ix_matriz_legal_normas_id', 'matriz_legal_normas', ['id'], unique=False)
    op.create_index('ix_matriz_legal_normas_ambito', 'matriz_legal_normas', ['ambito_aplicacion'], unique=False)
    op.create_index('ix_matriz_legal_normas_clasificacion', 'matriz_legal_normas', ['clasificacion_norma'], unique=False)
    op.create_index('ix_matriz_legal_normas_tema', 'matriz_legal_normas', ['tema_general'], unique=False)
    op.create_index('ix_matriz_legal_normas_anio', 'matriz_legal_normas', ['anio'], unique=False)
    op.create_index('ix_matriz_legal_normas_tipo_numero', 'matriz_legal_normas', ['tipo_norma', 'numero_norma'], unique=False)
    op.create_index('ix_matriz_legal_normas_articulo', 'matriz_legal_normas', ['articulo'], unique=False)

    # ===================== HISTORIAL DE NORMAS =====================
    op.create_table('matriz_legal_normas_historial',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('norma_id', sa.Integer(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('datos_json', sa.Text(), nullable=False),
        sa.Column('motivo_cambio', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('creado_por', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['norma_id'], ['matriz_legal_normas.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['creado_por'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_matriz_legal_normas_historial_id', 'matriz_legal_normas_historial', ['id'], unique=False)
    op.create_index('ix_matriz_legal_normas_historial_norma_id', 'matriz_legal_normas_historial', ['norma_id'], unique=False)

    # ===================== CUMPLIMIENTOS =====================
    op.create_table('matriz_legal_cumplimientos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('norma_id', sa.Integer(), nullable=False),
        sa.Column('estado', sa.String(length=20), nullable=False, server_default='pendiente'),
        sa.Column('evidencia_cumplimiento', sa.Text(), nullable=True),
        sa.Column('observaciones', sa.Text(), nullable=True),
        sa.Column('plan_accion', sa.Text(), nullable=True),
        sa.Column('responsable', sa.String(length=150), nullable=True),
        sa.Column('fecha_compromiso', sa.Date(), nullable=True),
        sa.Column('seguimiento', sa.Text(), nullable=True),
        sa.Column('fecha_ultima_evaluacion', sa.DateTime(), nullable=True),
        sa.Column('fecha_proxima_revision', sa.Date(), nullable=True),
        sa.Column('evaluado_por', sa.Integer(), nullable=True),
        sa.Column('aplica_empresa', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('justificacion_no_aplica', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['empresa_id'], ['empresas.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['norma_id'], ['matriz_legal_normas.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['evaluado_por'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('empresa_id', 'norma_id', name='uq_cumplimiento_empresa_norma')
    )
    op.create_index('ix_matriz_legal_cumplimientos_id', 'matriz_legal_cumplimientos', ['id'], unique=False)
    op.create_index('ix_matriz_legal_cumplimientos_empresa', 'matriz_legal_cumplimientos', ['empresa_id'], unique=False)
    op.create_index('ix_matriz_legal_cumplimientos_norma', 'matriz_legal_cumplimientos', ['norma_id'], unique=False)
    op.create_index('ix_matriz_legal_cumplimientos_estado', 'matriz_legal_cumplimientos', ['estado'], unique=False)

    # ===================== HISTORIAL DE CUMPLIMIENTOS =====================
    op.create_table('matriz_legal_cumplimientos_historial',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('cumplimiento_id', sa.Integer(), nullable=False),
        sa.Column('estado_anterior', sa.String(length=50), nullable=True),
        sa.Column('estado_nuevo', sa.String(length=50), nullable=False),
        sa.Column('observaciones', sa.Text(), nullable=True),
        sa.Column('evidencia_anterior', sa.Text(), nullable=True),
        sa.Column('evidencia_nueva', sa.Text(), nullable=True),
        sa.Column('plan_accion_anterior', sa.Text(), nullable=True),
        sa.Column('plan_accion_nuevo', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('creado_por', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['cumplimiento_id'], ['matriz_legal_cumplimientos.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['creado_por'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_matriz_legal_cumplimientos_historial_id', 'matriz_legal_cumplimientos_historial', ['id'], unique=False)
    op.create_index('ix_matriz_legal_cumplimientos_historial_cumplimiento', 'matriz_legal_cumplimientos_historial', ['cumplimiento_id'], unique=False)

    # ===================== DATOS INICIALES =====================
    # Insertar sector "TODOS LOS SECTORES"
    op.execute("""
        INSERT INTO sectores_economicos (nombre, es_todos_los_sectores, activo, created_at)
        VALUES ('TODOS LOS SECTORES', true, true, NOW())
    """)


def downgrade() -> None:
    # Eliminar tablas en orden inverso (por dependencias)
    op.drop_table('matriz_legal_cumplimientos_historial')
    op.drop_table('matriz_legal_cumplimientos')
    op.drop_table('matriz_legal_normas_historial')
    op.drop_table('matriz_legal_normas')
    op.drop_table('matriz_legal_importaciones')
    op.drop_table('empresas')
    op.drop_table('sectores_economicos')
