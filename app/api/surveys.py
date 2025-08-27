from typing import Any, List
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func

from app.dependencies import get_current_active_user
from app.database import get_db
from app.models.user import User
from app.models.survey import Survey, SurveyQuestion, UserSurvey, UserSurveyAnswer, SurveyStatus, UserSurveyStatus
from app.models.course import Course
from app.models.worker import Worker
from app.schemas.survey import (
    SurveyCreate, SurveyUpdate, SurveyResponse,
    SurveyListResponse, SurveyQuestionCreate, SurveyQuestionUpdate,
    SurveyQuestionResponse, UserSurveyCreate, UserSurveyResponse,
    UserSurveyAnswerCreate, UserSurveyAnswerResponse,
    SurveySubmission, SurveyStatistics, SurveyPresentation,
    SurveyDetailedResults, EmployeeResponse, AnswerDetail
)
from app.schemas.common import MessageResponse, PaginatedResponse

router = APIRouter()


@router.get("/", response_model=PaginatedResponse[SurveyListResponse])
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
        if current_user.role.value not in ["admin", "capacitador"]:
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
async def create_survey(
    survey_data: SurveyCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Create new survey (admin and capacitador roles only)
    """
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # Check if course exists (if course_id is provided)
    if survey_data.course_id:
        course = db.query(Course).filter(Course.id == survey_data.course_id).first()
        if not course:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Course not found"
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
        "questions": survey.questions
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
    
    # Build query for available surveys
    query = db.query(Survey).options(joinedload(Survey.course)).filter(
        and_(
            Survey.status == SurveyStatus.PUBLISHED,
            or_(
                # General surveys (not course-specific)
                Survey.course_id.is_(None),
                # Course-specific surveys for enrolled courses
                Survey.course_id.in_(enrolled_course_ids)
            )
        )
    )
    
    # Filter out surveys already completed by the user
    completed_survey_ids = db.query(UserSurvey.survey_id).filter(
        and_(
            UserSurvey.user_id == current_user.id,
            UserSurvey.status == UserSurveyStatus.COMPLETED
        )
    ).subquery()
    
    query = query.filter(~Survey.id.in_(completed_survey_ids))
    
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
        available_surveys = db.query(Survey).options(joinedload(Survey.course)).filter(
            Survey.course_id.in_(course_ids),
            Survey.status == SurveyStatus.PUBLISHED
        ).all()
        
        # Get user's survey submissions
        user_surveys = db.query(UserSurvey).filter(
            UserSurvey.user_id == current_user.id
        ).all()
        
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
            detail="Survey not found"
        )
    
    # Check if user can access this survey
    if current_user.role.value != "admin" and survey.status != SurveyStatus.PUBLISHED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Survey is not available"
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
        "questions": survey.questions
    }
    
    return survey_dict


@router.put("/{survey_id}", response_model=SurveyResponse)
async def update_survey(
    survey_id: int,
    survey_data: SurveyUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Update survey (admin and capacitador roles only)
    """
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    survey = db.query(Survey).options(joinedload(Survey.course)).filter(Survey.id == survey_id).first()
    
    if not survey:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Survey not found"
        )
    
    # Update survey fields (excluding questions)
    update_data = survey_data.dict(exclude_unset=True, exclude={'questions'})
    for field, value in update_data.items():
        setattr(survey, field, value)
    
    # Handle questions update if provided
    if survey_data.questions is not None:
        # Delete existing questions
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
    
    db.commit()
    db.refresh(survey)
    
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
        "questions": survey.questions
    }
    
    return survey_dict


@router.delete("/{survey_id}", response_model=MessageResponse)
async def delete_survey(
    survey_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Delete survey (admin and capacitador roles only)
    """
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    survey = db.query(Survey).filter(Survey.id == survey_id).first()
    
    if not survey:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Survey not found"
        )
    
    db.delete(survey)
    db.commit()
    
    return MessageResponse(message="Survey deleted successfully")


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
    if current_user.role.value != "admin" and survey.status != SurveyStatus.PUBLISHED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Survey is not available"
        )
    
    questions = db.query(SurveyQuestion).filter(
        SurveyQuestion.survey_id == survey_id
    ).order_by(SurveyQuestion.order).all()
    
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
    if current_user.role.value not in ["admin", "capacitador"]:
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
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Update survey question (admin and capacitador roles only)
    """
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    question = db.query(SurveyQuestion).filter(SurveyQuestion.id == question_id).first()
    
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found"
        )
    
    # Update question fields
    update_data = question_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(question, field, value)
    
    db.commit()
    db.refresh(question)
    
    return question


