"""remove_unused_fields_from_course_materials

Revision ID: b70a6d1fef41
Revises: 616d076232d1
Create Date: 2025-08-26 07:07:13.444654

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b70a6d1fef41'
down_revision = '616d076232d1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Remove unused fields from course_materials table
    op.drop_column('course_materials', 'file_path')
    op.drop_column('course_materials', 'file_size')
    op.drop_column('course_materials', 'mime_type')
    op.drop_column('course_materials', 'duration_seconds')


def downgrade() -> None:
    # Add back the removed fields in case of rollback
    op.add_column('course_materials', sa.Column('file_path', sa.String(500), nullable=True))
    op.add_column('course_materials', sa.Column('file_size', sa.Integer(), nullable=True))
    op.add_column('course_materials', sa.Column('mime_type', sa.String(100), nullable=True))
    op.add_column('course_materials', sa.Column('duration_seconds', sa.Integer(), nullable=True))