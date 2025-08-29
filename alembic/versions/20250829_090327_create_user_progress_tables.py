"""Create user progress tables

Revision ID: 20250829_090327_create_user_progress_tables
Revises: b75e3259670b
Create Date: 2025-08-29T09:03:27.758101

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20250829_090327_create_user_progress_tables'
down_revision = 'b75e3259670b'
branch_labels = None
depends_on = None


def upgrade():
    # Create user_material_progress table
    op.create_table('user_material_progress',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('enrollment_id', sa.Integer(), nullable=False),
        sa.Column('material_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('time_spent_seconds', sa.Integer(), nullable=True),
        sa.Column('progress_percentage', sa.Float(), nullable=True),
        sa.Column('last_position', sa.Integer(), nullable=True),
        sa.Column('attempts', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['enrollment_id'], ['enrollments.id'], ),
        sa.ForeignKeyConstraint(['material_id'], ['course_materials.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_material_progress_id'), 'user_material_progress', ['id'], unique=False)
    
    # Create user_module_progress table
    op.create_table('user_module_progress',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('enrollment_id', sa.Integer(), nullable=False),
        sa.Column('module_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('progress_percentage', sa.Float(), nullable=True),
        sa.Column('materials_completed', sa.Integer(), nullable=True),
        sa.Column('total_materials', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['enrollment_id'], ['enrollments.id'], ),
        sa.ForeignKeyConstraint(['module_id'], ['course_modules.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_module_progress_id'), 'user_module_progress', ['id'], unique=False)


def downgrade():
    # Drop user_module_progress table
    op.drop_index(op.f('ix_user_module_progress_id'), table_name='user_module_progress')
    op.drop_table('user_module_progress')
    
    # Drop user_material_progress table
    op.drop_index(op.f('ix_user_material_progress_id'), table_name='user_material_progress')
    op.drop_table('user_material_progress')
