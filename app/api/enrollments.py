from typing import Any, List
from datetime import datetime
import secrets
import string

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_

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
from app.schemas.enrollment import EnrollmentResponse, EnrollmentCreate, BulkEnrollmentCreate, BulkEnrollmentResponse
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
            detail="Course not found"
        )
    
    # Only allow enrollment in published courses
    if course.status != CourseStatus.PUBLISHED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only published courses are available for enrollment"
        )
    
    # Check if user is already enrolled
    existing_enrollment = db.query(Enrollment).filter(
        and_(
            Enrollment.user_id == current_user.id,
            Enrollment.course_id == course_id
        )
    ).first()
    
    if existing_enrollment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Already enrolled in this course"
        )
    
    # Create enrollment
    enrollment = Enrollment(
        user_id=current_user.id,
        course_id=course_id,
        status=EnrollmentStatus.ACTIVE
    )
    enrollment.start_enrollment()
    
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)
    
    return {
        "message": "Successfully enrolled in course",
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
            detail="Not enough permissions"
        )
    
    successful_enrollments = []
    failed_enrollments = []
    
    # Check if course exists and is published
    course = db.query(Course).filter(Course.id == assignment_data.course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    # Only allow assignment of published courses
    if course.status != CourseStatus.PUBLISHED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only published courses can be assigned to users"
        )
    
    for user_id in assignment_data.user_ids:
        try:
            # Check if user exists
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                failed_enrollments.append({
                    "user_id": user_id,
                    "course_id": assignment_data.course_id,
                    "error": "User not found"
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
            detail="Only administrators can mark courses as completed"
        )
    
    # Check if course exists
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    # Check if course type is optional or training
    if course.course_type not in [CourseType.OPTIONAL, CourseType.TRAINING]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only optional and training courses can be marked as completed"
        )
    
    # Check if user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
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
            detail="User is not enrolled in this course"
        )
    
    # Mark as completed
    enrollment.complete_enrollment()
    enrollment.progress = 100.0
    
    db.commit()
    db.refresh(enrollment)
    
    return {
        "message": "Course marked as completed successfully",
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
            detail="Course not found"
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
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not enrolled in this course"
        )
    
    # Start the enrollment if it's pending
    if enrollment.status == EnrollmentStatus.PENDING:
        enrollment.start_enrollment()
        db.commit()
        db.refresh(enrollment)
    
    return {
        "message": "Course started successfully",
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
            detail="Not enough permissions"
        )
    
    successful_enrollments = []
    failed_enrollments = []
    
    # Check if course exists and is published
    course = db.query(Course).filter(Course.id == assignment_data.course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    # Only allow assignment of published courses
    if course.status != CourseStatus.PUBLISHED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only published courses can be assigned to workers"
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
                    "error": "Worker not found"
                })
                continue
            
            # If worker is not registered, auto-register them
            if not worker.is_registered or not worker.user_id:
                # Create a temporary username based on document number
                temp_username = f"temp_{worker.document_number}"
                
                # Check if a user with this username already exists
                existing_user = db.query(User).filter(
                    (User.username == temp_username) | 
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
            
            # Check if already enrolled
            existing_enrollment = db.query(Enrollment).filter(
                and_(
                    Enrollment.user_id == worker.user_id,
                    Enrollment.course_id == assignment_data.course_id
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


@router.delete("/enrollment/{enrollment_id}")
async def cancel_enrollment(
    enrollment_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Cancel an enrollment (admin and capacitador roles only)
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
            detail="Enrollment not found"
        )
    
    enrollment.cancel_enrollment("Cancelled by administrator")
    db.commit()
    
    return MessageResponse(message="Enrollment cancelled successfully")


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
            detail="Course not found"
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
            detail="Worker not found"
        )
    
    # Check if worker has a user account
    if not worker.user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Worker is not registered in the system"
        )
    
    # Check if worker is enrolled in the course
    enrollment = db.query(Enrollment).filter(
        Enrollment.user_id == worker.user_id,
        Enrollment.course_id == course_id
    ).first()
    
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Worker is not enrolled in this course"
        )
    
    try:
        # Use a more detailed approach with logging
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"Starting removal of worker {worker_id} from course {course_id}")
        logger.info(f"Enrollment ID: {enrollment.id}")
        
        # Delete related attendance records first
        attendance_records = db.query(Attendance).filter(
            Attendance.enrollment_id == enrollment.id
        ).all()
        
        logger.info(f"Found {len(attendance_records)} attendance records to delete")
        for attendance in attendance_records:
            logger.info(f"Deleting attendance record {attendance.id}")
            db.delete(attendance)
        
        # Delete related user evaluations
        user_evaluations = db.query(UserEvaluation).filter(
            UserEvaluation.enrollment_id == enrollment.id
        ).all()
        
        logger.info(f"Found {len(user_evaluations)} user evaluations to delete")
        for user_evaluation in user_evaluations:
            logger.info(f"Deleting user evaluation {user_evaluation.id}")
            db.delete(user_evaluation)
        
        # Delete related user material progress
        user_progress_records = db.query(UserMaterialProgress).filter(
            UserMaterialProgress.enrollment_id == enrollment.id
        ).all()
        
        logger.info(f"Found {len(user_progress_records)} user progress records to delete")
        for progress in user_progress_records:
            logger.info(f"Deleting user progress record {progress.id}")
            db.delete(progress)
            
        # Delete related user surveys
        user_surveys = db.query(UserSurvey).filter(
            UserSurvey.enrollment_id == enrollment.id
        ).all()
        
        logger.info(f"Found {len(user_surveys)} user surveys to delete")
        for survey in user_surveys:
            logger.info(f"Deleting user survey {survey.id}")
            db.delete(survey)
        
        # Then delete the enrollment
        logger.info(f"Deleting enrollment {enrollment.id}")
        db.delete(enrollment)
        
        logger.info("Committing transaction")
        db.commit()
        
        logger.info("Worker successfully removed from course")
        return {
            "message": "Worker successfully removed from course",
            "worker_id": worker_id,
            "course_id": course_id,
            "reason": reason
        }
    except Exception as e:
        db.rollback()
        import traceback
        logger.error(f"Error removing worker from course: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error removing worker from course: {str(e)}"
        )