from typing import Any, List, Dict
from datetime import datetime, date, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, extract
import os

from app.dependencies import get_current_active_user
from app.database import get_db
from app.models.user import User, UserRole
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.evaluation import Evaluation, UserEvaluation, Question
from app.models.attendance import Attendance
from app.models.certificate import Certificate
from app.models.worker import Worker
from app.models.occupational_exam import OccupationalExam, ExamType
from app.models.admin_config import AdminConfig
from app.models.notification import Notification, NotificationType, NotificationStatus, NotificationPriority
from app.schemas.report import (
    CourseReportResponse, UserReportResponse, AttendanceReportResponse,
    EvaluationReportResponse, CertificateReportResponse, DashboardStatsResponse,
    ReportFilters, ExportFormat, OccupationalExamReportResponse
)
from app.schemas.common import MessageResponse, PaginatedResponse

router = APIRouter()


@router.get("/dashboard{trailing_slash:path}", response_model=DashboardStatsResponse)
async def get_dashboard_stats(
    trailing_slash: str = "",
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get dashboard statistics
    """
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # Get basic counts
    total_users = db.query(User).count()
    total_courses = db.query(Course).count()
    total_enrollments = db.query(Enrollment).count()
    total_certificates = db.query(Certificate).count()
    
    # Get active enrollments (not completed)
    active_enrollments = db.query(Enrollment).filter(
        Enrollment.status != "completed"
    ).count()
    
    # Get recent enrollments (last 30 days)
    thirty_days_ago = datetime.now() - timedelta(days=30)
    recent_enrollments = db.query(Enrollment).filter(
        Enrollment.enrolled_at >= thirty_days_ago
    ).count()
    
    # Get completion rate
    completed_enrollments = db.query(Enrollment).filter(
        Enrollment.status == "completed"
    ).count()
    
    completion_rate = 0
    if total_enrollments > 0:
        completion_rate = (completed_enrollments / total_enrollments) * 100
    
    # Get monthly enrollment trends (last 6 months)
    monthly_enrollments = []
    for i in range(6):
        month_start = datetime.now().replace(day=1) - timedelta(days=30*i)
        month_end = month_start.replace(day=28) + timedelta(days=4)
        month_end = month_end - timedelta(days=month_end.day)
        
        count = db.query(Enrollment).filter(
            and_(
                Enrollment.enrolled_at >= month_start,
                Enrollment.enrolled_at <= month_end
            )
        ).count()
        
        monthly_enrollments.append({
            "month": month_start.strftime("%Y-%m"),
            "count": count
        })
    
    monthly_enrollments.reverse()
    
    return DashboardStatsResponse(
        total_users=total_users,
        total_courses=total_courses,
        total_enrollments=total_enrollments,
        active_enrollments=active_enrollments,
        total_certificates=total_certificates,
        recent_enrollments=recent_enrollments,
        completion_rate=completion_rate,
        monthly_enrollments=monthly_enrollments
    )


@router.get("/courses{trailing_slash:path}", response_model=PaginatedResponse[CourseReportResponse])
async def get_course_reports(
    trailing_slash: str = "",
    skip: int = 0,
    limit: int = 100,
    course_id: int = None,
    start_date: date = None,
    end_date: date = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get course reports
    """
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    query = db.query(Course)
    
    # Apply filters
    if course_id:
        query = query.filter(Course.id == course_id)
    
    if start_date:
        query = query.filter(Course.created_at >= start_date)
    
    if end_date:
        query = query.filter(Course.created_at <= end_date)
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    courses = query.offset(skip).limit(limit).all()
    
    # Build report data
    course_reports = []
    for course in courses:
        # Get enrollment statistics
        total_enrollments = db.query(Enrollment).filter(
            Enrollment.course_id == course.id
        ).count()
        
        active_enrollments = db.query(Enrollment).filter(
            and_(
                Enrollment.course_id == course.id,
                Enrollment.status == "active"
            )
        ).count()
        
        completed_enrollments = db.query(Enrollment).filter(
            and_(
                Enrollment.course_id == course.id,
                Enrollment.status == "completed"
            )
        ).count()
        
        # Get average evaluation score
        avg_score = db.query(func.avg(UserEvaluation.score)).join(
            Evaluation
        ).filter(
            Evaluation.course_id == course.id
        ).scalar() or 0
        
        # Get attendance rate
        total_attendance_records = db.query(Attendance).join(
            Enrollment
        ).filter(
            Enrollment.course_id == course.id
        ).count()
        
        present_records = db.query(Attendance).join(
            Enrollment
        ).filter(
            and_(
                Enrollment.course_id == course.id,
                Attendance.status == "present"
            )
        ).count()
        
        attendance_rate = 0
        if total_attendance_records > 0:
            attendance_rate = (present_records / total_attendance_records) * 100
        
        course_reports.append(CourseReportResponse(
            course_id=course.id,
            course_title=course.title,
            total_enrollments=total_enrollments,
            active_enrollments=active_enrollments,
            completed_enrollments=completed_enrollments,
            completion_rate=(completed_enrollments / total_enrollments * 100) if total_enrollments > 0 else 0,
            average_evaluation_score=round(avg_score, 2),
            attendance_rate=round(attendance_rate, 2)
        ))
    
    # Calculate pagination info
    page = (skip // limit) + 1 if limit > 0 else 1
    pages = (total + limit - 1) // limit if limit > 0 else 1
    has_next = skip + limit < total
    has_prev = skip > 0
    
    return PaginatedResponse(
        items=course_reports,
        total=total,
        page=page,
        size=limit,
        pages=pages,
        has_next=has_next,
        has_prev=has_prev
    )


@router.get("/users{trailing_slash:path}", response_model=PaginatedResponse[UserReportResponse])
async def get_user_reports(
    trailing_slash: str = "",
    skip: int = 0,
    limit: int = 100,
    user_id: int = None,
    role: str = None,
    start_date: date = None,
    end_date: date = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get user reports
    """
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    query = db.query(User)
    
    # Apply filters
    if user_id:
        query = query.filter(User.id == user_id)
    
    if role:
        query = query.filter(User.role == role)
    
    if start_date:
        query = query.filter(User.created_at >= start_date)
    
    if end_date:
        query = query.filter(User.created_at <= end_date)
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    users = query.offset(skip).limit(limit).all()
    
    # Build report data
    user_reports = []
    for user in users:
        # Get enrollment statistics
        total_enrollments = db.query(Enrollment).filter(
            Enrollment.user_id == user.id
        ).count()
        
        completed_courses = db.query(Enrollment).filter(
            and_(
                Enrollment.user_id == user.id,
                Enrollment.status == "completed"
            )
        ).count()
        
        # Get certificates earned
        certificates_earned = db.query(Certificate).filter(
            Certificate.user_id == user.id
        ).count()
        
        # Get average evaluation score
        avg_score = db.query(func.avg(UserEvaluation.score)).filter(
            UserEvaluation.user_id == user.id
        ).scalar() or 0
        
        # Get attendance rate
        total_attendance = db.query(Attendance).filter(
            Attendance.user_id == user.id
        ).count()
        
        present_attendance = db.query(Attendance).filter(
            and_(
                Attendance.user_id == user.id,
                Attendance.status == "present"
            )
        ).count()
        
        attendance_rate = 0
        if total_attendance > 0:
            attendance_rate = (present_attendance / total_attendance) * 100
        
        user_reports.append(UserReportResponse(
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role.value,
            total_enrollments=total_enrollments,
            completed_enrollments=completed_courses,
            certificates_earned=certificates_earned,
            average_evaluation_score=round(avg_score, 2),
            attendance_rate=round(attendance_rate, 2),
            created_at=user.created_at
        ))
    
    # Calculate pagination info
    page = (skip // limit) + 1 if limit > 0 else 1
    pages = (total + limit - 1) // limit if limit > 0 else 1
    has_next = skip + limit < total
    has_prev = skip > 0
    
    return PaginatedResponse(
        items=user_reports,
        total=total,
        page=page,
        size=limit,
        pages=pages,
        has_next=has_next,
        has_prev=has_prev
    )


@router.get("/attendance{trailing_slash:path}", response_model=PaginatedResponse[AttendanceReportResponse])
async def get_attendance_reports(
    trailing_slash: str = "",
    skip: int = 0,
    limit: int = 100,
    course_id: int = None,
    user_id: int = None,
    start_date: date = None,
    end_date: date = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get attendance reports
    """
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # Build query with joins
    query = db.query(
        Attendance,
        User.username,
        User.first_name,
        User.last_name,
        Course.title.label('course_title')
    ).join(
        User, Attendance.user_id == User.id
    ).join(
        Enrollment, Attendance.enrollment_id == Enrollment.id
    ).join(
        Course, Enrollment.course_id == Course.id
    )
    
    # Apply filters
    if course_id:
        query = query.filter(Course.id == course_id)
    
    if user_id:
        query = query.filter(User.id == user_id)
    
    if start_date:
        query = query.filter(func.date(Attendance.session_date) >= start_date)
    
    if end_date:
        query = query.filter(func.date(Attendance.session_date) <= end_date)
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    attendance_records = query.offset(skip).limit(limit).all()
    
    # Build report data
    attendance_reports = []
    for record in attendance_records:
        attendance, username, first_name, last_name, course_title = record
        full_name = f"{first_name} {last_name}"
        
        attendance_reports.append(AttendanceReportResponse(
            attendance_id=attendance.id,
            user_id=attendance.user_id,
            username=username,
            full_name=full_name,
            course_title=course_title,
            date=attendance.session_date.date() if attendance.session_date else None,
            status=attendance.status.value,
            check_in_time=attendance.check_in_time,
            check_out_time=attendance.check_out_time,
            notes=attendance.notes
        ))
    
    # Calculate pagination info
    page = (skip // limit) + 1 if limit > 0 else 1
    pages = (total + limit - 1) // limit if limit > 0 else 1
    has_next = skip + limit < total
    has_prev = skip > 0
    
    return PaginatedResponse(
        items=attendance_reports,
        total=total,
        page=page,
        size=limit,
        pages=pages,
        has_next=has_next,
        has_prev=has_prev
    )


@router.get("/evaluations", response_model=PaginatedResponse[EvaluationReportResponse])
async def get_evaluation_reports(
    skip: int = 0,
    limit: int = 100,
    course_id: int = None,
    evaluation_id: int = None,
    start_date: date = None,
    end_date: date = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get evaluation reports
    """
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    query = db.query(Evaluation).join(Course)
    
    # Apply filters
    if course_id:
        query = query.filter(Course.id == course_id)
    
    if evaluation_id:
        query = query.filter(Evaluation.id == evaluation_id)
    
    if start_date:
        query = query.filter(Evaluation.created_at >= start_date)
    
    if end_date:
        query = query.filter(Evaluation.created_at <= end_date)
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    evaluations = query.offset(skip).limit(limit).all()
    
    # Build report data
    evaluation_reports = []
    for evaluation in evaluations:
        # Get response statistics
        total_responses = db.query(UserEvaluation).filter(
            UserEvaluation.evaluation_id == evaluation.id
        ).count()
        
        avg_score = db.query(func.avg(UserEvaluation.score)).filter(
            UserEvaluation.evaluation_id == evaluation.id
        ).scalar() or 0
        
        max_score = db.query(func.max(UserEvaluation.score)).filter(
            UserEvaluation.evaluation_id == evaluation.id
        ).scalar() or 0
        
        min_score = db.query(func.min(UserEvaluation.score)).filter(
            UserEvaluation.evaluation_id == evaluation.id
        ).scalar() or 0
        
        # Calculate max possible score from questions
        max_possible_score = db.query(func.sum(Question.points)).filter(
            Question.evaluation_id == evaluation.id
        ).scalar() or 0
        
        # Get pass rate (using evaluation's passing_score)
        passed_responses = db.query(UserEvaluation).filter(
            and_(
                UserEvaluation.evaluation_id == evaluation.id,
                UserEvaluation.score >= evaluation.passing_score
            )
        ).count()
        
        pass_rate = 0
        if total_responses > 0:
            pass_rate = (passed_responses / total_responses) * 100
        
        evaluation_reports.append(EvaluationReportResponse(
            evaluation_id=evaluation.id,
            title=evaluation.title,
            course_title=evaluation.course.title,
            total_responses=total_responses,
            average_score=round(avg_score, 2),
            max_score=max_score,
            min_score=min_score,
            pass_rate=round(pass_rate, 2),
            max_possible_score=max_possible_score
        ))
    
    # Calculate pagination info
    page = (skip // limit) + 1 if limit > 0 else 1
    pages = (total + limit - 1) // limit if limit > 0 else 1
    has_next = skip + limit < total
    has_prev = skip > 0
    
    return PaginatedResponse(
        items=evaluation_reports,
        total=total,
        page=page,
        size=limit,
        pages=pages,
        has_next=has_next,
        has_prev=has_prev
    )


@router.get("/certificates", response_model=PaginatedResponse[CertificateReportResponse])
async def get_certificate_reports(
    skip: int = 0,
    limit: int = 100,
    course_id: int = None,
    user_id: int = None,
    status: str = None,
    start_date: date = None,
    end_date: date = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get certificate reports
    """
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # Build query with joins
    query = db.query(
        Certificate,
        User.email,
        User.first_name,
        User.last_name,
        Course.title.label('course_title')
    ).join(
        User, Certificate.user_id == User.id
    ).join(
        Course, Certificate.course_id == Course.id
    )
    
    # Apply filters
    if course_id:
        query = query.filter(Course.id == course_id)
    
    if user_id:
        query = query.filter(User.id == user_id)
    
    if status:
        query = query.filter(Certificate.status == status)
    
    if start_date:
        query = query.filter(Certificate.issue_date >= start_date)
    
    if end_date:
        query = query.filter(Certificate.issue_date <= end_date)
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    certificate_records = query.offset(skip).limit(limit).all()
    
    # Build report data
    certificate_reports = []
    for record in certificate_records:
        certificate, email, first_name, last_name, course_title = record
        full_name = f"{first_name} {last_name}"
        
        certificate_reports.append(CertificateReportResponse(
            certificate_id=certificate.id,
            user_id=certificate.user_id,
            email=email,
            full_name=full_name,
            course_title=course_title,
            certificate_number=certificate.certificate_number,
            issued_at=certificate.issue_date,
            status=certificate.status.value,
            verification_code=certificate.verification_code
        ))
    
    # Calculate pagination info
    page = (skip // limit) + 1 if limit > 0 else 1
    pages = (total + limit - 1) // limit if limit > 0 else 1
    has_next = skip + limit < total
    has_prev = skip > 0
    
    return PaginatedResponse(
        items=certificate_reports,
        total=total,
        page=page,
        size=limit,
        pages=pages,
        has_next=has_next,
        has_prev=has_prev
    )


@router.post("/export")
async def export_report(
    report_type: str = Query(..., description="Type of report to export"),
    format: ExportFormat = Query(ExportFormat.CSV, description="Export format"),
    filters: ReportFilters = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Export report data
    """
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # This would typically generate and return a file
    # For now, return a message indicating the export request
    return MessageResponse(
        message=f"Export request for {report_type} report in {format.value} format has been queued"
    )


@router.get("/analytics/trends")
async def get_analytics_trends(
    period: str = Query("monthly", description="Period for trends (daily, weekly, monthly)"),
    metric: str = Query("enrollments", description="Metric to analyze"),
    start_date: date = None,
    end_date: date = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get analytics trends
    """
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # Set default date range if not provided
    if not end_date:
        end_date = date.today()
    
    if not start_date:
        if period == "daily":
            start_date = end_date - timedelta(days=30)
        elif period == "weekly":
            start_date = end_date - timedelta(weeks=12)
        else:  # monthly
            start_date = end_date - timedelta(days=365)
    
    trends = []
    
    if metric == "enrollments":
        # Get enrollment trends
        if period == "monthly":
            # Group by month
            results = db.query(
                extract('year', Enrollment.enrolled_at).label('year'),
                extract('month', Enrollment.enrolled_at).label('month'),
                func.count(Enrollment.id).label('count')
            ).filter(
                and_(
                    Enrollment.enrolled_at >= start_date,
                    Enrollment.enrolled_at <= end_date
                )
            ).group_by(
                extract('year', Enrollment.enrolled_at),
                extract('month', Enrollment.enrolled_at)
            ).all()
            
            for result in results:
                trends.append({
                    "period": f"{int(result.year)}-{int(result.month):02d}",
                    "value": result.count
                })
    
    return {
        "metric": metric,
        "period": period,
        "start_date": start_date,
        "end_date": end_date,
        "trends": trends
    }


@router.get("/analytics/performance")
async def get_performance_analytics(
    course_id: int = None,
    user_id: int = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get performance analytics
    """
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    analytics = {}
    
    if course_id:
        # Course performance analytics
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Course not found"
            )
        
        # Get course statistics
        total_enrollments = db.query(Enrollment).filter(
            Enrollment.course_id == course_id
        ).count()
        
        completed_enrollments = db.query(Enrollment).filter(
            and_(
                Enrollment.course_id == course_id,
                Enrollment.status == "completed"
            )
        ).count()
        
        avg_evaluation_score = db.query(func.avg(UserEvaluation.score)).join(
        Evaluation
    ).filter(
        Evaluation.course_id == course_id
    ).scalar() or 0
        
        analytics = {
            "course_id": course_id,
            "course_title": course.title,
            "total_enrollments": total_enrollments,
            "completed_enrollments": completed_enrollments,
            "completion_rate": (completed_enrollments / total_enrollments * 100) if total_enrollments > 0 else 0,
            "average_evaluation_score": round(avg_evaluation_score, 2)
        }
    
    elif user_id:
        # User performance analytics
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Get user statistics
        total_enrollments = db.query(Enrollment).filter(
            Enrollment.user_id == user_id
        ).count()
        
        completed_courses = db.query(Enrollment).filter(
            and_(
                Enrollment.user_id == user_id,
                Enrollment.status == "completed"
            )
        ).count()
        
        avg_score = db.query(func.avg(UserEvaluation.score)).filter(
            UserEvaluation.user_id == user_id
        ).scalar() or 0
        
        certificates_earned = db.query(Certificate).filter(
            Certificate.user_id == user_id
        ).count()
        
        analytics = {
            "user_id": user_id,
            "email": user.email,
            "total_enrollments": total_enrollments,
            "completed_courses": completed_courses,
            "completion_rate": (completed_courses / total_enrollments * 100) if total_enrollments > 0 else 0,
            "average_score": round(avg_score, 2),
            "certificates_earned": certificates_earned
        }
    
    return analytics


@router.get("/evaluation-ranking")
async def get_evaluation_ranking(
    limit: int = Query(10, description="Number of top performers to return"),
    course_id: int = Query(None, description="Filter by specific course"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get ranking of employees by evaluation performance
    """
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # Base query for evaluation responses with user and course info
    query = db.query(
        User.id.label('user_id'),
        User.email,
        User.first_name,
        User.last_name,
        Course.title.label('course_title'),
        func.avg(UserEvaluation.score).label('average_score'),
        func.count(UserEvaluation.id).label('total_evaluations')
    ).join(
        UserEvaluation, User.id == UserEvaluation.user_id
    ).join(
        Evaluation, UserEvaluation.evaluation_id == Evaluation.id
    ).join(
        Course, Evaluation.course_id == Course.id
    ).filter(
        User.role == UserRole.EMPLOYEE
    )
    
    # Filter by course if specified
    if course_id:
        query = query.filter(Course.id == course_id)
    
    # Group by user and course, order by average score
    results = query.group_by(
        User.id, User.email, User.first_name, User.last_name, Course.title
    ).order_by(
        func.avg(UserEvaluation.score).desc()
    ).limit(limit).all()
    
    ranking = []
    for i, result in enumerate(results, 1):
        ranking.append({
            "rank": i,
            "user_id": result.user_id,
            "email": result.email,
            "full_name": f"{result.first_name} {result.last_name}",
            "course_title": result.course_title,
            "average_score": round(result.average_score, 2),
            "total_evaluations": result.total_evaluations
        })
    
    return {
        "ranking": ranking,
        "total_entries": len(ranking),
        "course_filter": course_id
    }


@router.get("/occupational-exams", response_model=PaginatedResponse[OccupationalExamReportResponse])
async def get_occupational_exam_reports(
    skip: int = 0,
    limit: int = 100,
    worker_id: int = None,
    exam_type: str = None,
    start_date: date = None,
    end_date: date = None,
    overdue_only: bool = False,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get occupational exam reports with next exam date calculations
    """
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # Base query joining occupational exams with workers
    query = db.query(OccupationalExam).join(Worker)
    
    # Apply filters
    if worker_id:
        query = query.filter(OccupationalExam.worker_id == worker_id)
    
    if exam_type:
        query = query.filter(OccupationalExam.exam_type == exam_type)
    
    if start_date:
        query = query.filter(OccupationalExam.exam_date >= start_date)
    
    if end_date:
        query = query.filter(OccupationalExam.exam_date <= end_date)
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    exams = query.offset(skip).limit(limit).all()
    
    # Build report data with next exam calculations
    exam_reports = []
    today = date.today()
    
    for exam in exams:
        worker = exam.worker
        
        # Get position configuration to determine periodicity
        position_config = db.query(AdminConfig).filter(
            and_(
                AdminConfig.category == "position",
                AdminConfig.display_name == worker.position,
                AdminConfig.is_active == True
            )
        ).first()
        
        periodicity = position_config.emo_periodicity if position_config else None
        next_exam_date = None
        days_until_next_exam = None
        is_overdue = False
        
        # Calculate next exam date based on periodicity
        # For INGRESO exams, calculate when the first PERIODICO exam should be
        # For PERIODICO exams, calculate the next PERIODICO exam
        if periodicity and (exam.exam_type == ExamType.PERIODICO or exam.exam_type == ExamType.INGRESO):
            if periodicity == "anual":
                # Add exactly one year to the exam date
                try:
                    next_exam_date = exam.exam_date.replace(year=exam.exam_date.year + 1)
                except ValueError:
                    # Handle leap year edge case (Feb 29)
                    next_exam_date = exam.exam_date.replace(year=exam.exam_date.year + 1, month=2, day=28)
            elif periodicity == "semestral":
                # Add 6 months
                month = exam.exam_date.month + 6
                year = exam.exam_date.year
                if month > 12:
                    month -= 12
                    year += 1
                try:
                    next_exam_date = date(year, month, exam.exam_date.day)
                except ValueError:
                    # Handle month with fewer days (e.g., Jan 31 + 6 months = Jul 31, but if it was Jan 31 -> Jul 31 is fine, but Jan 31 -> Jun 31 doesn't exist)
                    import calendar
                    last_day = calendar.monthrange(year, month)[1]
                    next_exam_date = date(year, month, min(exam.exam_date.day, last_day))
            elif periodicity == "trimestral":
                # Add 3 months
                month = exam.exam_date.month + 3
                year = exam.exam_date.year
                if month > 12:
                    month -= 12
                    year += 1
                try:
                    next_exam_date = date(year, month, exam.exam_date.day)
                except ValueError:
                    # Handle month with fewer days
                    import calendar
                    last_day = calendar.monthrange(year, month)[1]
                    next_exam_date = date(year, month, min(exam.exam_date.day, last_day))
        
        # Calculate days until next exam and check if overdue
        if next_exam_date:
            days_until_next_exam = (next_exam_date - today).days
            is_overdue = days_until_next_exam < 0
        
        # Skip if filtering for overdue only and this exam is not overdue
        if overdue_only and not is_overdue:
            continue
        
        # Check if notification should be sent (30 days before or overdue)
        notification_sent = False
        if next_exam_date and worker.user_id:
            should_notify = is_overdue or (days_until_next_exam is not None and days_until_next_exam <= 30)
            
            if should_notify:
                # Check if notification already exists for this exam
                existing_notification = db.query(Notification).filter(
                    and_(
                        Notification.user_id == worker.user_id,
                        Notification.additional_data.contains(f'"exam_id":{exam.id}')
                    )
                ).first()
                
                if not existing_notification:
                    # Create notification
                    notification_title = "Examen Ocupacional Próximo" if not is_overdue else "Examen Ocupacional Vencido"
                    notification_message = f"Su examen ocupacional {'está vencido' if is_overdue else 'vence pronto'}. Fecha programada: {next_exam_date.strftime('%d/%m/%Y')}"
                    
                    # Send email notification for overdue exams
                    if is_overdue and worker.email:
                        # Implement email sending for overdue exams
                        from app.utils.email import send_email
                        send_email(
                            recipient=worker.email,
                            subject=notification_title,
                            body=notification_message,
                            template="exam_notification",
                            context={
                                "worker_name": worker.full_name,
                                "exam_type": exam.exam_type.value,
                                "exam_date": next_exam_date.strftime('%d/%m/%Y'),
                                "is_overdue": is_overdue
                            }
                        )
                    
                    notification = Notification(
                        user_id=worker.user_id,
                        title=notification_title,
                        message=notification_message,
                        notification_type=NotificationType.IN_APP,
                        priority=NotificationPriority.HIGH if is_overdue else NotificationPriority.NORMAL,
                        additional_data=f'{{"exam_id":{exam.id},"worker_id":{worker.id},"next_exam_date":"{next_exam_date}"}}'
                    )
                    db.add(notification)
                    db.commit()
                    notification_sent = True
        
        exam_reports.append(OccupationalExamReportResponse(
             exam_id=exam.id,
             worker_id=worker.id,
             worker_name=worker.full_name,
             document_number=worker.document_number,
             position=worker.position,
             exam_type=exam.exam_type.value,
             exam_date=exam.exam_date,
             next_exam_date=next_exam_date,
             periodicity=periodicity,
             medical_aptitude=exam.medical_aptitude_concept.value,
             examining_doctor=exam.examining_doctor,
             medical_center=exam.medical_center,
             days_until_next_exam=days_until_next_exam,
             is_overdue=is_overdue,
             notification_sent=notification_sent
         ))
    
    # Calculate pagination info
    page = (skip // limit) + 1 if limit > 0 else 1
    pages = (total + limit - 1) // limit if limit > 0 else 1
    has_next = skip + limit < total
    has_prev = skip > 0
    
    filtered_total = len(exam_reports)
    
    # Recalculate pagination info based on filtered total
    pages = (filtered_total + limit - 1) // limit if limit > 0 else 1
    has_next = skip + limit < filtered_total
    
    return PaginatedResponse(
        items=exam_reports,
        total=filtered_total,  # Use filtered count
        page=page,
        size=limit,
        pages=pages,
        has_next=has_next,
        has_prev=has_prev
    )


@router.get("/occupational-exams/pdf")
async def generate_occupational_exam_report_pdf(
    worker_id: int = None,
    exam_type: str = None,
    start_date: date = None,
    end_date: date = None,
    overdue_only: bool = False,
    download: bool = Query(True, description="Si se debe descargar el archivo"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Generate PDF report for occupational exams
    """
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    try:
        # Import HTML to PDF converter and storage manager
        from app.services.html_to_pdf import HTMLToPDFConverter
        from app.utils.storage import storage_manager
        from app.config import settings
        
        # Get occupational exam data using the same logic as the get endpoint
        query = db.query(OccupationalExam).join(Worker)
        
        # Apply filters
        if worker_id:
            query = query.filter(OccupationalExam.worker_id == worker_id)
        
        if exam_type:
            query = query.filter(OccupationalExam.exam_type == exam_type)
        
        if start_date:
            query = query.filter(OccupationalExam.exam_date >= start_date)
        
        if end_date:
            query = query.filter(OccupationalExam.exam_date <= end_date)
        
        # Get all exams (no pagination for PDF)
        exams = query.all()
        
        # Build report data
        today = date.today()
        pending_exams = []
        overdue_exams = []
        
        for exam in exams:
            worker = exam.worker
            
            # Calculate next exam date based on exam type
            if exam.exam_type == ExamType.INGRESO:
                next_exam_date = exam.exam_date + timedelta(days=365)  # Annual
            elif exam.exam_type == ExamType.PERIODICO:
                next_exam_date = exam.exam_date + timedelta(days=365)  # Annual
            elif exam.exam_type == ExamType.RETIRO:
                next_exam_date = None  # No next exam for exit exams
            else:
                next_exam_date = exam.exam_date + timedelta(days=365)  # Default annual
            
            exam_data = {
                'employee_name': worker.full_name,
                'document': worker.document_number or 'N/A',
                'position': worker.position or 'N/A',
                'exam_type': exam.exam_type.value,
                'exam_date': exam.exam_date.strftime('%d/%m/%Y'),
                'due_date': next_exam_date.strftime('%d/%m/%Y') if next_exam_date else 'N/A'
            }
            
            # Categorize exams
            if next_exam_date:
                if next_exam_date < today:
                    overdue_exams.append(exam_data)
                elif next_exam_date <= today + timedelta(days=30):  # Due within 30 days
                    pending_exams.append(exam_data)
        
        # Filter by overdue only if requested
        if overdue_only:
            pending_exams = []
        
        # Prepare statistics
        total_workers = db.query(Worker).count()
        total_pending = len(pending_exams)
        total_overdue = len(overdue_exams)
        up_to_date = total_workers - total_pending - total_overdue
        
        statistics = {
            'total_workers': total_workers,
            'up_to_date': up_to_date,
            'pending': total_pending,
            'overdue': total_overdue
        }
        
        # Prepare template data
        template_data = {
            'statistics': statistics,
            'pending_exams': pending_exams,
            'overdue_exams': overdue_exams,
            'total_pending': total_pending,
            'total_overdue': total_overdue
        }
        
        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"reporte_examenes_ocupacionales_{timestamp}.pdf"
        
        # Create medical_reports directory if it doesn't exist (for local storage)
        reports_dir = "medical_reports"
        if not os.path.exists(reports_dir):
            os.makedirs(reports_dir)
        
        local_filepath = os.path.join(reports_dir, filename)
        
        # Initialize HTML to PDF converter
        converter = HTMLToPDFConverter()
        
        # Generate PDF content
        pdf_content = converter.generate_occupational_exam_report_pdf(template_data)
        
        # Determine if use Firebase Storage or local storage
        use_firebase = getattr(settings, 'USE_FIREBASE_STORAGE', 'False').lower() == 'true'
        
        # Firebase Storage path
        firebase_path = f"medical_reports/{filename}"
        
        if use_firebase:
            # Upload to Firebase Storage
            storage_manager.upload_file(firebase_path, pdf_content, content_type="application/pdf")
            # Get public URL
            file_url = storage_manager.get_public_url(firebase_path)
            # Also save locally for FileResponse
            with open(local_filepath, "wb") as f:
                f.write(pdf_content)
        else:
            # Save PDF to disk for FileResponse
            with open(local_filepath, "wb") as f:
                f.write(pdf_content)
            file_url = None
        
        # Prepare response parameters
        response_params = {
            "path": local_filepath,
            "media_type": "application/pdf"
        }
        
        # Add filename for download if requested
        if download:
            response_params["filename"] = f"Reporte_Examenes_Ocupacionales_{datetime.now().strftime('%d_%m_%Y')}.pdf"
        
        # Return file response
        return FileResponse(**response_params)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al generar el PDF: {str(e)}"
        )