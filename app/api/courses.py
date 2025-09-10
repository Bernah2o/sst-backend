from typing import Any, List, Union
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_
import os

from app.database import get_db
from app.dependencies import get_current_active_user
from app.models.user import User


def check_and_complete_course(db: Session, user_id: int, course_id: int):
    """Check if course is truly completed and mark enrollment as completed if so"""
    enrollment = db.query(Enrollment).filter(
        and_(
            Enrollment.user_id == user_id,
            Enrollment.course_id == course_id,
            Enrollment.status == EnrollmentStatus.ACTIVE
        )
    ).first()
    
    if not enrollment or enrollment.progress < 95:
        return False
    
    from app.models.survey import Survey, UserSurvey, SurveyStatus, UserSurveyStatus
    from app.models.evaluation import Evaluation, UserEvaluation, UserEvaluationStatus
    from app.schemas.evaluation import EvaluationStatus
    
    # Check required surveys
    required_surveys = db.query(Survey).filter(
        and_(
            Survey.course_id == course_id,
            Survey.required_for_completion == True,
            Survey.status == SurveyStatus.PUBLISHED
        )
    ).all()
    
    surveys_completed = True
    for survey in required_surveys:
        user_submission = db.query(UserSurvey).filter(
            and_(
                UserSurvey.user_id == user_id,
                UserSurvey.survey_id == survey.id,
                UserSurvey.status == UserSurveyStatus.COMPLETED
            )
        ).first()
        if not user_submission:
            surveys_completed = False
            break
    
    # Check evaluation if surveys are completed
    evaluation_completed = True
    if surveys_completed:
        course_evaluations = db.query(Evaluation).filter(
            and_(
                Evaluation.course_id == course_id,
                Evaluation.status == EvaluationStatus.PUBLISHED
            )
        ).all()
        
        if course_evaluations:  # If there are evaluations, check if completed
            evaluation_completed = False
            for evaluation in course_evaluations:
                completed_evaluation = db.query(UserEvaluation).filter(
                    and_(
                        UserEvaluation.user_id == user_id,
                        UserEvaluation.evaluation_id == evaluation.id,
                        UserEvaluation.status == UserEvaluationStatus.COMPLETED
                    )
                ).first()
                if completed_evaluation:
                    evaluation_completed = True
                    break
    
    # Complete enrollment if all requirements are met
    if surveys_completed and evaluation_completed:
        enrollment.complete_enrollment()
        db.commit()
        return True
    
    return False
from app.models.course import (
    Course,
    CourseModule,
    CourseMaterial,
    CourseStatus,
    CourseType,
)
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.schemas.report import AttendanceReportResponse
from app.schemas.common import PaginatedResponse
from app.models.attendance import Attendance, AttendanceStatus
from app.models.user_progress import UserMaterialProgress, MaterialProgressStatus
from app.schemas.common import MessageResponse, PaginatedResponse
from app.utils.storage import storage_manager
from app.config import settings
import os
from urllib.parse import urlparse
from app.schemas.course import (
    CourseCreate,
    CourseUpdate,
    CourseResponse,
    CourseListResponse,
    UserCourseResponse,
    CourseModuleCreate,
    CourseModuleUpdate,
    CourseModuleResponse,
    CourseMaterialCreate,
    CourseMaterialUpdate,
    CourseMaterialResponse,
    CourseMaterialWithProgressResponse,
)
from app.schemas.report import AttendanceReportResponse

router = APIRouter()


