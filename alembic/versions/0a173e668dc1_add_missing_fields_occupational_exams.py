"""add_missing_fields_occupational_exams

Revision ID: 0a173e668dc1
Revises: 45501dc73afb
Create Date: 2026-01-23 16:21:01.567424

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0a173e668dc1'
down_revision = '45501dc73afb'
branch_labels = None
depends_on = None


def _table_exists(conn, table_name: str) -> bool:
    result = conn.execute(sa.text(
        "SELECT 1 FROM information_schema.tables WHERE table_name = :name"
    ), {"name": table_name}).fetchone()
    return result is not None


def _index_exists(conn, index_name: str) -> bool:
    result = conn.execute(sa.text(
        "SELECT 1 FROM pg_indexes WHERE indexname = :name"
    ), {"name": index_name}).fetchone()
    return result is not None


def _constraint_exists(conn, constraint_name: str, table_name: str) -> bool:
    result = conn.execute(sa.text("""
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = :cname AND table_name = :tname
    """), {"cname": constraint_name, "tname": table_name}).fetchone()
    return result is not None


def _column_exists(conn, table_name: str, column_name: str) -> bool:
    result = conn.execute(sa.text("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = :tname AND column_name = :cname
    """), {"tname": table_name, "cname": column_name}).fetchone()
    return result is not None


