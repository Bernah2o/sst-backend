"""
API para Lecciones Interactivas
"""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, func

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User, UserRole
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.course import CourseModule, CourseMaterial
from app.models.user_progress import UserMaterialProgress, UserModuleProgress, MaterialProgressStatus
from app.models.interactive_lesson import (
    InteractiveLesson,
    LessonSlide,
    InlineQuiz,
    InlineQuizAnswer,
    InteractiveActivity,
    LessonStatus,
    SlideContentType,
    ActivityType,
    QuestionType,
)
from app.models.interactive_progress import (
    UserLessonProgress,
    UserSlideProgress,
    UserActivityAttempt,
    LessonProgressStatus,
)
from app.schemas.interactive_lesson import (
    InteractiveLessonCreate,
    InteractiveLessonUpdate,
    InteractiveLessonResponse,
    InteractiveLessonListResponse,
    LessonSlideCreate,
    LessonSlideUpdate,
    LessonSlideResponse,
    InteractiveActivityCreate,
    InteractiveActivityUpdate,
    InteractiveActivityResponse,
    InlineQuizCreate,
    InlineQuizUpdate,
    InlineQuizResponse,
    UserLessonProgressResponse,
    UserSlideProgressResponse,
    UserActivityAttemptResponse,
    SlideViewRequest,
    QuizSubmitRequest,
    QuizSubmitResponse,
    ActivitySubmitRequest,
    ActivitySubmitResponse,
    LessonProgressSummary,
    SlideReorderRequest,
    LessonWithProgressResponse,
)
from app.schemas.common import PaginatedResponse, MessageResponse

router = APIRouter()


# ==================== Helper Functions ====================

def is_admin_or_trainer(user: User) -> bool:
    """Verifica si el usuario es admin o capacitador"""
    return user.role in [UserRole.ADMIN, UserRole.TRAINER]


def get_lesson_or_404(db: Session, lesson_id: int) -> InteractiveLesson:
    """Obtiene una lección o lanza 404"""
    lesson = db.query(InteractiveLesson).filter(
        InteractiveLesson.id == lesson_id
    ).first()
    if not lesson:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lección no encontrada"
        )
    return lesson


def get_slide_or_404(db: Session, slide_id: int) -> LessonSlide:
    """Obtiene un slide o lanza 404"""
    slide = db.query(LessonSlide).filter(LessonSlide.id == slide_id).first()
    if not slide:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Slide no encontrado"
        )
    return slide


def get_activity_or_404(db: Session, activity_id: int) -> InteractiveActivity:
    """Obtiene una actividad o lanza 404"""
    activity = db.query(InteractiveActivity).filter(
        InteractiveActivity.id == activity_id
    ).first()
    if not activity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Actividad no encontrada"
        )
    return activity


def get_user_enrollment_for_lesson(
    db: Session, user_id: int, lesson: InteractiveLesson
) -> Optional[Enrollment]:
    """Obtiene el enrollment del usuario para el curso que contiene la lección"""
    module = db.query(CourseModule).filter(
        CourseModule.id == lesson.module_id
    ).first()
    if not module:
        return None

    return db.query(Enrollment).filter(
        and_(
            Enrollment.user_id == user_id,
            Enrollment.course_id == module.course_id,
            Enrollment.status.in_([EnrollmentStatus.PENDING, EnrollmentStatus.ACTIVE])
        )
    ).first()


def update_module_progress_after_lesson(
    db: Session, lesson: InteractiveLesson, user_id: int, enrollment_id: int
) -> None:
    """Updates the module progress after completing an interactive lesson"""
    module_id = lesson.module_id

    # Count materials in the module
    module_materials = db.query(CourseMaterial).filter(
        CourseMaterial.module_id == module_id
    ).all()
    completed_materials = db.query(UserMaterialProgress).filter(
        and_(
            UserMaterialProgress.user_id == user_id,
            UserMaterialProgress.material_id.in_([m.id for m in module_materials]),
            UserMaterialProgress.status == MaterialProgressStatus.COMPLETED
        )
    ).count() if module_materials else 0

    # Count interactive lessons in the module (only published ones)
    module_lessons = db.query(InteractiveLesson).filter(
        and_(
            InteractiveLesson.module_id == module_id,
            InteractiveLesson.status == LessonStatus.PUBLISHED
        )
    ).all()
    completed_lessons = db.query(UserLessonProgress).filter(
        and_(
            UserLessonProgress.user_id == user_id,
            UserLessonProgress.lesson_id.in_([l.id for l in module_lessons]),
            UserLessonProgress.enrollment_id == enrollment_id,
            UserLessonProgress.status == LessonProgressStatus.COMPLETED.value
        )
    ).count() if module_lessons else 0

    # Calculate totals
    total_items = len(module_materials) + len(module_lessons)
    completed_items = completed_materials + completed_lessons

    # Update or create module progress
    module_progress = db.query(UserModuleProgress).filter(
        and_(
            UserModuleProgress.user_id == user_id,
            UserModuleProgress.module_id == module_id
        )
    ).first()

    if not module_progress:
        module_progress = UserModuleProgress(
            user_id=user_id,
            module_id=module_id,
            enrollment_id=enrollment_id
        )
        db.add(module_progress)

    module_progress.materials_completed = completed_items
    module_progress.total_materials = total_items
    module_progress.calculate_progress()

    # Update course progress
    module = db.query(CourseModule).filter(CourseModule.id == module_id).first()
    course_modules = db.query(CourseModule).filter(
        CourseModule.course_id == module.course_id
    ).all()

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
    from app.models.enrollment import Enrollment
    enrollment = db.query(Enrollment).filter(
        Enrollment.id == enrollment_id
    ).first()

    if enrollment:
        enrollment.update_progress(course_progress_percentage)

    db.commit()


