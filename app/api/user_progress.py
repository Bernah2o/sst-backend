from typing import Any, List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from app.database import get_db
from app.dependencies import get_current_active_user
from app.models.user import User, UserRole
from app.models.course import Course, CourseStatus
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.user_progress import UserMaterialProgress, UserModuleProgress, MaterialProgressStatus
from app.models.survey import Survey, UserSurvey, SurveyStatus, UserSurveyStatus
from app.models.evaluation import Evaluation, UserEvaluation, UserEvaluationStatus
from app.schemas.enrollment import (
    UserProgress, 
    UserProgressListResponse, 
    UserProgressStatus, 
    CourseProgressDetail
)

router = APIRouter()


def map_enrollment_to_progress_status(enrollment_status: str, progress: float) -> UserProgressStatus:
    """Map enrollment status and progress to UserProgressStatus"""
    if enrollment_status == EnrollmentStatus.COMPLETED.value:
        return UserProgressStatus.COMPLETED
    elif enrollment_status == EnrollmentStatus.ACTIVE.value:
        if progress > 0:
            return UserProgressStatus.IN_PROGRESS
        else:
            return UserProgressStatus.NOT_STARTED
    elif enrollment_status == EnrollmentStatus.SUSPENDED.value:
        return UserProgressStatus.BLOCKED
    elif enrollment_status == EnrollmentStatus.CANCELLED.value:
        return UserProgressStatus.EXPIRED
    else:  # PENDING
        return UserProgressStatus.NOT_STARTED