def upgrade() -> None:
    conn = op.get_bind()

    # Create admin_config table if not exists
    if not _table_exists(conn, 'admin_config'):
        op.create_table('admin_config',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('category', sa.String(length=50), nullable=False),
            sa.Column('display_name', sa.String(length=200), nullable=False),
            sa.Column('emo_periodicity', sa.String(length=50), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )

    # Create indexes idempotently
    op.execute('CREATE INDEX IF NOT EXISTS ix_admin_config_category ON admin_config (category)')
    op.execute('CREATE INDEX IF NOT EXISTS ix_admin_config_id ON admin_config (id)')

    # Drop constraints idempotently
    if _constraint_exists(conn, 'criterios_exclusion_nombre_key', 'criterios_exclusion'):
        op.drop_constraint('criterios_exclusion_nombre_key', 'criterios_exclusion', type_='unique')

    # Alter columns (these are idempotent by nature)
    try:
        op.alter_column('factores_riesgo', 'nombre',
                   existing_type=sa.VARCHAR(length=100),
                   nullable=False)
    except:
        pass

    try:
        op.alter_column('factores_riesgo', 'categoria',
                   existing_type=postgresql.ENUM('fisico', 'quimico', 'biologico', 'ergonomico', 'psicosocial', 'seguridad', name='categoriafactorriesgo'),
                   nullable=False)
    except:
        pass

    try:
        op.alter_column('factores_riesgo', 'requiere_sve',
                   existing_type=sa.BOOLEAN(),
                   server_default=None,
                   existing_nullable=False)
    except:
        pass

    try:
        op.alter_column('factores_riesgo', 'activo',
                   existing_type=sa.BOOLEAN(),
                   server_default=None,
                   existing_nullable=False)
    except:
        pass

    # Add column to occupational_exams if not exists
    if not _column_exists(conn, 'occupational_exams', 'tipo_examen_id'):
        op.add_column('occupational_exams', sa.Column('tipo_examen_id', sa.Integer(), nullable=True))

    # Drop indexes idempotently
    op.execute('DROP INDEX IF EXISTS ix_occupational_exams_cargo_id_momento_examen')

    # Create foreign key if not exists
    if not _constraint_exists(conn, 'occupational_exams_tipo_examen_id_fkey', 'occupational_exams'):
        try:
            op.create_foreign_key('occupational_exams_tipo_examen_id_fkey', 'occupational_exams', 'tipos_examen', ['tipo_examen_id'], ['id'])
        except:
            pass

    # Drop and create indexes idempotently
    op.execute('DROP INDEX IF EXISTS ix_profesiograma_controles_esiae_pf')
    op.execute('CREATE INDEX IF NOT EXISTS ix_profesiograma_controles_esiae_id ON profesiograma_controles_esiae (id)')

    try:
        op.alter_column('profesiograma_examenes', 'obligatorio',
                   existing_type=sa.BOOLEAN(),
                   server_default=None,
                   existing_nullable=False)
    except:
        pass

    # Drop indexes idempotently
    op.execute('DROP INDEX IF EXISTS ix_profesiograma_examenes_new_profesiograma_id')
    op.execute('DROP INDEX IF EXISTS ix_profesiograma_examenes_new_tipo_examen_id')
    op.execute('DROP INDEX IF EXISTS ix_profesiograma_examenes_profesiograma_id')
    op.execute('DROP INDEX IF EXISTS ix_profesiograma_examenes_tipo_examen_id')

    try:
        op.alter_column('profesiograma_factores', 'fecha_registro',
                   existing_type=postgresql.TIMESTAMP(),
                   server_default=None,
                   existing_nullable=False)
    except:
        pass

    # Drop constraint idempotently
    if _constraint_exists(conn, 'uq_profesiograma_inmunizaciones_profesiograma_inmunizacion', 'profesiograma_inmunizaciones'):
        op.drop_constraint('uq_profesiograma_inmunizaciones_profesiograma_inmunizacion', 'profesiograma_inmunizaciones', type_='unique')

    # Drop and create indexes idempotently
    op.execute('DROP INDEX IF EXISTS ix_profesiograma_intervenciones_pf')
    op.execute('CREATE INDEX IF NOT EXISTS ix_profesiograma_intervenciones_id ON profesiograma_intervenciones (id)')

    try:
        op.alter_column('programas', 'activo',
                   existing_type=sa.BOOLEAN(),
                   server_default=None,
                   existing_nullable=False)
    except:
        pass

    op.execute('CREATE INDEX IF NOT EXISTS ix_programas_id ON programas (id)')

    try:
        op.alter_column('restricciones_medicas', 'activa',
                   existing_type=sa.BOOLEAN(),
                   server_default=None,
                   existing_nullable=False)
    except:
        pass

    try:
        op.alter_column('restricciones_medicas', 'estado_implementacion',
                   existing_type=postgresql.ENUM('pendiente', 'en_proceso', 'implementada', 'vencida', name='estadoimplementacionrestriccion'),
                   server_default=None,
                   existing_nullable=False)
    except:
        pass

    try:
        op.alter_column('restricciones_medicas', 'implementada',
                   existing_type=sa.BOOLEAN(),
                   server_default=None,
                   existing_nullable=False)
    except:
        pass

    try:
        op.alter_column('restricciones_medicas', 'fecha_creacion',
                   existing_type=postgresql.TIMESTAMP(),
                   server_default=None,
                   existing_nullable=False)
    except:
        pass

    # Drop constraint idempotently
    if _constraint_exists(conn, 'tipos_examen_nombre_key', 'tipos_examen'):
        op.drop_constraint('tipos_examen_nombre_key', 'tipos_examen', type_='unique')

    # Manage vacation_balances indexes
    op.execute('DROP INDEX IF EXISTS ix_vacation_balances_worker_id_nonunique')
    op.execute('CREATE INDEX IF NOT EXISTS ix_vacation_balances_worker_id ON vacation_balances (worker_id)')

    try:
        op.alter_column('workers', 'tiene_restricciones_activas',
                   existing_type=sa.BOOLEAN(),
                   server_default=None,
                   existing_nullable=False)
    except:
        pass


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('workers', 'tiene_restricciones_activas',
               existing_type=sa.BOOLEAN(),
               server_default=sa.text('false'),
               existing_nullable=False)
    op.drop_index(op.f('ix_vacation_balances_worker_id'), table_name='vacation_balances')
    op.create_index('ix_vacation_balances_worker_id_nonunique', 'vacation_balances', ['worker_id'], unique=False)
    op.create_unique_constraint('tipos_examen_nombre_key', 'tipos_examen', ['nombre'], postgresql_nulls_not_distinct=False)
    op.alter_column('restricciones_medicas', 'fecha_creacion',
               existing_type=postgresql.TIMESTAMP(),
               server_default=sa.text('now()'),
               existing_nullable=False)
    op.alter_column('restricciones_medicas', 'implementada',
               existing_type=sa.BOOLEAN(),
               server_default=sa.text('false'),
               existing_nullable=False)
    op.alter_column('restricciones_medicas', 'estado_implementacion',
               existing_type=postgresql.ENUM('pendiente', 'en_proceso', 'implementada', 'vencida', name='estadoimplementacionrestriccion'),
               server_default=sa.text("'pendiente'::estadoimplementacionrestriccion"),
               existing_nullable=False)
    op.alter_column('restricciones_medicas', 'activa',
               existing_type=sa.BOOLEAN(),
               server_default=sa.text('true'),
               existing_nullable=False)
    op.drop_index(op.f('ix_programas_id'), table_name='programas')
    op.alter_column('programas', 'activo',
               existing_type=sa.BOOLEAN(),
               server_default=sa.text('true'),
               existing_nullable=False)
    op.drop_index(op.f('ix_profesiograma_intervenciones_id'), table_name='profesiograma_intervenciones')
    op.create_index('ix_profesiograma_intervenciones_pf', 'profesiograma_intervenciones', ['profesiograma_id', 'factor_riesgo_id'], unique=False)
    op.create_unique_constraint('uq_profesiograma_inmunizaciones_profesiograma_inmunizacion', 'profesiograma_inmunizaciones', ['profesiograma_id', 'inmunizacion_id'], postgresql_nulls_not_distinct=False)
    op.alter_column('profesiograma_factores', 'fecha_registro',
               existing_type=postgresql.TIMESTAMP(),
               server_default=sa.text('CURRENT_TIMESTAMP'),
               existing_nullable=False)
    op.create_index('ix_profesiograma_examenes_tipo_examen_id', 'profesiograma_examenes', ['tipo_examen_id'], unique=False)
    op.create_index('ix_profesiograma_examenes_profesiograma_id', 'profesiograma_examenes', ['profesiograma_id'], unique=False)
    op.create_index('ix_profesiograma_examenes_new_tipo_examen_id', 'profesiograma_examenes', ['tipo_examen_id'], unique=False)
    op.create_index('ix_profesiograma_examenes_new_profesiograma_id', 'profesiograma_examenes', ['profesiograma_id'], unique=False)
    op.alter_column('profesiograma_examenes', 'obligatorio',
               existing_type=sa.BOOLEAN(),
               server_default=sa.text('true'),
               existing_nullable=False)
    op.drop_index(op.f('ix_profesiograma_controles_esiae_id'), table_name='profesiograma_controles_esiae')
    op.create_index('ix_profesiograma_controles_esiae_pf', 'profesiograma_controles_esiae', ['profesiograma_id', 'factor_riesgo_id'], unique=False)
    op.drop_constraint(None, 'occupational_exams', type_='foreignkey')
    op.create_index('ix_occupational_exams_cargo_id_momento_examen', 'occupational_exams', ['cargo_id_momento_examen'], unique=False)
    op.drop_column('occupational_exams', 'tipo_examen_id')
    op.alter_column('factores_riesgo', 'activo',
               existing_type=sa.BOOLEAN(),
               server_default=sa.text('true'),
               existing_nullable=False)
    op.alter_column('factores_riesgo', 'requiere_sve',
               existing_type=sa.BOOLEAN(),
               server_default=sa.text('false'),
               existing_nullable=False)
    op.alter_column('factores_riesgo', 'categoria',
               existing_type=postgresql.ENUM('fisico', 'quimico', 'biologico', 'ergonomico', 'psicosocial', 'seguridad', name='categoriafactorriesgo'),
               nullable=True)
    op.alter_column('factores_riesgo', 'nombre',
               existing_type=sa.VARCHAR(length=100),
               nullable=True)
    op.create_unique_constraint('criterios_exclusion_nombre_key', 'criterios_exclusion', ['nombre'], postgresql_nulls_not_distinct=False)
    op.drop_index(op.f('ix_admin_config_id'), table_name='admin_config')
    op.drop_index(op.f('ix_admin_config_category'), table_name='admin_config')
    op.drop_table('admin_config')
    # ### end Alembic commands ###
