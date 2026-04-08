"""add_missing_worker_novedad_enum_values

Revision ID: 9ab4c6d8e0f1
Revises: f6e7d8c9b0a1
Create Date: 2026-04-08 14:45:00.000000
"""

from alembic import op


revision = "9ab4c6d8e0f1"
down_revision = "f6e7d8c9b0a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_type t
                JOIN pg_namespace n ON n.oid = t.typnamespace
                WHERE t.typname = 'novedadtype'
            ) THEN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_enum e
                    JOIN pg_type t ON t.oid = e.enumtypid
                    WHERE t.typname = 'novedadtype'
                      AND e.enumlabel = 'trabajo_en_casa'
                ) THEN
                    EXECUTE 'ALTER TYPE novedadtype ADD VALUE ''trabajo_en_casa''';
                END IF;

                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_enum e
                    JOIN pg_type t ON t.oid = e.enumtypid
                    WHERE t.typname = 'novedadtype'
                      AND e.enumlabel = 'cobertura_en_el_exterior'
                ) THEN
                    EXECUTE 'ALTER TYPE novedadtype ADD VALUE ''cobertura_en_el_exterior''';
                END IF;
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    pass
