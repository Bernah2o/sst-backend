from typing import Any, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.database import get_db
from app.dependencies import get_current_active_user, require_admin
from app.models.user import User
from app.models.course import Course, CourseModule, CourseMaterial
from app.models.enrollment import Enrollment
from app.models.user_progress import UserMaterialProgress, UserModuleProgress, MaterialProgressStatus
from app.schemas.common import MessageResponse

router = APIRouter()


@router.post("/material/{material_id}/start")
async def start_material(
    material_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Mark material as started by user
    """
    # Get material and verify access
    material = db.query(CourseMaterial).filter(CourseMaterial.id == material_id).first()
    if not material:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Material not found"
        )
    
    # Get module and course
    module = db.query(CourseModule).filter(CourseModule.id == material.module_id).first()
    course = db.query(Course).filter(Course.id == module.course_id).first()
    
    # Check enrollment
    enrollment = db.query(Enrollment).filter(
        and_(
            Enrollment.user_id == current_user.id,
            Enrollment.course_id == course.id
        )
    ).first()
    
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enrolled in this course"
        )
    
    # Check if progress already exists
    existing_progress = db.query(UserMaterialProgress).filter(
        and_(
            UserMaterialProgress.user_id == current_user.id,
            UserMaterialProgress.material_id == material_id
        )
    ).first()
    
    if existing_progress:
        if existing_progress.status == MaterialProgressStatus.NOT_STARTED:
            existing_progress.start_material()
            db.commit()
            db.refresh(existing_progress)
        return {
            "message": "Material progress updated",
            "progress_id": existing_progress.id,
            "status": existing_progress.status
        }
    
    # Create new progress record
    progress = UserMaterialProgress(
        user_id=current_user.id,
        material_id=material_id,
        enrollment_id=enrollment.id
    )
    progress.start_material()
    
    db.add(progress)
    db.commit()
    db.refresh(progress)
    
    return {
        "message": "Material started successfully",
        "progress_id": progress.id,
        "status": progress.status
    }


@router.post("/material/{material_id}/complete")
async def complete_material(
    material_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Mark material as completed by user
    """
    # Get existing progress
    progress = db.query(UserMaterialProgress).filter(
        and_(
            UserMaterialProgress.user_id == current_user.id,
            UserMaterialProgress.material_id == material_id
        )
    ).first()
    
    if not progress:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Material progress not found. Start the material first."
        )
    
    # Complete the material
    progress.complete_material()
    db.commit()
    db.refresh(progress)
    
    # Update module progress
    material = db.query(CourseMaterial).filter(CourseMaterial.id == material_id).first()
    module_id = material.module_id
    
    # Check if all materials in module are completed
    module_materials = db.query(CourseMaterial).filter(CourseMaterial.module_id == module_id).all()
    completed_materials = db.query(UserMaterialProgress).filter(
        and_(
            UserMaterialProgress.user_id == current_user.id,
            UserMaterialProgress.material_id.in_([m.id for m in module_materials]),
            UserMaterialProgress.status == MaterialProgressStatus.COMPLETED
        )
    ).count()
    
    module_progress_percentage = (completed_materials / len(module_materials)) * 100 if module_materials else 0
    
    # Update or create module progress
    module_progress = db.query(UserModuleProgress).filter(
        and_(
            UserModuleProgress.user_id == current_user.id,
            UserModuleProgress.module_id == module_id
        )
    ).first()
    
    if not module_progress:
        module_progress = UserModuleProgress(
            user_id=current_user.id,
            module_id=module_id,
            enrollment_id=progress.enrollment_id
        )
        db.add(module_progress)
    
    module_progress.materials_completed = completed_materials
    module_progress.total_materials = len(module_materials)
    module_progress.calculate_progress()
    
    # Update overall course progress
    module = db.query(CourseModule).filter(CourseModule.id == module_id).first()
    course_modules = db.query(CourseModule).filter(CourseModule.course_id == module.course_id).all()
    
    # Calculate course progress as average of all module progress percentages
    total_progress = 0
    for course_module in course_modules:
        module_prog = db.query(UserModuleProgress).filter(
            and_(
                UserModuleProgress.user_id == current_user.id,
                UserModuleProgress.module_id == course_module.id
            )
        ).first()
        if module_prog:
            total_progress += module_prog.progress_percentage
    
    course_progress_percentage = total_progress / len(course_modules) if course_modules else 0
    
    # Update enrollment progress
    enrollment = db.query(Enrollment).filter(Enrollment.id == progress.enrollment_id).first()
    enrollment.update_progress(course_progress_percentage)
    
    if course_progress_percentage >= 100:
        enrollment.complete_enrollment()
    
    db.commit()
    
    return {
        "message": "Material completed successfully",
        "material_progress": progress.progress_percentage,
        "module_progress": module_progress.progress_percentage,
        "course_progress": course_progress_percentage,
        "course_completed": course_progress_percentage >= 100
    }


