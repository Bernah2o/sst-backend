from typing import Any, List, Optional
from datetime import datetime
import secrets
import string

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from app.database import get_db
from app.dependencies import get_current_active_user
from app.models.user import User, UserRole
from app.models.course import Course, CourseStatus, CourseType
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.worker import Worker
from app.models.attendance import Attendance
from app.models.evaluation import UserEvaluation
from app.models.user_progress import UserMaterialProgress
from app.models.survey import UserSurvey
from app.schemas.enrollment import EnrollmentResponse, EnrollmentCreate, EnrollmentUpdate, BulkEnrollmentCreate, BulkEnrollmentResponse
from app.schemas.common import MessageResponse
from app.api.auth_worker_update import update_worker_after_registration
from app.services.auth import auth_service

router = APIRouter()


@router.post("/course/{course_id}/enroll")
async def enroll_in_course(
    course_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Enroll current user in a course
    """
    # Check if course exists and is published
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Curso no encontrado"
        )
    
    # Only allow enrollment in published courses
    if course.status != CourseStatus.PUBLISHED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo los cursos publicados están disponibles para inscripción"
        )
    
    # Check if user is already enrolled (excluding cancelled enrollments)
    existing_enrollment = db.query(Enrollment).filter(
        and_(
            Enrollment.user_id == current_user.id,
            Enrollment.course_id == course_id,
            Enrollment.status != EnrollmentStatus.CANCELLED
        )
    ).first()
    
    if existing_enrollment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya está inscrito en este curso"
        )
    
    # Create enrollment
    enrollment = Enrollment(
        user_id=current_user.id,
        course_id=course_id,
        status=EnrollmentStatus.ACTIVE.value
    )
    enrollment.start_enrollment()
    
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)
    
    return {
        "message": "Inscripción exitosa en el curso",
        "enrollment_id": enrollment.id,
        "course_title": course.title
    }


@router.post("/bulk-assign")
async def bulk_assign_courses(
    assignment_data: BulkEnrollmentCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> BulkEnrollmentResponse:
    """Assign a course to multiple users (admin and capacitador roles only)
    """
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permisos insuficientes"
        )
    
    successful_enrollments = []
    failed_enrollments = []
    
    # Check if course exists and is published
    course = db.query(Course).filter(Course.id == assignment_data.course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Curso no encontrado"
        )
    
    # Only allow assignment of published courses
    if course.status != CourseStatus.PUBLISHED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo los cursos publicados pueden ser asignados a usuarios"
        )
    
    for user_id in assignment_data.user_ids:
        try:
            # Check if user exists
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                failed_enrollments.append({
                    "user_id": user_id,
                    "course_id": assignment_data.course_id,
                    "error": "Usuario no encontrado"
                })
                continue
            
            # Check if already enrolled
            existing_enrollment = db.query(Enrollment).filter(
                and_(
                    Enrollment.user_id == user_id,
                    Enrollment.course_id == assignment_data.course_id
                )
            ).first()
            
            if existing_enrollment:
                # Instead of treating as error, update the existing enrollment if needed
                if existing_enrollment.status != assignment_data.status or existing_enrollment.notes != assignment_data.notes:
                    existing_enrollment.status = assignment_data.status
                    existing_enrollment.notes = assignment_data.notes
                    db.commit()
                    db.refresh(existing_enrollment)
                
                # Add to successful enrollments
                enrollment_response = EnrollmentResponse(
                    id=existing_enrollment.id,
                    user_id=existing_enrollment.user_id,
                    course_id=existing_enrollment.course_id,
                    status=existing_enrollment.status,
                    progress=existing_enrollment.progress,
                    grade=existing_enrollment.grade,
                    notes=existing_enrollment.notes,
                    enrolled_at=existing_enrollment.enrolled_at,
                    completed_at=existing_enrollment.completed_at,
                    created_at=existing_enrollment.created_at,
                    updated_at=existing_enrollment.updated_at
                )
                successful_enrollments.append(enrollment_response)
                continue
            
            # Create enrollment
            enrollment = Enrollment(
                user_id=user_id,
                course_id=assignment_data.course_id,
                status=assignment_data.status,
                notes=assignment_data.notes
            )
            enrollment.start_enrollment()
            
            db.add(enrollment)
            db.commit()
            db.refresh(enrollment)
            
            # Create response object
            enrollment_response = EnrollmentResponse(
                id=enrollment.id,
                user_id=enrollment.user_id,
                course_id=enrollment.course_id,
                status=enrollment.status,
                progress=enrollment.progress,
                grade=enrollment.grade,
                notes=enrollment.notes,
                enrolled_at=enrollment.enrolled_at,
                started_at=enrollment.started_at,
                completed_at=enrollment.completed_at,
                created_at=enrollment.created_at,
                updated_at=enrollment.updated_at
            )
            
            successful_enrollments.append(enrollment_response)
            
        except Exception as e:
            failed_enrollments.append({
                "user_id": user_id,
                "course_id": assignment_data.course_id,
                "error": str(e)
            })
    
    return BulkEnrollmentResponse(
        successful_enrollments=successful_enrollments,
        failed_enrollments=failed_enrollments,
        total_processed=len(assignment_data.user_ids),
        successful_count=len(successful_enrollments),
        failed_count=len(failed_enrollments)
    )


@router.post("/mark-course-completed/{course_id}/{user_id}")
async def mark_course_completed(
    course_id: int,
    user_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Mark a course as completed for a specific user (admin only)
    Only works for optional and training course types
    """
    if current_user.role.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los administradores pueden marcar cursos como completados"
        )
    
    # Check if course exists
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Curso no encontrado"
        )
    
    # Check if course type is optional or training
    if course.course_type not in [CourseType.OPTIONAL, CourseType.TRAINING]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo los cursos opcionales y de entrenamiento pueden ser marcados como completados"
        )
    
    # Check if user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )
    
    # Check if enrollment exists
    enrollment = db.query(Enrollment).filter(
        and_(
            Enrollment.user_id == user_id,
            Enrollment.course_id == course_id
        )
    ).first()
    
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El usuario no está inscrito en este curso"
        )
    
    # Mark as completed
    enrollment.complete_enrollment()
    enrollment.progress = 100.0
    
    db.commit()
    db.refresh(enrollment)
    
    return {
        "message": "Curso marcado como completado exitosamente",
        "enrollment_id": enrollment.id,
        "course_title": course.title,
        "user_name": user.full_name,
        "completed_at": enrollment.completed_at
    }


