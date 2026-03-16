from typing import Any, List
from datetime import datetime, date
import time
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func

from app.dependencies import get_current_active_user, get_current_user, has_role_or_custom
from app.database import get_db
from app.models.user import User, UserRole
from app.models.survey import Survey, SurveyQuestion, UserSurvey, UserSurveyAnswer, SurveyStatus, UserSurveyStatus
from app.models.course import Course
from app.models.worker import Worker
from app.schemas.survey import (
    SurveyCreate, SurveyUpdate, SurveyResponse,
    SurveyListResponse, SurveyQuestionCreate, SurveyQuestionUpdate,
    SurveyQuestionResponse, UserSurveyCreate, UserSurveyResponse,
    UserSurveyAnswerCreate, UserSurveyAnswerResponse,
    SurveySubmission, SurveyStatistics, SurveyPresentation,
    SurveyDetailedResults, EmployeeResponse, AnswerDetail, QuestionAnalysis
)
from pydantic import BaseModel
from app.schemas.common import MessageResponse, PaginatedResponse
from typing import List
from app.services.html_to_pdf import HTMLToPDFConverter

# Schema for assigning general surveys
class SurveyAssignment(BaseModel):
    survey_id: int
    user_ids: List[int]

router = APIRouter()

# ---------------------------------------------------------------------------
# Plantillas de encuestas estandarizadas
# ---------------------------------------------------------------------------
SURVEY_TEMPLATES = {
    "nordico": {
        "id": "nordico",
        "name": "Cuestionario Nórdico de Síntomas Musculoesqueléticos (Kuorinka)",
        "description": (
            "Instrumento estandarizado para la detección y análisis de síntomas "
            "musculoesqueléticos aplicable a cualquier tipo de trabajo. "
            "Desarrollado por Kuorinka et al. (1987)."
        ),
        "instructions": (
            "Marque SI o NO para cada zona corporal según las molestias que ha "
            "experimentado. Responda con honestidad sobre las zonas que le han "
            "generado molestias en los últimos 12 meses y en los últimos 7 días."
        ),
        "is_anonymous": False,
        "questions": [
            # --- CUELLO ---
            {"question_text": "CUELLO — ¿Ha tenido molestias en el cuello en los últimos 12 meses?", "question_type": "yes_no", "is_required": True, "order_index": 0},
            {"question_text": "CUELLO — ¿Ha tenido impedimento para realizar su trabajo normal en los últimos 12 meses a causa de molestias en el cuello?", "question_type": "yes_no", "is_required": True, "order_index": 1},
            {"question_text": "CUELLO — ¿Ha tenido molestias en el cuello en los últimos 7 días?", "question_type": "yes_no", "is_required": True, "order_index": 2},
            # --- HOMBROS ---
            {"question_text": "HOMBROS — ¿Ha tenido molestias en los hombros en los últimos 12 meses?", "question_type": "yes_no", "is_required": True, "order_index": 3},
            {"question_text": "HOMBROS — ¿Ha tenido impedimento para realizar su trabajo normal en los últimos 12 meses a causa de molestias en los hombros?", "question_type": "yes_no", "is_required": True, "order_index": 4},
            {"question_text": "HOMBROS — ¿Ha tenido molestias en los hombros en los últimos 7 días?", "question_type": "yes_no", "is_required": True, "order_index": 5},
            # --- CODOS ---
            {"question_text": "CODOS — ¿Ha tenido molestias en los codos en los últimos 12 meses?", "question_type": "yes_no", "is_required": True, "order_index": 6},
            {"question_text": "CODOS — ¿Ha tenido impedimento para realizar su trabajo normal en los últimos 12 meses a causa de molestias en los codos?", "question_type": "yes_no", "is_required": True, "order_index": 7},
            {"question_text": "CODOS — ¿Ha tenido molestias en los codos en los últimos 7 días?", "question_type": "yes_no", "is_required": True, "order_index": 8},
            # --- MUÑECAS / MANOS ---
            {"question_text": "MUÑECAS/MANOS — ¿Ha tenido molestias en las muñecas o manos en los últimos 12 meses?", "question_type": "yes_no", "is_required": True, "order_index": 9},
            {"question_text": "MUÑECAS/MANOS — ¿Ha tenido impedimento para realizar su trabajo normal en los últimos 12 meses a causa de molestias en las muñecas o manos?", "question_type": "yes_no", "is_required": True, "order_index": 10},
            {"question_text": "MUÑECAS/MANOS — ¿Ha tenido molestias en las muñecas o manos en los últimos 7 días?", "question_type": "yes_no", "is_required": True, "order_index": 11},
            # --- REGIÓN DORSAL / LUMBAR ALTA ---
            {"question_text": "REGIÓN DORSAL/LUMBAR ALTA — ¿Ha tenido molestias en la parte alta de la espalda en los últimos 12 meses?", "question_type": "yes_no", "is_required": True, "order_index": 12},
            {"question_text": "REGIÓN DORSAL/LUMBAR ALTA — ¿Ha tenido impedimento para realizar su trabajo normal en los últimos 12 meses a causa de molestias en la parte alta de la espalda?", "question_type": "yes_no", "is_required": True, "order_index": 13},
            {"question_text": "REGIÓN DORSAL/LUMBAR ALTA — ¿Ha tenido molestias en la parte alta de la espalda en los últimos 7 días?", "question_type": "yes_no", "is_required": True, "order_index": 14},
            # --- ZONA LUMBAR BAJA ---
            {"question_text": "ZONA LUMBAR BAJA — ¿Ha tenido molestias en la zona lumbar baja (parte baja de la espalda) en los últimos 12 meses?", "question_type": "yes_no", "is_required": True, "order_index": 15},
            {"question_text": "ZONA LUMBAR BAJA — ¿Ha tenido impedimento para realizar su trabajo normal en los últimos 12 meses a causa de molestias en la zona lumbar baja?", "question_type": "yes_no", "is_required": True, "order_index": 16},
            {"question_text": "ZONA LUMBAR BAJA — ¿Ha tenido molestias en la zona lumbar baja en los últimos 7 días?", "question_type": "yes_no", "is_required": True, "order_index": 17},
            # --- CADERAS / MUSLOS ---
            {"question_text": "CADERAS/MUSLOS — ¿Ha tenido molestias en las caderas o muslos en los últimos 12 meses?", "question_type": "yes_no", "is_required": True, "order_index": 18},
            {"question_text": "CADERAS/MUSLOS — ¿Ha tenido impedimento para realizar su trabajo normal en los últimos 12 meses a causa de molestias en las caderas o muslos?", "question_type": "yes_no", "is_required": True, "order_index": 19},
            {"question_text": "CADERAS/MUSLOS — ¿Ha tenido molestias en las caderas o muslos en los últimos 7 días?", "question_type": "yes_no", "is_required": True, "order_index": 20},
            # --- RODILLAS ---
            {"question_text": "RODILLAS — ¿Ha tenido molestias en las rodillas en los últimos 12 meses?", "question_type": "yes_no", "is_required": True, "order_index": 21},
            {"question_text": "RODILLAS — ¿Ha tenido impedimento para realizar su trabajo normal en los últimos 12 meses a causa de molestias en las rodillas?", "question_type": "yes_no", "is_required": True, "order_index": 22},
            {"question_text": "RODILLAS — ¿Ha tenido molestias en las rodillas en los últimos 7 días?", "question_type": "yes_no", "is_required": True, "order_index": 23},
            # --- TOBILLOS / PIES ---
            {"question_text": "TOBILLOS/PIES — ¿Ha tenido molestias en los tobillos o pies en los últimos 12 meses?", "question_type": "yes_no", "is_required": True, "order_index": 24},
            {"question_text": "TOBILLOS/PIES — ¿Ha tenido impedimento para realizar su trabajo normal en los últimos 12 meses a causa de molestias en los tobillos o pies?", "question_type": "yes_no", "is_required": True, "order_index": 25},
            {"question_text": "TOBILLOS/PIES — ¿Ha tenido molestias en los tobillos o pies en los últimos 7 días?", "question_type": "yes_no", "is_required": True, "order_index": 26},
        ],
    },
    "burnout": {
        "id": "burnout",
        "name": "Encuesta de Síndrome de Burnout (MBI — Maslach Burnout Inventory)",
        "description": (
            "Instrumento validado internacionalmente para medir el síndrome de burnout "
            "laboral en tres dimensiones: agotamiento emocional, despersonalización y "
            "realización personal. Basado en el MBI de Maslach & Jackson (1981)."
        ),
        "instructions": (
            "A continuación encontrará una serie de enunciados acerca de su trabajo y "
            "sus sentimientos en él. Indique en la escala con qué frecuencia experimenta "
            "cada situación: 0 = Nunca  |  1 = Pocas veces al año o menos  |  "
            "2 = Una vez al mes o menos  |  3 = Unas pocas veces al mes  |  "
            "4 = Una vez a la semana  |  5 = Pocas veces a la semana  |  6 = Todos los días."
        ),
        "is_anonymous": True,
        "questions": [
            # --- AGOTAMIENTO EMOCIONAL (9 ítems) ---
            {"question_text": "EE1 — Me siento emocionalmente agotado/a por mi trabajo.", "question_type": "scale", "is_required": True, "order_index": 0, "min_value": 0, "max_value": 6},
            {"question_text": "EE2 — Me siento agotado/a al final de la jornada laboral.", "question_type": "scale", "is_required": True, "order_index": 1, "min_value": 0, "max_value": 6},
            {"question_text": "EE3 — Me siento cansado/a cuando me levanto por la mañana y tengo que enfrentarme a otro día en el trabajo.", "question_type": "scale", "is_required": True, "order_index": 2, "min_value": 0, "max_value": 6},
            {"question_text": "EE4 — Trabajar todo el día con personas es un esfuerzo real para mí.", "question_type": "scale", "is_required": True, "order_index": 3, "min_value": 0, "max_value": 6},
            {"question_text": "EE5 — Me siento exhausto/a por mi trabajo.", "question_type": "scale", "is_required": True, "order_index": 4, "min_value": 0, "max_value": 6},
            {"question_text": "EE6 — Me siento frustrado/a en mi trabajo.", "question_type": "scale", "is_required": True, "order_index": 5, "min_value": 0, "max_value": 6},
            {"question_text": "EE7 — Creo que estoy trabajando demasiado.", "question_type": "scale", "is_required": True, "order_index": 6, "min_value": 0, "max_value": 6},
            {"question_text": "EE8 — Trabajar directamente con personas me produce estrés.", "question_type": "scale", "is_required": True, "order_index": 7, "min_value": 0, "max_value": 6},
            {"question_text": "EE9 — Me siento al límite de mis posibilidades en el trabajo.", "question_type": "scale", "is_required": True, "order_index": 8, "min_value": 0, "max_value": 6},
            # --- DESPERSONALIZACIÓN (5 ítems) ---
            {"question_text": "DP1 — Creo que trato a algunos compañeros o personas del trabajo como si fueran objetos impersonales.", "question_type": "scale", "is_required": True, "order_index": 9, "min_value": 0, "max_value": 6},
            {"question_text": "DP2 — Me he vuelto más insensible con las personas desde que ejerzo esta profesión.", "question_type": "scale", "is_required": True, "order_index": 10, "min_value": 0, "max_value": 6},
            {"question_text": "DP3 — Me preocupa el hecho de que este trabajo me esté endureciendo emocionalmente.", "question_type": "scale", "is_required": True, "order_index": 11, "min_value": 0, "max_value": 6},
            {"question_text": "DP4 — No me importa realmente lo que les ocurra a algunas personas con las que interactúo en el trabajo.", "question_type": "scale", "is_required": True, "order_index": 12, "min_value": 0, "max_value": 6},
            {"question_text": "DP5 — Siento que las personas con las que trabajo me culpan de algunos de sus problemas.", "question_type": "scale", "is_required": True, "order_index": 13, "min_value": 0, "max_value": 6},
            # --- REALIZACIÓN PERSONAL (8 ítems) ---
            {"question_text": "RP1 — Puedo entender fácilmente cómo se sienten las personas con las que trabajo.", "question_type": "scale", "is_required": True, "order_index": 14, "min_value": 0, "max_value": 6},
            {"question_text": "RP2 — Trato eficazmente los problemas de las personas con las que trabajo.", "question_type": "scale", "is_required": True, "order_index": 15, "min_value": 0, "max_value": 6},
            {"question_text": "RP3 — Creo que estoy influyendo positivamente en las personas con mi trabajo.", "question_type": "scale", "is_required": True, "order_index": 16, "min_value": 0, "max_value": 6},
            {"question_text": "RP4 — Me siento muy activo/a en mi trabajo.", "question_type": "scale", "is_required": True, "order_index": 17, "min_value": 0, "max_value": 6},
            {"question_text": "RP5 — Puedo crear fácilmente un ambiente relajado con las personas con las que trabajo.", "question_type": "scale", "is_required": True, "order_index": 18, "min_value": 0, "max_value": 6},
            {"question_text": "RP6 — Me siento estimulado/a después de trabajar con las personas.", "question_type": "scale", "is_required": True, "order_index": 19, "min_value": 0, "max_value": 6},
            {"question_text": "RP7 — He conseguido muchas cosas útiles en mi trabajo.", "question_type": "scale", "is_required": True, "order_index": 20, "min_value": 0, "max_value": 6},
            {"question_text": "RP8 — En mi trabajo, trato los problemas emocionales con mucha calma.", "question_type": "scale", "is_required": True, "order_index": 21, "min_value": 0, "max_value": 6},
        ],
    },
}