@router.get("/", response_model=PaginatedResponse[CourseListResponse])
@router.get("", response_model=PaginatedResponse[CourseListResponse])
async def get_courses(
    skip: int = 0,
    limit: int = 100,
    search: str = None,
    course_type: CourseType = None,
    status: CourseStatus = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get all courses with optional filtering
    """
    query = db.query(Course)

    # Apply filters
    if search:
        query = query.filter(
            or_(
                Course.title.ilike(f"%{search}%"),
                Course.description.ilike(f"%{search}%"),
            )
        )

    if course_type:
        query = query.filter(Course.course_type == course_type)

    if status:
        query = query.filter(Course.status == status)
    else:
        # Only show published courses for users who are not admin or capacitador
        if current_user.role.value not in ["admin", "capacitador"]:
            query = query.filter(Course.status == CourseStatus.PUBLISHED)

    # Get total count
    total = query.count()

    # Apply pagination and eager load modules
    courses = query.options(joinedload(Course.modules)).offset(skip).limit(limit).all()

    # Calculate pagination info
    page = (skip // limit) + 1 if limit > 0 else 1
    size = limit
    pages = (total + limit - 1) // limit if limit > 0 else 1
    has_next = skip + limit < total
    has_prev = skip > 0

    return PaginatedResponse(
        items=courses,
        total=total,
        page=page,
        size=size,
        pages=pages,
        has_next=has_next,
        has_prev=has_prev,
    )


@router.post("/", response_model=CourseResponse)
@router.post("", response_model=CourseResponse)
async def create_course(
    course_data: CourseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    Create new course (admin and capacitador roles only)
    """
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Permisos insuficientes"
        )

    # Create new course
    course = Course(**course_data.dict(), created_by=current_user.id)

    db.add(course)
    db.commit()
    db.refresh(course)

    return CourseResponse.from_orm(course)


@router.get("/user{trailing_slash:path}", response_model=List[UserCourseResponse])
async def get_user_courses(
    trailing_slash: str = "",
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get courses for current user (only published courses)
    """
    # Get all enrollments for the current user
    enrollments = (
        db.query(Enrollment).filter(Enrollment.user_id == current_user.id).all()
    )

    # Get the courses for these enrollments, but only published courses
    course_ids = [enrollment.course_id for enrollment in enrollments]
    courses = (
        db.query(Course)
        .filter(
            and_(Course.id.in_(course_ids), Course.status == CourseStatus.PUBLISHED)
        )
        .all()
    )

    # Create UserCourseResponse objects with enrollment data
    user_courses = []
    for course in courses:
        enrollment = next((e for e in enrollments if e.course_id == course.id), None)
        if enrollment:
            user_course = UserCourseResponse(
                id=course.id,
                title=course.title,
                description=course.description,
                course_type=course.course_type,
                status=course.status,
                duration_hours=course.duration_hours,
                is_mandatory=course.is_mandatory,
                thumbnail=course.thumbnail,
                created_at=course.created_at,
                published_at=course.published_at,
                modules=course.modules,  # Include modules
                progress=enrollment.progress,
                enrolled_at=enrollment.enrolled_at,
                completed=enrollment.status == EnrollmentStatus.COMPLETED.value,
            )
            user_courses.append(user_course)

    return user_courses


@router.get("/{course_id}", response_model=Union[CourseResponse, UserCourseResponse])
async def get_course(
    course_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get course by ID
    """
    course = db.query(Course).filter(Course.id == course_id).first()

    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Curso no encontrado"
        )

    # Check if user can access this course
    if current_user.role.value not in ["admin", "capacitador"]:
        # For non-admin users, check if course is published AND user is enrolled
        if course.status != CourseStatus.PUBLISHED:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Curso no disponible"
            )
        
        # Check if user is enrolled in the course
        enrollment = db.query(Enrollment).filter(
            and_(
                Enrollment.user_id == current_user.id,
                Enrollment.course_id == course_id
            )
        ).first()
        
        if not enrollment:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="No está inscrito en este curso"
            )
        
        # Check if course is truly completed (materials + surveys + evaluation + certificate)
        course_truly_completed = False
        if enrollment.progress >= 95:  # Only check if materials are completed
            from app.models.survey import Survey, UserSurvey, SurveyStatus, UserSurveyStatus
            from app.models.evaluation import Evaluation, UserEvaluation, UserEvaluationStatus
            from app.schemas.evaluation import EvaluationStatus
            
            # Check required surveys
            required_surveys = db.query(Survey).filter(
                and_(
                    Survey.course_id == course_id,
                    Survey.required_for_completion == True,
                    Survey.status == SurveyStatus.PUBLISHED
                )
            ).all()
            
            surveys_completed = True
            for survey in required_surveys:
                user_submission = db.query(UserSurvey).filter(
                    and_(
                        UserSurvey.user_id == current_user.id,
                        UserSurvey.survey_id == survey.id,
                        UserSurvey.status == UserSurveyStatus.COMPLETED
                    )
                ).first()
                if not user_submission:
                    surveys_completed = False
                    break
            
            # Check evaluation if surveys are completed
            evaluation_completed = True
            if surveys_completed:
                course_evaluations = db.query(Evaluation).filter(
                    and_(
                        Evaluation.course_id == course_id,
                        Evaluation.status == EvaluationStatus.PUBLISHED
                    )
                ).all()
                
                if course_evaluations:  # If there are evaluations, check if completed
                    evaluation_completed = False
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
                            break
            
            # Course is truly completed only if materials, surveys, and evaluations are done
            course_truly_completed = surveys_completed and evaluation_completed
        
        # Return UserCourseResponse with progress information for enrolled users
        return UserCourseResponse(
            id=course.id,
            title=course.title,
            description=course.description,
            course_type=course.course_type,
            status=course.status,
            duration_hours=course.duration_hours,
            is_mandatory=course.is_mandatory,
            thumbnail=course.thumbnail,
            created_at=course.created_at,
            published_at=course.published_at,
            modules=course.modules,
            progress=enrollment.progress,
            enrolled_at=enrollment.enrolled_at,
            completed=course_truly_completed,
        )
    
    # For admin/capacitador users, return CourseResponse without progress
    return CourseResponse.from_orm(course)