@router.get("/")
async def get_user_progress(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    user_id: Optional[int] = Query(None),
    course_id: Optional[int] = Query(None),
    status: Optional[UserProgressStatus] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> UserProgressListResponse:
    """
    Get user progress with pagination and filters
    Admin and capacitador can view all progress, employees can only view their own
    """
    # Build query based on user role
    query = db.query(Enrollment).join(User).join(Course)
    
    # Role-based filtering
    if current_user.role.value not in ["admin", "capacitador"]:
        # Employees can only see their own progress
        query = query.filter(Enrollment.user_id == current_user.id)
    elif user_id:
        # Admin/capacitador can filter by specific user
        query = query.filter(Enrollment.user_id == user_id)
    
    # Additional filters
    if course_id:
        query = query.filter(Enrollment.course_id == course_id)
    
    # Exclude cancelled enrollments
    query = query.filter(Enrollment.status != EnrollmentStatus.CANCELLED)
    
    # Get total count
    total = query.count()
    
    # Get enrollments with pagination
    enrollments = query.offset(skip).limit(limit).all()
    
    # Build response
    progress_items = []
    for enrollment in enrollments:
        user = db.query(User).filter(User.id == enrollment.user_id).first()
        course = db.query(Course).filter(Course.id == enrollment.course_id).first()
        
        # Map status
        progress_status = map_enrollment_to_progress_status(enrollment.status, enrollment.progress)
        
        # Filter by status if specified
        if status and progress_status != status:
            continue
        
        # Get course progress details
        course_details = None
        if enrollment.progress >= 100:
            # Check surveys
            required_surveys = db.query(Survey).filter(
                and_(
                    Survey.course_id == course.id,
                    Survey.required_for_completion == True,
                    Survey.status == SurveyStatus.PUBLISHED
                )
            ).all()
            
            pending_surveys = []
            for survey in required_surveys:
                user_submission = db.query(UserSurvey).filter(
                    and_(
                        UserSurvey.user_id == user.id,
                        UserSurvey.survey_id == survey.id,
                        UserSurvey.status == UserSurveyStatus.COMPLETED
                    )
                ).first()
                
                if not user_submission:
                    pending_surveys.append({
                        "id": survey.id,
                        "title": survey.title,
                        "description": survey.description
                    })
            
            # Check evaluation status
            evaluation_status = "not_started"
            course_evaluations = db.query(Evaluation).filter(
                and_(
                    Evaluation.course_id == course.id,
                    Evaluation.status == "published"
                )
            ).all()
            
            for evaluation in course_evaluations:
                completed_evaluation = db.query(UserEvaluation).filter(
                    and_(
                        UserEvaluation.user_id == user.id,
                        UserEvaluation.evaluation_id == evaluation.id,
                        UserEvaluation.status == UserEvaluationStatus.COMPLETED
                    )
                ).first()
                
                if completed_evaluation:
                    evaluation_status = "completed"
                    break
                else:
                    started_evaluation = db.query(UserEvaluation).filter(
                        and_(
                            UserEvaluation.user_id == user.id,
                            UserEvaluation.evaluation_id == evaluation.id
                        )
                    ).first()
                    if started_evaluation:
                        evaluation_status = "in_progress"
            
            course_details = CourseProgressDetail(
                overall_progress=enrollment.progress,
                can_take_survey=len(pending_surveys) > 0,
                can_take_evaluation=len(pending_surveys) == 0 and evaluation_status != "completed",
                pending_surveys=pending_surveys,
                evaluation_status=evaluation_status,
                survey_status="completed" if len(pending_surveys) == 0 else "pending"
            )
        
        progress_item = UserProgress(
            user_id=user.id,
            course_id=course.id,
            user_name=f"{user.first_name} {user.last_name}" if user.first_name and user.last_name else user.username,
            course_name=course.title,
            status=progress_status,
            progress_percentage=enrollment.progress,
            enrolled_at=enrollment.enrolled_at,
            started_at=enrollment.started_at,
            completed_at=enrollment.completed_at,
            grade=enrollment.grade,
            course_details=course_details
        )
        
        progress_items.append(progress_item)
    
    return UserProgressListResponse(
        items=progress_items,
        total=len(progress_items),  # Adjusted total after status filtering
        skip=skip,
        limit=limit
    )


@router.get("/user/{user_id}")
async def get_user_progress_by_id(
    user_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> List[UserProgress]:
    """
    Get all progress for a specific user
    """
    # Permission check
    if current_user.role.value not in ["admin", "capacitador"] and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # Get user enrollments
    enrollments = db.query(Enrollment).filter(
        and_(
            Enrollment.user_id == user_id,
            Enrollment.status != EnrollmentStatus.CANCELLED
        )
    ).all()
    
    progress_items = []
    for enrollment in enrollments:
        user = db.query(User).filter(User.id == enrollment.user_id).first()
        course = db.query(Course).filter(Course.id == enrollment.course_id).first()
        
        progress_status = map_enrollment_to_progress_status(enrollment.status, enrollment.progress)
        
        progress_item = UserProgress(
            user_id=user.id,
            course_id=course.id,
            user_name=f"{user.first_name} {user.last_name}" if user.first_name and user.last_name else user.username,
            course_name=course.title,
            status=progress_status,
            progress_percentage=enrollment.progress,
            enrolled_at=enrollment.enrolled_at,
            started_at=enrollment.started_at,
            completed_at=enrollment.completed_at,
            grade=enrollment.grade
        )
        
        progress_items.append(progress_item)
    
    return progress_items


@router.get("/course/{course_id}")
async def get_course_progress(
    course_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> UserProgressListResponse:
    """
    Get progress for all users in a specific course
    """
    # Permission check
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # Get course enrollments
    query = db.query(Enrollment).filter(
        and_(
            Enrollment.course_id == course_id,
            Enrollment.status != EnrollmentStatus.CANCELLED
        )
    )
    
    total = query.count()
    enrollments = query.offset(skip).limit(limit).all()
    
    progress_items = []
    for enrollment in enrollments:
        user = db.query(User).filter(User.id == enrollment.user_id).first()
        course = db.query(Course).filter(Course.id == enrollment.course_id).first()
        
        progress_status = map_enrollment_to_progress_status(enrollment.status, enrollment.progress)
        
        progress_item = UserProgress(
            user_id=user.id,
            course_id=course.id,
            user_name=f"{user.first_name} {user.last_name}" if user.first_name and user.last_name else user.username,
            course_name=course.title,
            status=progress_status,
            progress_percentage=enrollment.progress,
            enrolled_at=enrollment.enrolled_at,
            started_at=enrollment.started_at,
            completed_at=enrollment.completed_at,
            grade=enrollment.grade
        )
        
        progress_items.append(progress_item)
    
    return UserProgressListResponse(
        items=progress_items,
        total=total,
        skip=skip,
        limit=limit
    )