from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum


class EnrollmentStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    SUSPENDED = "suspended"


# Enrollment Schemas
class EnrollmentBase(BaseModel):
    user_id: int
    course_id: int
    status: EnrollmentStatus = EnrollmentStatus.PENDING
    progress: float = Field(0.0, ge=0.0, le=100.0)
    grade: Optional[float] = Field(None, ge=0.0, le=100.0)
    notes: Optional[str] = None


class EnrollmentCreate(BaseModel):
    user_id: Optional[int] = None
    worker_id: Optional[int] = None  # Support both user_id and worker_id
    course_id: int
    status: EnrollmentStatus = EnrollmentStatus.PENDING
    progress: float = Field(0.0, ge=0.0, le=100.0)
    grade: Optional[float] = Field(None, ge=0.0, le=100.0)
    notes: Optional[str] = None


class EnrollmentUpdate(BaseModel):
    status: Optional[EnrollmentStatus] = None
    progress: Optional[float] = Field(None, ge=0.0, le=100.0)
    grade: Optional[float] = Field(None, ge=0.0, le=100.0)
    notes: Optional[str] = None


class EnrollmentResponse(EnrollmentBase):
    id: int
    enrolled_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    # Nested objects
    user: Optional[dict] = None
    course: Optional[dict] = None

    class Config:
        from_attributes = True


class EnrollmentListResponse(BaseModel):
    enrollments: list[EnrollmentResponse]
    total: int
    page: int
    size: int
    pages: int


# Enrollment Statistics
class EnrollmentStats(BaseModel):
    total_enrollments: int
    active_enrollments: int
    completed_enrollments: int
    pending_enrollments: int
    cancelled_enrollments: int
    suspended_enrollments: int
    completion_rate: float
    average_progress: float
    average_grade: Optional[float] = None


# User Enrollment Summary
class UserEnrollmentSummary(BaseModel):
    user_id: int
    total_enrollments: int
    active_enrollments: int
    completed_enrollments: int
    completion_rate: float
    average_grade: Optional[float] = None
    certificates_earned: int
    last_activity: Optional[datetime] = None


# Course Enrollment Summary
class CourseEnrollmentSummary(BaseModel):
    course_id: int
    course_title: str
    total_enrollments: int
    active_enrollments: int
    completed_enrollments: int
    completion_rate: float
    average_grade: Optional[float] = None
    average_progress: float


# Bulk Enrollment
class BulkEnrollmentCreate(BaseModel):
    user_ids: list[int]
    course_id: int
    status: EnrollmentStatus = EnrollmentStatus.PENDING
    notes: Optional[str] = None


class BulkEnrollmentResponse(BaseModel):
    successful_enrollments: list[EnrollmentResponse]
    failed_enrollments: list[dict]
    total_processed: int
    successful_count: int
    failed_count: int


# Enrollment Progress Update
class EnrollmentProgressUpdate(BaseModel):
    progress: float = Field(..., ge=0.0, le=100.0)
    notes: Optional[str] = None


# Enrollment Completion
class EnrollmentCompletion(BaseModel):
    grade: Optional[float] = Field(None, ge=0.0, le=100.0)
    notes: Optional[str] = None
    completion_date: Optional[datetime] = None