@router.put("/{course_id}", response_model=CourseResponse)
async def update_course(
    course_id: int,
    course_data: CourseUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Update course (admin and capacitador roles only)
    """
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Permisos insuficientes"
        )

    course = db.query(Course).filter(Course.id == course_id).first()

    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Curso no encontrado"
        )

    # Update course fields
    update_data = course_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(course, field, value)

    db.commit()
    db.refresh(course)

    return CourseResponse.from_orm(course)


@router.delete("/{course_id}", response_model=MessageResponse)
async def delete_course(
    course_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Delete course (admin and capacitador roles only)
    """
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Permisos insuficientes"
        )

    course = db.query(Course).filter(Course.id == course_id).first()

    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Curso no encontrado"
        )

    # Check if course has enrolled users
    from app.models.enrollment import Enrollment

    enrolled_count = (
        db.query(Enrollment).filter(Enrollment.course_id == course_id).count()
    )

    if enrolled_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede eliminar el curso porque tiene {enrolled_count} empleado(s) asignado(s). Primero debe desasignar a todos los empleados.",
        )

    # Check if course status allows deletion (only draft or archived)
    if course.status not in [CourseStatus.DRAFT, CourseStatus.ARCHIVED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se pueden eliminar cursos en estado 'Borrador' o 'Archivado'. Cambie el estado del curso antes de eliminarlo.",
        )

    # Since modules and materials have cascade="all, delete-orphan", they will be deleted automatically
    # We only need to handle the course deletion itself
    try:
        db.delete(course)
        db.commit()

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al eliminar el curso: {str(e)}",
        )

    return MessageResponse(message="Curso eliminado exitosamente")


# Course Module endpoints
@router.post("/{course_id}/modules", response_model=CourseModuleResponse)
async def create_course_module(
    course_id: int,
    module_data: CourseModuleCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Create new course module (admin and capacitador roles only)
    """
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Permisos insuficientes"
        )

    # Check if course exists
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Course not found"
        )

    # Create new module
    module = CourseModule(**module_data.dict(), course_id=course_id)

    db.add(module)
    db.commit()
    db.refresh(module)

    return module


@router.get("/{course_id}/modules", response_model=List[CourseModuleResponse])
async def get_course_modules(
    course_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get all modules for a course
    """
    # Check if course exists
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Course not found"
        )

    # Check if user can access this course
    if current_user.role.value not in ["admin", "capacitador"]:
        # For non-admin users, check if course is published AND user is enrolled
        if course.status != CourseStatus.PUBLISHED:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Curso no disponible"
            )
        
        # Check if user is enrolled in the course
        enrollment = db.query(Enrollment).filter(
            and_(
                Enrollment.user_id == current_user.id,
                Enrollment.course_id == course_id
            )
        ).first()
        
        if not enrollment:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="No está inscrito en este curso"
            )

    modules = (
        db.query(CourseModule)
        .filter(CourseModule.course_id == course_id)
        .order_by(CourseModule.order_index)
        .all()
    )

    return modules


