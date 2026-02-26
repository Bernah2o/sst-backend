"""lowercase seguimiento enum values

Revision ID: c5d6e7f809a1
Revises: b4c5d6e7f809
Create Date: 2026-02-26 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c5d6e7f809a1"
down_revision = "b4c5d6e7f809"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # convert enum columns to text so we can modify the values freely
    op.execute("ALTER TABLE seguimientos ALTER COLUMN estado TYPE text")
    op.execute("ALTER TABLE seguimientos ALTER COLUMN valoracion_riesgo TYPE text")

    # update existing records to lowercase
    op.execute(
        "UPDATE seguimientos SET estado = LOWER(estado) WHERE estado IS NOT NULL AND estado != LOWER(estado)"
    )
    op.execute(
        "UPDATE seguimientos SET valoracion_riesgo = LOWER(valoracion_riesgo) "
        "WHERE valoracion_riesgo IS NOT NULL AND valoracion_riesgo != LOWER(valoracion_riesgo)"
    )

    # recreate enum types with lowercase labels; we drop old definitions first
    op.execute("DROP TYPE IF EXISTS estadoseguimiento")
    op.execute("CREATE TYPE estadoseguimiento AS ENUM ('iniciado','terminado')")
    op.execute("DROP TYPE IF EXISTS valoracionriesgo")
    op.execute(
        "CREATE TYPE valoracionriesgo AS ENUM ('bajo','medio','alto','muy_alto')"
    )

    # convert columns back to their enum types using casting
    # note: original enum type was created with name 'estadoseguimiento'
    op.execute(
        "ALTER TABLE seguimientos ALTER COLUMN estado TYPE estadoseguimiento "
        "USING estado::estadoseguimiento"
    )
    op.execute(
        "ALTER TABLE seguimientos ALTER COLUMN valoracion_riesgo TYPE valoracionriesgo "
        "USING valoracion_riesgo::valoracionriesgo"
    )


def downgrade() -> None:
    # downgrade: convert columns back to text, recreate enums with uppercase values,
    # then cast again.  (data will stay lowercase unless user manually uppercases it)
    op.execute("ALTER TABLE seguimientos ALTER COLUMN estado TYPE text")
    op.execute("ALTER TABLE seguimientos ALTER COLUMN valoracion_riesgo TYPE text")

    # recreate original uppercase enums
    op.execute("DROP TYPE IF EXISTS estadoseguimiento")
    op.execute("CREATE TYPE estadoseguimiento AS ENUM ('INICIADO','TERMINADO')")
    op.execute("DROP TYPE IF EXISTS valoracionriesgo")
    op.execute(
        "CREATE TYPE valoracionriesgo AS ENUM ('BAJO','MEDIO','ALTO','MUY_ALTO')"
    )

    # cast columns back to enum (will error if text values not matching)
    op.execute(
        "ALTER TABLE seguimientos ALTER COLUMN estado TYPE estadoseguimiento USING estado::estadoseguimiento"
    )
    op.execute(
        "ALTER TABLE seguimientos ALTER COLUMN valoracion_riesgo TYPE valoracionriesgo USING valoracion_riesgo::valoracionriesgo"
    )