def _user_survey_year_expr():
    return func.extract(
        "year",
        func.coalesce(UserSurvey.response_date, func.date(UserSurvey.completed_at)),
    )


def _build_question_analysis(
    db: Session,
    survey: Survey,
    year: int = None,
) -> List[QuestionAnalysis]:
    base_user_surveys = db.query(UserSurvey.id).filter(
        and_(
            UserSurvey.survey_id == survey.id,
            UserSurvey.status == UserSurveyStatus.COMPLETED,
        )
    )

    if year is not None:
        base_user_surveys = base_user_surveys.filter(_user_survey_year_expr() == year)

    user_survey_ids = [row.id for row in base_user_surveys.all()]
    total_completed = len(user_survey_ids)

    if total_completed == 0:
        return [
            QuestionAnalysis(
                question_id=q.id,
                question_text=q.question_text,
                question_type=q.question_type.value,
                total_answers=0,
                missing_answers=0,
            )
            for q in (survey.questions or [])
        ]

    answers = (
        db.query(UserSurveyAnswer)
        .filter(UserSurveyAnswer.user_survey_id.in_(user_survey_ids))
        .all()
    )

    answers_by_question: dict[int, list[UserSurveyAnswer]] = {}
    for ans in answers:
        answers_by_question.setdefault(ans.question_id, []).append(ans)

    import json

    result: List[QuestionAnalysis] = []
    for q in (survey.questions or []):
        q_answers = answers_by_question.get(q.id, [])
        qt = q.question_type.value

        counts = None
        avg = None
        samples = None
        min_allowed = q.min_value
        max_allowed = q.max_value

        if qt == "rating":
            if min_allowed is None:
                min_allowed = 1
            if max_allowed is None:
                max_allowed = 5

        if qt in ["single_choice", "yes_no"]:
            counts = {}
            if q.options:
                try:
                    for opt in json.loads(q.options):
                        counts[str(opt)] = 0
                except (json.JSONDecodeError, TypeError):
                    pass
            for a in q_answers:
                key = (a.answer_text or "").strip() or "(Sin respuesta)"
                counts[key] = counts.get(key, 0) + 1

        elif qt == "multiple_choice":
            counts = {}
            if q.options:
                try:
                    for opt in json.loads(q.options):
                        counts[str(opt)] = 0
                except (json.JSONDecodeError, TypeError):
                    pass
            for a in q_answers:
                if a.selected_options:
                    try:
                        selected = json.loads(a.selected_options)
                        if isinstance(selected, list):
                            for opt in selected:
                                key = str(opt)
                                counts[key] = counts.get(key, 0) + 1
                            continue
                    except (json.JSONDecodeError, TypeError):
                        pass
                key = (a.answer_text or "").strip()
                if key:
                    counts[key] = counts.get(key, 0) + 1

        elif qt in ["rating", "scale"]:
            values = [a.answer_value for a in q_answers if a.answer_value is not None]
            counts = {}
            for v in values:
                key = str(v)
                counts[key] = counts.get(key, 0) + 1
            if values:
                avg = round(sum(values) / len(values), 2)

        elif qt in ["text", "textarea"]:
            texts = [
                (a.answer_text or "").strip()
                for a in q_answers
                if (a.answer_text or "").strip()
            ]
            samples = texts[:20]

        else:
            texts = [
                (a.answer_text or "").strip()
                for a in q_answers
                if (a.answer_text or "").strip()
            ]
            samples = texts[:20] if texts else None

        answered_count = len(q_answers)
        missing = max(total_completed - answered_count, 0)

        result.append(
            QuestionAnalysis(
                question_id=q.id,
                question_text=q.question_text,
                question_type=qt,
                total_answers=answered_count,
                missing_answers=missing,
                counts=counts,
                average=avg,
                min_value=min_allowed,
                max_value=max_allowed,
                samples=samples,
            )
        )

    return result