@router.put("/modules/{module_id}", response_model=CourseModuleResponse)
async def update_course_module(
    module_id: int,
    module_data: CourseModuleUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Update course module (admin and capacitador roles only)
    """
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    module = db.query(CourseModule).filter(CourseModule.id == module_id).first()

    if not module:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Módulo no encontrado"
        )

    # Update module fields
    update_data = module_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(module, field, value)

    db.commit()
    db.refresh(module)

    return module


@router.delete("/modules/{module_id}", response_model=MessageResponse)
async def delete_course_module(
    module_id: int,
    force: bool = Query(
        False, description="Forzar eliminación incluso si hay registros de progreso"
    ),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Delete course module (admin and capacitador roles only)
    """
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    module = db.query(CourseModule).filter(CourseModule.id == module_id).first()

    if not module:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Módulo no encontrado"
        )

    try:
        # Importar modelos de progreso
        from app.models.user_progress import UserModuleProgress, UserMaterialProgress

        # Obtener todos los materiales del módulo
        materials = (
            db.query(CourseMaterial).filter(CourseMaterial.module_id == module_id).all()
        )
        material_ids = [material.id for material in materials]

        if force:
            # Si force=True, eliminar primero los registros de progreso relacionados
            # Eliminar registros de progreso de materiales primero
            if material_ids:
                material_progress_records = (
                    db.query(UserMaterialProgress)
                    .filter(UserMaterialProgress.material_id.in_(material_ids))
                    .all()
                )

                for progress in material_progress_records:
                    db.delete(progress)

            # Eliminar registros de progreso de módulos
            module_progress_records = (
                db.query(UserModuleProgress)
                .filter(UserModuleProgress.module_id == module_id)
                .all()
            )

            for progress in module_progress_records:
                db.delete(progress)

            # Eliminar los materiales del módulo
            for material in materials:
                db.delete(material)

            db.flush()
        else:
            # Si no se está forzando, verificar si hay registros de progreso
            has_progress = False

            # Verificar progreso de materiales
            if material_ids:
                material_progress_count = (
                    db.query(UserMaterialProgress)
                    .filter(UserMaterialProgress.material_id.in_(material_ids))
                    .count()
                )
                if material_progress_count > 0:
                    has_progress = True

            # Verificar progreso de módulos
            module_progress_count = (
                db.query(UserModuleProgress)
                .filter(UserModuleProgress.module_id == module_id)
                .count()
            )
            if module_progress_count > 0:
                has_progress = True

            if has_progress:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No se puede eliminar el módulo porque hay registros de progreso asociados. Use force=true para forzar la eliminación.",
                )

        # Ahora eliminar el módulo
        db.delete(module)
        db.commit()

        return MessageResponse(message="Módulo eliminado exitosamente")

    except HTTPException:
        # Re-lanzar HTTPExceptions sin modificar
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al eliminar el módulo: {str(e)}",
        )


