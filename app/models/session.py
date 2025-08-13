from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    Date,
    Boolean,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    session_date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    location = Column(String(255))
    max_capacity = Column(Integer)
    is_active = Column(Boolean, default=True)  # True for active, False for inactive
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    course = relationship("Course", back_populates="sessions")
    attendances = relationship("Attendance", back_populates="session")

    def __repr__(self):
        return f"<Session(id={self.id}, title='{self.title}', course_id={self.course_id})>"

    @property
    def duration_minutes(self) -> int:
        """Calculate session duration in minutes"""
        if self.start_time and self.end_time:
            start_datetime = datetime.combine(datetime.today(), self.start_time)
            end_datetime = datetime.combine(datetime.today(), self.end_time)
            duration = end_datetime - start_datetime
            return int(duration.total_seconds() / 60)
        return 0

    @property
    def is_past(self) -> bool:
        """Check if session is in the past"""
        if self.session_date and self.end_time:
            session_end = datetime.combine(self.session_date, self.end_time)
            return session_end < datetime.now()
        return False

    @property
    def is_current(self) -> bool:
        """Check if session is currently happening"""
        if self.session_date and self.start_time and self.end_time:
            now = datetime.now()
            session_start = datetime.combine(self.session_date, self.start_time)
            session_end = datetime.combine(self.session_date, self.end_time)
            return session_start <= now <= session_end
        return False

    @property
    def attendance_count(self) -> int:
        """Get count of attendances for this session"""
        return len([a for a in self.attendances if a.status in ['present', 'late', 'partial']])