@router.get("/", response_model=PaginatedResponse[SurveyListResponse])
@router.get("", response_model=PaginatedResponse[SurveyListResponse])
async def get_surveys(
    skip: int = 0,
    limit: int = 100,
    search: str = None,
    course_id: int = None,
    status: SurveyStatus = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get surveys with optional filtering
    """
    query = db.query(Survey).options(joinedload(Survey.course))
    
    # Apply filters
    if search:
        query = query.filter(
            or_(
                Survey.title.ilike(f"%{search}%"),
                Survey.description.ilike(f"%{search}%")
            )
        )
    
    if course_id:
        query = query.filter(Survey.course_id == course_id)
    
    if status:
        query = query.filter(Survey.status == status)
    else:
        # Only show active surveys for non-admin users
        if not has_role_or_custom(current_user, ["admin", "trainer"]):
            query = query.filter(Survey.status == SurveyStatus.PUBLISHED)
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    surveys = query.offset(skip).limit(limit).all()
    
    # Transform surveys to include course information
    survey_items = []
    for survey in surveys:
        survey_dict = {
            "id": survey.id,
            "title": survey.title,
            "description": survey.description,
            "status": survey.status,
            "is_anonymous": survey.is_anonymous,
            "course_id": survey.course_id,
            "is_course_survey": survey.is_course_survey,
            "required_for_completion": survey.required_for_completion,
            "course": {"id": survey.course.id, "title": survey.course.title} if survey.course else None,
            "created_at": survey.created_at,
            "published_at": survey.published_at,
            "closes_at": survey.closes_at
        }
        survey_items.append(survey_dict)
    
    # Calculate pagination info
    page = (skip // limit) + 1
    pages = (total + limit - 1) // limit  # Ceiling division
    has_next = skip + limit < total
    has_prev = skip > 0
    
    return PaginatedResponse(
        items=survey_items,
        total=total,
        page=page,
        size=limit,
        pages=pages,
        has_next=has_next,
        has_prev=has_prev
    )


@router.post("/", response_model=SurveyResponse)
@router.post("", response_model=SurveyResponse)
async def create_survey(
    survey_data: SurveyCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Create new survey (admin and capacitador roles only)
    """
    if not has_role_or_custom(current_user, ["admin", "trainer"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permisos insuficientes"
        )
    
    # Check if course exists (if course_id is provided)
    if survey_data.course_id:
        course = db.query(Course).filter(Course.id == survey_data.course_id).first()
        if not course:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Curso no encontrado"
            )
    
    # Create new survey
    survey_dict = survey_data.dict(exclude={'questions'})
    survey = Survey(
        **survey_dict,
        created_by=current_user.id
    )
    
    db.add(survey)
    db.commit()
    db.refresh(survey)
    
    # Load course relationship if exists
    if survey.course_id:
        survey = db.query(Survey).options(joinedload(Survey.course)).filter(Survey.id == survey.id).first()
    
    # Create questions if provided
    if survey_data.questions:
        for i, question_data in enumerate(survey_data.questions):
            question = SurveyQuestion(
                survey_id=survey.id,
                question_text=question_data.question_text,
                question_type=question_data.question_type,
                options=question_data.options,
                is_required=question_data.is_required,
                order_index=i,
                min_value=question_data.min_value,
                max_value=question_data.max_value,
                placeholder_text=question_data.placeholder_text
            )
            db.add(question)
        
        db.commit()
        db.refresh(survey)
    
    # Transform to proper response format
    survey_dict = {
        "id": survey.id,
        "title": survey.title,
        "description": survey.description,
        "instructions": survey.instructions,
        "is_anonymous": survey.is_anonymous,
        "allow_multiple_responses": survey.allow_multiple_responses,
        "closes_at": survey.closes_at,
        "expires_at": survey.expires_at,
        "status": survey.status,
        "course_id": survey.course_id,
        "is_course_survey": survey.is_course_survey,
        "required_for_completion": survey.required_for_completion,
        "course": {"id": survey.course.id, "title": survey.course.title} if survey.course else None,
        "created_by": survey.created_by,
        "created_at": survey.created_at,
        "updated_at": survey.updated_at,
        "published_at": survey.published_at,
        "questions": [{
            "id": q.id,
            "survey_id": q.survey_id,
            "question_text": q.question_text,
            "question_type": q.question_type,
            "options": q.options,
            "is_required": q.is_required,
            "order_index": q.order_index,
            "min_value": q.min_value,
            "max_value": q.max_value,
            "placeholder_text": q.placeholder_text,
            "created_at": q.created_at,
            "updated_at": q.updated_at
        } for q in survey.questions]
    }
    
    return survey_dict



@router.get("/available", response_model=PaginatedResponse[SurveyResponse])
async def get_available_surveys(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get available surveys for current user based on their course enrollments
    """
    from app.models.enrollment import Enrollment
    
    # Get user's active enrollments
    enrollments = db.query(Enrollment).filter(
        Enrollment.user_id == current_user.id
    ).all()
    
    enrolled_course_ids = [enrollment.course_id for enrollment in enrollments]
    
    # Build optimized query using LEFT JOIN to filter completed surveys
    query = db.query(Survey).options(joinedload(Survey.course)).outerjoin(
        UserSurvey,
        and_(
            UserSurvey.survey_id == Survey.id,
            UserSurvey.user_id == current_user.id,
            UserSurvey.status == UserSurveyStatus.COMPLETED
        )
    ).filter(
        and_(
            Survey.status == SurveyStatus.PUBLISHED,
            or_(
                # General surveys (not course-specific)
                Survey.course_id.is_(None),
                # Course-specific surveys for enrolled courses
                Survey.course_id.in_(enrolled_course_ids)
            ),
            # Exclude completed surveys
            UserSurvey.id.is_(None)
        )
    )
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    surveys = query.offset(skip).limit(limit).all()
    
    # Transform surveys to include course information
    survey_items = []
    for survey in surveys:
        survey_dict = {
            "id": survey.id,
            "title": survey.title,
            "description": survey.description,
            "instructions": survey.instructions,
            "is_anonymous": survey.is_anonymous,
            "allow_multiple_responses": survey.allow_multiple_responses,
            "closes_at": survey.closes_at,
            "expires_at": survey.expires_at,
            "status": survey.status,
            "course_id": survey.course_id,
            "is_course_survey": survey.is_course_survey,
            "required_for_completion": survey.required_for_completion,
            "course": {"id": survey.course.id, "title": survey.course.title} if survey.course else None,
            "created_by": survey.created_by,
            "created_at": survey.created_at,
            "updated_at": survey.updated_at,
            "published_at": survey.published_at,
            "questions": survey.questions
        }
        survey_items.append(survey_dict)
    
    # Calculate pagination info
    page = (skip // limit) + 1
    pages = (total + limit - 1) // limit  # Ceiling division
    has_next = skip + limit < total
    has_prev = skip > 0
    
    return PaginatedResponse(
        items=survey_items,
        total=total,
        page=page,
        size=limit,
        pages=pages,
        has_next=has_next,
        has_prev=has_prev
    )


@router.get("/general", response_model=PaginatedResponse[SurveyListResponse])
async def get_general_surveys(
    skip: int = 0,
    limit: int = 100,
    search: str = None,
    status: SurveyStatus = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get general surveys (not associated with any course) - for admin/capacitador management
    """
    if not has_role_or_custom(current_user, ["admin", "trainer"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permisos insuficientes"
        )
    
    # Query for surveys without course association
    query = db.query(Survey).filter(Survey.course_id.is_(None))
    
    # Apply filters
    if search:
        query = query.filter(
            or_(
                Survey.title.ilike(f"%{search}%"),
                Survey.description.ilike(f"%{search}%")
            )
        )
    
    if status:
        query = query.filter(Survey.status == status)
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    surveys = query.offset(skip).limit(limit).all()
    
    # Transform surveys to list response format
    survey_items = []
    for survey in surveys:
        survey_dict = {
            "id": survey.id,
            "title": survey.title,
            "description": survey.description,
            "status": survey.status,
            "is_anonymous": survey.is_anonymous,
            "course_id": None,  # Always None for general surveys
            "is_course_survey": False,  # Always False for general surveys
            "required_for_completion": False,  # Always False for general surveys
            "course": None,  # Always None for general surveys
            "created_at": survey.created_at,
            "published_at": survey.published_at,
            "closes_at": survey.closes_at
        }
        survey_items.append(survey_dict)
    
    # Calculate pagination info
    page = (skip // limit) + 1
    pages = (total + limit - 1) // limit  # Ceiling division
    has_next = skip + limit < total
    has_prev = skip > 0
    
    return PaginatedResponse(
        items=survey_items,
        total=total,
        page=page,
        size=limit,
        pages=pages,
        has_next=has_next,
        has_prev=has_prev
    )


@router.post("/assign", response_model=MessageResponse)
async def assign_general_survey(
    assignment: SurveyAssignment,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Asignar una encuesta general a usuarios específicos.
    Solo administradores y capacitadores pueden asignar encuestas.
    """
    # Verificar permisos
    if current_user.role not in [UserRole.ADMIN, UserRole.TRAINER]:
        raise HTTPException(
            status_code=403,
            detail="No tienes permisos para asignar encuestas"
        )
    
    # Verificar que la encuesta existe y es una encuesta general
    survey = db.query(Survey).filter(
        Survey.id == assignment.survey_id,
        Survey.course_id.is_(None)  # Solo encuestas generales
    ).first()
    
    if not survey:
        raise HTTPException(
            status_code=404,
            detail="Encuesta general no encontrada"
        )
    
    # Verificar que los usuarios existen
    users = db.query(User).filter(User.id.in_(assignment.user_ids)).all()
    if len(users) != len(assignment.user_ids):
        found_user_ids = [user.id for user in users]
        missing_ids = set(assignment.user_ids) - set(found_user_ids)
        raise HTTPException(
            status_code=400,
            detail=f"Algunos usuarios no existen. IDs faltantes: {list(missing_ids)}"
        )
    
    # Crear asignaciones de encuesta para cada usuario
    assignments_created = 0
    for user_id in assignment.user_ids:
        # Verificar si ya existe una asignación
        existing = db.query(UserSurvey).filter(
            UserSurvey.user_id == user_id,
            UserSurvey.survey_id == assignment.survey_id
        ).first()
        
        if not existing:
            user_survey = UserSurvey(
                user_id=user_id,
                survey_id=assignment.survey_id,
                enrollment_id=None,  # No hay enrollment para encuestas generales
                status=UserSurveyStatus.NOT_STARTED
            )
            db.add(user_survey)
            assignments_created += 1
    
    db.commit()
    
    return MessageResponse(
        message=f"Encuesta asignada exitosamente a {assignments_created} usuarios"
    )


@router.get("/my-surveys", response_class=JSONResponse)
async def get_my_surveys(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get current user's surveys with status (completed and pending)
    Similar to evaluations endpoint
    """
    from app.models.enrollment import Enrollment
    
    try:
        # Get user's enrollments
        user_enrollments = db.query(Enrollment).filter(
            Enrollment.user_id == current_user.id
        ).all()
        
        if not user_enrollments:
            return JSONResponse(
                content={
                    "items": [],
                    "total": 0,
                    "page": 1,
                    "size": 100,
                    "pages": 1,
                    "has_next": False,
                    "has_prev": False
                }
            )
        
        # Get course IDs from enrollments
        course_ids = [enrollment.course_id for enrollment in user_enrollments]
        
        # Get published surveys for these courses with course information
        course_surveys = db.query(Survey).options(joinedload(Survey.course)).filter(
            Survey.course_id.in_(course_ids),
            Survey.status == SurveyStatus.PUBLISHED
        ).all()
        
        # Get user's survey submissions to find assigned general surveys
        user_surveys = db.query(UserSurvey).filter(
            UserSurvey.user_id == current_user.id
        ).all()
        
        # Get general surveys that are assigned to this user
        assigned_general_survey_ids = [
            us.survey_id for us in user_surveys 
            if us.survey_id not in [cs.id for cs in course_surveys]
        ]
        
        general_surveys = []
        if assigned_general_survey_ids:
            general_surveys = db.query(Survey).options(joinedload(Survey.course)).filter(
                Survey.id.in_(assigned_general_survey_ids),
                Survey.course_id.is_(None),  # Only general surveys
                Survey.status == SurveyStatus.PUBLISHED
            ).all()
        
        # Combine course surveys and general surveys
        available_surveys = course_surveys + general_surveys
        
        # Create a map of survey_id to user_survey for quick lookup
        user_survey_map = {us.survey_id: us for us in user_surveys}
        
        # Build response with all available surveys
        survey_results = []
        
        for survey in available_surveys:
            user_survey = user_survey_map.get(survey.id)
            
            if user_survey:
                # User has started this survey
                survey_results.append({
                    "survey_id": survey.id,
                    "user_id": current_user.id,
                    "anonymous_token": user_survey.anonymous_token,
                    "id": user_survey.id,
                    "status": user_survey.status.value if user_survey.status else "not_started",
                    "started_at": user_survey.started_at.isoformat() if user_survey.started_at else None,
                    "completed_at": user_survey.completed_at.isoformat() if user_survey.completed_at else None,
                    "created_at": user_survey.created_at.isoformat() if user_survey.created_at else None,
                    "updated_at": user_survey.updated_at.isoformat() if user_survey.updated_at else None,
                    "title": survey.title,
                    "description": survey.description,
                    "survey": {
                        "id": survey.id,
                        "title": survey.title,
                        "description": survey.description,
                        "course": {"id": survey.course.id, "title": survey.course.title} if survey.course else None
                    }
                })
            else:
                # User hasn't started this survey yet
                survey_results.append({
                    "survey_id": survey.id,
                    "user_id": current_user.id,
                    "anonymous_token": None,
                    "id": None,
                    "status": "not_started",
                    "started_at": None,
                    "completed_at": None,
                    "created_at": None,
                    "updated_at": None,
                    "title": survey.title,
                    "description": survey.description,
                    "survey": {
                        "id": survey.id,
                        "title": survey.title,
                        "description": survey.description,
                        "course": {"id": survey.course.id, "title": survey.course.title} if survey.course else None
                    }
                })
        
        return JSONResponse(
            content={
                "items": survey_results,
                "total": len(survey_results),
                "page": 1,
                "size": 100,
                "pages": 1,
                "has_next": False,
                "has_prev": False
            }
        )
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Error retrieving user surveys: {str(e)}",
                "data": []
            }
    )


@router.get("/user-responses")
async def get_user_survey_responses(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Obtener las respuestas de encuestas del usuario para un curso específico
    """
    try:
        # Verificar que el curso existe
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            raise HTTPException(
                status_code=404,
                detail={
                    "success": False,
                    "message": "El curso especificado no existe",
                    "error_code": 404,
                    "timestamp": time.time()
                }
            )
        
        # Obtener las encuestas del curso
        surveys = db.query(Survey).filter(
            Survey.course_id == course_id,
            Survey.status == SurveyStatus.PUBLISHED
        ).all()
        
        if not surveys:
            return {
                "success": True,
                "message": "No hay encuestas disponibles para este curso",
                "data": [],
                "timestamp": time.time()
            }
        
        # Obtener las respuestas del usuario para estas encuestas
        user_responses = []
        for survey in surveys:
            user_survey = db.query(UserSurvey).filter(
                UserSurvey.survey_id == survey.id,
                UserSurvey.user_id == current_user.id
            ).first()
            
            if user_survey:
                # Obtener las respuestas detalladas
                answers = db.query(UserSurveyAnswer).filter(
                    UserSurveyAnswer.user_survey_id == user_survey.id
                ).all()
                
                survey_response = {
                    "survey_id": survey.id,
                    "survey_title": survey.title,
                    "survey_description": survey.description,
                    "status": user_survey.status.value,
                    "started_at": user_survey.started_at,
                    "completed_at": user_survey.completed_at,
                    "answers_count": len(answers),
                    "total_questions": len(survey.questions)
                }
                user_responses.append(survey_response)
        
        return {
            "success": True,
            "message": "Respuestas de encuestas obtenidas exitosamente",
            "data": user_responses,
            "timestamp": time.time()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": "Error interno del servidor al obtener las respuestas de encuestas",
                "detail": str(e),
                "error_code": 500,
                "timestamp": time.time()
            }
        )


@router.get("/by-template/{template_id}")
async def get_surveys_by_template(
    template_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """Lista todas las encuestas creadas a partir de una plantilla específica."""
    if not has_role_or_custom(current_user, ["admin", "trainer"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permisos insuficientes")
    surveys = (
        db.query(Survey)
        .filter(Survey.survey_template == template_id)
        .order_by(Survey.created_at.desc())
        .all()
    )
    return [
        {
            "id": s.id,
            "title": s.title,
            "description": s.description,
            "status": s.status,
            "created_at": s.created_at,
            "published_at": s.published_at,
            "closes_at": s.closes_at,
            "survey_template": s.survey_template,
            "total_responses": db.query(UserSurvey).filter(
                UserSurvey.survey_id == s.id,
                UserSurvey.status == UserSurveyStatus.COMPLETED,
            ).count(),
        }
        for s in surveys
    ]


@router.get("/{survey_id}/report/nordic-pdf")
async def export_nordic_pdf(
    survey_id: int,
    year: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """Genera PDF con análisis especializado del Cuestionario Nórdico (por región corporal)."""
    if not has_role_or_custom(current_user, ["admin", "trainer"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permisos insuficientes")

    survey = db.query(Survey).filter(Survey.id == survey_id).first()
    if not survey or survey.survey_template != "nordico":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Encuesta nórdica no encontrada")

    # Preguntas ordenadas
    questions = sorted(survey.questions, key=lambda q: q.order_index)

    # Obtener respuestas del año
    year_expr = _user_survey_year_expr()
    completed_ids = (
        db.query(UserSurvey.id)
        .filter(UserSurvey.survey_id == survey_id, UserSurvey.status == UserSurveyStatus.COMPLETED)
        .filter(func.extract("year", func.coalesce(UserSurvey.response_date, func.date(UserSurvey.completed_at))) == year)
        .subquery()
    )
    total = db.query(func.count()).select_from(completed_ids).scalar() or 0

    # Nombres de regiones y estructura de preguntas (9 regiones × 3 preguntas)
    regions = ["Cuello", "Hombros", "Codos", "Muñecas/Manos",
               "Región Dorsal/Lumbar Alta", "Zona Lumbar Baja",
               "Caderas/Muslos", "Rodillas", "Tobillos/Pies"]
    region_data = []
    for i, region in enumerate(regions):
        base = i * 3
        qs = questions[base:base + 3] if len(questions) > base + 2 else []
        row = {"region": region, "q12m": 0, "qimp": 0, "q7d": 0,
               "pct12m": 0.0, "pctimp": 0.0, "pct7d": 0.0}
        for j, label in enumerate(["q12m", "qimp", "q7d"]):
            if j < len(qs):
                yes_count = (
                    db.query(func.count(UserSurveyAnswer.id))
                    .filter(
                        UserSurveyAnswer.user_survey_id.in_(db.query(completed_ids)),
                        UserSurveyAnswer.question_id == qs[j].id,
                        func.lower(UserSurveyAnswer.answer_text) == "sí",
                    )
                    .scalar() or 0
                )
                row[label] = yes_count
                row[f"pct{label[1:]}"] = round((yes_count / total * 100) if total > 0 else 0, 1)
        region_data.append(row)

    from app.services.html_to_pdf import HTMLToPDFConverter
    from datetime import datetime as dt
    template_data = {
        "survey_title": survey.title,
        "year": year,
        "total_responses": total,
        "regions": region_data,
        "generated_at": dt.now().strftime("%d/%m/%Y %H:%M"),
    }
    pdf_bytes = HTMLToPDFConverter().generate_nordic_report_pdf(template_data)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="nordico_{survey_id}_{year}.pdf"'},
    )


@router.get("/{survey_id}/report/burnout-pdf")
async def export_burnout_pdf(
    survey_id: int,
    year: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """Genera PDF con análisis MBI (dimensiones: EE, DP, RP) del Síndrome de Burnout."""
    if not has_role_or_custom(current_user, ["admin", "trainer"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permisos insuficientes")

    survey = db.query(Survey).options(joinedload(Survey.questions)).filter(Survey.id == survey_id).first()
    if not survey or survey.survey_template != "burnout":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Encuesta de burnout no encontrada")

    questions = sorted(survey.questions, key=lambda q: q.order_index)

    completed_surveys = (
        db.query(UserSurvey)
        .join(User, UserSurvey.user_id == User.id)
        .filter(
            UserSurvey.survey_id == survey_id,
            UserSurvey.status == UserSurveyStatus.COMPLETED,
            func.extract("year", func.coalesce(UserSurvey.response_date, func.date(UserSurvey.completed_at))) == year,
        )
        .all()
    )
    total = len(completed_surveys)

    # Dimensiones MBI: EE=0-8, DP=9-13, RP=14-21
    dimensions = {"EE": (0, 9), "DP": (9, 14), "RP": (14, 22)}
    dim_labels = {"EE": "Agotamiento Emocional", "DP": "Despersonalización", "RP": "Realización Personal"}
    dim_max = {"EE": 54, "DP": 30, "RP": 48}

    employee_rows = []
    dim_totals = {"EE": 0.0, "DP": 0.0, "RP": 0.0}
    burnout_counts = {"bajo": 0, "moderado": 0, "alto": 0}

    for us in completed_surveys:
        answers = {a.question_id: a.answer_value for a in us.answers if a.answer_value is not None}
        scores = {}
        for dim, (start, end) in dimensions.items():
            qs = questions[start:end]
            scores[dim] = sum(answers.get(q.id, 0) for q in qs)
            dim_totals[dim] += scores[dim]

        # Clasificación MBI
        ee_high = scores["EE"] >= 27
        dp_high = scores["DP"] >= 13
        rp_low = scores["RP"] <= 33

        if ee_high and dp_high and rp_low:
            level = "alto"
        elif scores["EE"] >= 17 or scores["DP"] >= 7 or scores["RP"] <= 39:
            level = "moderado"
        else:
            level = "bajo"
        burnout_counts[level] += 1

        user_obj = db.query(User).filter(User.id == us.user_id).first()
        employee_rows.append({
            "name": f"{user_obj.first_name} {user_obj.last_name}" if user_obj else f"ID {us.user_id}",
            "ee": scores["EE"], "dp": scores["DP"], "rp": scores["RP"],
            "level": level,
        })

    dim_averages = {dim: round(dim_totals[dim] / total, 2) if total > 0 else 0 for dim in dim_totals}

    from app.services.html_to_pdf import HTMLToPDFConverter
    from datetime import datetime as dt
    template_data = {
        "survey_title": survey.title,
        "year": year,
        "total_responses": total,
        "dim_labels": dim_labels,
        "dim_max": dim_max,
        "dim_averages": dim_averages,
        "burnout_counts": burnout_counts,
        "employee_rows": employee_rows,
        "generated_at": dt.now().strftime("%d/%m/%Y %H:%M"),
    }
    pdf_bytes = HTMLToPDFConverter().generate_burnout_report_pdf(template_data)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="burnout_{survey_id}_{year}.pdf"'},
    )


@router.get("/templates")
async def get_survey_templates(
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Retorna las plantillas de encuestas estandarizadas disponibles."""
    if not has_role_or_custom(current_user, ["admin", "trainer"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permisos insuficientes",
        )
    return [
        {
            "id": t["id"],
            "name": t["name"],
            "description": t["description"],
            "question_count": len(t["questions"]),
        }
        for t in SURVEY_TEMPLATES.values()
    ]


@router.post("/from-template/{template_id}", response_model=SurveyResponse)
async def create_survey_from_template(
    template_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """Crea una encuesta en estado DRAFT a partir de una plantilla estandarizada."""
    if not has_role_or_custom(current_user, ["admin", "trainer"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permisos insuficientes",
        )
    template = SURVEY_TEMPLATES.get(template_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plantilla '{template_id}' no encontrada",
        )

    from app.models.survey import SurveyQuestionType as SQT

    survey = Survey(
        title=template["name"],
        description=template["description"],
        instructions=template["instructions"],
        is_anonymous=template["is_anonymous"],
        allow_multiple_responses=False,
        status=SurveyStatus.DRAFT,
        is_course_survey=False,
        required_for_completion=False,
        created_by=current_user.id,
        survey_template=template_id,
    )
    db.add(survey)
    db.commit()
    db.refresh(survey)

    for q_data in template["questions"]:
        question = SurveyQuestion(
            survey_id=survey.id,
            question_text=q_data["question_text"],
            question_type=SQT(q_data["question_type"]),
            options=q_data.get("options"),
            is_required=q_data.get("is_required", True),
            order_index=q_data["order_index"],
            min_value=q_data.get("min_value"),
            max_value=q_data.get("max_value"),
            placeholder_text=q_data.get("placeholder_text"),
        )
        db.add(question)

    db.commit()
    db.refresh(survey)

    return {
        "id": survey.id,
        "title": survey.title,
        "description": survey.description,
        "instructions": survey.instructions,
        "is_anonymous": survey.is_anonymous,
        "allow_multiple_responses": survey.allow_multiple_responses,
        "closes_at": survey.closes_at,
        "expires_at": survey.expires_at,
        "status": survey.status,
        "course_id": survey.course_id,
        "is_course_survey": survey.is_course_survey,
        "required_for_completion": survey.required_for_completion,
        "course": None,
        "created_by": survey.created_by,
        "created_at": survey.created_at,
        "updated_at": survey.updated_at,
        "published_at": survey.published_at,
        "survey_template": survey.survey_template,
        "questions": [
            {
                "id": q.id,
                "survey_id": q.survey_id,
                "question_text": q.question_text,
                "question_type": q.question_type,
                "options": q.options,
                "is_required": q.is_required,
                "order_index": q.order_index,
                "min_value": q.min_value,
                "max_value": q.max_value,
                "placeholder_text": q.placeholder_text,
                "created_at": q.created_at,
                "updated_at": q.updated_at,
            }
            for q in sorted(survey.questions, key=lambda x: x.order_index)
        ],
    }


@router.get("/{survey_id}", response_model=SurveyResponse)
async def get_survey(
    survey_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get survey by ID
    """
    survey = db.query(Survey).options(
        joinedload(Survey.questions),
        joinedload(Survey.course)
    ).filter(Survey.id == survey_id).first()
    
    if not survey:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Encuesta no encontrada"
        )
    
    # Check if user can access this survey
    if not has_role_or_custom(current_user, ["admin"]) and survey.status != SurveyStatus.PUBLISHED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La encuesta no está disponible"
        )
    
    # Transform to include course information
    survey_dict = {
        "id": survey.id,
        "title": survey.title,
        "description": survey.description,
        "instructions": survey.instructions,
        "is_anonymous": survey.is_anonymous,
        "allow_multiple_responses": survey.allow_multiple_responses,
        "status": survey.status,
        "course_id": survey.course_id,
        "is_course_survey": survey.is_course_survey,
        "required_for_completion": survey.required_for_completion,
        "course": {"id": survey.course.id, "title": survey.course.title} if survey.course else None,
        "created_by": survey.created_by,
        "created_at": survey.created_at,
        "updated_at": survey.updated_at,
        "published_at": survey.published_at,
        "closes_at": survey.closes_at,
        "expires_at": survey.expires_at,
        "questions": [{
            "id": q.id,
            "survey_id": q.survey_id,
            "question_text": q.question_text,
            "question_type": q.question_type,
            "options": q.options,
            "is_required": q.is_required,
            "order_index": q.order_index,
            "min_value": q.min_value,
            "max_value": q.max_value,
            "placeholder_text": q.placeholder_text,
            "created_at": q.created_at,
            "updated_at": q.updated_at
        } for q in survey.questions]
    }
    
    return survey_dict


@router.put("/{survey_id}", response_model=SurveyResponse)
async def update_survey(
    survey_id: int,
    survey_data: SurveyUpdate,
    force_update: bool = False,  # New parameter to force update even with responses
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Update survey (admin and capacitador roles only)
    """
    if not has_role_or_custom(current_user, ["admin", "trainer"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permisos insuficientes"
        )
    
    survey = db.query(Survey).options(joinedload(Survey.course)).filter(Survey.id == survey_id).first()
    
    if not survey:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Encuesta no encontrada"
        )
    
    # Check if survey has responses
    user_surveys_count = db.query(UserSurvey).filter(UserSurvey.survey_id == survey_id).count()
    has_responses = user_surveys_count > 0
    
    # Update survey fields (excluding questions)
    update_data = survey_data.dict(exclude_unset=True, exclude={'questions'})
    for field, value in update_data.items():
        setattr(survey, field, value)
    
    # Handle questions update if provided
    if survey_data.questions is not None:
        if has_responses and not force_update:
            if not update_data:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"No se pueden modificar las preguntas porque la encuesta ya tiene {user_surveys_count} respuestas. Use 'force_update=true' para forzar la actualización (esto puede afectar la integridad de las respuestas existentes)."
                )
            survey_data.questions = None
        
        if force_update and has_responses and survey_data.questions is not None:
            # When forcing update with existing responses, we need to handle this carefully
            # First, get existing questions with their IDs
            existing_questions = {q.id: q for q in survey.questions}
            
            # Track which questions to keep, update, or delete
            questions_to_keep = set()
            
            # Process each question in the update
            for i, question_data in enumerate(survey_data.questions):
                if hasattr(question_data, 'id') and question_data.id and question_data.id in existing_questions:
                    # Update existing question
                    existing_question = existing_questions[question_data.id]
                    update_question_data = question_data.dict(exclude_unset=True, exclude={'id'})
                    update_question_data['order_index'] = i
                    
                    for field, value in update_question_data.items():
                        setattr(existing_question, field, value)
                    
                    questions_to_keep.add(question_data.id)
                else:
                    # Create new question
                    new_question = SurveyQuestion(
                        survey_id=survey.id,
                        question_text=question_data.question_text,
                        question_type=question_data.question_type,
                        options=question_data.options,
                        is_required=question_data.is_required,
                        order_index=i,
                        min_value=question_data.min_value,
                        max_value=question_data.max_value,
                        placeholder_text=question_data.placeholder_text
                    )
                    db.add(new_question)
            
            # Delete questions that are no longer in the update (and their associated answers)
            questions_to_delete = set(existing_questions.keys()) - questions_to_keep
            if questions_to_delete:
                # Delete associated answers first
                for question_id in questions_to_delete:
                    db.query(UserSurveyAnswer).filter(UserSurveyAnswer.question_id == question_id).delete()
                
                # Delete the questions
                db.query(SurveyQuestion).filter(SurveyQuestion.id.in_(questions_to_delete)).delete()
        elif survey_data.questions is not None:
            # No responses or not forcing - safe to delete and recreate all questions
            db.query(SurveyQuestion).filter(SurveyQuestion.survey_id == survey_id).delete()
            
            # Create new questions
            for i, question_data in enumerate(survey_data.questions):
                question = SurveyQuestion(
                    survey_id=survey.id,
                    question_text=question_data.question_text,
                    question_type=question_data.question_type,
                    options=question_data.options,
                    is_required=question_data.is_required,
                    order_index=i,
                    min_value=question_data.min_value,
                    max_value=question_data.max_value,
                    placeholder_text=question_data.placeholder_text
                )
                db.add(question)
    
    try:
        db.commit()
        db.refresh(survey)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al actualizar la encuesta: {str(e)}"
        )
    
    # Transform to include course information
    survey_dict = {
        "id": survey.id,
        "title": survey.title,
        "description": survey.description,
        "instructions": survey.instructions,
        "is_anonymous": survey.is_anonymous,
        "allow_multiple_responses": survey.allow_multiple_responses,
        "status": survey.status,
        "course_id": survey.course_id,
        "is_course_survey": survey.is_course_survey,
        "required_for_completion": survey.required_for_completion,
        "course": {"id": survey.course.id, "title": survey.course.title} if survey.course else None,
        "created_by": survey.created_by,
        "created_at": survey.created_at,
        "updated_at": survey.updated_at,
        "published_at": survey.published_at,
        "closes_at": survey.closes_at,
        "expires_at": survey.expires_at,
        "questions": [{
            "id": q.id,
            "survey_id": q.survey_id,
            "question_text": q.question_text,
            "question_type": q.question_type,
            "options": q.options,
            "is_required": q.is_required,
            "order_index": q.order_index,
            "min_value": q.min_value,
            "max_value": q.max_value,
            "placeholder_text": q.placeholder_text,
            "created_at": q.created_at,
            "updated_at": q.updated_at
        } for q in survey.questions]
    }
    
    return survey_dict


@router.delete("/{survey_id}", response_model=MessageResponse)
async def delete_survey(
    survey_id: int,
    force: bool = False,  # New parameter to force deletion with cascade
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Delete survey (admin and capacitador roles only)
    """
    if not has_role_or_custom(current_user, ["admin", "trainer"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permisos insuficientes"
        )
    
    survey = db.query(Survey).filter(Survey.id == survey_id).first()
    
    if not survey:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Survey not found"
        )
    
    try:
        # Check if survey has responses
        user_surveys = db.query(UserSurvey).filter(UserSurvey.survey_id == survey_id).all()
        user_surveys_count = len(user_surveys)
        
        if user_surveys_count > 0 and not force:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No se puede eliminar la encuesta porque ya tiene {user_surveys_count} respuestas asociadas. Use el parámetro 'force=true' para eliminar en cascada o elimine primero las respuestas."
            )
        
        # If force is True, delete all related data in the correct order
        if force and user_surveys_count > 0:
            total_answers_deleted = 0
            
            # Delete all user survey answers for each user survey
            for user_survey in user_surveys:
                answers_count = db.query(UserSurveyAnswer).filter(UserSurveyAnswer.user_survey_id == user_survey.id).count()
                db.query(UserSurveyAnswer).filter(UserSurveyAnswer.user_survey_id == user_survey.id).delete()
                total_answers_deleted += answers_count
            
            # Delete all user surveys
            db.query(UserSurvey).filter(UserSurvey.survey_id == survey_id).delete()
            db.flush()  # Ensure the deletes are executed
        
        # Delete the survey (questions will be deleted automatically due to cascade="all, delete-orphan")
        db.delete(survey)
        db.commit()
        
        message = "Encuesta eliminada exitosamente"
        if force and user_surveys_count > 0:
            message += f" (se eliminaron {user_surveys_count} respuestas de usuarios y {total_answers_deleted} respuestas individuales)"
        
        return MessageResponse(message=message)
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        db.rollback()
        # Handle any other integrity constraint violations
        if "foreign key" in str(e).lower() or "viola la llave foránea" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se puede eliminar la encuesta porque tiene datos relacionados. Use el parámetro 'force=true' para eliminar en cascada."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error interno del servidor al eliminar la encuesta: {str(e)}"
            )


# Survey Questions endpoints
@router.get("/{survey_id}/questions", response_model=List[SurveyQuestionResponse])
async def get_survey_questions(
    survey_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get questions for a survey
    """
    # Check if survey exists
    survey = db.query(Survey).filter(Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Survey not found"
        )
    
    # Check if user can access this survey
    if not has_role_or_custom(current_user, ["admin"]) and survey.status != SurveyStatus.PUBLISHED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La encuesta no está disponible"
        )
    
    questions = db.query(SurveyQuestion).filter(
        SurveyQuestion.survey_id == survey_id
    ).order_by(SurveyQuestion.order_index).all()
    
    return questions


@router.post("/{survey_id}/questions", response_model=SurveyQuestionResponse)
async def create_survey_question(
    survey_id: int,
    question_data: SurveyQuestionCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Create new question for survey (admin and capacitador roles only)
    """
    if not has_role_or_custom(current_user, ["admin", "trainer"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # Check if survey exists
    survey = db.query(Survey).filter(Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Survey not found"
        )
    
    # Create new question
    question = SurveyQuestion(
        **question_data.dict(),
        survey_id=survey_id
    )
    
    db.add(question)
    db.commit()
    db.refresh(question)
    
    return question


@router.put("/questions/{question_id}", response_model=SurveyQuestionResponse)
async def update_survey_question(
    question_id: int,
    question_data: SurveyQuestionUpdate,
    force_update: bool = False,  # New parameter to force update even with responses
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Update survey question (admin and capacitador roles only)
    """
    if not has_role_or_custom(current_user, ["admin", "trainer"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    question = db.query(SurveyQuestion).filter(SurveyQuestion.id == question_id).first()
    
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pregunta no encontrada"
        )
    
    # Check if question has answers
    answers_count = db.query(UserSurveyAnswer).filter(UserSurveyAnswer.question_id == question_id).count()
    has_answers = answers_count > 0
    
    # Check if the update involves critical fields that could affect existing answers
    update_data = question_data.dict(exclude_unset=True)
    critical_fields = {'question_type', 'options', 'min_value', 'max_value'}
    has_critical_changes = any(field in update_data for field in critical_fields)
    
    if has_answers and has_critical_changes and not force_update:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede modificar la pregunta porque ya tiene {answers_count} respuestas y los cambios afectan campos críticos (tipo, opciones, valores min/max). Use 'force_update=true' para forzar la actualización (esto puede afectar la validez de las respuestas existentes)."
        )
    
    try:
        # Update question fields
        for field, value in update_data.items():
            setattr(question, field, value)
        
        db.commit()
        db.refresh(question)
        
        return question
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al actualizar la pregunta: {str(e)}"
        )


@router.delete("/questions/{question_id}", response_model=MessageResponse)
async def delete_survey_question(
    question_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Delete survey question (admin and capacitador roles only)
    """
    if not has_role_or_custom(current_user, ["admin", "trainer"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    question = db.query(SurveyQuestion).filter(SurveyQuestion.id == question_id).first()
    
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pregunta no encontrada"
        )
    
    try:
        # First, delete all answers associated with this question
        answers_count = db.query(UserSurveyAnswer).filter(UserSurveyAnswer.question_id == question_id).count()
        
        if answers_count > 0:
            # Delete all user survey answers for this question
            db.query(UserSurveyAnswer).filter(UserSurveyAnswer.question_id == question_id).delete()
            db.flush()  # Ensure the deletes are executed before deleting the question
        
        # Now delete the question
        db.delete(question)
        db.commit()
        
        message = f"Pregunta eliminada exitosamente"
        if answers_count > 0:
            message += f" (se eliminaron {answers_count} respuestas asociadas)"
        
        return MessageResponse(message=message)
        
    except Exception as e:
        db.rollback()
        # Handle any other integrity constraint violations
        if "foreign key" in str(e).lower() or "viola la llave foránea" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se puede eliminar la pregunta porque tiene datos relacionados. Contacte al administrador del sistema."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error interno del servidor al eliminar la pregunta: {str(e)}"
            )


# User Survey endpoints
@router.post("/{survey_id}/submit", response_model=UserSurveyResponse)
async def submit_survey(
    survey_id: int,
    submission_data: SurveySubmission,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Submit survey responses
    """
    # Check if survey exists and is active
    survey = db.query(Survey).options(joinedload(Survey.questions)).filter(
        and_(
            Survey.id == survey_id,
            Survey.status == SurveyStatus.PUBLISHED
        )
    ).first()
    
    if not survey:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Encuesta no encontrada o no activa"
        )
    
    submission_year = submission_data.response_date.year

    existing_submission_query = db.query(UserSurvey).filter(
        and_(
            UserSurvey.user_id == current_user.id,
            UserSurvey.survey_id == survey_id,
            UserSurvey.status == UserSurveyStatus.COMPLETED,
        )
    )

    if survey.allow_multiple_responses:
        existing_submission_query = existing_submission_query.filter(
            and_(
                UserSurvey.response_date.isnot(None),
                func.extract("year", UserSurvey.response_date) == submission_year,
            )
        )

    existing_submission = existing_submission_query.first()

    if existing_submission:
        if survey.allow_multiple_responses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Encuesta ya enviada para el año {submission_year}",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Encuesta ya enviada",
        )

    questions = list(survey.questions or [])
    if not questions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La encuesta no tiene preguntas configuradas",
        )

    answers_by_question_id = {}
    for answer in submission_data.answers:
        if answer.question_id in answers_by_question_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Respuesta duplicada para la pregunta {answer.question_id}",
            )
        answers_by_question_id[answer.question_id] = answer

    def is_question_answered(question: SurveyQuestion, answer: Any) -> bool:
        qt = question.question_type.value
        if qt in ["text", "textarea", "single_choice", "yes_no"]:
            return bool((answer.answer_text or "").strip())
        if qt in ["rating", "scale"]:
            if answer.answer_value is None:
                return False
            min_allowed = question.min_value
            max_allowed = question.max_value
            if qt == "rating":
                if min_allowed is None:
                    min_allowed = 1
                if max_allowed is None:
                    max_allowed = 5

            if min_allowed is not None and answer.answer_value < min_allowed:
                return False
            if max_allowed is not None and answer.answer_value > max_allowed:
                return False
            return True
        if qt == "multiple_choice":
            if answer.selected_options:
                try:
                    import json

                    selected = json.loads(answer.selected_options)
                    return isinstance(selected, list) and len(selected) > 0
                except (json.JSONDecodeError, TypeError):
                    return bool(answer.selected_options.strip())
            return bool((answer.answer_text or "").strip())
        return bool((answer.answer_text or "").strip()) or answer.answer_value is not None or bool(answer.selected_options)

    unanswered_questions = []
    for q in questions:
        a = answers_by_question_id.get(q.id)
        if not a or not is_question_answered(q, a):
            unanswered_questions.append(q)

    if unanswered_questions:
        missing = ", ".join(str(q.order_index + 1) for q in sorted(unanswered_questions, key=lambda x: x.order_index))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Debe contestar todas las preguntas antes de enviar. Faltan: {missing}",
        )
    
    # Get enrollment if this is a course survey
    enrollment_id = None
    if survey.course_id:
        from app.models.enrollment import Enrollment
        enrollment = db.query(Enrollment).filter(
            and_(
                Enrollment.user_id == current_user.id,
                Enrollment.course_id == survey.course_id
            )
        ).first()
        
        if not enrollment:
            raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No inscrito en el curso asociado con esta encuesta"
        )
        
        # Validate learning flow: course must be completed before taking surveys (95% means materials are done)
        if enrollment.progress < 95:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Debe completar todo el material del curso antes de responder la encuesta"
            )
        
        enrollment_id = enrollment.id
    
    # Check if there's an existing NOT_STARTED survey to update
    existing_not_started = db.query(UserSurvey).filter(
        and_(
            UserSurvey.user_id == current_user.id,
            UserSurvey.survey_id == survey_id,
            UserSurvey.status == UserSurveyStatus.NOT_STARTED
        )
    ).first()
    
    if existing_not_started and not survey.allow_multiple_responses:
        user_survey = existing_not_started
    else:
        user_survey = UserSurvey(
            user_id=current_user.id,
            survey_id=survey_id,
        )
        db.add(user_survey)

    user_survey.enrollment_id = enrollment_id
    user_survey.status = UserSurveyStatus.COMPLETED
    user_survey.response_date = submission_data.response_date
    user_survey.started_at = datetime.now()
    user_survey.completed_at = datetime.now()
    
    db.flush()  # Get the ID without committing
    
    db.query(UserSurveyAnswer).filter(UserSurveyAnswer.user_survey_id == user_survey.id).delete()

    question_ids = {q.id for q in questions}
    for answer_data in submission_data.answers:
        if answer_data.question_id not in question_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Pregunta {answer_data.question_id} no encontrada en esta encuesta",
            )

        db.add(
            UserSurveyAnswer(
                user_survey_id=user_survey.id,
                question_id=answer_data.question_id,
                answer_text=answer_data.answer_text,
                answer_value=answer_data.answer_value,
                selected_options=answer_data.selected_options,
            )
        )
    
    db.commit()
    db.refresh(user_survey)
    
    # Check if course can be completed now that survey is submitted
    if survey.course_id and survey.required_for_completion:
        from app.api.courses import check_and_complete_course
        check_and_complete_course(db, current_user.id, survey.course_id)
    
    return user_survey


