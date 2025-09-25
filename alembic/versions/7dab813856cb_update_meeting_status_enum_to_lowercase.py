"""update_meeting_status_enum_to_lowercase

Revision ID: 7dab813856cb
Revises: ed563185f685
Create Date: 2025-09-24 09:15:20.341130

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7dab813856cb'
down_revision = 'ed563185f685'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Cambiar la columna a texto temporalmente
    op.execute("ALTER TABLE committee_meetings ALTER COLUMN status TYPE text")
    
    # Actualizar los valores existentes
    op.execute("UPDATE committee_meetings SET status = 'scheduled' WHERE status = 'SCHEDULED'")
    op.execute("UPDATE committee_meetings SET status = 'in_progress' WHERE status = 'IN_PROGRESS'")
    op.execute("UPDATE committee_meetings SET status = 'completed' WHERE status = 'COMPLETED'")
    op.execute("UPDATE committee_meetings SET status = 'cancelled' WHERE status = 'CANCELLED'")
    op.execute("UPDATE committee_meetings SET status = 'postponed' WHERE status = 'POSTPONED'")
    
    # Eliminar el enum existente y crear uno nuevo con valores en minúsculas
    op.execute("DROP TYPE meetingstatusenum")
    op.execute("CREATE TYPE meetingstatusenum AS ENUM ('scheduled', 'in_progress', 'completed', 'cancelled', 'postponed')")
    op.execute("ALTER TABLE committee_meetings ALTER COLUMN status TYPE meetingstatusenum USING status::meetingstatusenum")


def downgrade() -> None:
    # Cambiar la columna a texto temporalmente
    op.execute("ALTER TABLE committee_meetings ALTER COLUMN status TYPE text")
    
    # Revertir los valores a MAYÚSCULAS
    op.execute("UPDATE committee_meetings SET status = 'SCHEDULED' WHERE status = 'scheduled'")
    op.execute("UPDATE committee_meetings SET status = 'IN_PROGRESS' WHERE status = 'in_progress'")
    op.execute("UPDATE committee_meetings SET status = 'COMPLETED' WHERE status = 'completed'")
    op.execute("UPDATE committee_meetings SET status = 'CANCELLED' WHERE status = 'cancelled'")
    op.execute("UPDATE committee_meetings SET status = 'POSTPONED' WHERE status = 'postponed'")
    
    # Restaurar el enum original con valores en MAYÚSCULAS
    op.execute("DROP TYPE meetingstatusenum")
    op.execute("CREATE TYPE meetingstatusenum AS ENUM ('SCHEDULED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED', 'POSTPONED')")
    op.execute("ALTER TABLE committee_meetings ALTER COLUMN status TYPE meetingstatusenum USING status::meetingstatusenum")