@router.delete("/questions/{question_id}", response_model=MessageResponse)
async def delete_survey_question(
    question_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Delete survey question (admin and capacitador roles only)
    """
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    question = db.query(SurveyQuestion).filter(SurveyQuestion.id == question_id).first()
    
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found"
        )
    
    db.delete(question)
    db.commit()
    
    return MessageResponse(message="Question deleted successfully")


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
    survey = db.query(Survey).filter(
        and_(
            Survey.id == survey_id,
            Survey.status == SurveyStatus.PUBLISHED
        )
    ).first()
    
    if not survey:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Survey not found or not active"
        )
    
    # Check if user has already submitted this survey
    existing_submission = db.query(UserSurvey).filter(
        and_(
            UserSurvey.user_id == current_user.id,
            UserSurvey.survey_id == survey_id
        )
    ).first()
    
    if existing_submission:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Survey already submitted"
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
                detail="Not enrolled in the course associated with this survey"
            )
        enrollment_id = enrollment.id
    
    # Create user survey record
    user_survey = UserSurvey(
        user_id=current_user.id,
        survey_id=survey_id,
        enrollment_id=enrollment_id,
        status=UserSurveyStatus.COMPLETED,
        started_at=datetime.now(),
        completed_at=datetime.now()
    )
    
    db.add(user_survey)
    db.flush()  # Get the ID without committing
    
    # Create answers
    for answer_data in submission_data.answers:
        # Verify question belongs to this survey
        question = db.query(SurveyQuestion).filter(
            and_(
                SurveyQuestion.id == answer_data.question_id,
                SurveyQuestion.survey_id == survey_id
            )
        ).first()
        
        if not question:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Question {answer_data.question_id} not found in this survey"
            )
        
        answer = UserSurveyAnswer(
            user_survey_id=user_survey.id,
            question_id=answer_data.question_id,
            answer_text=answer_data.answer_text,
            answer_value=answer_data.answer_value
        )
        
        db.add(answer)
    
    db.commit()
    db.refresh(user_survey)
    
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
    if current_user.role.value not in ["admin", "capacitador"]:
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
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get survey statistics (admin and capacitador roles only)
    """
    if current_user.role.value not in ["admin", "capacitador"]:
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
    
    # Get response statistics
    total_responses = db.query(UserSurvey).filter(UserSurvey.survey_id == survey_id).count()
    completed_responses = db.query(UserSurvey).filter(
        and_(
            UserSurvey.survey_id == survey_id,
            UserSurvey.status == UserSurveyStatus.COMPLETED
        )
    ).count()
    
    # Get question statistics
    questions = db.query(SurveyQuestion).filter(SurveyQuestion.survey_id == survey_id).all()
    question_stats = []
    
    for question in questions:
        answers = db.query(UserSurveyAnswer).filter(
            UserSurveyAnswer.question_id == question.id
        ).all()
        
        question_stats.append({
            "question_id": question.id,
            "question_text": question.question_text,
            "question_type": question.question_type,
            "total_answers": len(answers),
            "answers": [{
                "answer_text": answer.answer_text,
                "answer_value": answer.answer_value
            } for answer in answers]
        })
    
    return SurveyStatistics(
        survey_id=survey_id,
        total_responses=total_responses,
        completed_responses=completed_responses,
        completion_rate=completed_responses / total_responses if total_responses > 0 else 0,
        question_statistics=question_stats
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
    if current_user.role.value not in ["admin", "capacitador"] and current_user.id != user_id:
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
            detail="Course not found"
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
            detail="Not enrolled in this course"
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
            pending_surveys.append(survey)
    
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
    if current_user.role.value != "admin" and survey.status != SurveyStatus.PUBLISHED:
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
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get detailed survey results with employee information (admin and capacitador roles only)
    """
    if current_user.role.value not in ["admin", "capacitador"]:
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
    
    # Get all user surveys for this survey
    user_surveys = db.query(UserSurvey).options(
        joinedload(UserSurvey.user),
        joinedload(UserSurvey.answers)
    ).filter(UserSurvey.survey_id == survey_id).all()
    
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
                    if question.question_type.value == "multiple_choice" or question.question_type.value == "single_choice":
                        display_value = answer.answer_text or "Sin respuesta"
                    elif question.question_type.value in ["rating", "scale"]:
                        if answer.answer_value is not None:
                            display_value = f"{answer.answer_value}/{question.max_value or 10}"
                        else:
                            display_value = "Sin calificación"
                    elif question.question_type.value in ["text", "textarea"]:
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