@router.get(
    "/modules/{module_id}/materials",
    response_model=List[CourseMaterialWithProgressResponse]
)
async def get_module_materials(
    module_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get all materials for a module
    """
    # Check if module exists
    module = db.query(CourseModule).filter(CourseModule.id == module_id).first()
    if not module:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Module not found"
        )

    # Check if user can access this course
    course = db.query(Course).filter(Course.id == module.course_id).first()
    if current_user.role.value not in ["admin", "capacitador"]:
        # For non-admin users, check if course is published AND user is enrolled
        if course.status != CourseStatus.PUBLISHED:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Course not available"
            )
        
        # Check if user is enrolled in the course
        enrollment = db.query(Enrollment).filter(
            and_(
                Enrollment.user_id == current_user.id,
                Enrollment.course_id == module.course_id
            )
        ).first()
        
        if not enrollment:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Not enrolled in this course"
            )

    materials = (
        db.query(CourseMaterial)
        .filter(CourseMaterial.module_id == module_id)
        .order_by(CourseMaterial.order_index)
        .all()
    )
    
    # Para usuarios no administradores, añadir información de progreso
    if current_user.role.value not in ["admin", "capacitador"]:
        result = []
        for material in materials:
            # Buscar progreso del material
            material_progress = db.query(UserMaterialProgress).filter(
                and_(
                    UserMaterialProgress.user_id == current_user.id,
                    UserMaterialProgress.material_id == material.id
                )
            ).first()
            
            # Crear objeto de respuesta manualmente
            material_response = CourseMaterialWithProgressResponse(
                id=material.id,
                module_id=material.module_id,
                title=material.title,
                description=material.description,
                material_type=material.material_type,
                file_url=material.file_url,
                order_index=material.order_index,
                is_downloadable=material.is_downloadable,
                is_required=material.is_required,
                created_at=material.created_at,
                updated_at=material.updated_at,
                completed=material_progress is not None and material_progress.status == MaterialProgressStatus.COMPLETED,
                progress=material_progress.progress_percentage if material_progress else 0
            )
            
            result.append(material_response)
        return result
    
    # Para administradores, convertir a CourseMaterialResponse
    result = []
    for material in materials:
        material_response = CourseMaterialResponse(
            id=material.id,
            module_id=material.module_id,
            title=material.title,
            description=material.description,
            material_type=material.material_type,
            file_url=material.file_url,
            order_index=material.order_index,
            is_downloadable=material.is_downloadable,
            is_required=material.is_required,
            created_at=material.created_at,
            updated_at=material.updated_at
        )
        result.append(material_response)
    
    return result


@router.post("/modules/{module_id}/materials", response_model=CourseMaterialResponse)
async def create_course_material(
    module_id: int,
    material_data: CourseMaterialCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Create new course material (admin and capacitador roles only)
    """
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    # Check if module exists
    module = db.query(CourseModule).filter(CourseModule.id == module_id).first()
    if not module:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Module not found"
        )

    # Create new material
    material = CourseMaterial(
        **material_data.dict(exclude={"module_id"}), module_id=module_id
    )

    db.add(material)
    db.commit()
    db.refresh(material)

    # Create response manually to avoid serialization issues with SQLAlchemy relationships
    return CourseMaterialResponse(
        id=material.id,
        title=material.title,
        description=material.description,
        material_type=material.material_type,
        file_url=material.file_url,
        order_index=material.order_index,
        is_downloadable=material.is_downloadable,
        is_required=material.is_required,
        module_id=material.module_id,
        created_at=material.created_at,
        updated_at=material.updated_at
    )