@router.get("/{survey_id}/responses", response_model=PaginatedResponse[UserSurveyResponse])
async def get_survey_responses(
    survey_id: int,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get survey responses (admin and capacitador roles only)
    """
    if not has_role_or_custom(current_user, ["admin", "trainer"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # Check if survey exists
    survey = db.query(Survey).filter(Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Survey not found"
        )
    
    query = db.query(UserSurvey).filter(UserSurvey.survey_id == survey_id)
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    responses = query.offset(skip).limit(limit).all()
    
    # Calculate pagination info
    page = (skip // limit) + 1
    pages = (total + limit - 1) // limit  # Ceiling division
    has_next = skip + limit < total
    has_prev = skip > 0
    
    return PaginatedResponse(
        items=responses,
        total=total,
        page=page,
        size=limit,
        pages=pages,
        has_next=has_next,
        has_prev=has_prev
    )


@router.get("/{survey_id}/statistics", response_model=SurveyStatistics)
async def get_survey_statistics(
    survey_id: int,
    year: int = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get survey statistics (admin and capacitador roles only)
    """
    if not has_role_or_custom(current_user, ["admin", "trainer"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # Check if survey exists
    survey = db.query(Survey).filter(Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Survey not found"
        )
    
    survey_obj = db.query(Survey).options(joinedload(Survey.questions)).filter(Survey.id == survey_id).first()
    if not survey_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Survey not found",
        )

    completed_query = db.query(UserSurvey).filter(
        and_(
            UserSurvey.survey_id == survey_id,
            UserSurvey.status == UserSurveyStatus.COMPLETED,
        )
    )

    if year is not None:
        completed_query = completed_query.filter(_user_survey_year_expr() == year)

    completed_responses = completed_query.count()
    total_responses = completed_responses

    question_stats = _build_question_analysis(db=db, survey=survey_obj, year=year)

    return SurveyStatistics(
        survey_id=survey_id,
        total_responses=total_responses,
        completed_responses=completed_responses,
        completion_rate=completed_responses / total_responses if total_responses > 0 else 0,
        question_statistics=question_stats,
    )



@router.get("/user/{user_id}", response_model=PaginatedResponse[UserSurveyResponse])
async def get_user_surveys(
    user_id: int,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get surveys for a specific user
    """
    # Users can only see their own surveys unless they are admin or capacitador
    if not has_role_or_custom(current_user, ["admin", "trainer"]) and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    query = db.query(UserSurvey).filter(UserSurvey.user_id == user_id)
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    user_surveys = query.offset(skip).limit(limit).all()
    
    # Calculate pagination info
    page = (skip // limit) + 1
    pages = (total + limit - 1) // limit  # Ceiling division
    has_next = skip + limit < total
    has_prev = skip > 0
    
    return PaginatedResponse(
        items=user_surveys,
        total=total,
        page=page,
        size=limit,
        pages=pages,
        has_next=has_next,
        has_prev=has_prev
    )


@router.get("/course/{course_id}/required", response_model=List[SurveyResponse])
async def get_required_course_surveys(
    course_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get required surveys for a completed course
    """
    # Check if course exists
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Curso no encontrado"
        )
    
    # Check if user is enrolled in the course
    from app.models.enrollment import Enrollment
    enrollment = db.query(Enrollment).filter(
        and_(
            Enrollment.user_id == current_user.id,
            Enrollment.course_id == course_id
        )
    ).first()
    
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No inscrito en este curso"
        )
    
    # Get required surveys for this course that are active
    surveys = db.query(Survey).filter(
        and_(
            Survey.course_id == course_id,
            Survey.required_for_completion == True,
            Survey.status == SurveyStatus.PUBLISHED
        )
    ).all()
    
    # Filter out surveys already completed by the user
    pending_surveys = []
    for survey in surveys:
        user_submission = db.query(UserSurvey).filter(
            and_(
                UserSurvey.user_id == current_user.id,
                UserSurvey.survey_id == survey.id,
                UserSurvey.status == UserSurveyStatus.COMPLETED
            )
        ).first()
        
        if not user_submission:
            # Convert course object to dict if it exists
            course_dict = None
            if survey.course:
                course_dict = {"id": survey.course.id, "title": survey.course.title}
            
            survey_response = SurveyResponse(
                id=survey.id,
                title=survey.title,
                description=survey.description,
                status=survey.status,
                is_anonymous=survey.is_anonymous,
                course_id=survey.course_id,
                is_course_survey=survey.is_course_survey,
                required_for_completion=survey.required_for_completion,
                course=course_dict,
                created_by=survey.created_by,
                created_at=survey.created_at,
                updated_at=survey.updated_at,
                published_at=survey.published_at,
                questions=[]
            )
            pending_surveys.append(survey_response)
    
    return pending_surveys


@router.get("/{survey_id}/presentation", response_model=SurveyPresentation)
async def get_survey_presentation(
    survey_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get survey for presentation (without answers for active surveys)
    """
    survey = db.query(Survey).filter(Survey.id == survey_id).first()
    
    if not survey:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Survey not found"
        )
    
    # Check if user can access this survey
    if not has_role_or_custom(current_user, ["admin"]) and survey.status != SurveyStatus.PUBLISHED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Survey is not available"
        )
    
    # Get questions without correct answers for non-admin users
    questions = db.query(SurveyQuestion).filter(
        SurveyQuestion.survey_id == survey_id
    ).order_by(SurveyQuestion.order).all()
    
    # Check if user has already submitted this survey
    user_submission = db.query(UserSurvey).filter(
        and_(
            UserSurvey.user_id == current_user.id,
            UserSurvey.survey_id == survey_id
        )
    ).first()
    
    return SurveyPresentation(
        survey=survey,
        questions=questions,
        is_submitted=user_submission is not None,
        user_submission=user_submission
    )


@router.get("/{survey_id}/detailed-results", response_model=SurveyDetailedResults)
async def get_survey_detailed_results(
    survey_id: int,
    year: int = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get detailed survey results with employee information (admin and capacitador roles only)
    """
    if not has_role_or_custom(current_user, ["admin", "trainer"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # Check if survey exists
    survey = db.query(Survey).options(
        joinedload(Survey.questions),
        joinedload(Survey.course)
    ).filter(Survey.id == survey_id).first()
    
    if not survey:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Survey not found"
        )
    
    user_surveys_query = db.query(UserSurvey).options(
        joinedload(UserSurvey.user),
        joinedload(UserSurvey.answers)
    ).filter(UserSurvey.survey_id == survey_id)

    if year is not None:
        user_surveys_query = user_surveys_query.filter(
            and_(
                _user_survey_year_expr() == year,
            )
        )

    user_surveys = user_surveys_query.all()
    
    # Build employee responses with enhanced structure
    employee_responses = []
    for user_survey in user_surveys:
        if user_survey.user:
            # Get worker information from workers table
            worker = db.query(Worker).filter(Worker.user_id == user_survey.user.id).first()
            
            # Build structured answers list
            structured_answers = []
            answers_by_question = {answer.question_id: answer for answer in user_survey.answers}
            
            for question in survey.questions:
                answer = answers_by_question.get(question.id)
                
                if answer:
                    # Format display value based on question type
                    display_value = ""
                    if question.question_type.value in ["multiple_choice", "single_choice"]:
                        # For multiple/single choice, use selected_options if available, otherwise answer_text
                        if answer.selected_options:
                            try:
                                import json
                                selected = json.loads(answer.selected_options)
                                if isinstance(selected, list):
                                    display_value = ", ".join(selected) if selected else "Sin respuesta"
                                else:
                                    display_value = str(selected)
                            except (json.JSONDecodeError, TypeError):
                                display_value = answer.selected_options
                        else:
                            display_value = answer.answer_text or "Sin respuesta"
                    elif question.question_type.value in ["scale", "rating"]:
                        if answer.answer_value is not None:
                            display_value = f"{answer.answer_value}/{question.max_value or 10}"
                        else:
                            display_value = "Sin calificación"
                    elif question.question_type.value in ["text", "textarea", "yes_no"]:
                        display_value = answer.answer_text or "Sin respuesta"
                    else:
                        display_value = answer.answer_text or "Sin respuesta"
                    
                    answer_detail = AnswerDetail(
                        question_id=question.id,
                        question_text=question.question_text,
                        question_type=question.question_type.value,
                        answer_text=answer.answer_text,
                        answer_value=answer.answer_value,
                        selected_options=answer.selected_options,
                        display_value=display_value,
                        is_answered=True
                    )
                else:
                    # Question not answered
                    answer_detail = AnswerDetail(
                        question_id=question.id,
                        question_text=question.question_text,
                        question_type=question.question_type.value,
                        display_value="Sin respuesta",
                        is_answered=False
                    )
                
                structured_answers.append(answer_detail)
            
            # Calculate completion percentage
            answered_questions = len([a for a in structured_answers if a.is_answered])
            total_questions = len(survey.questions)
            completion_percentage = (answered_questions / total_questions * 100) if total_questions > 0 else 0
            
            # Calculate response time
            response_time_minutes = None
            if user_survey.started_at and user_survey.completed_at:
                time_diff = user_survey.completed_at - user_survey.started_at
                response_time_minutes = round(time_diff.total_seconds() / 60, 2)
            
            # Determine submission status
            submission_status = "completed" if user_survey.status == UserSurveyStatus.COMPLETED else user_survey.status.value
            
            employee_response = EmployeeResponse(
                user_id=user_survey.user.id,
                employee_name=f"{user_survey.user.first_name} {user_survey.user.last_name}",
                employee_email=user_survey.user.email,
                cargo=worker.position if worker else "No especificado",
                telefono=worker.phone if worker else "No especificado",
                response_date=user_survey.response_date,
                submission_date=user_survey.completed_at,
                submission_status=submission_status,
                response_time_minutes=response_time_minutes,
                answers=structured_answers,
                completion_percentage=round(completion_percentage, 1)
            )
            employee_responses.append(employee_response)
    
    # Calculate statistics
    total_responses = len(user_surveys)
    completed_responses = len([us for us in user_surveys if us.status == UserSurveyStatus.COMPLETED])
    completion_rate = completed_responses / total_responses if total_responses > 0 else 0
    
    return SurveyDetailedResults(
        survey_id=survey_id,
        survey_title=survey.title,
        survey_description=survey.description,
        course_title=survey.course.title if survey.course else None,
        total_responses=total_responses,
        completed_responses=completed_responses,
        completion_rate=completion_rate,
        questions=survey.questions,
        employee_responses=employee_responses
    )


@router.get("/{survey_id}/report/pdf")
async def get_survey_year_pdf_report(
    survey_id: int,
    year: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    if not has_role_or_custom(current_user, ["admin", "trainer"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )

    survey = db.query(Survey).options(
        joinedload(Survey.questions),
        joinedload(Survey.course),
    ).filter(Survey.id == survey_id).first()

    if not survey:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Survey not found",
        )

    question_stats = _build_question_analysis(db=db, survey=survey, year=year)

    completed_query = db.query(UserSurvey).filter(
        and_(
            UserSurvey.survey_id == survey_id,
            UserSurvey.status == UserSurveyStatus.COMPLETED,
            _user_survey_year_expr() == year,
        )
    )
    completed_responses = completed_query.count()
    total_responses = completed_responses
    completion_rate = 1.0 if total_responses > 0 else 0

    converter = HTMLToPDFConverter()
    pdf_content = converter.generate_survey_year_report_pdf(
        {
            "survey_id": survey.id,
            "survey_title": survey.title,
            "survey_description": survey.description,
            "course_title": survey.course.title if survey.course else None,
            "year": year,
            "total_responses": total_responses,
            "completed_responses": completed_responses,
            "completion_rate": completion_rate,
            "question_statistics": question_stats,
        }
    )

    filename = f"reporte_encuesta_{survey_id}_{year}.pdf"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=pdf_content, media_type="application/pdf", headers=headers)


@router.get("/{survey_id}/available-years", response_model=List[int])
async def get_survey_available_years(
    survey_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    if not has_role_or_custom(current_user, ["admin", "trainer"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )

    exists = db.query(Survey.id).filter(Survey.id == survey_id).first()
    if not exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Survey not found",
        )

    year_expr = _user_survey_year_expr().label("year")
    years = (
        db.query(year_expr)
        .filter(UserSurvey.survey_id == survey_id)
        .filter(year_expr.isnot(None))
        .distinct()
        .order_by(year_expr.desc())
        .all()
    )

    return [int(row.year) for row in years if row.year is not None]


@router.post("/cleanup/orphaned-answers", response_model=MessageResponse)
async def cleanup_orphaned_answers(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Clean up orphaned survey answers (admin only)
    This endpoint removes UserSurveyAnswer records that reference non-existent SurveyQuestion records
    """
    if not has_role_or_custom(current_user, ["admin"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los administradores pueden ejecutar la limpieza de datos"
        )
    
    try:
        # Find orphaned answers - answers that reference questions that don't exist
        orphaned_answers = db.query(UserSurveyAnswer).filter(
            ~UserSurveyAnswer.question_id.in_(
                db.query(SurveyQuestion.id)
            )
        ).all()
        
        orphaned_count = len(orphaned_answers)
        
        if orphaned_count == 0:
            return MessageResponse(message="No se encontraron respuestas huérfanas para limpiar")
        
        # Delete orphaned answers
        for answer in orphaned_answers:
            db.delete(answer)
        
        db.commit()
        
        return MessageResponse(
            message=f"Limpieza completada exitosamente. Se eliminaron {orphaned_count} respuestas huérfanas"
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error durante la limpieza de datos: {str(e)}"
        )


@router.get("/cleanup/check-integrity", response_model=dict)
async def check_data_integrity(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Check data integrity for surveys (admin only)
    Returns information about potential data integrity issues
    """
    if not has_role_or_custom(current_user, ["admin"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los administradores pueden verificar la integridad de datos"
        )
    
    try:
        # Check for orphaned answers
        orphaned_answers = db.query(UserSurveyAnswer).filter(
            ~UserSurveyAnswer.question_id.in_(
                db.query(SurveyQuestion.id)
            )
        ).all()
        
        # Check for orphaned user surveys
        orphaned_user_surveys = db.query(UserSurvey).filter(
            ~UserSurvey.survey_id.in_(
                db.query(Survey.id)
            )
        ).all()
        
        # Check for orphaned questions
        orphaned_questions = db.query(SurveyQuestion).filter(
            ~SurveyQuestion.survey_id.in_(
                db.query(Survey.id)
            )
        ).all()
        
        # Get specific problematic question IDs
        problematic_question_ids = [answer.question_id for answer in orphaned_answers]
        unique_problematic_question_ids = list(set(problematic_question_ids))
        
        return {
            "orphaned_answers": {
                "count": len(orphaned_answers),
                "question_ids": unique_problematic_question_ids
            },
            "orphaned_user_surveys": {
                "count": len(orphaned_user_surveys),
                "survey_ids": [us.survey_id for us in orphaned_user_surveys]
            },
            "orphaned_questions": {
                "count": len(orphaned_questions),
                "question_ids": [q.id for q in orphaned_questions]
            },
            "total_issues": len(orphaned_answers) + len(orphaned_user_surveys) + len(orphaned_questions)
        }
        
    except Exception as e:
        raise HTTPException(
             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
             detail=f"Error al verificar la integridad de datos: {str(e)}"
         )


@router.get("/{survey_id}/edit-impact", response_model=dict)
async def get_survey_edit_impact(
    survey_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get information about the impact of editing a survey (admin and capacitador roles only)
    Returns details about existing responses that would be affected
    """
    if not has_role_or_custom(current_user, ["admin", "trainer"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permisos insuficientes"
        )
    
    survey = db.query(Survey).filter(Survey.id == survey_id).first()
    
    if not survey:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Encuesta no encontrada"
        )
    
    try:
        # Get user surveys and their responses
        user_surveys = db.query(UserSurvey).filter(UserSurvey.survey_id == survey_id).all()
        
        # Get question-level response counts
        question_response_counts = {}
        for question in survey.questions:
            answer_count = db.query(UserSurveyAnswer).filter(UserSurveyAnswer.question_id == question.id).count()
            question_response_counts[question.id] = {
                "question_text": question.question_text,
                "question_type": question.question_type,
                "answer_count": answer_count
            }
        
        return {
            "survey_id": survey_id,
            "survey_title": survey.title,
            "total_user_surveys": len(user_surveys),
            "completed_surveys": len([us for us in user_surveys if us.status == UserSurveyStatus.COMPLETED]),
            "in_progress_surveys": len([us for us in user_surveys if us.status == UserSurveyStatus.IN_PROGRESS]),
            "question_response_counts": question_response_counts,
            "can_edit_safely": len(user_surveys) == 0,
            "requires_force_update": len(user_surveys) > 0,
            "warning_message": f"Esta encuesta tiene {len(user_surveys)} respuestas de usuarios. Editarla puede afectar la integridad de los datos existentes." if len(user_surveys) > 0 else None
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener información de impacto: {str(e)}"
        )


@router.get("/questions/{question_id}/edit-impact", response_model=dict)
async def get_question_edit_impact(
    question_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get information about the impact of editing a question (admin and capacitador roles only)
    Returns details about existing answers that would be affected
    """
    if not has_role_or_custom(current_user, ["admin", "trainer"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permisos insuficientes"
        )
    
    question = db.query(SurveyQuestion).filter(SurveyQuestion.id == question_id).first()
    
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pregunta no encontrada"
        )
    
    try:
        # Get answers for this question
        answers = db.query(UserSurveyAnswer).filter(UserSurveyAnswer.question_id == question_id).all()
        
        # Analyze answer distribution
        answer_distribution = {}
        for answer in answers:
            answer_value = answer.answer_value
            if answer_value in answer_distribution:
                answer_distribution[answer_value] += 1
            else:
                answer_distribution[answer_value] = 1
        
        return {
            "question_id": question_id,
            "question_text": question.question_text,
            "question_type": question.question_type,
            "current_options": question.options,
            "total_answers": len(answers),
            "answer_distribution": answer_distribution,
            "can_edit_safely": len(answers) == 0,
            "requires_force_update": len(answers) > 0,
            "critical_fields": ["question_type", "options", "min_value", "max_value"],
            "warning_message": f"Esta pregunta tiene {len(answers)} respuestas. Cambiar el tipo, opciones o valores min/max puede afectar la validez de las respuestas existentes." if len(answers) > 0 else None
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener información de impacto: {str(e)}"
        )
