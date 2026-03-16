"""add_survey_template_to_surveys

Revision ID: f2a3b4c5d6e7
Revises: caa7b9e1d2f3

"""

from alembic import op
import sqlalchemy as sa


revision = "f2a3b4c5d6e7"
down_revision = "caa7b9e1d2f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "surveys",
        sa.Column("survey_template", sa.String(50), nullable=True),
    )
    op.create_index(
        "ix_surveys_survey_template",
        "surveys",
        ["survey_template"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_surveys_survey_template", table_name="surveys")
    op.drop_column("surveys", "survey_template")
