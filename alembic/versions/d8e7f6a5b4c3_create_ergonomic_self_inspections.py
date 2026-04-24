"""create ergonomic_self_inspections

Revision ID: d8e7f6a5b4c3
Revises: c3d4e5f6a7b8
Create Date: 2026-04-23 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = 'd8e7f6a5b4c3'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'ergonomic_self_inspections',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('worker_id', sa.Integer(), nullable=False),
        sa.Column('evaluation_date', sa.Date(), nullable=False),
        sa.Column('month_year', sa.String(length=7), nullable=True),
        sa.Column('modality', sa.String(length=20), nullable=True),
        sa.Column('evaluator_name', sa.String(length=200), nullable=True),
        sa.Column('chair_height_check', sa.Boolean(), nullable=True),
        sa.Column('chair_height_obs', sa.Text(), nullable=True),
        sa.Column('chair_lumbar_check', sa.Boolean(), nullable=True),
        sa.Column('chair_lumbar_obs', sa.Text(), nullable=True),
        sa.Column('chair_armrests_check', sa.Boolean(), nullable=True),
        sa.Column('chair_armrests_obs', sa.Text(), nullable=True),
        sa.Column('chair_condition_check', sa.Boolean(), nullable=True),
        sa.Column('chair_condition_obs', sa.Text(), nullable=True),
        sa.Column('desk_elbows_90_check', sa.Boolean(), nullable=True),
        sa.Column('desk_elbows_90_obs', sa.Text(), nullable=True),
        sa.Column('desk_leg_space_check', sa.Boolean(), nullable=True),
        sa.Column('desk_leg_space_obs', sa.Text(), nullable=True),
        sa.Column('desk_edges_check', sa.Boolean(), nullable=True),
        sa.Column('desk_edges_obs', sa.Text(), nullable=True),
        sa.Column('monitor_eye_level_check', sa.Boolean(), nullable=True),
        sa.Column('monitor_eye_level_obs', sa.Text(), nullable=True),
        sa.Column('monitor_distance_check', sa.Boolean(), nullable=True),
        sa.Column('monitor_distance_obs', sa.Text(), nullable=True),
        sa.Column('monitor_glare_check', sa.Boolean(), nullable=True),
        sa.Column('monitor_glare_obs', sa.Text(), nullable=True),
        sa.Column('laptop_setup_check', sa.Boolean(), nullable=True),
        sa.Column('laptop_setup_obs', sa.Text(), nullable=True),
        sa.Column('keyboard_mouse_level_check', sa.Boolean(), nullable=True),
        sa.Column('keyboard_mouse_level_obs', sa.Text(), nullable=True),
        sa.Column('wrist_rest_check', sa.Boolean(), nullable=True),
        sa.Column('wrist_rest_obs', sa.Text(), nullable=True),
        sa.Column('wrists_neutral_check', sa.Boolean(), nullable=True),
        sa.Column('wrists_neutral_obs', sa.Text(), nullable=True),
        sa.Column('lighting_reflection_check', sa.Boolean(), nullable=True),
        sa.Column('lighting_reflection_obs', sa.Text(), nullable=True),
        sa.Column('feet_on_floor_check', sa.Boolean(), nullable=True),
        sa.Column('feet_on_floor_obs', sa.Text(), nullable=True),
        sa.Column('active_breaks_check', sa.Boolean(), nullable=True),
        sa.Column('active_breaks_obs', sa.Text(), nullable=True),
        sa.Column('no_pain_check', sa.Boolean(), nullable=True),
        sa.Column('no_pain_obs', sa.Text(), nullable=True),
        sa.Column('pain_discomfort', sa.Boolean(), nullable=True),
        sa.Column('pain_region', sa.String(length=120), nullable=True),
        sa.Column('pain_intensity', sa.Integer(), nullable=True),
        sa.Column('report_description', sa.Text(), nullable=True),
        sa.Column('needs_medical_attention', sa.Boolean(), nullable=True),
        sa.Column('worker_signature', sa.String(length=255), nullable=True),
        sa.Column('sst_signature', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('sst_management_data', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['worker_id'], ['workers.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ergonomic_self_inspections_id'), 'ergonomic_self_inspections', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_ergonomic_self_inspections_id'), table_name='ergonomic_self_inspections')
    op.drop_table('ergonomic_self_inspections')

