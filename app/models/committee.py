"""
SQLAlchemy models for Committee Management System
"""
from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, Date, 
    ForeignKey, Enum, Numeric, CheckConstraint, Index
)
from sqlalchemy.orm import relationship, validates
from sqlalchemy.sql import func
import enum

from app.database import Base

# Enums
class CommitteeTypeEnum(enum.Enum):
    COPASST = "copasst"
    CONVIVENCIA = "convivencia"

class CommitteeRoleEnum(enum.Enum):
    PRESIDENT = "PRESIDENT"
    VICE_PRESIDENT = "VICE_PRESIDENT"
    SECRETARY = "SECRETARY"
    MEMBER = "MEMBER"
    ALTERNATE = "ALTERNATE"

class MeetingStatusEnum(enum.Enum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    POSTPONED = "postponed"

class AttendanceStatusEnum(enum.Enum):
    PRESENT = "present"
    ABSENT = "absent"
    EXCUSED = "excused"
    LATE = "late"

class VotingStatusEnum(enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    CLOSED = "closed"
    CANCELLED = "cancelled"

class VoteChoiceEnum(enum.Enum):
    YES = "yes"
    NO = "no"
    ABSTAIN = "abstain"

class ActivityStatusEnum(enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    OVERDUE = "overdue"

class ActivityPriorityEnum(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class DocumentTypeEnum(enum.Enum):
    MEETING_MINUTES = "meeting_minutes"
    REGULATION = "regulation"
    REPORT = "report"
    INVESTIGATION = "investigation"
    PROCEDURE = "procedure"
    FORM = "form"
    CERTIFICATE = "certificate"
    OTHER = "other"

# Models
class CommitteeType(Base):
    """Tipos de comités disponibles"""
    __tablename__ = "committee_types"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    committees = relationship("Committee", back_populates="committee_type_rel")

class Committee(Base):
    """Comités principales"""
    __tablename__ = "committees"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    committee_type = Column(Enum(CommitteeTypeEnum, values_callable=lambda x: [e.value for e in x]), nullable=False)
    committee_type_id = Column(Integer, ForeignKey("committee_types.id"), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    establishment_date = Column(Date)
    dissolution_date = Column(Date)
    meeting_frequency_days = Column(Integer, default=30)
    quorum_percentage = Column(Numeric(5, 2), default=50.00)
    regulations_document_url = Column(String(500))
    notes = Column(Text)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"))
    
    # Constraints
    __table_args__ = (
        CheckConstraint('quorum_percentage >= 0 AND quorum_percentage <= 100', 
                       name='check_quorum_percentage'),
        CheckConstraint('meeting_frequency_days > 0', 
                       name='check_meeting_frequency'),
        CheckConstraint('dissolution_date IS NULL OR establishment_date IS NULL OR dissolution_date >= establishment_date', 
                       name='check_dissolution_after_establishment'),
        Index('idx_committee_type_active', 'committee_type', 'is_active'),
    )
    
    # Relationships
    committee_type_rel = relationship("CommitteeType", back_populates="committees")
    members = relationship("CommitteeMember", back_populates="committee", cascade="all, delete-orphan")
    meetings = relationship("CommitteeMeeting", back_populates="committee", cascade="all, delete-orphan")
    votings = relationship("CommitteeVoting", back_populates="committee", cascade="all, delete-orphan")
    activities = relationship("CommitteeActivity", back_populates="committee", cascade="all, delete-orphan")
    documents = relationship("CommitteeDocument", back_populates="committee", cascade="all, delete-orphan")
    permissions = relationship("CommitteePermission", back_populates="committee", cascade="all, delete-orphan")

class CommitteeRole(Base):
    """Roles disponibles en los comités"""
    __tablename__ = "committee_roles"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    members = relationship("CommitteeMember", back_populates="role_rel")

class CommitteeMember(Base):
    """Miembros de los comités"""
    __tablename__ = "committee_members"
    
    id = Column(Integer, primary_key=True, index=True)
    committee_id = Column(Integer, ForeignKey("committees.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(Enum(CommitteeRoleEnum, values_callable=lambda x: [e.value for e in x]), nullable=False)
    role_id = Column(Integer, ForeignKey("committee_roles.id"), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date)
    appointment_document_url = Column(String(500))
    notes = Column(Text)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"))
    
    # Constraints
    __table_args__ = (
        CheckConstraint('end_date IS NULL OR end_date >= start_date', 
                       name='check_end_after_start'),
        Index('idx_committee_user_active', 'committee_id', 'user_id', 'is_active'),
        Index('idx_committee_role', 'committee_id', 'role_id'),
    )
    
    # Relationships
    committee = relationship("Committee", back_populates="members")
    user = relationship("User", foreign_keys=[user_id])
    role_rel = relationship("CommitteeRole", back_populates="members")
    meeting_attendances = relationship("MeetingAttendance", back_populates="member")
    votes = relationship("CommitteeVote", back_populates="member", foreign_keys="CommitteeVote.member_id")
    assigned_activities = relationship("CommitteeActivity", back_populates="assigned_member")

class CommitteeMeeting(Base):
    """Reuniones de comités"""
    __tablename__ = "committee_meetings"
    
    id = Column(Integer, primary_key=True, index=True)
    committee_id = Column(Integer, ForeignKey("committees.id"), nullable=False)
    title = Column(String(300), nullable=False)
    description = Column(Text)
    meeting_date = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer)
    location = Column(String(200))
    meeting_type = Column(String(50), default='regular')  # 'regular', 'extraordinary', 'emergency'
    status = Column(String(50), default="scheduled", nullable=False)
    agenda = Column(Text)
    minutes_content = Column(Text)
    minutes_document_url = Column(String(500))
    quorum_achieved = Column(Boolean)
    attendees_count = Column(Integer, default=0)
    notes = Column(Text)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"))
    
    # Constraints
    __table_args__ = (
        CheckConstraint('duration_minutes > 0', name='check_positive_duration'),
        CheckConstraint('attendees_count >= 0', name='check_non_negative_attendees'),
        Index('idx_committee_meeting_date', 'committee_id', 'meeting_date'),
        Index('idx_meeting_status', 'status'),
    )
    
    # Relationships
    committee = relationship("Committee", back_populates="meetings")
    attendances = relationship("MeetingAttendance", back_populates="meeting", cascade="all, delete-orphan")
    votings = relationship("CommitteeVoting", back_populates="meeting")
    activities = relationship("CommitteeActivity", back_populates="meeting")

class MeetingAttendance(Base):
    """Asistencia a reuniones"""
    __tablename__ = "meeting_attendance"
    
    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("committee_meetings.id"), nullable=False)
    member_id = Column(Integer, ForeignKey("committee_members.id"), nullable=False)
    attendance_status = Column(String(50), default="present", nullable=False)
    arrival_time = Column(DateTime)
    departure_time = Column(DateTime)
    excuse_reason = Column(Text)
    notes = Column(Text)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Constraints
    __table_args__ = (
        CheckConstraint('departure_time IS NULL OR arrival_time IS NULL OR departure_time >= arrival_time', 
                       name='check_departure_after_arrival'),
        Index('idx_meeting_member_attendance', 'meeting_id', 'member_id'),
    )
    
    # Relationships
    meeting = relationship("CommitteeMeeting", back_populates="attendances")
    member = relationship("CommitteeMember", back_populates="meeting_attendances")

class CommitteeVoting(Base):
    """Votaciones de comités"""
    __tablename__ = "committee_votings"
    
    id = Column(Integer, primary_key=True, index=True)
    committee_id = Column(Integer, ForeignKey("committees.id"), nullable=False)
    meeting_id = Column(Integer, ForeignKey("committee_meetings.id"))
    title = Column(String(300), nullable=False)
    description = Column(Text)
    voting_type = Column(String(50), default='simple')  # 'simple', 'qualified', 'secret'
    status = Column(String(50), default="draft", nullable=False)
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    requires_quorum = Column(Boolean, default=True, nullable=False)
    minimum_votes_required = Column(Integer)
    allow_abstention = Column(Boolean, default=True, nullable=False)
    is_secret = Column(Boolean, default=False, nullable=False)
    results_summary = Column(Text)
    notes = Column(Text)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"))
    
    # Constraints
    __table_args__ = (
        CheckConstraint('end_date IS NULL OR start_date IS NULL OR end_date >= start_date', 
                       name='check_end_after_start_voting'),
        CheckConstraint('minimum_votes_required IS NULL OR minimum_votes_required > 0', 
                       name='check_positive_minimum_votes'),
        Index('idx_committee_voting_status', 'committee_id', 'status'),
        Index('idx_voting_dates', 'start_date', 'end_date'),
    )
    
    # Relationships
    committee = relationship("Committee", back_populates="votings")
    meeting = relationship("CommitteeMeeting", back_populates="votings")
    votes = relationship("CommitteeVote", back_populates="voting", cascade="all, delete-orphan")

class CommitteeVote(Base):
    """Votos individuales"""
    __tablename__ = "committee_votes"
    
    id = Column(Integer, primary_key=True, index=True)
    voting_id = Column(Integer, ForeignKey("committee_votings.id"), nullable=False)
    member_id = Column(Integer, ForeignKey("committee_members.id"), nullable=False)
    vote_value = Column(String(20), nullable=False)
    vote_date = Column(DateTime, default=func.now(), nullable=False)
    comments = Column(Text)
    is_proxy_vote = Column(Boolean, default=False, nullable=False)
    proxy_member_id = Column(Integer, ForeignKey("committee_members.id"))
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Constraints
    __table_args__ = (
        Index('idx_voting_member_vote', 'voting_id', 'member_id'),
    )
    
    # Relationships
    voting = relationship("CommitteeVoting", back_populates="votes")
    member = relationship("CommitteeMember", back_populates="votes", foreign_keys=[member_id])
    proxy_member = relationship("CommitteeMember", foreign_keys=[proxy_member_id])

class CommitteeActivity(Base):
    """Actividades y seguimiento de comités"""
    __tablename__ = "committee_activities"
    
    id = Column(Integer, primary_key=True, index=True)
    committee_id = Column(Integer, ForeignKey("committees.id"), nullable=False)
    meeting_id = Column(Integer, ForeignKey("committee_meetings.id"))
    title = Column(String(300), nullable=False)
    description = Column(Text)
    activity_type = Column(String(50), default='task')  # 'task', 'investigation', 'report', 'follow_up'
    priority = Column(String(20), default="medium", nullable=False)
    status = Column(String(50), default="pending", nullable=False)
    assigned_to = Column(Integer, ForeignKey("committee_members.id"))
    due_date = Column(Date)
    completion_date = Column(Date)
    progress_percentage = Column(Integer, default=0, nullable=False)
    supporting_document_url = Column(String(500))
    notes = Column(Text)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"))
    
    # Constraints
    __table_args__ = (
        CheckConstraint('progress_percentage >= 0 AND progress_percentage <= 100', 
                       name='check_progress_percentage'),
        CheckConstraint('completion_date IS NULL OR due_date IS NULL OR completion_date >= due_date', 
                       name='check_completion_after_due'),
        Index('idx_committee_activity_status', 'committee_id', 'status'),
        Index('idx_activity_assigned_to', 'assigned_to'),
        Index('idx_activity_due_date', 'due_date'),
    )
    
    # Relationships
    committee = relationship("Committee", back_populates="activities")
    meeting = relationship("CommitteeMeeting", back_populates="activities")
    assigned_member = relationship("CommitteeMember", back_populates="assigned_activities")

class CommitteeDocument(Base):
    """Documentos de comités"""
    __tablename__ = "committee_documents"
    
    id = Column(Integer, primary_key=True, index=True)
    committee_id = Column(Integer, ForeignKey("committees.id"), nullable=False)
    title = Column(String(300), nullable=False)
    description = Column(Text)
    document_type = Column(String(50), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer)
    mime_type = Column(String(100))
    version = Column(String(20), default='1.0')
    is_public = Column(Boolean, default=False, nullable=False)
    download_count = Column(Integer, default=0, nullable=False)
    tags = Column(String(500))  # JSON or comma-separated tags
    expiry_date = Column(Date)
    notes = Column(Text)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    uploaded_by = Column(Integer, ForeignKey("users.id"))
    
    # Constraints
    __table_args__ = (
        CheckConstraint('file_size IS NULL OR file_size > 0', name='check_positive_file_size'),
        CheckConstraint('download_count >= 0', name='check_non_negative_downloads'),
        Index('idx_committee_document_type', 'committee_id', 'document_type'),
        Index('idx_document_public', 'is_public'),
    )
    
    # Relationships
    committee = relationship("Committee", back_populates="documents")

class CommitteePermission(Base):
    """Permisos de comités"""
    __tablename__ = "committee_permissions"
    
    id = Column(Integer, primary_key=True, index=True)
    committee_id = Column(Integer, ForeignKey("committees.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    permission_type = Column(String(50), nullable=False)  # 'view', 'edit', 'admin', 'vote', 'upload_documents'
    granted_by = Column(Integer, ForeignKey("users.id"))
    granted_at = Column(DateTime, default=func.now(), nullable=False)
    expires_at = Column(DateTime)
    is_active = Column(Boolean, default=True, nullable=False)
    notes = Column(Text)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Constraints
    __table_args__ = (
        CheckConstraint('expires_at IS NULL OR expires_at > granted_at', 
                       name='check_expiry_after_granted'),
        Index('idx_committee_user_permission', 'committee_id', 'user_id', 'permission_type'),
        Index('idx_permission_active', 'is_active'),
    )
    
    # Relationships
    committee = relationship("Committee", back_populates="permissions")