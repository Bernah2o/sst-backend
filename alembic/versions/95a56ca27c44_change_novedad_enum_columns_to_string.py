"""Change novedad enum columns to string

Revision ID: 95a56ca27c44
Revises: 27da8e52a020
Create Date: 2025-09-28 20:54:25.457710

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '95a56ca27c44'
down_revision = '27da8e52a020'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Change tipo column from enum to string
    op.execute("ALTER TABLE worker_novedades ALTER COLUMN tipo TYPE varchar(50) USING tipo::text")
    
    # Change status column from enum to string  
    op.execute("ALTER TABLE worker_novedades ALTER COLUMN status TYPE varchar(20) USING status::text")


def downgrade() -> None:
    # Revert status column back to enum
    op.execute("ALTER TABLE worker_novedades ALTER COLUMN status TYPE novedadstatus USING status::novedadstatus")
    
    # Revert tipo column back to enum
    op.execute("ALTER TABLE worker_novedades ALTER COLUMN tipo TYPE novedadtype USING tipo::novedadtype")