@router.put("/materials/{material_id}", response_model=CourseMaterialResponse)
async def update_course_material(
    material_id: int,
    material_data: CourseMaterialUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Update course material (admin and capacitador roles only)
    """
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    material = db.query(CourseMaterial).filter(CourseMaterial.id == material_id).first()

    if not material:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Material no encontrado"
        )

    # Update material fields
    update_data = material_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(material, field, value)

    db.commit()
    db.refresh(material)

    # Create response manually to avoid serialization issues with SQLAlchemy relationships
    return CourseMaterialResponse(
        id=material.id,
        title=material.title,
        description=material.description,
        material_type=material.material_type,
        file_url=material.file_url,
        order_index=material.order_index,
        is_downloadable=material.is_downloadable,
        is_required=material.is_required,
        module_id=material.module_id,
        created_at=material.created_at,
        updated_at=material.updated_at
    )


@router.delete("/materials/{material_id}", response_model=MessageResponse)
async def delete_course_material(
    material_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Delete course material (admin and capacitador roles only)
    """
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    material = db.query(CourseMaterial).filter(CourseMaterial.id == material_id).first()

    if not material:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Material not found"
        )

    try:
        # Store module_id before deleting the material
        module_id = material.module_id
        user_ids = []

        # First delete all user progress records for this material
        from app.models.user_progress import UserMaterialProgress, UserModuleProgress

        progress_records = (
            db.query(UserMaterialProgress)
            .filter(UserMaterialProgress.material_id == material_id)
            .all()
        )

        for progress in progress_records:
            user_ids.append(progress.user_id)
            db.delete(progress)

        # Delete file from storage before deleting the material record
        if material.file_url:
            try:
                # Determine if file is stored in Firebase or locally
                if material.file_url.startswith("http"):
                    # Firebase Storage - extract path from URL
                    parsed_url = urlparse(material.file_url)
                    if "firebase" in parsed_url.netloc or "googleapis.com" in parsed_url.netloc:
                        # Extract Firebase path from URL
                        # URL format: https://storage.googleapis.com/bucket-name/path/to/file
                        # or https://firebasestorage.googleapis.com/v0/b/bucket-name/o/path%2Fto%2Ffile
                        if "googleapis.com" in parsed_url.netloc:
                            # Extract path after bucket name
                            path_parts = parsed_url.path.strip('/').split('/', 1)
                            if len(path_parts) > 1:
                                firebase_path = path_parts[1]
                            else:
                                firebase_path = parsed_url.path.strip('/')
                        else:
                            firebase_path = parsed_url.path.strip('/')
                        
                        # Delete from Firebase Storage
                        await storage_manager.delete_file(firebase_path, "firebase")
                else:
                    # Local storage - file_url contains relative path
                    if material.file_url.startswith("/uploads/"):
                        # Remove leading slash and construct full path
                        relative_path = material.file_url.lstrip("/")
                        local_file_path = os.path.join(settings.upload_dir, relative_path.replace("uploads/", ""))
                    elif material.file_url.startswith("/static/"):
                        # Static file
                        relative_path = material.file_url.lstrip("/")
                        local_file_path = os.path.join("static", relative_path.replace("static/", ""))
                    else:
                        # Direct file path
                        local_file_path = material.file_url
                    
                    # Delete from local storage
                    await storage_manager.delete_file(local_file_path, "local")
                    
            except Exception as e:
                # Continue with database deletion even if file deletion fails
                pass

        # Then delete the material
        db.delete(material)
        db.commit()

        # Update module progress for all affected users
        if module_id and user_ids:
            user_ids = list(set(user_ids))  # Remove duplicates
            for user_id in user_ids:
                # Get all materials in the module
                module_materials = (
                    db.query(CourseMaterial)
                    .filter(CourseMaterial.module_id == module_id)
                    .all()
                )

                # Count completed materials for this user
                completed_materials = (
                    db.query(UserMaterialProgress)
                    .filter(
                        UserMaterialProgress.user_id == user_id,
                        UserMaterialProgress.material_id.in_(
                            [m.id for m in module_materials]
                        ),
                        UserMaterialProgress.status == MaterialProgressStatus.COMPLETED,
                    )
                    .count()
                )

                # Update module progress
                module_progress = (
                    db.query(UserModuleProgress)
                    .filter(
                        UserModuleProgress.user_id == user_id,
                        UserModuleProgress.module_id == module_id,
                    )
                    .first()
                )

                if module_progress:
                    module_progress.materials_completed = completed_materials
                    module_progress.total_materials = len(module_materials)
                    module_progress.calculate_progress()
                    db.commit()

        return MessageResponse(message="Material deleted successfully")
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al eliminar el material: {str(e)}",
        )


