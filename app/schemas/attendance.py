from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum

# Schemas actualizados para Pydantic V2


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
    course_name: Optional[str] = None
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
    
    # Virtual attendance specific fields
    session_code: Optional[str] = Field(None, max_length=20)
    virtual_session_link: Optional[str] = Field(None, max_length=500)
    device_fingerprint: Optional[str] = Field(None, max_length=255)
    connection_quality: Optional[str] = Field(None, max_length=50)
    minimum_duration_met: bool = False
    facilitator_confirmed: bool = False
    virtual_evidence: Optional[str] = None
    browser_info: Optional[str] = Field(None, max_length=255)
    
    # Employee system time fields
    employee_system_time: Optional[datetime] = None
    employee_local_time: Optional[str] = Field(None, max_length=50)
    employee_timezone: Optional[str] = Field(None, max_length=100)
    
    notes: Optional[str] = None


class AttendanceCreate(AttendanceBase):
    send_notifications: bool = False


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
    
    # Virtual attendance specific fields
    session_code: Optional[str] = Field(None, max_length=20)
    virtual_session_link: Optional[str] = Field(None, max_length=500)
    device_fingerprint: Optional[str] = Field(None, max_length=255)
    connection_quality: Optional[str] = Field(None, max_length=50)
    minimum_duration_met: Optional[bool] = None
    facilitator_confirmed: Optional[bool] = None
    virtual_evidence: Optional[str] = None
    browser_info: Optional[str] = Field(None, max_length=255)
    
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
    course_name: Optional[str] = None
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
    course_name: Optional[str] = None
    total_sessions: int
    attended_sessions: int
    attendance_rate: float
    total_hours: float
    completed_hours: float
    completion_rate: float


class CourseAttendanceSummary(BaseModel):
    course_name: Optional[str] = None
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


# Virtual Attendance Specific Schemas

class VirtualAttendanceCheckIn(BaseModel):
    user_id: int
    course_name: str
    session_date: datetime
    session_code: Optional[str] = None
    virtual_session_link: Optional[str] = None
    device_fingerprint: Optional[str] = None
    browser_info: Optional[str] = None
    ip_address: Optional[str] = None
    # Employee system time fields
    employee_system_time: Optional[datetime] = None
    employee_local_time: Optional[str] = None
    employee_timezone: Optional[str] = None


class VirtualAttendanceCheckOut(BaseModel):
    attendance_id: int
    connection_quality: Optional[str] = None
    virtual_evidence: Optional[str] = None
    notes: Optional[str] = None


class SessionCodeGenerate(BaseModel):
    course_name: str
    session_date: datetime
    valid_duration_minutes: int = 15
    facilitator_id: int


class SessionCodeValidate(BaseModel):
    session_code: str
    user_id: int
    course_name: str
    session_date: datetime


class VirtualAttendanceResponse(BaseModel):
    id: int
    status: str
    message: str
    session_code: Optional[str] = None
    check_in_time: Optional[datetime] = None
    check_out_time: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    minimum_duration_met: bool = False


# Virtual Session Schemas

class VirtualSessionBase(BaseModel):
    course_name: str
    session_date: datetime
    end_date: datetime  # Nueva fecha y hora final de la sesión
    virtual_session_link: str
    session_code: str
    valid_until: datetime
    max_participants: Optional[int] = None
    description: Optional[str] = None
    is_active: bool = True


class VirtualSessionCreate(VirtualSessionBase):
    creator_id: int


class VirtualSessionUpdate(BaseModel):
    course_name: Optional[str] = None
    session_date: Optional[datetime] = None
    end_date: Optional[datetime] = None  # Nueva fecha y hora final de la sesión
    virtual_session_link: Optional[str] = None
    valid_until: Optional[datetime] = None
    max_participants: Optional[int] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class VirtualSessionResponse(VirtualSessionBase):
    id: int
    creator_id: int
    created_at: datetime
    updated_at: datetime
    participants_count: int = 0

    class Config:
        from_attributes = True


class VirtualSessionListResponse(BaseModel):
    id: int
    course_name: str
    session_date: datetime
    end_date: datetime  # Nueva fecha y hora final de la sesión
    virtual_session_link: str
    session_code: str
    valid_until: datetime
    max_participants: Optional[int] = None
    description: Optional[str] = None
    is_active: bool
    creator_id: int
    created_at: datetime
    updated_at: datetime
    participants_count: int = 0
    creator_name: Optional[str] = None

    class Config:
        from_attributes = True