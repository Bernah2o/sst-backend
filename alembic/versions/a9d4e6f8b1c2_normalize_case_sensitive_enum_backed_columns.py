"""normalize_case_sensitive_enum_backed_columns

Revision ID: a9d4e6f8b1c2
Revises: 90d76a10d060
Create Date: 2026-03-26 13:40:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "a9d4e6f8b1c2"
down_revision = "90d76a10d060"
branch_labels = None
depends_on = None


def _column_exists(conn, table_name: str, column_name: str) -> bool:
    result = conn.execute(
        sa.text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = :table_name
              AND column_name = :column_name
            """
        ),
        {"table_name": table_name, "column_name": column_name},
    ).fetchone()
    return result is not None


def _normalize_to_varchar_lower(table_name: str, column_name: str, length: int) -> None:
    op.execute(
        sa.text(
            f'ALTER TABLE "{table_name}" ALTER COLUMN "{column_name}" TYPE VARCHAR({length}) USING "{column_name}"::text'
        )
    )
    op.execute(
        sa.text(
            f'UPDATE "{table_name}" SET "{column_name}" = LOWER(BTRIM("{column_name}")) WHERE "{column_name}" IS NOT NULL'
        )
    )


def _enum_exists(conn, enum_name: str) -> bool:
    result = conn.execute(
        sa.text(
            """
            SELECT 1
            FROM pg_type
            WHERE typname = :enum_name
            """
        ),
        {"enum_name": enum_name},
    ).fetchone()
    return result is not None


def _enum_is_in_use(conn, enum_name: str) -> bool:
    result = conn.execute(
        sa.text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND udt_name = :enum_name
            LIMIT 1
            """
        ),
        {"enum_name": enum_name},
    ).fetchone()
    return result is not None


def upgrade() -> None:
    conn = op.get_bind()

    if _column_exists(conn, "users", "role"):
        _normalize_to_varchar_lower("users", "role", 50)
        op.execute(sa.text("ALTER TABLE users ALTER COLUMN role SET DEFAULT 'employee'"))

    if _column_exists(conn, "workers", "assigned_role"):
        _normalize_to_varchar_lower("workers", "assigned_role", 50)
        op.execute(sa.text("ALTER TABLE workers ALTER COLUMN assigned_role SET DEFAULT 'employee'"))

    if _column_exists(conn, "contractors", "assigned_role"):
        _normalize_to_varchar_lower("contractors", "assigned_role", 50)
        op.execute(sa.text("ALTER TABLE contractors ALTER COLUMN assigned_role SET DEFAULT 'employee'"))

    if _column_exists(conn, "interactive_lessons", "navigation_type"):
        _normalize_to_varchar_lower("interactive_lessons", "navigation_type", 20)
        op.execute(
            sa.text(
                "ALTER TABLE interactive_lessons ALTER COLUMN navigation_type SET DEFAULT 'sequential'"
            )
        )

    if _column_exists(conn, "interactive_lessons", "status"):
        _normalize_to_varchar_lower("interactive_lessons", "status", 20)
        op.execute(
            sa.text(
                "ALTER TABLE interactive_lessons ALTER COLUMN status SET DEFAULT 'draft'"
            )
        )

    if _column_exists(conn, "lesson_slides", "slide_type"):
        _normalize_to_varchar_lower("lesson_slides", "slide_type", 30)

    if _enum_exists(conn, "cloophva") and not _enum_is_in_use(conn, "cloophva"):
        op.execute(sa.text("DROP TYPE cloophva"))


def downgrade() -> None:
    pass