@router.get("/{course_id}/validation")
async def validate_course_requirements(
    course_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Validate if course has required surveys and evaluations for publication
    """
    # Check if course exists
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Curso no encontrado"
        )
    
    # Check if user has permission to validate this course
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permisos insuficientes"
        )
    
    # Check for associated surveys
    from app.models.survey import Survey, SurveyStatus
    surveys = db.query(Survey).filter(
        and_(
            Survey.course_id == course_id,
            Survey.status == SurveyStatus.PUBLISHED
        )
    ).all()
    
    # Check for associated evaluations
    from app.models.evaluation import Evaluation
    from app.schemas.evaluation import EvaluationStatus
    evaluations = db.query(Evaluation).filter(
        and_(
            Evaluation.course_id == course_id,
            Evaluation.status == EvaluationStatus.PUBLISHED
        )
    ).all()
    
    # Determine if course requires full process
    requires_full_process = (
        course.course_type in [CourseType.INDUCTION, CourseType.REINDUCTION] or 
        course.is_mandatory
    )
    
    has_surveys = len(surveys) > 0
    has_evaluations = len(evaluations) > 0
    
    return {
        "course_id": course_id,
        "course_title": course.title,
        "requires_full_process": requires_full_process,
        "has_surveys": has_surveys,
        "has_evaluations": has_evaluations,
        "surveys_count": len(surveys),
        "evaluations_count": len(evaluations),
        "can_publish": not requires_full_process or (has_surveys and has_evaluations),
        "missing_requirements": [
            "surveys" if requires_full_process and not has_surveys else None,
            "evaluations" if requires_full_process and not has_evaluations else None
        ],
        "surveys": [{
            "id": survey.id,
            "title": survey.title,
            "status": survey.status.value
        } for survey in surveys],
        "evaluations": [{
            "id": evaluation.id,
            "title": evaluation.title,
            "status": evaluation.status.value
        } for evaluation in evaluations]
    }


@router.get("/{course_id}/attendance-report", response_model=Union[PaginatedResponse, None])
async def get_course_attendance_report(
    course_id: int,
    skip: int = 0,
    limit: int = 100,
    format: str = "json",
    download: bool = Query(False, description="Set to true to download the file with a custom filename"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get attendance report for a specific course
    """
    # Check if course exists
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    # Check permissions
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # Get all enrolled users for this course
    enrolled_users_query = db.query(
        User.id,
        User.email,
        User.first_name,
        User.last_name,
        User.document_number,
        User.position,
        User.department.label("area"),
        Enrollment.id.label("enrollment_id")
    ).join(
        Enrollment, User.id == Enrollment.user_id
    ).filter(
        Enrollment.course_id == course_id,
        Enrollment.status == EnrollmentStatus.ACTIVE
    )
    
    # Get total count of enrolled users
    total_enrolled = enrolled_users_query.count()
    
    if total_enrolled == 0:
        if format == "pdf":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No se encontraron usuarios inscritos para este curso"
            )
        return PaginatedResponse(
            items=[],
            total=0,
            page=1,
            size=limit,
            pages=0,
            has_next=False,
            has_prev=False
        )
    
    # Get all enrolled users for PDF generation or paginated users for API response
    if format == "pdf":
        enrolled_users = enrolled_users_query.all()
    else:
        enrolled_users = enrolled_users_query.offset(skip).limit(limit).all()
    
    # Get attendance records for these users
    user_ids = [user.id for user in enrolled_users]
    attendance_records = db.query(Attendance).filter(
        Attendance.user_id.in_(user_ids),
        Attendance.course_id == course_id
    ).all()
    
    # Create a mapping of user_id to attendance records
    attendance_by_user = {}
    for record in attendance_records:
        if record.user_id not in attendance_by_user:
            attendance_by_user[record.user_id] = []
        attendance_by_user[record.user_id].append(record)
    
    # Build the response
    attendance_reports = []
    for user in enrolled_users:
        user_attendance = attendance_by_user.get(user.id, [])
        
        if user_attendance:
            # If user has attendance records, include them
            for record in user_attendance:
                attendance_reports.append(AttendanceReportResponse(
                    attendance_id=record.id,
                    user_id=user.id,
                    username=user.email,
                    full_name=f"{user.first_name} {user.last_name}",
                    course_title=course.title,
                    date=record.session_date.date() if record.session_date else None,
                    status=record.status.value,
                    check_in_time=record.check_in_time,
                    check_out_time=record.check_out_time,
                    notes=record.notes
                ))
        else:
            # If user has no attendance records, show as not registered
            attendance_reports.append(AttendanceReportResponse(
                attendance_id=0,  # No attendance record
                user_id=user.id,
                username=user.email,
                full_name=f"{user.first_name} {user.last_name}",
                course_title=course.title,
                date=None,
                status="not_registered",
                check_in_time=None,
                check_out_time=None,
                notes="Sin asistencia registrada"
            ))
    
    # If PDF format is requested, generate PDF
    if format == "pdf":
        try:
            # Import HTML to PDF converter
            from app.services.html_to_pdf import HTMLToPDFConverter
            
            # Create attendance_lists directory if it doesn't exist
            attendance_dir = "attendance_lists"
            if not os.path.exists(attendance_dir):
                os.makedirs(attendance_dir)
            
            # Generate filename with simple naming to avoid encoding issues
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"reporte_asistencia_curso_{course_id}_{timestamp}.pdf"
            local_filepath = os.path.join(attendance_dir, filename)
            
            # Initialize HTML to PDF converter
            converter = HTMLToPDFConverter()
            
            # Prepare attendees data for the template
            attendees_data = []
            for user in enrolled_users:
                attendees_data.append({
                    "name": f"{user.first_name} {user.last_name}",
                    "document": user.document_number or "N/A",
                    "position": user.position or "N/A",
                    "area": user.department or "N/A"  # Usar department en lugar de area
                })
            
            # Calculate attendance percentage
            present_count = sum(1 for report in attendance_reports if report.status == "present")
            attendance_percentage = (present_count / len(attendance_reports)) * 100 if attendance_reports else 0
            
            # Prepare data for the template
            session_data = {
                "title": "Reporte de Asistencia del Curso",
                "course_title": course.title,
                "session_date": datetime.now().strftime("%d/%m/%Y"),
                "instructor_name": current_user.first_name + " " + current_user.last_name,
                "location": course.location or "No especificado",
                "duration": str(course.duration_hours) if course.duration_hours else "N/A",
                "attendance_percentage": round(attendance_percentage, 2)
            }
            
            # Prepare template data with the correct structure
            template_data = {
                "session": session_data,
                "attendees": attendees_data
            }
            
            # Generate PDF from HTML template
            pdf_content = converter.generate_attendance_list_pdf(template_data)
            
            # Write PDF content to file
            with open(local_filepath, 'wb') as pdf_file:
                pdf_file.write(pdf_content)
            
            # Preparar parámetros de respuesta
            response_params = {
                "path": local_filepath,
                "media_type": "application/pdf"
            }
            
            # Si se solicita descarga, agregar un nombre de archivo personalizado
            if download:
                # Limpiar nombre del curso para el nombre de archivo
                import re
                clean_course_name = re.sub(r'[^\w\s-]', '', course.title).strip()
                clean_course_name = re.sub(r'[-\s]+', '_', clean_course_name)
                
                # Agregar nombre de archivo a los parámetros de respuesta
                response_params["filename"] = f"Reporte_Asistencia_{clean_course_name}_{datetime.now().strftime('%Y%m%d')}.pdf"
            
            # Devolver respuesta de archivo con los parámetros apropiados
            return FileResponse(**response_params)
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error generando PDF: {str(e)}"
            )
    
    # Calculate pagination info for API response
    page = (skip // limit) + 1 if limit > 0 else 1
    size = limit
    pages = (total_enrolled + limit - 1) // limit if limit > 0 else 1
    has_next = skip + limit < total_enrolled
    has_prev = skip > 0
    
    return PaginatedResponse(
        items=attendance_reports,
        total=total_enrolled,
        page=page,
        size=size,
        pages=pages,
        has_next=has_next,
        has_prev=has_prev
    )


@router.post("/{course_id}/complete-enrollment", response_model=MessageResponse)
async def complete_course_enrollment(
    course_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Mark course enrollment as completed if all requirements are met
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
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No está inscrito en este curso"
        )
    
    if enrollment.status == EnrollmentStatus.COMPLETED:
        return MessageResponse(message="El curso ya está marcado como completado")
    
    # Check and complete course if requirements are met
    completed = check_and_complete_course(db, current_user.id, course_id)
    
    if completed:
        return MessageResponse(message="Curso completado exitosamente")
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se han cumplido todos los requisitos para completar el curso"
        )
