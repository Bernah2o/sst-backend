"""add_system_settings_table

Revision ID: a1b2c3d4e5f7
Revises: 0a173e668dc1
Create Date: 2026-01-27 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f7'
down_revision = '0a173e668dc1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Crear tabla system_settings
    op.create_table('system_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=100), nullable=False),
        sa.Column('value', sa.String(length=500), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_system_settings_id'), 'system_settings', ['id'], unique=False)
    op.create_index(op.f('ix_system_settings_key'), 'system_settings', ['key'], unique=True)

    # Insertar configuración por defecto para notificaciones de exámenes
    op.execute("""
        INSERT INTO system_settings (key, value, description, is_enabled)
        VALUES (
            'exam_notifications_enabled',
            'true',
            'Habilitar/deshabilitar el envío automático de notificaciones de exámenes ocupacionales',
            true
        )
    """)


def downgrade() -> None:
    op.drop_index(op.f('ix_system_settings_key'), table_name='system_settings')
    op.drop_index(op.f('ix_system_settings_id'), table_name='system_settings')
    op.drop_table('system_settings')