def calculate_lesson_progress(
    db: Session, lesson_progress: UserLessonProgress
) -> None:
    """Recalcula el progreso de una lección"""
    lesson = lesson_progress.lesson
    total_slides = len(lesson.slides)

    if total_slides == 0:
        lesson_progress.progress_percentage = 0.0
        return

    # Contar slides vistos
    viewed_slides = db.query(UserSlideProgress).filter(
        and_(
            UserSlideProgress.lesson_progress_id == lesson_progress.id,
            UserSlideProgress.viewed == True
        )
    ).count()

    lesson_progress.progress_percentage = (viewed_slides / total_slides) * 100

    # Calcular puntuación de quizzes
    quiz_results = db.query(
        func.sum(UserSlideProgress.points_earned)
    ).filter(
        and_(
            UserSlideProgress.lesson_progress_id == lesson_progress.id,
            UserSlideProgress.quiz_answered == True
        )
    ).scalar() or 0

    total_quiz_points = sum(
        slide.inline_quiz.points
        for slide in lesson.slides
        if slide.inline_quiz
    )

    lesson_progress.quiz_earned_points = quiz_results
    lesson_progress.quiz_total_points = total_quiz_points

    if total_quiz_points > 0:
        lesson_progress.quiz_score = (quiz_results / total_quiz_points) * 100

    # Verificar si completó
    if lesson_progress.progress_percentage >= 100:
        lesson_progress.status = LessonProgressStatus.COMPLETED.value
        lesson_progress.completed_at = datetime.utcnow()

    db.commit()


# ==================== CRUD Lecciones ====================

@router.get("", response_model=PaginatedResponse[InteractiveLessonListResponse])
async def get_lessons(
    module_id: Optional[int] = None,
    status: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Listar lecciones interactivas"""
    query = db.query(InteractiveLesson)

    # Filtrar por módulo
    if module_id:
        query = query.filter(InteractiveLesson.module_id == module_id)

    # Empleados solo ven lecciones publicadas
    if not is_admin_or_trainer(current_user):
        query = query.filter(InteractiveLesson.status == LessonStatus.PUBLISHED)
    elif status:
        query = query.filter(InteractiveLesson.status == status)

    total = query.count()
    lessons = query.order_by(InteractiveLesson.order_index).offset(skip).limit(limit).all()

    # Agregar conteo de slides y actividades
    items = []
    for lesson in lessons:
        lesson_dict = {
            "id": lesson.id,
            "module_id": lesson.module_id,
            "title": lesson.title,
            "description": lesson.description,
            "thumbnail": lesson.thumbnail,
            "order_index": lesson.order_index,
            "navigation_type": lesson.navigation_type,
            "status": lesson.status,
            "is_required": lesson.is_required,
            "estimated_duration_minutes": lesson.estimated_duration_minutes,
            "passing_score": lesson.passing_score,
            "created_by": lesson.created_by,
            "created_at": lesson.created_at,
            "updated_at": lesson.updated_at,
            "slides_count": len(lesson.slides),
            "activities_count": len(lesson.activities),
        }
        items.append(InteractiveLessonListResponse(**lesson_dict))

    # Calculate pagination values
    page = (skip // limit) + 1 if limit > 0 else 1
    pages = (total + limit - 1) // limit if limit > 0 else 1
    has_next = skip + limit < total
    has_prev = skip > 0

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        size=limit,
        pages=pages,
        has_next=has_next,
        has_prev=has_prev
    )


@router.post("", response_model=InteractiveLessonResponse, status_code=status.HTTP_201_CREATED)
async def create_lesson(
    lesson_data: InteractiveLessonCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Crear nueva lección interactiva"""
    if not is_admin_or_trainer(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para crear lecciones"
        )

    # Verificar que el módulo existe
    module = db.query(CourseModule).filter(
        CourseModule.id == lesson_data.module_id
    ).first()
    if not module:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Módulo no encontrado"
        )

    # Crear lección
    lesson = InteractiveLesson(
        module_id=lesson_data.module_id,
        title=lesson_data.title,
        description=lesson_data.description,
        thumbnail=lesson_data.thumbnail,
        order_index=lesson_data.order_index,
        navigation_type=lesson_data.navigation_type,
        is_required=lesson_data.is_required,
        estimated_duration_minutes=lesson_data.estimated_duration_minutes,
        passing_score=lesson_data.passing_score,
        created_by=current_user.id,
    )
    db.add(lesson)
    db.flush()

    # Crear slides si se proporcionaron
    for slide_data in lesson_data.slides or []:
        slide = LessonSlide(
            lesson_id=lesson.id,
            title=slide_data.title,
            order_index=slide_data.order_index,
            slide_type=slide_data.slide_type,
            content=slide_data.content,
            notes=slide_data.notes,
            is_required=slide_data.is_required,
        )
        db.add(slide)
        db.flush()

        # Crear quiz inline si se proporcionó
        if slide_data.inline_quiz:
            quiz = InlineQuiz(
                slide_id=slide.id,
                question_text=slide_data.inline_quiz.question_text,
                question_type=slide_data.inline_quiz.question_type,
                points=slide_data.inline_quiz.points,
                explanation=slide_data.inline_quiz.explanation,
                required_to_continue=slide_data.inline_quiz.required_to_continue,
                show_feedback_immediately=slide_data.inline_quiz.show_feedback_immediately,
            )
            db.add(quiz)
            db.flush()

            for answer_data in slide_data.inline_quiz.answers:
                answer = InlineQuizAnswer(
                    quiz_id=quiz.id,
                    answer_text=answer_data.answer_text,
                    is_correct=answer_data.is_correct,
                    order_index=answer_data.order_index,
                    explanation=answer_data.explanation,
                )
                db.add(answer)

    # Crear actividades si se proporcionaron
    for activity_data in lesson_data.activities or []:
        activity = InteractiveActivity(
            lesson_id=lesson.id,
            slide_id=activity_data.slide_id,
            title=activity_data.title,
            instructions=activity_data.instructions,
            activity_type=activity_data.activity_type,
            order_index=activity_data.order_index,
            config=activity_data.config,
            points=activity_data.points,
            max_attempts=activity_data.max_attempts,
            show_feedback=activity_data.show_feedback,
            time_limit_seconds=activity_data.time_limit_seconds,
        )
        db.add(activity)

    db.commit()
    db.refresh(lesson)

    return lesson


