from typing import Any, List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, or_

from app.database import get_db
from app.dependencies import get_current_active_user, has_role_or_custom
from app.models.user import User, UserRole
from app.models.worker import Worker
from app.models.course import Course, CourseStatus, CourseModule, CourseType
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
    elif enrollment_status == EnrollmentStatus.SUSPENDED.value:
        return UserProgressStatus.BLOCKED
    elif enrollment_status == EnrollmentStatus.CANCELLED.value:
        return UserProgressStatus.EXPIRED
    else:
        # For ACTIVE, PENDING, or any other status
        # If there is progress, it is in progress regardless of the enrollment status label
        if progress > 0:
            return UserProgressStatus.IN_PROGRESS
        else:
            return UserProgressStatus.NOT_STARTED


@router.get("/")
async def get_user_progress(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    user_id: Optional[int] = Query(None),
    course_id: Optional[int] = Query(None),
    status: Optional[UserProgressStatus] = Query(None),
    search: Optional[str] = Query(None),
    course_type: Optional[str] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> UserProgressListResponse:
    """
    Get user progress with pagination and filters
    Admin and capacitador can view all progress, employees can only view their own
    """
    # Build query based on user role
    query = db.query(Enrollment).join(User, Enrollment.user_id == User.id).join(Course, Enrollment.course_id == Course.id).outerjoin(Worker, Worker.user_id == User.id)
    
    # Role-based filtering
    if not has_role_or_custom(current_user, ["admin", "trainer", "supervisor"]):
        # Employees can only see their own progress
        query = query.filter(Enrollment.user_id == current_user.id)
    elif user_id:
        # Admin/capacitador can filter by specific user
        query = query.filter(Enrollment.user_id == user_id)
    
    # Additional filters
    if course_id:
        query = query.filter(Enrollment.course_id == course_id)
    
    if course_type:
        query = query.filter(Course.course_type == course_type)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                User.first_name.ilike(search_term),
                User.last_name.ilike(search_term),
                User.email.ilike(search_term),
                func.concat(User.first_name, ' ', User.last_name).ilike(search_term),
                Worker.first_name.ilike(search_term),
                Worker.last_name.ilike(search_term),
                Worker.document_number.ilike(search_term),
                func.concat(Worker.first_name, ' ', Worker.last_name).ilike(search_term)
            )
        )
    
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
        worker = db.query(Worker).filter(Worker.user_id == user.id).first()
        course = db.query(Course).filter(Course.id == enrollment.course_id).first()
        
        # Map status
        progress_status = map_enrollment_to_progress_status(enrollment.status, enrollment.progress)
        
        # Filter by status if specified
        if status and progress_status != status:
            continue
        
        # Calculate time spent
        total_seconds = db.query(func.sum(UserMaterialProgress.time_spent_seconds)).filter(
            UserMaterialProgress.enrollment_id == enrollment.id
        ).scalar() or 0
        time_spent_minutes = int(total_seconds / 60)

        # Calculate modules
        total_modules = db.query(CourseModule).filter(CourseModule.course_id == course.id).count()
        modules_completed = db.query(UserModuleProgress).filter(
            and_(
                UserModuleProgress.enrollment_id == enrollment.id,
                UserModuleProgress.status == MaterialProgressStatus.COMPLETED.value
            )
        ).count()

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
            id=enrollment.id,
            enrollment_id=enrollment.id,
            user_id=user.id,
            course_id=course.id,
            user_name=f"{worker.first_name} {worker.last_name}" if worker else (f"{user.first_name} {user.last_name}" if user.first_name and user.last_name else user.username),
            user_document=worker.document_number if worker else user.document_number,
            user_position=worker.position if worker else user.position,
            user_area=(worker.area_obj.name if worker and worker.area_obj else user.department),
            course_name=course.title,
            course_type=course.course_type.value if course.course_type else None,
            status=progress_status,
            progress_percentage=enrollment.progress,
            time_spent_minutes=time_spent_minutes,
            modules_completed=modules_completed,
            total_modules=total_modules,
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
    if not has_role_or_custom(current_user, ["admin", "trainer", "supervisor"]) and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permisos insuficientes"
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
        worker = db.query(Worker).filter(Worker.user_id == user.id).first()
        course = db.query(Course).filter(Course.id == enrollment.course_id).first()
        
        progress_status = map_enrollment_to_progress_status(enrollment.status, enrollment.progress)
        
        # Calculate time spent
        total_seconds = db.query(func.sum(UserMaterialProgress.time_spent_seconds)).filter(
            UserMaterialProgress.enrollment_id == enrollment.id
        ).scalar() or 0
        time_spent_minutes = int(total_seconds / 60)

        # Calculate modules
        total_modules = db.query(CourseModule).filter(CourseModule.course_id == course.id).count()
        modules_completed = db.query(UserModuleProgress).filter(
            and_(
                UserModuleProgress.enrollment_id == enrollment.id,
                UserModuleProgress.status == MaterialProgressStatus.COMPLETED.value
            )
        ).count()

        progress_item = UserProgress(
            id=enrollment.id,
            enrollment_id=enrollment.id,
            user_id=user.id,
            course_id=course.id,
            user_name=f"{worker.first_name} {worker.last_name}" if worker else (f"{user.first_name} {user.last_name}" if user.first_name and user.last_name else user.username),
            user_document=worker.document_number if worker else user.document_number,
            user_position=worker.position if worker else user.position,
            user_area=(worker.area_obj.name if worker and worker.area_obj else user.department),
            course_name=course.title,
            course_type=course.course_type.value if course.course_type else None,
            status=progress_status,
            progress_percentage=enrollment.progress,
            time_spent_minutes=time_spent_minutes,
            modules_completed=modules_completed,
            total_modules=total_modules,
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
    if not has_role_or_custom(current_user, ["admin", "trainer", "supervisor"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permisos insuficientes"
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
        worker = db.query(Worker).filter(Worker.user_id == user.id).first()
        course = db.query(Course).filter(Course.id == enrollment.course_id).first()
        
        progress_status = map_enrollment_to_progress_status(enrollment.status, enrollment.progress)
        
        # Calculate time spent
        total_seconds = db.query(func.sum(UserMaterialProgress.time_spent_seconds)).filter(
            UserMaterialProgress.enrollment_id == enrollment.id
        ).scalar() or 0
        time_spent_minutes = int(total_seconds / 60)

        # Calculate modules
        total_modules = db.query(CourseModule).filter(CourseModule.course_id == course.id).count()
        modules_completed = db.query(UserModuleProgress).filter(
            and_(
                UserModuleProgress.enrollment_id == enrollment.id,
                UserModuleProgress.status == MaterialProgressStatus.COMPLETED.value
            )
        ).count()

        progress_item = UserProgress(
            id=enrollment.id,
            enrollment_id=enrollment.id,
            user_id=user.id,
            course_id=course.id,
            user_name=f"{worker.first_name} {worker.last_name}" if worker else (f"{user.first_name} {user.last_name}" if user.first_name and user.last_name else user.username),
            user_document=worker.document_number if worker else user.document_number,
            user_position=worker.position if worker else user.position,
            user_area=(worker.area_obj.name if worker and worker.area_obj else user.department),
            course_name=course.title,
            course_type=course.course_type.value if course.course_type else None,
            status=progress_status,
            progress_percentage=enrollment.progress,
            time_spent_minutes=time_spent_minutes,
            modules_completed=modules_completed,
            total_modules=total_modules,
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


@router.get("/{enrollment_id}/details")
async def get_enrollment_details(
    enrollment_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get detailed pending items for a specific enrollment.
    Only accessible by admin, capacitador, or supervisor.
    """
    if not has_role_or_custom(current_user, ["admin", "trainer", "supervisor"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para ver detalles de progreso de otros usuarios"
        )

    enrollment = db.query(Enrollment).filter(Enrollment.id == enrollment_id).first()
    if not enrollment:
        raise HTTPException(status_code=404, detail="Inscripción no encontrada")

    from app.services.course_notifications import CourseNotificationService
    service = CourseNotificationService(db)
    return service.get_pending_items(enrollment)


@router.post("/remind/{enrollment_id}")
async def send_reminder(
    enrollment_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Send a manual reminder to the user for a specific enrollment
    """
    if not has_role_or_custom(current_user, ["admin", "trainer", "supervisor"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para enviar recordatorios"
        )
        
    from app.services.course_notifications import CourseNotificationService
    service = CourseNotificationService(db)
    
    if service.send_reminder(enrollment_id):
        return {"message": "Recordatorio enviado exitosamente"}
    else:
        # If it returns False, it might be because of no email or no pending items
        # We can check specific conditions if needed, but for now generic error is fine
        # Or maybe it's not an error, just "Nothing sent"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="No se pudo enviar el recordatorio (verifique si el usuario tiene email y actividades pendientes)"
        )
