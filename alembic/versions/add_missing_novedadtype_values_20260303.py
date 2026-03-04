"""Add missing novedadtype values (trabajo_en_casa, cobertura_en_el_exterior)

Revision ID: add_missing_novedadtype_values_20260303
Revises: 4389729ad81a
Create Date: 2026-03-03 17:30:00.000000
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = 'add_missing_novedadtype_values_20260303'
down_revision = '4389729ad81a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add missing enum labels if they don't exist, then ensure column type is novedadtype
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_type t
            JOIN pg_enum e ON t.oid = e.enumtypid
            WHERE t.typname = 'novedadtype' AND e.enumlabel = 'trabajo_en_casa'
        ) THEN
            ALTER TYPE novedadtype ADD VALUE 'trabajo_en_casa';
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM pg_type t
            JOIN pg_enum e ON t.oid = e.enumtypid
            WHERE t.typname = 'novedadtype' AND e.enumlabel = 'cobertura_en_el_exterior'
        ) THEN
            ALTER TYPE novedadtype ADD VALUE 'cobertura_en_el_exterior';
        END IF;
    END$$;
    """)

    # Ensure column 'tipo' is using enum type (if it is currently varchar/text convert it)
    op.execute("""
    DO $$
    DECLARE
        col_type text;
    BEGIN
        SELECT data_type INTO col_type
        FROM information_schema.columns
        WHERE table_name = 'worker_novedades' AND column_name = 'tipo';

        -- If the column is not already of enum type (data_type = 'USER-DEFINED') then cast
        IF col_type IS NULL THEN
            RAISE NOTICE 'column worker_novedades.tipo not found';
        ELSIF col_type != 'USER-DEFINED' THEN
            ALTER TABLE worker_novedades ALTER COLUMN tipo TYPE novedadtype USING tipo::novedadtype;
        END IF;
    END$$;
    """)


def downgrade() -> None:
    # Downgrade: can't remove enum values easily; leave as-is. If column was converted, leave it.
    pass