@router.get("/{lesson_id}", response_model=InteractiveLessonResponse)
async def get_lesson(
    lesson_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Obtener lección por ID"""
    lesson = db.query(InteractiveLesson).options(
        joinedload(InteractiveLesson.slides).joinedload(LessonSlide.inline_quiz).joinedload(InlineQuiz.answers),
        joinedload(InteractiveLesson.activities),
    ).filter(InteractiveLesson.id == lesson_id).first()

    if not lesson:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lección no encontrada"
        )

    # Empleados solo ven lecciones publicadas
    if not is_admin_or_trainer(current_user) and lesson.status != LessonStatus.PUBLISHED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene acceso a esta lección"
        )

    return lesson


@router.put("/{lesson_id}", response_model=InteractiveLessonResponse)
async def update_lesson(
    lesson_id: int,
    lesson_data: InteractiveLessonUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Actualizar lección"""
    if not is_admin_or_trainer(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para editar lecciones"
        )

    lesson = get_lesson_or_404(db, lesson_id)

    # Actualizar campos
    update_data = lesson_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(lesson, field, value)

    lesson.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(lesson)

    return lesson


@router.delete("/{lesson_id}", response_model=MessageResponse)
async def delete_lesson(
    lesson_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Eliminar lección"""
    if not is_admin_or_trainer(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para eliminar lecciones"
        )

    lesson = get_lesson_or_404(db, lesson_id)
    db.delete(lesson)
    db.commit()

    return MessageResponse(message="Lección eliminada exitosamente")


# ==================== CRUD Slides ====================

@router.get("/{lesson_id}/slides", response_model=List[LessonSlideResponse])
async def get_slides(
    lesson_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Listar slides de una lección"""
    lesson = get_lesson_or_404(db, lesson_id)

    slides = db.query(LessonSlide).options(
        joinedload(LessonSlide.inline_quiz).joinedload(InlineQuiz.answers)
    ).filter(
        LessonSlide.lesson_id == lesson_id
    ).order_by(LessonSlide.order_index).all()

    return slides


@router.post("/{lesson_id}/slides", response_model=LessonSlideResponse, status_code=status.HTTP_201_CREATED)
async def create_slide(
    lesson_id: int,
    slide_data: LessonSlideCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Crear slide en una lección"""
    if not is_admin_or_trainer(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para crear slides"
        )

    lesson = get_lesson_or_404(db, lesson_id)

    slide = LessonSlide(
        lesson_id=lesson_id,
        title=slide_data.title,
        order_index=slide_data.order_index,
        slide_type=slide_data.slide_type,
        content=slide_data.content,
        notes=slide_data.notes,
        is_required=slide_data.is_required,
    )
    db.add(slide)
    db.flush()

    # Crear quiz inline si se proporcionó
    if slide_data.inline_quiz:
        quiz = InlineQuiz(
            slide_id=slide.id,
            question_text=slide_data.inline_quiz.question_text,
            question_type=slide_data.inline_quiz.question_type,
            points=slide_data.inline_quiz.points,
            explanation=slide_data.inline_quiz.explanation,
            required_to_continue=slide_data.inline_quiz.required_to_continue,
            show_feedback_immediately=slide_data.inline_quiz.show_feedback_immediately,
        )
        db.add(quiz)
        db.flush()

        for answer_data in slide_data.inline_quiz.answers:
            answer = InlineQuizAnswer(
                quiz_id=quiz.id,
                answer_text=answer_data.answer_text,
                is_correct=answer_data.is_correct,
                order_index=answer_data.order_index,
                explanation=answer_data.explanation,
            )
            db.add(answer)

    db.commit()
    db.refresh(slide)

    return slide


@router.put("/slides/{slide_id}", response_model=LessonSlideResponse)
async def update_slide(
    slide_id: int,
    slide_data: LessonSlideUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Actualizar slide"""
    if not is_admin_or_trainer(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para editar slides"
        )

    slide = get_slide_or_404(db, slide_id)

    update_data = slide_data.model_dump(exclude_unset=True, exclude={"inline_quiz"})
    for field, value in update_data.items():
        setattr(slide, field, value)

    # Actualizar quiz inline si se proporcionó
    if slide_data.inline_quiz is not None:
        if slide.inline_quiz:
            # Actualizar quiz existente
            quiz_data = slide_data.inline_quiz.model_dump(exclude_unset=True, exclude={"answers"})
            for field, value in quiz_data.items():
                setattr(slide.inline_quiz, field, value)

            # Actualizar respuestas si se proporcionaron
            if slide_data.inline_quiz.answers is not None:
                # Eliminar respuestas existentes
                db.query(InlineQuizAnswer).filter(
                    InlineQuizAnswer.quiz_id == slide.inline_quiz.id
                ).delete()

                # Crear nuevas respuestas
                for answer_data in slide_data.inline_quiz.answers:
                    answer = InlineQuizAnswer(
                        quiz_id=slide.inline_quiz.id,
                        answer_text=answer_data.answer_text,
                        is_correct=answer_data.is_correct,
                        order_index=answer_data.order_index,
                        explanation=answer_data.explanation,
                    )
                    db.add(answer)

    slide.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(slide)

    return slide


@router.delete("/slides/{slide_id}", response_model=MessageResponse)
async def delete_slide(
    slide_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Eliminar slide"""
    if not is_admin_or_trainer(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para eliminar slides"
        )

    slide = get_slide_or_404(db, slide_id)
    db.delete(slide)
    db.commit()

    return MessageResponse(message="Slide eliminado exitosamente")


@router.put("/{lesson_id}/slides/reorder", response_model=List[LessonSlideResponse])
async def reorder_slides(
    lesson_id: int,
    reorder_data: SlideReorderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reordenar slides de una lección"""
    if not is_admin_or_trainer(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para reordenar slides"
        )

    lesson = get_lesson_or_404(db, lesson_id)

    for index, slide_id in enumerate(reorder_data.slide_ids):
        slide = db.query(LessonSlide).filter(
            and_(
                LessonSlide.id == slide_id,
                LessonSlide.lesson_id == lesson_id
            )
        ).first()
        if slide:
            slide.order_index = index

    db.commit()

    slides = db.query(LessonSlide).filter(
        LessonSlide.lesson_id == lesson_id
    ).order_by(LessonSlide.order_index).all()

    return slides


# ==================== CRUD Actividades ====================

@router.get("/{lesson_id}/activities", response_model=List[InteractiveActivityResponse])
async def get_activities(
    lesson_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Listar actividades de una lección"""
    lesson = get_lesson_or_404(db, lesson_id)

    activities = db.query(InteractiveActivity).filter(
        InteractiveActivity.lesson_id == lesson_id
    ).order_by(InteractiveActivity.order_index).all()

    return activities


@router.post("/{lesson_id}/activities", response_model=InteractiveActivityResponse, status_code=status.HTTP_201_CREATED)
async def create_activity(
    lesson_id: int,
    activity_data: InteractiveActivityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Crear actividad en una lección"""
    if not is_admin_or_trainer(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para crear actividades"
        )

    lesson = get_lesson_or_404(db, lesson_id)

    activity = InteractiveActivity(
        lesson_id=lesson_id,
        slide_id=activity_data.slide_id,
        title=activity_data.title,
        instructions=activity_data.instructions,
        activity_type=activity_data.activity_type,
        order_index=activity_data.order_index,
        config=activity_data.config,
        points=activity_data.points,
        max_attempts=activity_data.max_attempts,
        show_feedback=activity_data.show_feedback,
        time_limit_seconds=activity_data.time_limit_seconds,
    )
    db.add(activity)
    db.commit()
    db.refresh(activity)

    return activity


@router.put("/activities/{activity_id}", response_model=InteractiveActivityResponse)
async def update_activity(
    activity_id: int,
    activity_data: InteractiveActivityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Actualizar actividad"""
    if not is_admin_or_trainer(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para editar actividades"
        )

    activity = get_activity_or_404(db, activity_id)

    update_data = activity_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(activity, field, value)

    activity.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(activity)

    return activity


@router.delete("/activities/{activity_id}", response_model=MessageResponse)
async def delete_activity(
    activity_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Eliminar actividad"""
    if not is_admin_or_trainer(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para eliminar actividades"
        )

    activity = get_activity_or_404(db, activity_id)
    db.delete(activity)
    db.commit()

    return MessageResponse(message="Actividad eliminada exitosamente")


# ==================== Progreso del Estudiante ====================

@router.post("/{lesson_id}/start", response_model=UserLessonProgressResponse)
async def start_lesson(
    lesson_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Iniciar una lección (crea registro de progreso)"""
    lesson = get_lesson_or_404(db, lesson_id)

    if lesson.status != LessonStatus.PUBLISHED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La lección no está publicada"
        )

    # Verificar enrollment
    enrollment = get_user_enrollment_for_lesson(db, current_user.id, lesson)
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No está inscrito en este curso"
        )

    # Buscar progreso existente
    progress = db.query(UserLessonProgress).filter(
        and_(
            UserLessonProgress.user_id == current_user.id,
            UserLessonProgress.lesson_id == lesson_id,
            UserLessonProgress.enrollment_id == enrollment.id
        )
    ).first()

    if not progress:
        # Crear nuevo progreso
        progress = UserLessonProgress(
            user_id=current_user.id,
            lesson_id=lesson_id,
            enrollment_id=enrollment.id,
            status=LessonProgressStatus.IN_PROGRESS.value,
            started_at=datetime.utcnow(),
        )
        db.add(progress)
        db.commit()
        db.refresh(progress)

    return progress


@router.post("/{lesson_id}/slide/{slide_id}/view", response_model=UserSlideProgressResponse)
async def mark_slide_viewed(
    lesson_id: int,
    slide_id: int,
    view_data: SlideViewRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Marcar un slide como visto"""
    lesson = get_lesson_or_404(db, lesson_id)
    slide = get_slide_or_404(db, slide_id)

    if slide.lesson_id != lesson_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El slide no pertenece a esta lección"
        )

    # Obtener o crear progreso de lección
    enrollment = get_user_enrollment_for_lesson(db, current_user.id, lesson)
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No está inscrito en este curso"
        )

    lesson_progress = db.query(UserLessonProgress).filter(
        and_(
            UserLessonProgress.user_id == current_user.id,
            UserLessonProgress.lesson_id == lesson_id,
            UserLessonProgress.enrollment_id == enrollment.id
        )
    ).first()

    if not lesson_progress:
        lesson_progress = UserLessonProgress(
            user_id=current_user.id,
            lesson_id=lesson_id,
            enrollment_id=enrollment.id,
            status=LessonProgressStatus.IN_PROGRESS.value,
            started_at=datetime.utcnow(),
        )
        db.add(lesson_progress)
        db.flush()

    # Buscar o crear progreso de slide
    slide_progress = db.query(UserSlideProgress).filter(
        and_(
            UserSlideProgress.lesson_progress_id == lesson_progress.id,
            UserSlideProgress.slide_id == slide_id
        )
    ).first()

    if not slide_progress:
        slide_progress = UserSlideProgress(
            lesson_progress_id=lesson_progress.id,
            slide_id=slide_id,
        )
        db.add(slide_progress)

    slide_progress.mark_viewed()

    if view_data and view_data.time_spent_seconds:
        lesson_progress.time_spent_seconds += view_data.time_spent_seconds

    db.commit()

    # Recalcular progreso
    calculate_lesson_progress(db, lesson_progress)

    db.refresh(slide_progress)
    return slide_progress


@router.post("/{lesson_id}/slide/{slide_id}/quiz", response_model=QuizSubmitResponse)
async def submit_quiz_answer(
    lesson_id: int,
    slide_id: int,
    quiz_data: QuizSubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Enviar respuesta a quiz inline"""
    lesson = get_lesson_or_404(db, lesson_id)
    slide = get_slide_or_404(db, slide_id)

    if slide.lesson_id != lesson_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El slide no pertenece a esta lección"
        )

    if not slide.inline_quiz:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este slide no tiene quiz"
        )

    quiz = slide.inline_quiz

    # Obtener enrollment y progreso
    enrollment = get_user_enrollment_for_lesson(db, current_user.id, lesson)
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No está inscrito en este curso"
        )

    lesson_progress = db.query(UserLessonProgress).filter(
        and_(
            UserLessonProgress.user_id == current_user.id,
            UserLessonProgress.lesson_id == lesson_id,
            UserLessonProgress.enrollment_id == enrollment.id
        )
    ).first()

    if not lesson_progress:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe iniciar la lección primero"
        )

    # Evaluar respuesta
    is_correct = False
    correct_answer_id = None

    if quiz.question_type == QuestionType.MULTIPLE_CHOICE:
        if quiz_data.selected_answer_id:
            answer = db.query(InlineQuizAnswer).filter(
                and_(
                    InlineQuizAnswer.id == quiz_data.selected_answer_id,
                    InlineQuizAnswer.quiz_id == quiz.id
                )
            ).first()
            if answer:
                is_correct = answer.is_correct

        # Obtener respuesta correcta
        correct = db.query(InlineQuizAnswer).filter(
            and_(
                InlineQuizAnswer.quiz_id == quiz.id,
                InlineQuizAnswer.is_correct == True
            )
        ).first()
        if correct:
            correct_answer_id = correct.id

    elif quiz.question_type == QuestionType.TRUE_FALSE:
        # Para TRUE_FALSE también usamos selected_answer_id (igual que MULTIPLE_CHOICE)
        if quiz_data.selected_answer_id:
            answer = db.query(InlineQuizAnswer).filter(
                and_(
                    InlineQuizAnswer.id == quiz_data.selected_answer_id,
                    InlineQuizAnswer.quiz_id == quiz.id
                )
            ).first()
            if answer:
                is_correct = answer.is_correct

        # Obtener respuesta correcta
        correct = db.query(InlineQuizAnswer).filter(
            and_(
                InlineQuizAnswer.quiz_id == quiz.id,
                InlineQuizAnswer.is_correct == True
            )
        ).first()
        if correct:
            correct_answer_id = correct.id

    MAX_QUIZ_ATTEMPTS = 3
    RETRY_COOLDOWN_SECONDS = 60  # 1 minuto de espera para reintentar

    # Guardar progreso del slide
    slide_progress = db.query(UserSlideProgress).filter(
        and_(
            UserSlideProgress.lesson_progress_id == lesson_progress.id,
            UserSlideProgress.slide_id == slide_id
        )
    ).first()

    if not slide_progress:
        slide_progress = UserSlideProgress(
            lesson_progress_id=lesson_progress.id,
            slide_id=slide_id,
        )
        db.add(slide_progress)
        db.flush()

    # Verificar si ya agotó los intentos o ya respondió correctamente
    current_attempts = slide_progress.quiz_attempts or 0
    if slide_progress.quiz_answered:
        if slide_progress.quiz_correct:
            # Ya respondió correctamente, no puede reintentar
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya ha completado este quiz correctamente"
            )
        else:
            # Agotó intentos incorrectamente - verificar si ha pasado el tiempo de espera
            if slide_progress.answered_at:
                seconds_since_last_attempt = (datetime.utcnow() - slide_progress.answered_at).total_seconds()
                if seconds_since_last_attempt < RETRY_COOLDOWN_SECONDS:
                    # Aún en período de espera
                    remaining_seconds = int(RETRY_COOLDOWN_SECONDS - seconds_since_last_attempt)
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Debe esperar {remaining_seconds} segundos para reintentar"
                    )
                else:
                    # Ha pasado el tiempo, reiniciar intentos
                    slide_progress.quiz_answered = False
                    slide_progress.quiz_attempts = 0
                    slide_progress.quiz_correct = False
                    slide_progress.points_earned = 0.0
                    db.flush()

    # Registrar el intento
    slide_progress.submit_quiz_answer(
        answer={
            "selected_answer_id": quiz_data.selected_answer_id,
            "text_answer": quiz_data.text_answer,
            "boolean_answer": quiz_data.boolean_answer,
        },
        is_correct=is_correct,
        points=quiz.points,
        max_attempts=MAX_QUIZ_ATTEMPTS
    )

    db.commit()

    # Recalcular progreso
    calculate_lesson_progress(db, lesson_progress)

    # Calcular intentos restantes
    attempts_used = slide_progress.quiz_attempts
    attempts_remaining = max(0, MAX_QUIZ_ATTEMPTS - attempts_used)
    can_retry = not is_correct and attempts_remaining > 0

    # Solo dar puntos si es correcta
    points_earned = quiz.points if is_correct else 0

    # Solo mostrar respuesta correcta y explicación cuando:
    # - Es correcto, o
    # - Ya no quedan intentos
    show_answer = is_correct or attempts_remaining == 0

    # Calcular tiempo de espera para reintentar si agotó intentos
    retry_available_in_seconds = None
    if not is_correct and attempts_remaining == 0:
        # Agotó los intentos, informar que puede reintentar en 1 minuto
        retry_available_in_seconds = RETRY_COOLDOWN_SECONDS

    return QuizSubmitResponse(
        is_correct=is_correct,
        points_earned=points_earned,
        correct_answer_id=correct_answer_id if quiz.show_feedback_immediately and show_answer else None,
        explanation=quiz.explanation if quiz.show_feedback_immediately and show_answer else None,
        attempts_used=attempts_used,
        attempts_remaining=attempts_remaining,
        can_retry=can_retry,
        retry_available_in_seconds=retry_available_in_seconds,
    )


@router.post("/{lesson_id}/activity/{activity_id}", response_model=ActivitySubmitResponse)
async def submit_activity(
    lesson_id: int,
    activity_id: int,
    submit_data: ActivitySubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Enviar respuesta a una actividad interactiva"""
    lesson = get_lesson_or_404(db, lesson_id)
    activity = get_activity_or_404(db, activity_id)

    if activity.lesson_id != lesson_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La actividad no pertenece a esta lección"
        )

    # Obtener enrollment
    enrollment = get_user_enrollment_for_lesson(db, current_user.id, lesson)
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No está inscrito en este curso"
        )

    # Contar intentos previos
    attempts_count = db.query(UserActivityAttempt).filter(
        and_(
            UserActivityAttempt.user_id == current_user.id,
            UserActivityAttempt.activity_id == activity_id,
            UserActivityAttempt.enrollment_id == enrollment.id
        )
    ).count()

    if attempts_count >= activity.max_attempts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ha alcanzado el máximo de intentos para esta actividad"
        )

    # Evaluar respuesta según el tipo de actividad
    is_correct, score, feedback, correct_solution = evaluate_activity_response(
        activity, submit_data.response
    )

    points_earned = activity.points * (score / 100) if score > 0 else 0

    # Guardar intento
    attempt = UserActivityAttempt(
        user_id=current_user.id,
        activity_id=activity_id,
        enrollment_id=enrollment.id,
        attempt_number=attempts_count + 1,
        user_response=submit_data.response,
        is_correct=is_correct,
        score=score,
        time_spent_seconds=submit_data.time_spent_seconds,
        feedback=feedback if activity.show_feedback else None,
    )
    db.add(attempt)
    db.commit()

    return ActivitySubmitResponse(
        is_correct=is_correct,
        score=score,
        points_earned=points_earned,
        feedback=feedback if activity.show_feedback else None,
        correct_solution=correct_solution if activity.show_feedback and not is_correct else None,
        attempts_remaining=activity.max_attempts - attempts_count - 1,
    )


def evaluate_activity_response(activity: InteractiveActivity, response: dict) -> tuple:
    """Evalúa la respuesta de una actividad y retorna (is_correct, score, feedback, correct_solution)"""
    config = activity.config
    activity_type = activity.activity_type

    if activity_type == ActivityType.DRAG_DROP:
        return evaluate_drag_drop(config, response)
    elif activity_type == ActivityType.MATCHING:
        return evaluate_matching(config, response)
    elif activity_type == ActivityType.ORDERING:
        return evaluate_ordering(config, response)
    elif activity_type == ActivityType.HOTSPOT:
        return evaluate_hotspot(config, response)
    else:
        return False, 0, {"message": "Tipo de actividad no soportado"}, None


def evaluate_drag_drop(config: dict, response: dict) -> tuple:
    """Evalúa actividad de drag & drop"""
    items = config.get("items", [])
    user_placements = response.get("placements", {})  # {item_id: zone_id}

    correct_count = 0
    total = len(items)

    for item in items:
        item_id = item.get("id")
        correct_zone = item.get("correct_zone")
        user_zone = user_placements.get(item_id)

        if user_zone == correct_zone:
            correct_count += 1

    score = (correct_count / total * 100) if total > 0 else 0
    is_correct = correct_count == total

    feedback = {
        "correct_count": correct_count,
        "total": total,
        "message": "¡Correcto!" if is_correct else f"Has acertado {correct_count} de {total} elementos."
    }

    correct_solution = {item["id"]: item["correct_zone"] for item in items}

    return is_correct, score, feedback, correct_solution


def evaluate_matching(config: dict, response: dict) -> tuple:
    """Evalúa actividad de matching"""
    pairs = config.get("pairs", [])
    user_matches = response.get("matches", {})  # {left_id: right_value}

    correct_count = 0
    total = len(pairs)

    for pair in pairs:
        pair_id = pair.get("id")
        correct_right = pair.get("right")
        user_right = user_matches.get(pair_id)

        if user_right == correct_right:
            correct_count += 1

    score = (correct_count / total * 100) if total > 0 else 0
    is_correct = correct_count == total

    feedback = {
        "correct_count": correct_count,
        "total": total,
        "message": "¡Correcto!" if is_correct else f"Has acertado {correct_count} de {total} pares."
    }

    correct_solution = {pair["id"]: pair["right"] for pair in pairs}

    return is_correct, score, feedback, correct_solution


def evaluate_ordering(config: dict, response: dict) -> tuple:
    """Evalúa actividad de ordenamiento"""
    items = config.get("items", [])
    user_order = response.get("order", [])  # [item_id, item_id, ...]

    correct_order = sorted(items, key=lambda x: x.get("correct_position", 0))
    correct_ids = [item["id"] for item in correct_order]

    correct_count = sum(1 for i, item_id in enumerate(user_order) if i < len(correct_ids) and item_id == correct_ids[i])
    total = len(items)

    score = (correct_count / total * 100) if total > 0 else 0
    is_correct = user_order == correct_ids

    feedback = {
        "correct_count": correct_count,
        "total": total,
        "message": "¡Correcto!" if is_correct else f"Has colocado {correct_count} de {total} elementos en la posición correcta."
    }

    correct_solution = correct_ids

    return is_correct, score, feedback, correct_solution


def evaluate_hotspot(config: dict, response: dict) -> tuple:
    """Evalúa actividad de hotspot"""
    hotspots = config.get("hotspots", [])
    user_clicks = response.get("clicked_hotspots", [])  # [hotspot_id, ...]

    correct_hotspots = [hs["id"] for hs in hotspots if hs.get("is_correct")]

    # Calcular intersección
    correct_clicks = set(user_clicks) & set(correct_hotspots)
    incorrect_clicks = set(user_clicks) - set(correct_hotspots)

    total_correct = len(correct_hotspots)
    user_correct = len(correct_clicks)

    # Penalizar clicks incorrectos
    penalty = len(incorrect_clicks) * 0.5
    score = max(0, ((user_correct - penalty) / total_correct * 100)) if total_correct > 0 else 0

    is_correct = set(user_clicks) == set(correct_hotspots)

    feedback = {
        "correct_clicks": user_correct,
        "total_correct": total_correct,
        "incorrect_clicks": len(incorrect_clicks),
        "message": "¡Correcto!" if is_correct else f"Has identificado {user_correct} de {total_correct} elementos correctos."
    }

    correct_solution = correct_hotspots

    return is_correct, score, feedback, correct_solution


@router.post("/{lesson_id}/complete", response_model=UserLessonProgressResponse)
async def complete_lesson(
    lesson_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Completar una lección manualmente"""
    lesson = get_lesson_or_404(db, lesson_id)

    enrollment = get_user_enrollment_for_lesson(db, current_user.id, lesson)
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No está inscrito en este curso"
        )

    lesson_progress = db.query(UserLessonProgress).filter(
        and_(
            UserLessonProgress.user_id == current_user.id,
            UserLessonProgress.lesson_id == lesson_id,
            UserLessonProgress.enrollment_id == enrollment.id
        )
    ).first()

    if not lesson_progress:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe iniciar la lección primero"
        )

    # Verificar que todos los slides requeridos estén vistos
    required_slides = db.query(LessonSlide).filter(
        and_(
            LessonSlide.lesson_id == lesson_id,
            LessonSlide.is_required == True
        )
    ).all()

    viewed_slides = db.query(UserSlideProgress).filter(
        and_(
            UserSlideProgress.lesson_progress_id == lesson_progress.id,
            UserSlideProgress.viewed == True
        )
    ).all()

    viewed_ids = {sp.slide_id for sp in viewed_slides}
    required_ids = {s.id for s in required_slides}

    if not required_ids.issubset(viewed_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe ver todos los slides requeridos antes de completar la lección"
        )

    # Verificar quizzes requeridos
    for slide in required_slides:
        if slide.inline_quiz and slide.inline_quiz.required_to_continue:
            slide_progress = next(
                (sp for sp in viewed_slides if sp.slide_id == slide.id), None
            )
            if not slide_progress or not slide_progress.quiz_answered:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Debe responder el quiz del slide '{slide.title}'"
                )

    # Verificar que el puntaje del quiz cumple con el passing_score
    if lesson.passing_score and lesson.passing_score > 0:
        # Recalcular el score actual del usuario
        calculate_lesson_progress(db, lesson_progress)

        if lesson_progress.quiz_score is None or lesson_progress.quiz_score < lesson.passing_score:
            current_score = lesson_progress.quiz_score or 0
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No ha alcanzado el puntaje mínimo requerido. Puntaje actual: {current_score:.1f}%, requerido: {lesson.passing_score}%"
            )

    lesson_progress.complete_lesson()
    db.commit()

    # Update module progress after completing the lesson
    update_module_progress_after_lesson(db, lesson, current_user.id, enrollment.id)

    db.refresh(lesson_progress)

    return lesson_progress


@router.get("/{lesson_id}/progress", response_model=UserLessonProgressResponse)
async def get_lesson_progress(
    lesson_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Obtener progreso del usuario en una lección"""
    lesson = get_lesson_or_404(db, lesson_id)

    enrollment = get_user_enrollment_for_lesson(db, current_user.id, lesson)
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No está inscrito en este curso"
        )

    lesson_progress = db.query(UserLessonProgress).options(
        joinedload(UserLessonProgress.slide_progress)
    ).filter(
        and_(
            UserLessonProgress.user_id == current_user.id,
            UserLessonProgress.lesson_id == lesson_id,
            UserLessonProgress.enrollment_id == enrollment.id
        )
    ).first()

    if not lesson_progress:
        # Retornar progreso vacío
        return UserLessonProgressResponse(
            id=0,
            user_id=current_user.id,
            lesson_id=lesson_id,
            enrollment_id=enrollment.id,
            status=LessonProgressStatus.NOT_STARTED,
            current_slide_index=0,
            progress_percentage=0.0,
            time_spent_seconds=0,
            slide_progress=[],
        )

    return lesson_progress


# ==================== Generación de Contenido con IA ====================

from pydantic import BaseModel, Field

class GenerateContentRequest(BaseModel):
    """Request para generar contenido con IA"""
    tema: str = Field(..., min_length=3, max_length=200, description="Tema principal de la lección")
    descripcion: Optional[str] = Field(None, max_length=500, description="Descripción adicional")
    num_slides: int = Field(5, ge=3, le=10, description="Número de slides a generar")
    incluir_quiz: bool = Field(True, description="Incluir preguntas de quiz")
    incluir_actividad: bool = Field(True, description="Incluir actividad interactiva")


class GenerateContentResponse(BaseModel):
    """Response de generación de contenido"""
    success: bool
    message: str
    lesson_id: int
    slides_created: int
    quizzes_created: int
    activities_created: int


@router.post("/{lesson_id}/generate-content", response_model=GenerateContentResponse)
async def generate_lesson_content(
    lesson_id: int,
    request: GenerateContentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Genera contenido automáticamente para una lección usando IA.

    El contenido se genera basado en el tema y se agregan slides,
    quizzes y actividades interactivas automáticamente.
    """
    from app.services.ai_service import ai_service

    if not is_admin_or_trainer(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para generar contenido"
        )

    lesson = get_lesson_or_404(db, lesson_id)

    # Verificar que el servicio de IA está configurado
    if not ai_service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servicio de IA no configurado. Configure PERPLEXITY_API_KEY."
        )

    try:
        # Generar contenido con IA
        result = await ai_service.generate_interactive_lesson_content(
            titulo=lesson.title,
            tema=request.tema,
            descripcion=request.descripcion,
            num_slides=request.num_slides,
            incluir_quiz=request.incluir_quiz,
            incluir_actividad=request.incluir_actividad,
        )

        slides_created = 0
        quizzes_created = 0
        activities_created = 0

        # Crear slides generados
        for slide_data in result.get("slides", []):
            slide_type_str = slide_data.get("slide_type", "text")
            try:
                slide_type = SlideContentType(slide_type_str)
            except ValueError:
                slide_type = SlideContentType.TEXT

            new_slide = LessonSlide(
                lesson_id=lesson_id,
                title=slide_data.get("title", f"Slide {slide_data.get('order_index', 0) + 1}"),
                order_index=slide_data.get("order_index", slides_created),
                slide_type=slide_type,
                content=slide_data.get("content", {}),
            )
            db.add(new_slide)
            db.flush()  # Para obtener el ID
            slides_created += 1

            # Si es un slide de quiz, crear el quiz
            if slide_type == SlideContentType.QUIZ and "quiz" in slide_data:
                quiz_data = slide_data["quiz"]
                question_type_str = quiz_data.get("question_type", "multiple_choice")
                try:
                    question_type = QuestionType(question_type_str)
                except ValueError:
                    question_type = QuestionType.MULTIPLE_CHOICE

                new_quiz = InlineQuiz(
                    slide_id=new_slide.id,
                    question_text=quiz_data.get("question_text", ""),
                    question_type=question_type,
                    points=quiz_data.get("points", 1),
                    explanation=quiz_data.get("explanation", ""),
                    required_to_continue=False,
                    show_feedback_immediately=True,
                )
                db.add(new_quiz)
                db.flush()

                # Crear opciones del quiz
                for idx, option in enumerate(quiz_data.get("options", [])):
                    new_answer = InlineQuizAnswer(
                        quiz_id=new_quiz.id,
                        answer_text=option.get("text", ""),
                        is_correct=option.get("is_correct", False),
                        order_index=idx,
                    )
                    db.add(new_answer)

                quizzes_created += 1

        # Crear actividad interactiva si existe
        activity_data = result.get("activity")
        if activity_data and request.incluir_actividad:
            activity_type_str = activity_data.get("activity_type", "matching")
            try:
                activity_type = ActivityType(activity_type_str)
            except ValueError:
                activity_type = ActivityType.MATCHING

            new_activity = InteractiveActivity(
                lesson_id=lesson_id,
                title=activity_data.get("title", "Actividad práctica"),
                instructions=activity_data.get("instructions", ""),
                activity_type=activity_type,
                order_index=0,
                config=activity_data.get("config", {}),
                points=activity_data.get("points", 5),
                max_attempts=3,
                show_feedback=True,
            )
            db.add(new_activity)
            activities_created += 1

        db.commit()

        return GenerateContentResponse(
            success=True,
            message=f"Contenido generado exitosamente: {slides_created} slides, {quizzes_created} quizzes, {activities_created} actividades",
            lesson_id=lesson_id,
            slides_created=slides_created,
            quizzes_created=quizzes_created,
            activities_created=activities_created,
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al generar contenido: {str(e)}"
        )
