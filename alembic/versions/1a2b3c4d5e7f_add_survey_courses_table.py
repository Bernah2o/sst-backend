"""add_survey_courses_table

Revision ID: 1a2b3c4d5e7f
Revises: f2a3b4c5d6e7

"""

from alembic import op
import sqlalchemy as sa


revision = "1a2b3c4d5e7f"
down_revision = "f2a3b4c5d6e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "survey_courses",
        sa.Column("survey_id", sa.Integer(), sa.ForeignKey("surveys.id"), nullable=False),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("survey_id", "course_id"),
    )
    op.create_index(
        "ix_survey_courses_course_id",
        "survey_courses",
        ["course_id"],
        unique=False,
    )
    op.execute(
        """
        INSERT INTO survey_courses (survey_id, course_id, created_at)
        SELECT id, course_id, NOW()
        FROM surveys
        WHERE course_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_survey_courses_course_id", table_name="survey_courses")
    op.drop_table("survey_courses")
