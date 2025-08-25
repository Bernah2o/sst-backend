"""create custom roles table

Revision ID: c8d9e2f1a3b4
Revises: b75e3259670b
Create Date: 2025-01-25 08:10:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision = 'c8d9e2f1a3b4'
down_revision = 'b75e3259670b'
branch_labels = None
depends_on = None


def upgrade():
    # Crear tabla custom_roles
    op.create_table(
        'custom_roles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('display_name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_system_role', sa.Boolean(), nullable=False, default=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Crear índices
    op.create_index(op.f('ix_custom_roles_id'), 'custom_roles', ['id'], unique=False)
    op.create_index(op.f('ix_custom_roles_name'), 'custom_roles', ['name'], unique=True)
    
    # Crear tabla de asociación role_permissions
    op.create_table(
        'role_permissions',
        sa.Column('role_id', sa.Integer(), nullable=False),
        sa.Column('permission_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['role_id'], ['custom_roles.id'], ),
        sa.PrimaryKeyConstraint('role_id', 'permission_id')
    )
    
    # Insertar roles del sistema por defecto
    custom_roles_table = sa.table(
        'custom_roles',
        sa.column('name', sa.String),
        sa.column('display_name', sa.String),
        sa.column('description', sa.Text),
        sa.column('is_system_role', sa.Boolean),
        sa.column('is_active', sa.Boolean),
        sa.column('created_at', sa.DateTime),
        sa.column('updated_at', sa.DateTime)
    )
    
    now = datetime.utcnow()
    
    op.bulk_insert(
        custom_roles_table,
        [
            {
                'name': 'admin',
                'display_name': 'Administrador',
                'description': 'Acceso completo al sistema',
                'is_system_role': True,
                'is_active': True,
                'created_at': now,
                'updated_at': now
            },
            {
                'name': 'trainer',
                'display_name': 'Capacitador',
                'description': 'Crear y gestionar cursos, evaluaciones',
                'is_system_role': True,
                'is_active': True,
                'created_at': now,
                'updated_at': now
            },
            {
                'name': 'supervisor',
                'display_name': 'Supervisor',
                'description': 'Ver reportes, gestionar empleados',
                'is_system_role': True,
                'is_active': True,
                'created_at': now,
                'updated_at': now
            },
            {
                'name': 'employee',
                'display_name': 'Empleado',
                'description': 'Tomar cursos y evaluaciones',
                'is_system_role': True,
                'is_active': True,
                'created_at': now,
                'updated_at': now
            }
        ]
    )


def downgrade():
    # Eliminar tabla de asociación
    op.drop_table('role_permissions')
    
    # Eliminar índices
    op.drop_index(op.f('ix_custom_roles_name'), table_name='custom_roles')
    op.drop_index(op.f('ix_custom_roles_id'), table_name='custom_roles')
    
    # Eliminar tabla custom_roles
    op.drop_table('custom_roles')