@router.put("/material/{material_id}/progress")
async def update_material_progress(
    material_id: int,
    progress_percentage: float,
    time_spent_seconds: int = 0,
    last_position: float = 0.0,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Update material progress (for videos, reading time, etc.)
    """
    # Get existing progress
    progress = db.query(UserMaterialProgress).filter(
        and_(
            UserMaterialProgress.user_id == current_user.id,
            UserMaterialProgress.material_id == material_id
        )
    ).first()
    
    if not progress:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Material progress not found. Start the material first."
        )
    
    # Update progress
    progress.update_progress(progress_percentage, time_spent_seconds, last_position)
    
    # Auto-complete if 100%
    if progress_percentage >= 100 and progress.status != MaterialProgressStatus.COMPLETED:
        progress.complete_material()
    
    db.commit()
    db.refresh(progress)
    
    return {
        "message": "Progress updated successfully",
        "progress_percentage": progress.progress_percentage,
        "status": progress.status,
        "time_spent_seconds": progress.time_spent_seconds
    }


@router.get("/course/{course_id}")
async def get_course_progress(
    course_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get detailed progress for a course
    """
    # Check enrollment (admins can view any course progress)
    enrollment = db.query(Enrollment).filter(
        and_(
            Enrollment.user_id == current_user.id,
            Enrollment.course_id == course_id
        )
    ).first()
    
    if not enrollment and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enrolled in this course"
        )
    
    # For admins without enrollment, show aggregated progress from all enrolled users
    if not enrollment and current_user.role == "admin":
        from app.models.enrollment import EnrollmentStatus
        
        # Get all enrollments for this course to show aggregated data
        all_enrollments = db.query(Enrollment).filter(Enrollment.course_id == course_id).all()
        
        class MockEnrollment:
            def __init__(self):
                self.id = 0
                self.progress = 100 if all_enrollments else 0  # Show 100% to enable admin features
                self.status = EnrollmentStatus.ACTIVE
        enrollment = MockEnrollment()
    
    # Get course modules
    modules = db.query(CourseModule).filter(CourseModule.course_id == course_id).all()
    
    modules_progress = []
    for module in modules:
        # Get module progress - for admins, show aggregated data
        if current_user.role == "admin" and not enrollment.id:
            # For admins, show if any user has completed the module
            any_module_completed = db.query(UserModuleProgress).filter(
                and_(
                    UserModuleProgress.module_id == module.id,
                    UserModuleProgress.status == MaterialProgressStatus.COMPLETED
                )
            ).first()
            module_progress = any_module_completed
        else:
            module_progress = db.query(UserModuleProgress).filter(
                and_(
                    UserModuleProgress.user_id == current_user.id,
                    UserModuleProgress.module_id == module.id
                )
            ).first()
        
        # Get materials progress
        materials = db.query(CourseMaterial).filter(CourseMaterial.module_id == module.id).all()
        materials_progress = []
        
        for material in materials:
            if current_user.role == "admin" and not enrollment.id:
                # For admins, show if any user has completed the material
                any_material_completed = db.query(UserMaterialProgress).filter(
                    and_(
                        UserMaterialProgress.material_id == material.id,
                        UserMaterialProgress.status == MaterialProgressStatus.COMPLETED
                    )
                ).first()
                material_progress = any_material_completed
            else:
                material_progress = db.query(UserMaterialProgress).filter(
                    and_(
                        UserMaterialProgress.user_id == current_user.id,
                        UserMaterialProgress.material_id == material.id
                    )
                ).first()
            
            materials_progress.append({
                "material_id": material.id,
                "title": material.title,
                "material_type": material.material_type.value,
                "progress_percentage": material_progress.progress_percentage if material_progress else 0,
                "status": material_progress.status if material_progress else MaterialProgressStatus.NOT_STARTED.value,
                "time_spent_seconds": material_progress.time_spent_seconds if material_progress else 0,
                "last_position": material_progress.last_position if material_progress else 0.0
            })
        
        modules_progress.append({
            "module_id": module.id,
            "title": module.title,
            "progress_percentage": module_progress.progress_percentage if module_progress else 0,
            "status": module_progress.status if module_progress else MaterialProgressStatus.NOT_STARTED.value,
            "materials": materials_progress
        })
    
    # Check for pending required surveys if course is completed
    pending_surveys = []
    if enrollment.progress >= 100:
        from app.models.survey import Survey, UserSurvey, SurveyStatus, UserSurveyStatus
        
        # Get required surveys for this course
        required_surveys = db.query(Survey).filter(
            and_(
                Survey.course_id == course_id,
                Survey.required_for_completion == True,
                Survey.status == SurveyStatus.PUBLISHED
            )
        ).all()
        
        # Check which surveys are still pending
        for survey in required_surveys:
            user_submission = db.query(UserSurvey).filter(
                and_(
                    UserSurvey.user_id == current_user.id,
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
    
    # Check if user has already completed the evaluation for this course
    evaluation_completed = False
    evaluation_score = None
    evaluation_status = "not_started"
    if enrollment.progress >= 100 and len(pending_surveys) == 0:
        from app.models.evaluation import Evaluation, UserEvaluation, UserEvaluationStatus
        from app.schemas.evaluation import EvaluationStatus
        
        # Get evaluations for this course
        course_evaluations = db.query(Evaluation).filter(
            and_(
                Evaluation.course_id == course_id,
                Evaluation.status == EvaluationStatus.PUBLISHED
            )
        ).all()
        
        # Check if user has completed any evaluation for this course
        for evaluation in course_evaluations:
            completed_evaluation = db.query(UserEvaluation).filter(
                and_(
                    UserEvaluation.user_id == current_user.id,
                    UserEvaluation.evaluation_id == evaluation.id,
                    UserEvaluation.status == UserEvaluationStatus.COMPLETED
                )
            ).first()
            
            if completed_evaluation:
                evaluation_completed = True
                evaluation_score = completed_evaluation.percentage
                evaluation_status = "completed"
                break
            else:
                # Check if user has started but not completed
                started_evaluation = db.query(UserEvaluation).filter(
                    and_(
                        UserEvaluation.user_id == current_user.id,
                        UserEvaluation.evaluation_id == evaluation.id
                    )
                ).first()
                if started_evaluation:
                    evaluation_status = "in_progress"
    
    # Check survey completion status
    survey_status = "not_started"
    completed_surveys_count = 0
    total_surveys_count = 0
    if enrollment.progress >= 100:
        from app.models.survey import Survey, UserSurvey, SurveyStatus, UserSurveyStatus
        
        # Get all surveys for this course (not just required ones)
        all_surveys = db.query(Survey).filter(
            and_(
                Survey.course_id == course_id,
                Survey.status == SurveyStatus.PUBLISHED
            )
        ).all()
        
        total_surveys_count = len(all_surveys)
        
        for survey in all_surveys:
            user_submission = db.query(UserSurvey).filter(
                and_(
                    UserSurvey.user_id == current_user.id,
                    UserSurvey.survey_id == survey.id,
                    UserSurvey.status == UserSurveyStatus.COMPLETED
                )
            ).first()
            
            if user_submission:
                completed_surveys_count += 1
        
        if completed_surveys_count == total_surveys_count and total_surveys_count > 0:
            survey_status = "completed"
        elif completed_surveys_count > 0:
            survey_status = "in_progress"
        elif total_surveys_count > 0:
            survey_status = "available"
    
    # Get course information for passing_score
    course = db.query(Course).filter(Course.id == course_id).first()
    
    # Recalculate course progress as average of all module progress percentages
    if modules_progress:
        total_module_progress = sum(module["progress_percentage"] for module in modules_progress)
        course_progress_percentage = total_module_progress / len(modules_progress)
    else:
        course_progress_percentage = 0
    
    # Update enrollment progress if it's different
    if enrollment and abs(enrollment.progress - course_progress_percentage) > 0.01:
        enrollment.progress = course_progress_percentage
        db.commit()
        db.refresh(enrollment)
    
    return {
        "course_id": course_id,
        "enrollment_id": enrollment.id,
        "overall_progress": course_progress_percentage,
        "status": enrollment.status,
        "modules": modules_progress,
        "can_take_survey": course_progress_percentage >= 100,
        "can_take_evaluation": course_progress_percentage >= 100 and len(pending_surveys) == 0 and not evaluation_completed,  # Can only take evaluation after completing required surveys and if not already completed
        "pending_surveys": pending_surveys,
        "course_completed": course_progress_percentage >= 100 and len(pending_surveys) == 0,
        "evaluation_completed": evaluation_completed,
        "evaluation_score": evaluation_score,
        "evaluation_status": evaluation_status,
        "survey_status": survey_status,
        "completed_surveys_count": completed_surveys_count,
        "total_surveys_count": total_surveys_count,
        "passing_score": course.passing_score if course else 70.0
    }


@router.get("/user/dashboard")
async def get_user_dashboard(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get user dashboard with all course progress including module details
    """
    # Get all user enrollments
    enrollments = db.query(Enrollment).filter(Enrollment.user_id == current_user.id).all()
    
    courses_progress = []
    for enrollment in enrollments:
        course = db.query(Course).filter(Course.id == enrollment.course_id).first()
        
        # Get course modules with progress
        modules = db.query(CourseModule).filter(CourseModule.course_id == course.id).all()
        modules_progress = []
        
        for module in modules:
            # Get module progress
            module_progress = db.query(UserModuleProgress).filter(
                and_(
                    UserModuleProgress.user_id == current_user.id,
                    UserModuleProgress.module_id == module.id
                )
            ).first()
            
            # Get materials count and completed count for this module
            materials = db.query(CourseMaterial).filter(CourseMaterial.module_id == module.id).all()
            completed_materials = 0
            
            for material in materials:
                material_progress = db.query(UserMaterialProgress).filter(
                    and_(
                        UserMaterialProgress.user_id == current_user.id,
                        UserMaterialProgress.material_id == material.id,
                        UserMaterialProgress.status == MaterialProgressStatus.COMPLETED
                    )
                ).first()
                
                if material_progress:
                    completed_materials += 1
            
            modules_progress.append({
                "module_id": module.id,
                "title": module.title,
                "description": module.description,
                "progress_percentage": module_progress.progress_percentage if module_progress else 0,
                "status": module_progress.status if module_progress else MaterialProgressStatus.NOT_STARTED.value,
                "total_materials": len(materials),
                "completed_materials": completed_materials,
                "started_at": module_progress.started_at.isoformat() if module_progress and module_progress.started_at else None,
                "completed_at": module_progress.completed_at.isoformat() if module_progress and module_progress.completed_at else None
            })
        
        courses_progress.append({
            "course_id": course.id,
            "course_title": course.title,
            "course_type": course.course_type.value,
            "enrollment_status": enrollment.status,
            "progress_percentage": enrollment.progress,
            "enrolled_at": enrollment.enrolled_at.isoformat() if enrollment.enrolled_at else None,
            "started_at": enrollment.started_at.isoformat() if enrollment.started_at else None,
            "completed_at": enrollment.completed_at.isoformat() if enrollment.completed_at else None,
            "grade": enrollment.grade,
            "modules": modules_progress
        })
    
    return {
        "user_id": current_user.id,
        "total_courses": len(courses_progress),
        "completed_courses": len([c for c in courses_progress if c["progress_percentage"] >= 100]),
        "in_progress_courses": len([c for c in courses_progress if 0 < c["progress_percentage"] < 100]),
        "courses": courses_progress
    }


@router.post("/admin/material/{material_id}/reset/{user_id}")
async def reset_material_progress(
    material_id: int,
    user_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
) -> Any:
    """
    Reset material progress for a specific user (Admin only)
    """
    # Verify the target user exists
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Verify the material exists
    material = db.query(CourseMaterial).filter(CourseMaterial.id == material_id).first()
    if not material:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Material not found"
        )
    
    # Get existing progress
    progress = db.query(UserMaterialProgress).filter(
        and_(
            UserMaterialProgress.user_id == user_id,
            UserMaterialProgress.material_id == material_id
        )
    ).first()
    
    if not progress:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Material progress not found for this user"
        )
    
    # Reset the progress
    progress.status = MaterialProgressStatus.NOT_STARTED
    progress.progress_percentage = 0.0
    progress.started_at = None
    progress.completed_at = None
    progress.time_spent_seconds = 0
    progress.last_position = 0.0
    progress.attempts = 0
    
    # Ensure material_id is not null
    if progress.material_id is None:
        print(f"WARNING: material_id was None for progress ID {progress.id}, setting to {material_id}")
        progress.material_id = material_id
    
    db.commit()
    db.refresh(progress)
    
    # Recalculate module progress
    module_id = material.module_id
    module_materials = db.query(CourseMaterial).filter(CourseMaterial.module_id == module_id).all()
    completed_materials = db.query(UserMaterialProgress).filter(
        and_(
            UserMaterialProgress.user_id == user_id,
            UserMaterialProgress.material_id.in_([m.id for m in module_materials]),
            UserMaterialProgress.status == MaterialProgressStatus.COMPLETED
        )
    ).count()
    
    # Update module progress
    module_progress = db.query(UserModuleProgress).filter(
        and_(
            UserModuleProgress.user_id == user_id,
            UserModuleProgress.module_id == module_id
        )
    ).first()
    
    if module_progress:
        # Ensure module_id is not null
        if module_progress.module_id is None:
            print(f"WARNING: module_id was None for module progress, setting to {module_id}")
            module_progress.module_id = module_id
            
        module_progress.materials_completed = completed_materials
        module_progress.total_materials = len(module_materials)
        module_progress.calculate_progress()
        
        # Log for debugging
        print(f"Updated module progress: module_id={module_progress.module_id}, status={module_progress.status}, progress={module_progress.progress_percentage}%")
        
        # If no materials are completed, reset module status
        if completed_materials == 0:
            module_progress.status = MaterialProgressStatus.NOT_STARTED
            module_progress.started_at = None
            module_progress.completed_at = None
        
        # Log for debugging
        print(f"Updated module progress: module_id={module_progress.module_id}, status={module_progress.status}, progress={module_progress.progress_percentage}%")
    
    # Recalculate course progress
    module = db.query(CourseModule).filter(CourseModule.id == module_id).first()
    course_modules = db.query(CourseModule).filter(CourseModule.course_id == module.course_id).all()
    
    # Calculate course progress as average of all module progress percentages
    total_progress = 0
    for course_module in course_modules:
        module_prog = db.query(UserModuleProgress).filter(
            and_(
                UserModuleProgress.user_id == user_id,
                UserModuleProgress.module_id == course_module.id
            )
        ).first()
        if module_prog:
            total_progress += module_prog.progress_percentage
    
    course_progress_percentage = total_progress / len(course_modules) if course_modules else 0
    
    # Update enrollment progress
    enrollment = db.query(Enrollment).filter(
        and_(
            Enrollment.user_id == user_id,
            Enrollment.course_id == module.course_id
        )
    ).first()
    
    if enrollment:
        enrollment.update_progress(course_progress_percentage)
        
        # If course progress drops below 100%, reset completion status
        if course_progress_percentage < 100 and enrollment.completed_at:
            enrollment.completed_at = None
            enrollment.status = "in_progress" if course_progress_percentage > 0 else "enrolled"
    
    db.commit()
    
    return {
        "message": f"Material progress reset successfully for user {target_user.full_name}",
        "material_id": material_id,
        "user_id": user_id,
        "material_title": material.title,
        "user_name": target_user.full_name,
        "new_status": progress.status,
        "module_progress": module_progress.progress_percentage if module_progress else 0,
        "course_progress": course_progress_percentage
    }