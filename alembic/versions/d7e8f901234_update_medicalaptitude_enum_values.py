"""update medicalaptitude enum values

Revision ID: d7e8f901234
Revises: c6539913c1ed
Create Date: 2026-02-26 14:30:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d7e8f901234"
down_revision = "c6539913c1ed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # allow free updates by converting column to text
    op.execute(
        "ALTER TABLE occupational_exams ALTER COLUMN medical_aptitude_concept TYPE text"
    )

    # lowercase any existing data (APTO -> apto, etc.)
    op.execute(
        "UPDATE occupational_exams SET medical_aptitude_concept = LOWER(medical_aptitude_concept) "
        "WHERE medical_aptitude_concept IS NOT NULL AND medical_aptitude_concept != LOWER(medical_aptitude_concept)"
    )

    # create new enum with lowercase values and desired name
    op.execute(
        "CREATE TYPE medicalaptitude_enum AS ENUM ('apto','apto_con_recomendaciones','no_apto')"
    )

    # convert column to the new enum
    op.execute(
        "ALTER TABLE occupational_exams ALTER COLUMN medical_aptitude_concept TYPE medicalaptitude_enum "
        "USING medical_aptitude_concept::medicalaptitude_enum"
    )

    # drop the old type if it exists
    op.execute("DROP TYPE IF EXISTS medicalaptitude")


def downgrade() -> None:
    # convert to text
    op.execute(
        "ALTER TABLE occupational_exams ALTER COLUMN medical_aptitude_concept TYPE text"
    )

    # recreate original uppercase enum
    op.execute(
        "CREATE TYPE medicalaptitude AS ENUM ('APTO','APTO_CON_RECOMENDACIONES','NO_APTO')"
    )

    # cast back to old enum
    op.execute(
        "ALTER TABLE occupational_exams ALTER COLUMN medical_aptitude_concept TYPE medicalaptitude "
        "USING medical_aptitude_concept::medicalaptitude"
    )

    # drop the lowercase enum
    op.execute("DROP TYPE IF EXISTS medicalaptitude_enum")
