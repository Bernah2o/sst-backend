"""add_response_date_to_user_surveys

Revision ID: caa7b9e1d2f3
Revises: 756dfa14a956

"""

from alembic import op
import sqlalchemy as sa


revision = "caa7b9e1d2f3"
down_revision = "756dfa14a956"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_surveys", sa.Column("response_date", sa.Date(), nullable=True))
    op.create_index(
        "ix_user_surveys_response_date",
        "user_surveys",
        ["response_date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_user_surveys_response_date", table_name="user_surveys")
    op.drop_column("user_surveys", "response_date")

