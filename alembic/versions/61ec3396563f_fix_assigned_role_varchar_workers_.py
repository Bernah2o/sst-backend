"""fix_assigned_role_varchar_workers_contractors

Convierte workers.assigned_role y contractors.assigned_role de ENUM nativo
de PostgreSQL (userrole) a VARCHAR, para que CaseInsensitiveEnumType funcione
correctamente y no rechace valores en minuscula ('employee' vs 'EMPLOYEE').

Revision ID: 61ec3396563f
Revises: f2a3b4c5d6e7
Create Date: 2026-03-24 14:46:07.943403
"""
from alembic import op

revision = '61ec3396563f'
down_revision = 'f2a3b4c5d6e7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Convertir workers.assigned_role de ENUM nativo a VARCHAR
    op.execute(
        "ALTER TABLE workers ALTER COLUMN assigned_role TYPE VARCHAR(50) "
        "USING assigned_role::text"
    )
    # Normalizar a minusculas los valores existentes
    op.execute("UPDATE workers SET assigned_role = LOWER(assigned_role)")

    # Convertir contractors.assigned_role de ENUM nativo a VARCHAR
    op.execute(
        "ALTER TABLE contractors ALTER COLUMN assigned_role TYPE VARCHAR(50) "
        "USING assigned_role::text"
    )
    op.execute("UPDATE contractors SET assigned_role = LOWER(assigned_role)")


def downgrade() -> None:
    op.execute(
        "ALTER TABLE workers ALTER COLUMN assigned_role "
        "TYPE userrole USING assigned_role::userrole"
    )
    op.execute(
        "ALTER TABLE contractors ALTER COLUMN assigned_role "
        "TYPE userrole USING assigned_role::userrole"
    )