@router.post("/start-course/{course_id}")
async def start_course(
    course_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Start a course by activating the enrollment (changes status from pending to active)
    """
    # Check if course exists
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Curso no encontrado"
        )
    
    # Check if user is enrolled
    enrollment = db.query(Enrollment).filter(
        and_(
            Enrollment.user_id == current_user.id,
            Enrollment.course_id == course_id
        )
    ).first()
    
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El usuario no está inscrito en este curso"
        )
    
    # Start the enrollment if it's pending
    if enrollment.status == EnrollmentStatus.PENDING.value:
        enrollment.start_enrollment()
        db.commit()
        db.refresh(enrollment)
    
    return {
        "message": "Curso iniciado exitosamente",
        "enrollment_id": enrollment.id,
        "course_title": course.title,
        "status": enrollment.status,
        "started_at": enrollment.started_at
    }


@router.post("/bulk-assign-workers")
async def bulk_assign_courses_to_workers(
    assignment_data: BulkEnrollmentCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> BulkEnrollmentResponse:
    """
    Assign a course to multiple workers by their worker IDs (admin and capacitador roles only)
    If a worker is not registered, they will be auto-registered with a temporary user account
    """
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permisos insuficientes"
        )
    
    successful_enrollments = []
    failed_enrollments = []
    
    # Check if course exists and is published
    course = db.query(Course).filter(Course.id == assignment_data.course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Curso no encontrado"
        )
    
    # Only allow assignment of published courses
    if course.status != CourseStatus.PUBLISHED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo los cursos publicados pueden ser asignados a trabajadores"
        )
    
    # Process each worker ID
    for worker_id in assignment_data.user_ids:  # user_ids contains worker IDs in this context
        try:
            # Find the worker regardless of registration status
            worker = db.query(Worker).filter(
                Worker.id == worker_id,
                Worker.is_active == True
            ).first()
            
            if not worker:
                failed_enrollments.append({
                    "user_id": worker_id,
                    "course_id": assignment_data.course_id,
                    "error": "Trabajador no encontrado"
                })
                continue
            
            # If worker is not registered, auto-register them
            if not worker.is_registered or not worker.user_id:
                # Check if a user with this email or document number already exists
                existing_user = db.query(User).filter(
                    (User.email == worker.email) |
                    (User.document_number == worker.document_number)
                ).first()
                
                if existing_user:
                    # Link the existing user to this worker
                    worker.is_registered = True
                    worker.user_id = existing_user.id
                else:
                    # Create a new user for this worker
                    # Generate a random password (they'll need to reset it)
                    temp_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
                    
                    # Hash the password
                    hashed_password = auth_service.get_password_hash(temp_password)
                    
                    # Create the user
                    new_user = User(
                        username=temp_username,
                        email=worker.email,
                        hashed_password=hashed_password,
                        first_name=worker.first_name,
                        last_name=worker.last_name,
                        document_type=worker.document_type,
                        document_number=worker.document_number,
                        phone=worker.phone,
                        department=worker.department,
                        position=worker.position,
                        role=worker.assigned_role,  # Assign the role from worker
                        is_active=True,
                        is_verified=True  # Auto-verify
                    )
                    db.add(new_user)
                    db.flush()
                    
                    # Update worker to mark as registered and link to this user
                    worker.is_registered = True
                    worker.user_id = new_user.id
            
            # Check if already enrolled (excluding cancelled enrollments)
            existing_enrollment = db.query(Enrollment).filter(
                and_(
                    Enrollment.user_id == worker.user_id,
                    Enrollment.course_id == assignment_data.course_id,
                    Enrollment.status != EnrollmentStatus.CANCELLED
                )
            ).first()
            
            if existing_enrollment:
                # Instead of treating as error, update the existing enrollment if needed
                if existing_enrollment.status != assignment_data.status or existing_enrollment.notes != assignment_data.notes:
                    existing_enrollment.status = assignment_data.status
                    existing_enrollment.notes = assignment_data.notes
                    db.flush()
                
                # Add to successful enrollments
                successful_enrollments.append(EnrollmentResponse(
                    id=existing_enrollment.id,
                    user_id=existing_enrollment.user_id,
                    course_id=existing_enrollment.course_id,
                    status=existing_enrollment.status,
                    notes=existing_enrollment.notes,
                    enrolled_at=existing_enrollment.enrolled_at,
                    completed_at=existing_enrollment.completed_at,
                    grade=existing_enrollment.grade,
                    progress=existing_enrollment.progress,
                    created_at=existing_enrollment.created_at,
                    updated_at=existing_enrollment.updated_at
                ))
                continue
            
            # Create enrollment for the worker's user
            enrollment = Enrollment(
                user_id=worker.user_id,
                course_id=assignment_data.course_id,
                status=assignment_data.status,
                notes=assignment_data.notes,
                enrolled_at=datetime.utcnow()
            )
            db.add(enrollment)
            db.flush()
            
            successful_enrollments.append(EnrollmentResponse(
                id=enrollment.id,
                user_id=enrollment.user_id,
                course_id=enrollment.course_id,
                status=enrollment.status,
                notes=enrollment.notes,
                enrolled_at=enrollment.enrolled_at,
                completed_at=enrollment.completed_at,
                grade=enrollment.grade,
                progress=enrollment.progress,
                created_at=enrollment.created_at,
                updated_at=enrollment.updated_at
            ))
            
        except Exception as e:
            failed_enrollments.append({
                "user_id": worker_id,
                "course_id": assignment_data.course_id,
                "error": str(e)
            })
    
    db.commit()
    
    return BulkEnrollmentResponse(
        successful_enrollments=successful_enrollments,
        failed_enrollments=failed_enrollments,
        total_processed=len(assignment_data.user_ids),
        successful_count=len(successful_enrollments),
        failed_count=len(failed_enrollments)
    )


@router.get("/user/{user_id}")
async def get_user_enrollments(
    user_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get enrollments for a specific user (admin and capacitador roles, or own enrollments)
    """
    # Check permissions
    if current_user.role.value not in ["admin", "capacitador"] and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # Get user enrollments
    enrollments = db.query(Enrollment).filter(Enrollment.user_id == user_id).all()
    
    enrollment_details = []
    for enrollment in enrollments:
        course = db.query(Course).filter(Course.id == enrollment.course_id).first()
        enrollment_details.append({
            "enrollment_id": enrollment.id,
            "course_id": course.id,
            "course_title": course.title,
            "course_type": course.course_type.value,
            "status": enrollment.status,
            "progress": enrollment.progress,
            "enrolled_at": enrollment.enrolled_at.isoformat() if enrollment.enrolled_at else None,
            "started_at": enrollment.started_at.isoformat() if enrollment.started_at else None,
            "completed_at": enrollment.completed_at.isoformat() if enrollment.completed_at else None,
            "grade": enrollment.grade
        })
    
    return {
        "user_id": user_id,
        "total_enrollments": len(enrollment_details),
        "enrollments": enrollment_details
    }


@router.delete("/{enrollment_id}")
async def delete_enrollment(
    enrollment_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Permanently delete an enrollment and all related data from the database
    This action cannot be undone.
    """
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    enrollment = db.query(Enrollment).filter(Enrollment.id == enrollment_id).first()
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inscripción no encontrada"
        )
    
    # Get user and course info for logging
    user = db.query(User).filter(User.id == enrollment.user_id).first()
    worker = db.query(Worker).filter(Worker.user_id == enrollment.user_id).first() if enrollment.user_id else None
    course = db.query(Course).filter(Course.id == enrollment.course_id).first()
    
    # Delete all related data in the correct order to avoid foreign key constraints
    try:
        # 1. Delete attendance records (both with enrollment_id and orphaned records)
        # First, count and delete records with enrollment_id
        attendance_count = db.query(Attendance).filter(Attendance.enrollment_id == enrollment_id).count()
        db.query(Attendance).filter(Attendance.enrollment_id == enrollment_id).delete()
        
        # Also delete orphaned attendance records that match user_id and course_id but have no enrollment_id
        orphaned_attendance_count = db.query(Attendance).filter(
            Attendance.user_id == enrollment.user_id,
            Attendance.course_id == enrollment.course_id,
            Attendance.enrollment_id.is_(None)
        ).count()
        db.query(Attendance).filter(
            Attendance.user_id == enrollment.user_id,
            Attendance.course_id == enrollment.course_id,
            Attendance.enrollment_id.is_(None)
        ).delete()
        
        total_attendance_count = attendance_count + orphaned_attendance_count
        
        # 2. Delete user material progress
        material_progress_count = db.query(UserMaterialProgress).filter(
            UserMaterialProgress.enrollment_id == enrollment_id
        ).count()
        db.query(UserMaterialProgress).filter(
            UserMaterialProgress.enrollment_id == enrollment_id
        ).delete()
        
        # 3. Delete user module progress
        from app.models.user_progress import UserModuleProgress
        module_progress_count = db.query(UserModuleProgress).filter(
            UserModuleProgress.enrollment_id == enrollment_id
        ).count()
        db.query(UserModuleProgress).filter(
            UserModuleProgress.enrollment_id == enrollment_id
        ).delete()
        
        # 4. Delete user evaluations and their answers
        from app.models.evaluation import UserAnswer
        
        # First get all user evaluations for this enrollment
        user_evaluations = db.query(UserEvaluation).filter(
            UserEvaluation.enrollment_id == enrollment_id
        ).all()
        
        # Also get orphaned evaluations for the same user and course
        # First get all evaluations for this course
        from app.models.evaluation import Evaluation
        course_evaluations = db.query(Evaluation).filter(
            Evaluation.course_id == enrollment.course_id
        ).all()
        course_evaluation_ids = [eval.id for eval in course_evaluations]
        
        # Then get orphaned user evaluations for these course evaluations
        orphaned_evaluations = db.query(UserEvaluation).filter(
            UserEvaluation.user_id == enrollment.user_id,
            UserEvaluation.evaluation_id.in_(course_evaluation_ids),
            UserEvaluation.enrollment_id.is_(None)
        ).all()
        
        all_evaluations = user_evaluations + orphaned_evaluations
        evaluations_count = len(user_evaluations)
        orphaned_evaluations_count = len(orphaned_evaluations)
        total_evaluations_count = len(all_evaluations)
        user_answers_count = 0
        
        # Delete user answers for each evaluation (both regular and orphaned)
        for user_eval in all_evaluations:
            answers_count = db.query(UserAnswer).filter(
                UserAnswer.user_evaluation_id == user_eval.id
            ).count()
            user_answers_count += answers_count
            
            db.query(UserAnswer).filter(
                UserAnswer.user_evaluation_id == user_eval.id
            ).delete()
        
        # Delete the user evaluations with enrollment_id
        db.query(UserEvaluation).filter(
            UserEvaluation.enrollment_id == enrollment_id
        ).delete()
        
        # Delete orphaned evaluations for the same user and course
        db.query(UserEvaluation).filter(
            UserEvaluation.user_id == enrollment.user_id,
            UserEvaluation.evaluation_id.in_(course_evaluation_ids),
            UserEvaluation.enrollment_id.is_(None)
        ).delete()
        
        # 5. Delete user surveys and their answers related to this enrollment
        from app.models.survey import UserSurveyAnswer
        
        # First get all user surveys for this enrollment
        user_surveys = db.query(UserSurvey).filter(
            UserSurvey.enrollment_id == enrollment_id
        ).all()
        
        surveys_count = len(user_surveys)
        survey_answers_count = 0
        
        # Delete user survey answers for each survey
        for user_survey in user_surveys:
            answers_count = db.query(UserSurveyAnswer).filter(
                UserSurveyAnswer.user_survey_id == user_survey.id
            ).count()
            survey_answers_count += answers_count
            
            db.query(UserSurveyAnswer).filter(
                UserSurveyAnswer.user_survey_id == user_survey.id
            ).delete()
        
        # Now delete the user surveys
        db.query(UserSurvey).filter(
            UserSurvey.enrollment_id == enrollment_id
        ).delete()
        
        # 6. Delete certificates
        from app.models.certificate import Certificate
        certificates_count = db.query(Certificate).filter(
            and_(
                Certificate.user_id == enrollment.user_id,
                Certificate.course_id == enrollment.course_id
            )
        ).count()
        db.query(Certificate).filter(
            and_(
                Certificate.user_id == enrollment.user_id,
                Certificate.course_id == enrollment.course_id
            )
        ).delete()
        
        # 7. Finally, delete the enrollment itself
        db.delete(enrollment)
        
        db.commit()
        
        return MessageResponse(
            message=f"Inscripción eliminada permanentemente. Removidos: {total_attendance_count} registros de asistencia "
                   f"({attendance_count} con enrollment_id + {orphaned_attendance_count} huérfanos), "
                   f"{material_progress_count} registros de progreso de material, {module_progress_count} registros de progreso de módulo, "
                   f"{total_evaluations_count} evaluaciones ({evaluations_count} con enrollment_id + {orphaned_evaluations_count} huérfanas), "
                   f"{user_answers_count} respuestas de evaluación, "
                   f"{surveys_count} encuestas, {survey_answers_count} respuestas de encuesta, {certificates_count} certificados, "
                   f"y la inscripción para el usuario {user.email if user else 'N/A'} en el curso {course.title if course else 'N/A'}"
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error eliminando inscripción: {str(e)}"
        )


@router.get("/course/{course_id}/workers")
async def get_course_workers(
    course_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get all workers enrolled in a specific course (admin and capacitador roles only)
    """
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # Check if course exists
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Curso no encontrado"
        )
    
    # Get all enrollments for this course
    enrollments = db.query(Enrollment).filter(Enrollment.course_id == course_id).all()
    
    # Get user details for each enrollment
    enrolled_workers = []
    for enrollment in enrollments:
        user = db.query(User).filter(User.id == enrollment.user_id).first()
        if not user:
            continue
            
        # Check if user is associated with a worker
        worker = db.query(Worker).filter(Worker.user_id == user.id).first()
        
        worker_data = {
            "enrollment_id": enrollment.id,
            "user_id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": f"{user.first_name} {user.last_name}",
            "status": enrollment.status if isinstance(enrollment.status, str) else enrollment.status.value,
            "progress": enrollment.progress,
            "enrolled_at": enrollment.enrolled_at.isoformat() if enrollment.enrolled_at else None,
            "completed_at": enrollment.completed_at.isoformat() if enrollment.completed_at else None,
            "grade": enrollment.grade,
            "is_worker": worker is not None
        }
        
        # Add worker-specific information if available
        if worker:
            worker_data.update({
                "worker_id": worker.id,
                "department": worker.department,
                "position": worker.position,
                "document_number": worker.document_number,
                "is_active": worker.is_active
            })
        
        enrolled_workers.append(worker_data)
    
    return {
        "course_id": course_id,
        "course_title": course.title,
        "total_enrolled": len(enrolled_workers),
        "enrolled_workers": enrolled_workers
    }


@router.delete("/course/{course_id}/worker/{worker_id}")
async def remove_worker_from_course(
    course_id: int,
    worker_id: int,
    reason: str = Query(None, description="Justificación para retirar al trabajador del curso"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Remove a worker from a course (admin and capacitador roles only)
    """
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # Check if course exists
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    # Check if worker exists
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trabajador no encontrado"
        )
    
    # Check if worker has a user account
    if not worker.user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El trabajador no está registrado en el sistema"
        )
    
    # Check if worker is enrolled in the course
    enrollment = db.query(Enrollment).filter(
        Enrollment.user_id == worker.user_id,
        Enrollment.course_id == course_id
    ).first()
    
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El trabajador no está inscrito en este curso"
        )
    
    try:
        # Remove worker from course
        
        # Delete related attendance records first
        attendance_records = db.query(Attendance).filter(
            Attendance.enrollment_id == enrollment.id
        ).all()
        
        for attendance in attendance_records:
            db.delete(attendance)
        
        # Delete related user evaluations
        user_evaluations = db.query(UserEvaluation).filter(
            UserEvaluation.enrollment_id == enrollment.id
        ).all()
        
        for user_evaluation in user_evaluations:
            db.delete(user_evaluation)
        
        # Delete related user material progress
        user_progress_records = db.query(UserMaterialProgress).filter(
            UserMaterialProgress.enrollment_id == enrollment.id
        ).all()
        
        for progress in user_progress_records:
            db.delete(progress)
            
        # Delete related user surveys
        user_surveys = db.query(UserSurvey).filter(
            UserSurvey.enrollment_id == enrollment.id
        ).all()
        
        for survey in user_surveys:
            db.delete(survey)
        
        # Then delete the enrollment
        db.delete(enrollment)
        
        db.commit()
        return {
            "message": "Trabajador removido exitosamente del curso",
            "worker_id": worker_id,
            "course_id": course_id,
            "reason": reason
        }
    except Exception as e:
        db.rollback()
        import traceback
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error removiendo trabajador del curso: {str(e)}"
        )


@router.get("/")
@router.get("")  # Add route without trailing slash to avoid 307 redirect
async def get_enrollments(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get all enrollments with pagination (admin and capacitador roles only)
    """
    # Check permissions
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # Get total count (excluding cancelled enrollments)
    total = db.query(Enrollment).filter(Enrollment.status != EnrollmentStatus.CANCELLED).count()
    
    # Get enrollments with pagination (excluding cancelled enrollments)
    enrollments = db.query(Enrollment).filter(Enrollment.status != EnrollmentStatus.CANCELLED).offset(skip).limit(limit).all()
    
    # Build response with enrollment details
    enrollment_details = []
    for enrollment in enrollments:
        user = db.query(User).filter(User.id == enrollment.user_id).first()
        course = db.query(Course).filter(Course.id == enrollment.course_id).first()
        
        enrollment_details.append({
            "id": enrollment.id,
            "user_id": enrollment.user_id,
            "user_email": user.email if user else None,
            "first_name": user.first_name if user else None,
            "last_name": user.last_name if user else None,
            "full_name": f"{user.first_name} {user.last_name}" if user and user.first_name and user.last_name else None,
            "document_number": user.document_number if user else None,
            "position": user.position if user else None,
            "department": user.department if user else None,
            "fecha_de_ingreso": user.hire_date.isoformat() if user and user.hire_date else None,
            "is_active": user.is_active if user else None,
            "assigned_role": user.role.value if user and user.role else None,
            "course_id": enrollment.course_id,
            "course_title": course.title if course else None,
            "status": enrollment.status,
            "progress": enrollment.progress,
            "grade": enrollment.grade,
            "notes": enrollment.notes,
            "enrolled_at": enrollment.enrolled_at.isoformat() if enrollment.enrolled_at else None,
            "started_at": enrollment.started_at.isoformat() if enrollment.started_at else None,
            "completed_at": enrollment.completed_at.isoformat() if enrollment.completed_at else None,
            "created_at": enrollment.created_at.isoformat() if enrollment.created_at else None,
            "updated_at": enrollment.updated_at.isoformat() if enrollment.updated_at else None
        })
    
    return {
        "items": enrollment_details,  # Changed from "enrollments" to "items" to match frontend expectation
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.post("/")
@router.post("")  # Add route without trailing slash to avoid 307 redirect
async def create_enrollment(
    enrollment_data: EnrollmentCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Create a new enrollment (admin and capacitador roles only)
    """
    # Check permissions
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # Check if course exists
    course = db.query(Course).filter(Course.id == enrollment_data.course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    # Check if user exists (support both user_id and worker_id)
    user_id = None
    
    if enrollment_data.user_id:
        # Direct user_id provided
        user_id = enrollment_data.user_id
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado"
            )
    elif enrollment_data.worker_id:
        # Worker_id provided, need to get the associated user_id
        from app.models.worker import Worker
        worker = db.query(Worker).filter(Worker.id == enrollment_data.worker_id).first()
        if not worker:
            raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trabajador no encontrado"
        )
        if not worker.user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El trabajador no está registrado en el sistema. Por favor registre al trabajador primero."
            )
        user_id = worker.user_id
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario asociado no encontrado"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Se debe proporcionar user_id o worker_id"
        )
    
    # Check if already enrolled (excluding cancelled enrollments)
    
    existing_enrollment = db.query(Enrollment).filter(
        and_(
            Enrollment.user_id == user_id,
            Enrollment.course_id == enrollment_data.course_id,
            Enrollment.status != EnrollmentStatus.CANCELLED
        )
    ).first()
    
    if existing_enrollment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El usuario ya está inscrito en este curso"
        )

    
    # Create enrollment
    enrollment = Enrollment(
        user_id=user_id,
        course_id=enrollment_data.course_id,
        status=(enrollment_data.status or EnrollmentStatus.PENDING).value,
        progress=enrollment_data.progress or 0.0,
        grade=enrollment_data.grade,
        notes=enrollment_data.notes
    )
    
    if enrollment.status == EnrollmentStatus.ACTIVE.value:
        enrollment.start_enrollment()
    
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)
    
    return {
        "message": "Inscripción creada exitosamente",
        "enrollment_id": enrollment.id,
        "user_id": enrollment.user_id,
        "course_id": enrollment.course_id,
        "status": enrollment.status
    }


@router.get("/stats")
async def get_enrollment_stats(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get enrollment statistics by status
    """
    # Check permissions
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # Get counts by status
    stats_query = db.query(
        Enrollment.status,
        func.count(Enrollment.id).label('count')
    ).group_by(Enrollment.status).all()
    
    # Initialize stats with default values
    stats = {
        "total_enrollments": 0,
        "completed_enrollments": 0,
        "active_enrollments": 0,
        "pending_enrollments": 0
    }
    
    # Populate stats from query results
    for status_result, count in stats_query:
        if status_result == EnrollmentStatus.COMPLETED:
            stats["completed_enrollments"] = count
        elif status_result == EnrollmentStatus.ACTIVE:
            stats["active_enrollments"] = count
        elif status_result == EnrollmentStatus.PENDING:
            stats["pending_enrollments"] = count
        
        stats["total_enrollments"] += count
    
    return stats


@router.get("/my-enrollments")
async def get_my_enrollments(
    course_id: Optional[int] = Query(None, description="Filter enrollments by course ID"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get enrollments for the current user, with optional filtering by course_id
    """
    # Build the query for current user's enrollments
    query = db.query(Enrollment).filter(Enrollment.user_id == current_user.id)
    
    # Apply course_id filter if provided
    if course_id is not None:
        query = query.filter(Enrollment.course_id == course_id)
    
    # Execute the query
    enrollments = query.all()
    
    enrollment_details = []
    for enrollment in enrollments:
        course = db.query(Course).filter(Course.id == enrollment.course_id).first()
        
        enrollment_details.append({
            "id": enrollment.id,
            "user_id": enrollment.user_id,
            "course_id": enrollment.course_id,
            "course": {
                "id": course.id if course else None,
                "title": course.title if course else None,
                "description": course.description if course else None,
                "duration_hours": course.duration_hours if course else None,
                "course_type": course.course_type if course else None,
                "is_mandatory": course.is_mandatory if course else None,
                "thumbnail": course.thumbnail if course else None,
                "status": course.status if course else None
            },
            "course_title": course.title if course else None,  # Keep for backward compatibility
            "status": enrollment.status,
            "progress": enrollment.progress,
            "grade": enrollment.grade,
            "notes": enrollment.notes,
            "enrolled_at": enrollment.enrolled_at.isoformat() if enrollment.enrolled_at else None,
            "started_at": enrollment.started_at.isoformat() if enrollment.started_at else None,
            "completed_at": enrollment.completed_at.isoformat() if enrollment.completed_at else None,
            "created_at": enrollment.created_at.isoformat() if enrollment.created_at else None,
            "updated_at": enrollment.updated_at.isoformat() if enrollment.updated_at else None
        })
    
    return {
        "items": enrollment_details,
        "total": len(enrollment_details)
    }


# Routes with {enrollment_id} parameters - placed at end to avoid conflicts
@router.get("/{enrollment_id}")
async def get_enrollment(
    enrollment_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get enrollment by ID
    """
    # Check permissions
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    enrollment = db.query(Enrollment).filter(Enrollment.id == enrollment_id).first()
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inscripción no encontrada"
        )
    
    # Get user and course details
    user = db.query(User).filter(User.id == enrollment.user_id).first()
    course = db.query(Course).filter(Course.id == enrollment.course_id).first()
    
    return {
        "id": enrollment.id,
        "user_id": enrollment.user_id,
        "user_email": user.email if user else None,
        "first_name": user.first_name if user else None,
        "last_name": user.last_name if user else None,
        "full_name": f"{user.first_name} {user.last_name}" if user and user.first_name and user.last_name else None,
        "course_id": enrollment.course_id,
        "course_title": course.title if course else None,
        "status": enrollment.status,
        "progress": enrollment.progress,
        "grade": enrollment.grade,
        "notes": enrollment.notes,
        "enrolled_at": enrollment.enrolled_at.isoformat() if enrollment.enrolled_at else None,
        "started_at": enrollment.started_at.isoformat() if enrollment.started_at else None,
        "completed_at": enrollment.completed_at.isoformat() if enrollment.completed_at else None,
        "created_at": enrollment.created_at.isoformat() if enrollment.created_at else None,
        "updated_at": enrollment.updated_at.isoformat() if enrollment.updated_at else None
    }


@router.put("/{enrollment_id}")
async def update_enrollment(
    enrollment_id: int,
    enrollment_data: EnrollmentUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Update an enrollment (admin and capacitador roles only)
    """
    # Check permissions
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # Get enrollment
    enrollment = db.query(Enrollment).filter(Enrollment.id == enrollment_id).first()
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inscripción no encontrada"
        )
    
    # Update enrollment fields
    if enrollment_data.status is not None:
        enrollment.status = enrollment_data.status.value
        
        # Handle status-specific logic
        if enrollment_data.status == EnrollmentStatus.ACTIVE and enrollment.started_at is None:
            enrollment.start_enrollment()
        elif enrollment_data.status == EnrollmentStatus.COMPLETED:
            enrollment.complete_enrollment(enrollment_data.grade)
        elif enrollment_data.status == EnrollmentStatus.CANCELLED:
            enrollment.cancel_enrollment(enrollment_data.notes)
        elif enrollment_data.status == EnrollmentStatus.SUSPENDED:
            enrollment.suspend_enrollment(enrollment_data.notes)
    
    if enrollment_data.progress is not None:
        enrollment.update_progress(enrollment_data.progress)
    
    if enrollment_data.grade is not None:
        enrollment.grade = enrollment_data.grade
    
    if enrollment_data.notes is not None:
        enrollment.notes = enrollment_data.notes
    
    # Update timestamp
    enrollment.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(enrollment)
    
    # Get user and course details for response
    user = db.query(User).filter(User.id == enrollment.user_id).first()
    course = db.query(Course).filter(Course.id == enrollment.course_id).first()
    
    return {
        "message": "Inscripción actualizada exitosamente",
        "enrollment": {
            "id": enrollment.id,
            "user_id": enrollment.user_id,
            "user_email": user.email if user else None,
            "first_name": user.first_name if user else None,
            "last_name": user.last_name if user else None,
            "full_name": f"{user.first_name} {user.last_name}" if user and user.first_name and user.last_name else None,
            "course_id": enrollment.course_id,
            "course_title": course.title if course else None,
            "status": enrollment.status,
            "progress": enrollment.progress,
            "grade": enrollment.grade,
            "notes": enrollment.notes,
            "enrolled_at": enrollment.enrolled_at.isoformat() if enrollment.enrolled_at else None,
            "started_at": enrollment.started_at.isoformat() if enrollment.started_at else None,
            "completed_at": enrollment.completed_at.isoformat() if enrollment.completed_at else None,
            "created_at": enrollment.created_at.isoformat() if enrollment.created_at else None,
            "updated_at": enrollment.updated_at.isoformat() if enrollment.updated_at else None
        }
    }


@router.get("/debug/all")
async def get_all_enrollments_debug(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Debug endpoint to get ALL enrollments including cancelled ones (admin only)
    """
    if current_user.role.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # Get ALL enrollments including cancelled ones
    enrollments = db.query(Enrollment).all()
    
    enrollment_details = []
    for enrollment in enrollments:
        user = db.query(User).filter(User.id == enrollment.user_id).first()
        course = db.query(Course).filter(Course.id == enrollment.course_id).first()
        
        enrollment_details.append({
            "id": enrollment.id,
            "user_id": enrollment.user_id,
            "user_email": user.email if user else None,
            "course_id": enrollment.course_id,
            "course_title": course.title if course else None,
            "status": enrollment.status,
            "created_at": enrollment.created_at.isoformat() if enrollment.created_at else None
        })
    
    return {
        "items": enrollment_details,
        "total": len(enrollment_details)
    }