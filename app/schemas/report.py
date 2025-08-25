from typing import List, Optional, Any, Dict
from datetime import datetime, date
from enum import Enum
from pydantic import BaseModel


class ExportFormat(str, Enum):
    CSV = "csv"
    EXCEL = "excel"
    PDF = "pdf"
    JSON = "json"


class ReportFilters(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    course_id: Optional[int] = None
    user_id: Optional[int] = None
    status: Optional[str] = None
    role: Optional[str] = None


class DashboardStatsResponse(BaseModel):
    total_users: int
    total_courses: int
    total_enrollments: int
    active_enrollments: int
    total_certificates: int
    recent_enrollments: int
    completion_rate: float
    monthly_enrollments: List[Dict[str, Any]]


class CourseReportResponse(BaseModel):
    course_id: int
    course_title: str
    total_enrollments: int
    active_enrollments: int
    completed_enrollments: int
    completion_rate: float
    average_evaluation_score: float
    attendance_rate: float


class UserReportResponse(BaseModel):
    user_id: int
    email: str
    full_name: str
    role: str
    total_enrollments: int
    completed_enrollments: int
    certificates_earned: int
    average_evaluation_score: float
    attendance_rate: float
    created_at: datetime


class AttendanceReportResponse(BaseModel):
    attendance_id: int
    user_id: int
    username: str
    full_name: str
    course_title: str
    date: date
    status: str
    check_in_time: Optional[datetime]
    check_out_time: Optional[datetime]
    notes: Optional[str]


class EvaluationReportResponse(BaseModel):
    evaluation_id: int
    title: str
    course_title: str
    total_responses: int
    average_score: float
    max_score: float
    min_score: float
    pass_rate: float
    max_possible_score: float


class CertificateReportResponse(BaseModel):
    certificate_id: int
    user_id: int
    email: str
    full_name: str
    course_title: str
    certificate_number: str
    issued_at: datetime
    status: str
    verification_code: Optional[str] = None


class TrendDataPoint(BaseModel):
    period: str
    value: int


class AnalyticsTrendsResponse(BaseModel):
    metric: str
    period: str
    start_date: date
    end_date: date
    trends: List[TrendDataPoint]


class CoursePerformanceResponse(BaseModel):
    course_id: int
    course_title: str
    total_enrollments: int
    completed_enrollments: int
    completion_rate: float
    average_evaluation_score: float


class UserPerformanceResponse(BaseModel):
    user_id: int
    username: str
    total_enrollments: int
    completed_courses: int
    completion_rate: float
    average_score: float
    certificates_earned: int


class OccupationalExamReportResponse(BaseModel):
    exam_id: int
    worker_id: int
    worker_name: str
    document_number: str
    position: str
    exam_type: str
    exam_date: date
    next_exam_date: Optional[date]
    periodicity: Optional[str]
    medical_aptitude: str
    examining_doctor: Optional[str]
    medical_center: Optional[str]
    days_until_next_exam: Optional[int]
    is_overdue: bool
    notification_sent: bool