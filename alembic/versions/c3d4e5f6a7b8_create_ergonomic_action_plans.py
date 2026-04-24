"""create_ergonomic_action_plans

Revision ID: c3d4e5f6a7b8
Revises: b1c2d3e4f5a6
Create Date: 2026-04-23 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c3d4e5f6a7b8'
down_revision = 'b1c2d3e4f5a6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'ergonomic_action_plans',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('assessment_id', sa.Integer(), sa.ForeignKey('homework_assessments.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('worker_id', sa.Integer(), sa.ForeignKey('workers.id'), nullable=False),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('non_compliant_items', sa.Text(), nullable=True),
        sa.Column('primary_risk', sa.String(50), nullable=True),
        sa.Column('finding_description', sa.Text(), nullable=True),
        sa.Column('work_frequency', sa.String(30), nullable=True),
        sa.Column('sst_conclusion', sa.String(30), nullable=True),
        sa.Column('sst_conclusion_custom', sa.Text(), nullable=True),
        sa.Column('worker_accepts', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('worker_agreement_name', sa.String(200), nullable=True),
        sa.Column('worker_agreement_date', sa.Date(), nullable=True),
        sa.Column('worker_signature', sa.String(255), nullable=True),
        sa.Column('sst_approver_name', sa.String(200), nullable=True),
        sa.Column('sst_approval_date', sa.Date(), nullable=True),
        sa.Column('sst_signature', sa.String(255), nullable=True),
        sa.Column('verification_date', sa.Date(), nullable=True),
        sa.Column('verification_method', sa.Text(), nullable=True),
        sa.Column('followup_result', sa.String(30), nullable=True),
        sa.Column('followup_decision', sa.String(30), nullable=True),
        sa.Column('final_observations', sa.Text(), nullable=True),
        sa.Column('plan_status', sa.String(20), nullable=False, server_default='OPEN'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ergonomic_action_plans_id', 'ergonomic_action_plans', ['id'])
    op.create_index('ix_ergonomic_action_plans_worker_id', 'ergonomic_action_plans', ['worker_id'])

    op.create_table(
        'ergonomic_measures',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('plan_id', sa.Integer(), sa.ForeignKey('ergonomic_action_plans.id', ondelete='CASCADE'), nullable=False),
        sa.Column('measure_type', sa.String(40), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('responsible', sa.String(40), nullable=False),
        sa.Column('commitment_date', sa.Date(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='pendiente'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ergonomic_measures_id', 'ergonomic_measures', ['id'])
    op.create_index('ix_ergonomic_measures_plan_id', 'ergonomic_measures', ['plan_id'])


def downgrade() -> None:
    op.drop_index('ix_ergonomic_measures_plan_id', table_name='ergonomic_measures')
    op.drop_index('ix_ergonomic_measures_id', table_name='ergonomic_measures')
    op.drop_table('ergonomic_measures')
    op.drop_index('ix_ergonomic_action_plans_worker_id', table_name='ergonomic_action_plans')
    op.drop_index('ix_ergonomic_action_plans_id', table_name='ergonomic_action_plans')
    op.drop_table('ergonomic_action_plans')
