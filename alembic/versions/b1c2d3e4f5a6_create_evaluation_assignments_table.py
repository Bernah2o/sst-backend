"""create_evaluation_assignments_table

Revision ID: b1c2d3e4f5a6
Revises: a1b2c3d4e5f9
Create Date: 2026-04-23

"""
from alembic import op
import sqlalchemy as sa


revision = 'b1c2d3e4f5a6'
down_revision = 'a1b2c3d4e5f9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'evaluation_assignments',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('evaluation_id', sa.Integer(),
                  sa.ForeignKey('evaluations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.Integer(),
                  sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=True),
        sa.Column('assigned_by', sa.Integer(),
                  sa.ForeignKey('users.id'), nullable=False),
        sa.Column('assigned_at', sa.DateTime(), nullable=False),
        sa.Column('deadline', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index('ix_eval_assign_eval_id', 'evaluation_assignments', ['evaluation_id'])
    op.create_index('ix_eval_assign_user_id', 'evaluation_assignments', ['user_id'])
    op.create_unique_constraint('uq_eval_assign', 'evaluation_assignments', ['evaluation_id', 'user_id'])


def downgrade() -> None:
    op.drop_constraint('uq_eval_assign', 'evaluation_assignments', type_='unique')
    op.drop_index('ix_eval_assign_user_id', table_name='evaluation_assignments')
    op.drop_index('ix_eval_assign_eval_id', table_name='evaluation_assignments')
    op.drop_table('evaluation_assignments')
