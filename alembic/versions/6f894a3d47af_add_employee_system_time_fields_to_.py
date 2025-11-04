"""add_employee_system_time_fields_to_attendance

Revision ID: 6f894a3d47af
Revises: e49f5c85d29b
Create Date: 2025-11-01 16:57:42.196933

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6f894a3d47af'
down_revision = 'e49f5c85d29b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add employee system time fields to attendance table
    op.add_column('attendances', sa.Column('employee_system_time', sa.DateTime(), nullable=True))
    op.add_column('attendances', sa.Column('employee_local_time', sa.String(length=50), nullable=True))
    op.add_column('attendances', sa.Column('employee_timezone', sa.String(length=100), nullable=True))


def downgrade() -> None:
    # Remove employee system time fields from attendance table
    op.drop_column('attendances', 'employee_timezone')
    op.drop_column('attendances', 'employee_local_time')
    op.drop_column('attendances', 'employee_system_time')