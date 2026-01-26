"""update vacation_balances indexes (remove year uniqueness)

Revision ID: 1628902c0728
Revises: 9ea839e74703
Create Date: 2025-12-01 15:21:14.421801

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '1628902c0728'
down_revision = '9ea839e74703'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Eliminar constraint único compuesto si existe (idempotente)
    conn = op.get_bind()
    result = conn.execute(sa.text("""
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'uq_vacation_balances_worker_year'
        AND table_name = 'vacation_balances'
    """)).fetchone()

    if result:
        op.drop_constraint(
            'uq_vacation_balances_worker_year',
            'vacation_balances',
            type_='unique'
        )

    # Eliminar índice único sobre worker_id si existe
    op.execute('DROP INDEX IF EXISTS ix_vacation_balances_worker_id')

    # Crear índices NO únicos para mejorar consultas (idempotente)
    op.execute('''
        CREATE INDEX IF NOT EXISTS ix_vacation_balances_worker_id_nonunique
        ON vacation_balances (worker_id)
    ''')
    op.execute('''
        CREATE INDEX IF NOT EXISTS ix_vacation_balances_year_nonunique
        ON vacation_balances (year)
    ''')


def downgrade() -> None:
    # Revertir a estado anterior: eliminar índices no únicos
    op.drop_index('ix_vacation_balances_year_nonunique', table_name='vacation_balances')
    op.drop_index('ix_vacation_balances_worker_id_nonunique', table_name='vacation_balances')

    # Restaurar el índice único sobre worker_id (comportamiento previo)
    op.create_index(
        'ix_vacation_balances_worker_id',
        'vacation_balances',
        ['worker_id'],
        unique=True
    )