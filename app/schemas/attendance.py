from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum


class AttendanceStatus(str, Enum):
    PRESENT = "present"
    ABSENT = "absent"
    LATE = "late"
    EXCUSED = "excused"
    PARTIAL = "partial"


class AttendanceType(str, Enum):
    IN_PERSON = "in_person"
    VIRTUAL = "virtual"
    HYBRID = "hybrid"
    SELF_PACED = "self_paced"


# Attendance Schemas
class AttendanceBase(BaseModel):
    user_id: int
    course_id: int
    session_date: datetime
    status: AttendanceStatus
    attendance_type: AttendanceType = AttendanceType.IN_PERSON
    check_in_time: Optional[datetime] = None
    check_out_time: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    scheduled_duration_minutes: Optional[int] = None
    completion_percentage: float = 0.0
    location: Optional[str] = Field(None, max_length=255)
    ip_address: Optional[str] = Field(None, max_length=45)
    device_info: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = None


class AttendanceCreate(AttendanceBase):
    pass


class AttendanceUpdate(BaseModel):
    status: Optional[AttendanceStatus] = None
    attendance_type: Optional[AttendanceType] = None
    check_in_time: Optional[datetime] = None
    check_out_time: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    scheduled_duration_minutes: Optional[int] = None
    completion_percentage: Optional[float] = None
    location: Optional[str] = Field(None, max_length=255)
    ip_address: Optional[str] = Field(None, max_length=45)
    device_info: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = None
    verified_by: Optional[int] = None
    verified_at: Optional[datetime] = None


class AttendanceResponse(AttendanceBase):
    id: int
    verified_by: Optional[int] = None
    verified_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    attendance_percentage: float

    class Config:
        from_attributes = True


class UserInfo(BaseModel):
    id: int
    name: str
    email: str

class CourseInfo(BaseModel):
    id: int
    title: str

class AttendanceListResponse(BaseModel):
    id: int
    user_id: int
    course_id: int
    enrollment_id: Optional[int] = None
    session_id: Optional[int] = None
    session_date: datetime
    status: AttendanceStatus
    attendance_type: AttendanceType
    check_in_time: Optional[datetime] = None
    check_out_time: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    scheduled_duration_minutes: Optional[int] = None
    completion_percentage: float
    location: Optional[str] = None
    ip_address: Optional[str] = None
    device_info: Optional[str] = None
    notes: Optional[str] = None
    verified_by: Optional[int] = None
    verified_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    user: Optional[UserInfo] = None
    course: Optional[CourseInfo] = None

    class Config:
        from_attributes = True


# Attendance Summary Schemas
class AttendanceSummary(BaseModel):
    user_id: int
    course_id: int
    total_sessions: int
    attended_sessions: int
    attendance_rate: float
    total_hours: float
    completed_hours: float
    completion_rate: float


class CourseAttendanceSummary(BaseModel):
    course_id: int
    course_title: str
    total_enrolled: int
    total_sessions: int
    average_attendance_rate: float
    average_completion_rate: float


# Bulk Attendance Registration Schemas
class BulkAttendanceCreate(BaseModel):
    course_id: int
    session_id: Optional[int] = None
    session_date: datetime
    user_ids: list[int]
    status: AttendanceStatus = AttendanceStatus.PRESENT
    attendance_type: AttendanceType = AttendanceType.IN_PERSON
    location: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = None
    send_notifications: bool = False


class BulkAttendanceResponse(BaseModel):
    message: str
    created_count: int
    skipped_count: int
    errors: list[str] = []


class AttendanceNotificationData(BaseModel):
    user_name: str
    user_email: str
    course_title: str
    session_title: str
    session_date: str
    session_time: str
    location: Optional[str] = None
    status: str