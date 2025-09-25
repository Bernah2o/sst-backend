"""fix_meeting_attendance_column_name

Revision ID: cafe2465b142
Revises: 7dab813856cb
Create Date: 2025-09-24 16:24:11.242809

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cafe2465b142'
down_revision = '7dab813856cb'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Renombrar la columna 'status' a 'attendance_status' en meeting_attendance
    op.alter_column('meeting_attendance', 'status', new_column_name='attendance_status')
    
    # Cambiar el tipo de enum a string y actualizar valores
    op.execute("ALTER TABLE meeting_attendance ALTER COLUMN attendance_status TYPE text")
    
    # Actualizar los valores del enum a strings simples
    op.execute("UPDATE meeting_attendance SET attendance_status = 'present' WHERE attendance_status = 'PRESENT'")
    op.execute("UPDATE meeting_attendance SET attendance_status = 'absent' WHERE attendance_status = 'ABSENT'")
    op.execute("UPDATE meeting_attendance SET attendance_status = 'excused' WHERE attendance_status = 'EXCUSED'")
    op.execute("UPDATE meeting_attendance SET attendance_status = 'late' WHERE attendance_status = 'LATE'")
    
    # Cambiar el tipo a VARCHAR(50)
    op.execute("ALTER TABLE meeting_attendance ALTER COLUMN attendance_status TYPE VARCHAR(50)")


def downgrade() -> None:
    # Revertir el tipo a enum
    op.execute("ALTER TABLE meeting_attendance ALTER COLUMN attendance_status TYPE text")
    
    # Revertir los valores a enum
    op.execute("UPDATE meeting_attendance SET attendance_status = 'PRESENT' WHERE attendance_status = 'present'")
    op.execute("UPDATE meeting_attendance SET attendance_status = 'ABSENT' WHERE attendance_status = 'absent'")
    op.execute("UPDATE meeting_attendance SET attendance_status = 'EXCUSED' WHERE attendance_status = 'excused'")
    op.execute("UPDATE meeting_attendance SET attendance_status = 'LATE' WHERE attendance_status = 'late'")
    
    # Restaurar el tipo enum
    op.execute("ALTER TABLE meeting_attendance ALTER COLUMN attendance_status TYPE attendancestatusenum USING attendance_status::attendancestatusenum")
    
    # Renombrar de vuelta a 'status'
    op.alter_column('meeting_attendance', 'attendance_status', new_column_name='status')