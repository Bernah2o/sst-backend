from typing import Any, List
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func

from app.dependencies import get_current_active_user
from app.database import get_db
from app.models.user import User
from app.models.course import Course
from app.models.evaluation import (
    Evaluation, Question, Answer, UserEvaluation, UserAnswer,
    EvaluationStatus, UserEvaluationStatus, QuestionType
)
from app.schemas.evaluation import (
    EvaluationCreate, EvaluationUpdate, EvaluationResponse,
    EvaluationListResponse, EvaluationSubmission,
    UserEvaluationResponse, AnswerSubmission
)
from app.schemas.common import MessageResponse, PaginatedResponse
from app.models.certificate import Certificate, CertificateStatus
from app.services.certificate_generator import CertificateGenerator
import uuid

router = APIRouter()


@router.get("/", response_model=PaginatedResponse[EvaluationListResponse])
@router.get("", response_model=PaginatedResponse[EvaluationListResponse])
async def get_evaluations(
    skip: int = 0,
    limit: int = 100,
    course_id: int = None,
    status: EvaluationStatus = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get all evaluations with optional filtering
    """
    from app.models.course import Course
    
    query = db.query(Evaluation).join(Course, Evaluation.course_id == Course.id)
    
    # Apply filters
    if course_id:
        query = query.filter(Evaluation.course_id == course_id)
    
    if status:
        query = query.filter(Evaluation.status == status)
    else:
        # Only show active evaluations for non-admin/capacitador users
        if current_user.role.value not in ["admin", "capacitador"]:
            query = query.filter(Evaluation.status == EvaluationStatus.PUBLISHED)
    
    # Get total count
    total = query.count()
    
    # Apply pagination and eager load course
    evaluations = query.options(joinedload(Evaluation.course)).offset(skip).limit(limit).all()
    
    # Calculate pagination fields
    page = (skip // limit) + 1 if limit > 0 else 1
    pages = (total + limit - 1) // limit if limit > 0 else 1
    has_next = skip + limit < total
    has_prev = skip > 0
    
    return PaginatedResponse(
        items=evaluations,
        total=total,
        page=page,
        size=limit,
        pages=pages,
        has_next=has_next,
        has_prev=has_prev
    )


@router.get("/available", response_model=List[EvaluationResponse])
async def get_available_evaluations(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get available evaluations for the current user (active evaluations not yet completed)
    """
    # Get active evaluations
    evaluations_query = db.query(Evaluation).filter(
        Evaluation.status == EvaluationStatus.PUBLISHED
    )
    
    # Get evaluations already completed by the user
    completed_evaluation_ids = db.query(UserEvaluation.evaluation_id).filter(
        UserEvaluation.user_id == current_user.id
    ).subquery()
    
    # Filter out completed evaluations
    available_evaluations = evaluations_query.filter(
        ~Evaluation.id.in_(completed_evaluation_ids)
    ).all()
    
    return available_evaluations


@router.get("/stats")
async def get_evaluation_stats(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get evaluation statistics by status
    """
    # Check permissions
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # Get counts by status
    stats_query = db.query(
        Evaluation.status,
        func.count(Evaluation.id).label('count')
    ).group_by(Evaluation.status).all()
    
    # Initialize stats with default values
    stats = {
        "total": 0,
        "draft": 0,
        "published": 0,
        "archived": 0
    }
    
    # Populate stats from query results
    for status_result, count in stats_query:
        stats[status_result.value] = count
        stats["total"] += count
    
    return stats


@router.post("/", response_model=EvaluationResponse)
@router.post("", response_model=EvaluationResponse)
async def create_evaluation(
    evaluation_data: EvaluationCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Create new evaluation (admin and capacitador roles only)
    """
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # Create new evaluation
    evaluation = Evaluation(
        **evaluation_data.dict(exclude={"questions"}),
        created_by=current_user.id
    )
    
    db.add(evaluation)
    db.commit()
    db.refresh(evaluation)
    
    # Add questions if provided
    if evaluation_data.questions:
        for question_data in evaluation_data.questions:
            question = Question(
                **question_data.dict(exclude={"options", "correct_answer"}),
                evaluation_id=evaluation.id
            )
            db.add(question)
            db.commit()
            db.refresh(question)
            
            # Add answers from options if provided
            if question_data.options:
                for i, option_text in enumerate(question_data.options):
                    if option_text.strip():  # Only add non-empty options
                        is_correct = option_text == question_data.correct_answer
                        answer = Answer(
                            answer_text=option_text,
                            is_correct=is_correct,
                            order_index=i,
                            question_id=question.id
                        )
                        db.add(answer)
        
        db.commit()
    
    return evaluation


# Routes with path parameters will be moved to the end of the file


def update_user_best_score(db: Session, user_id: int, evaluation_id: int):
    """
    Update the user's best score for an evaluation based on all completed attempts
    """
    # Get all completed attempts for this user and evaluation
    completed_attempts = db.query(UserEvaluation).filter(
        and_(
            UserEvaluation.user_id == user_id,
            UserEvaluation.evaluation_id == evaluation_id,
            UserEvaluation.status == UserEvaluationStatus.COMPLETED
        )
    ).all()
    
    if not completed_attempts:
        return
    
    # Find the attempt with the highest percentage
    best_attempt = max(completed_attempts, key=lambda x: x.percentage or 0)
    
    # Update all attempts to mark only the best one as the "best"
    for attempt in completed_attempts:
        attempt.is_best_attempt = (attempt.id == best_attempt.id)
    
    db.commit()


# Routes with path parameters moved to end of file


@router.get("/results")
async def get_user_evaluation_results(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get current user's evaluation results
    """
    from fastapi.responses import JSONResponse
    
    try:
        user_evaluations = db.query(UserEvaluation).filter(
            UserEvaluation.user_id == current_user.id
        ).all()
        
        # Return simple dictionary to avoid Pydantic validation issues
        result = []
        for ue in user_evaluations:
            # Ensure all values are of the correct type
            result.append({
                "id": int(ue.id),
                "user_id": int(ue.user_id),
                "evaluation_id": int(ue.evaluation_id),
                "enrollment_id": int(ue.enrollment_id) if ue.enrollment_id else None,
                "attempt_number": int(ue.attempt_number),
                "status": ue.status.value if ue.status else None,
                "score": float(ue.score) if ue.score is not None else None,
                "total_points": float(ue.total_points) if ue.total_points is not None else None,
                "max_points": float(ue.max_points) if ue.max_points is not None else None,
                "percentage": float(ue.percentage) if ue.percentage is not None else None,
                "time_spent_minutes": int(ue.time_spent_minutes) if ue.time_spent_minutes is not None else None,
                "passed": bool(ue.passed),
                "started_at": ue.started_at.isoformat() if ue.started_at else None,
                "completed_at": ue.completed_at.isoformat() if ue.completed_at else None,
                "expires_at": ue.expires_at.isoformat() if ue.expires_at else None,
                "created_at": ue.created_at.isoformat() if ue.created_at else None,
                "updated_at": ue.updated_at.isoformat() if ue.updated_at else None
            })
        
        # Return a direct JSONResponse to bypass FastAPI validation
        return JSONResponse(
            content={
                "success": True,
                "data": result
            }
        )
    except Exception as e:
        print(f"Error getting user evaluation results: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Error retrieving evaluation results: {str(e)}",
                "data": []
            }
        )


@router.post("/{evaluation_id}/submit")
async def submit_evaluation(
    evaluation_id: int,
    answers: List[AnswerSubmission],
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Submit evaluation answers
    """
    from datetime import datetime
    from app.models.evaluation import UserAnswer
    
    # Get the evaluation
    evaluation = db.query(Evaluation).filter(Evaluation.id == evaluation_id).first()
    if not evaluation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation not found"
        )
    
    # Get the user's current evaluation attempt
    user_evaluation = db.query(UserEvaluation).filter(
        and_(
            UserEvaluation.user_id == current_user.id,
            UserEvaluation.evaluation_id == evaluation_id,
            UserEvaluation.status == UserEvaluationStatus.IN_PROGRESS
        )
    ).first()
    
    if not user_evaluation:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active evaluation attempt found"
        )
    
    # Check if evaluation has expired
    if user_evaluation.expires_at and datetime.utcnow() > user_evaluation.expires_at:
        # Mark as expired and don't allow submission
        user_evaluation.status = UserEvaluationStatus.EXPIRED
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Evaluation time has expired"
        )
    
    # Get all questions for this evaluation
    questions = db.query(Question).filter(Question.evaluation_id == evaluation_id).all()
    questions_dict = {q.id: q for q in questions}
    
    # Validate that all required questions are answered
    answered_question_ids = {answer.question_id for answer in answers}
    required_question_ids = {q.id for q in questions}
    
    if answered_question_ids != required_question_ids:
        missing_questions = required_question_ids - answered_question_ids
        extra_questions = answered_question_ids - required_question_ids
        
        error_details = []
        if missing_questions:
            error_details.append(f"Missing answers for questions: {list(missing_questions)}")
        if extra_questions:
            error_details.append(f"Extra answers for non-existent questions: {list(extra_questions)}")
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid answers: " + "; ".join(error_details)
        )
    
    # Delete existing answers for this attempt (in case of resubmission)
    db.query(UserAnswer).filter(
        UserAnswer.user_evaluation_id == user_evaluation.id
    ).delete()
    
    # Save new answers
    total_points = 0
    max_points = 0
    
    for answer_submission in answers:
        question = questions_dict[answer_submission.question_id]
        max_points += question.points
        
        # Calculate points for this answer
        points_earned = 0
        is_correct = False
        
        if question.question_type == QuestionType.MULTIPLE_CHOICE:
            # For multiple choice, check if the selected option is correct
            if answer_submission.selected_option_id:
                answer_option = db.query(Answer).filter(
                    and_(
                        Answer.id == answer_submission.selected_option_id,
                        Answer.question_id == question.id
                    )
                ).first()
                
                if answer_option and answer_option.is_correct:
                    points_earned = question.points
                    is_correct = True
        
        elif question.question_type == QuestionType.TRUE_FALSE:
            # For true/false, check if the answer matches the correct answer
            if answer_submission.boolean_answer is not None:
                # Assuming the correct answer is stored in the question's correct_answer field
                # You might need to adjust this based on your data model
                if hasattr(question, 'correct_answer') and answer_submission.boolean_answer == question.correct_answer:
                    points_earned = question.points
                    is_correct = True
        
        elif question.question_type == QuestionType.SHORT_ANSWER:
            # For short answer, you might want to implement fuzzy matching or manual grading
            # For now, we'll mark it as requiring manual review
            points_earned = 0  # Will need manual grading
            is_correct = False
        
        total_points += points_earned
        
        # Create user answer record
        selected_answer_ids = None
        if answer_submission.selected_option_id:
            selected_answer_ids = str(answer_submission.selected_option_id)
        
        user_answer = UserAnswer(
            user_evaluation_id=user_evaluation.id,
            question_id=question.id,
            selected_answer_ids=selected_answer_ids,
            answer_text=answer_submission.text_answer,
            points_earned=points_earned,
            is_correct=is_correct
        )
        
        db.add(user_answer)
    
    # Calculate final score and percentage
    percentage = (total_points / max_points * 100) if max_points > 0 else 0
    passed = percentage >= evaluation.passing_score
    
    # Calculate time spent
    current_time = datetime.utcnow()
    time_spent_minutes = None
    if user_evaluation.started_at:
        time_spent_delta = current_time - user_evaluation.started_at
        time_spent_minutes = int(time_spent_delta.total_seconds() / 60)
    
    # Update user evaluation with results
    user_evaluation.status = UserEvaluationStatus.COMPLETED
    user_evaluation.completed_at = current_time
    user_evaluation.score = total_points
    user_evaluation.total_points = total_points
    user_evaluation.max_points = max_points
    user_evaluation.percentage = percentage
    user_evaluation.passed = passed
    user_evaluation.time_spent_minutes = time_spent_minutes
    
    db.commit()
    
    # Generate certificate if passed
    certificate_url = None
    if passed:
        try:
            # Check if certificate already exists
            existing_certificate = db.query(Certificate).filter(
                and_(
                    Certificate.user_id == user_evaluation.user_id,
                    Certificate.course_id == user_evaluation.evaluation.course_id
                )
            ).first()
            
            if not existing_certificate:
                # Generate certificate automatically
                import uuid
                certificate_number = f"CERT-{datetime.now().year}-{str(uuid.uuid4())[:8].upper()}"
                verification_code = str(uuid.uuid4())
                
                # Get course and user info
                course = user_evaluation.evaluation.course
                user = user_evaluation.user
                
                certificate = Certificate(
                    user_id=user_evaluation.user_id,
                    course_id=user_evaluation.evaluation.course_id,
                    certificate_number=certificate_number,
                    title=f"Certificado de Finalización - {course.title}",
                    description=f"Certifica que {user.full_name} ha completado satisfactoriamente el curso {course.title}",
                    score_achieved=percentage,
                    completion_date=current_time,
                    issue_date=current_time,
                    status=CertificateStatus.ISSUED,
                    verification_code=verification_code,
                    template_used="default",
                    issued_by=None  # Auto-generated
                )
                
                db.add(certificate)
                db.commit()
                db.refresh(certificate)
                
                # Generate PDF
                try:
                    from app.services.certificate_generator import CertificateGenerator
                    generator = CertificateGenerator(db)
                    generator.generate_certificate_pdf(certificate.id)
                    certificate_url = f"/certificates/{certificate.id}/download"
                except Exception as pdf_error:
                    print(f"Failed to generate PDF for certificate {certificate.id}: {str(pdf_error)}")
                    certificate_url = f"/certificates/{certificate.id}"
                    
                print(f"Certificate {certificate.certificate_number} generated for user {user_evaluation.user_id} completing course {user_evaluation.evaluation.course_id}")
            else:
                certificate_url = f"/certificates/{existing_certificate.id}"
                print(f"Certificate already exists for user {user_evaluation.user_id} and course {user_evaluation.evaluation.course_id}")
                
        except Exception as e:
            print(f"Failed to generate certificate for user_evaluation {user_evaluation.id}: {str(e)}")
    
    return {
        "success": True,
        "message": "Evaluation submitted successfully",
        "results": {
            "user_evaluation_id": user_evaluation.id,
            "score": total_points,
            "max_points": max_points,
            "percentage": percentage,
            "passed": passed,
            "time_spent_minutes": time_spent_minutes,
            "certificate_url": certificate_url
        }
    }


# Specific routes without path parameters


@router.get("/my-results", response_class=JSONResponse)
async def get_my_evaluation_results(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Alternative endpoint to get current user's evaluation results
    """
    from fastapi.responses import JSONResponse
    import json
    
    try:
        # Build query with joins to get evaluation and course information
        query = db.query(
            UserEvaluation,
            Evaluation.title.label('evaluation_title'),
            Course.title.label('course_title')
        ).join(
            Evaluation, UserEvaluation.evaluation_id == Evaluation.id
        ).join(
            Course, Evaluation.course_id == Course.id
        ).filter(
            UserEvaluation.user_id == current_user.id
        )
        
        results = query.all()
        
        # Return simple dictionary to avoid Pydantic validation issues
        result = []
        for user_eval, evaluation_title, course_title in results:
            # Ensure all values are of the correct type and handle None values properly
            result.append({
                "id": int(user_eval.id),
                "user_id": int(user_eval.user_id),
                "evaluation_id": int(user_eval.evaluation_id),
                "evaluation_title": evaluation_title,
                "course_title": course_title,
                "enrollment_id": int(user_eval.enrollment_id) if user_eval.enrollment_id else None,
                "attempt_number": int(user_eval.attempt_number),
                "status": user_eval.status.value if user_eval.status else None,
                "score": float(user_eval.score) if user_eval.score is not None else None,
                "total_points": float(user_eval.total_points) if user_eval.total_points is not None else None,
                "max_points": float(user_eval.max_points) if user_eval.max_points is not None else None,
                "percentage": float(user_eval.percentage) if user_eval.percentage is not None else None,
                "time_spent_minutes": int(user_eval.time_spent_minutes) if user_eval.time_spent_minutes is not None else None,
                "passed": bool(user_eval.passed),
                "responded": user_eval.status == UserEvaluationStatus.COMPLETED,  # Add responded property
                "started_at": user_eval.started_at.isoformat() if user_eval.started_at else None,
                "completed_at": user_eval.completed_at.isoformat() if user_eval.completed_at else None,
                "expires_at": user_eval.expires_at.isoformat() if user_eval.expires_at else None,
                "created_at": user_eval.created_at.isoformat() if user_eval.created_at else None,
                "updated_at": user_eval.updated_at.isoformat() if user_eval.updated_at else None
            })
        
        # Return a direct JSONResponse to bypass FastAPI validation
        return JSONResponse(
            content={
                "success": True,
                "data": result
            }
        )
    except Exception as e:
        print(f"Error getting user evaluation results: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Error retrieving evaluation results: {str(e)}",
                "data": []
            }
        )


# Route /{evaluation_id}/results moved to end of file


@router.get("/user/{user_id}", response_model=PaginatedResponse[UserEvaluationResponse])
async def get_user_evaluations(
    user_id: int,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get user evaluations
    """
    # Users can only see their own evaluations unless they are admin or capacitador
    if current_user.role.value not in ["admin", "capacitador"] and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    query = db.query(UserEvaluation).filter(UserEvaluation.user_id == user_id)
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    user_evaluations = query.offset(skip).limit(limit).all()
    
    # Calculate pagination fields
    page = (skip // limit) + 1 if limit > 0 else 1
    pages = (total + limit - 1) // limit if limit > 0 else 1
    has_next = skip + limit < total
    has_prev = skip > 0
    
    return PaginatedResponse(
        items=user_evaluations,
        total=total,
        page=page,
        size=limit,
        pages=pages,
        has_next=has_next,
        has_prev=has_prev
    )


@router.get("/admin/all-results")
async def get_all_evaluation_results(
    evaluation_id: int = None,
    user_id: int = None,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get all evaluation results for admin view with user information
    """
    from fastapi.responses import JSONResponse
    
    # Only admin and capacitador can access this endpoint
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    try:
        # Build query with joins to get user, evaluation and course information
        query = db.query(
            UserEvaluation,
            User.email,
            User.first_name,
            User.last_name,
            User.email.label('user_email'),
            Evaluation.title.label('evaluation_title'),
            Course.title.label('course_title')
        ).join(
            User, UserEvaluation.user_id == User.id
        ).join(
            Evaluation, UserEvaluation.evaluation_id == Evaluation.id
        ).join(
            Course, Evaluation.course_id == Course.id
        )
        
        # Apply filters
        if evaluation_id:
            query = query.filter(UserEvaluation.evaluation_id == evaluation_id)
        
        if user_id:
            query = query.filter(UserEvaluation.user_id == user_id)
        
        # Show all evaluations that have been started (including in progress)
        query = query.filter(UserEvaluation.started_at.isnot(None))
        
        # Get total count
        total = query.count()
        
        # Apply pagination and ordering (use started_at for all evaluations)
        results = query.order_by(UserEvaluation.started_at.desc()).offset(skip).limit(limit).all()
        
        # Build response data
        evaluation_results = []
        for result in results:
            user_eval, email, first_name, last_name, user_email, evaluation_title, course_title = result
            
            evaluation_results.append({
                "id": int(user_eval.id),
                "user_id": int(user_eval.user_id),
                "email": email,
                "full_name": f"{first_name} {last_name}",
                "user_email": user_email,
                "evaluation_id": int(user_eval.evaluation_id),
                "evaluation_title": evaluation_title,
                "course_title": course_title,
                "attempt_number": int(user_eval.attempt_number),
                "status": user_eval.status.value if user_eval.status else None,
                "score": float(user_eval.score) if user_eval.score is not None else None,
                "total_points": float(user_eval.total_points) if user_eval.total_points is not None else None,
                "max_points": float(user_eval.max_points) if user_eval.max_points is not None else None,
                "percentage": float(user_eval.percentage) if user_eval.percentage is not None else None,
                "time_spent_minutes": int(user_eval.time_spent_minutes) if user_eval.time_spent_minutes is not None else None,
                "passed": bool(user_eval.passed),
                "started_at": user_eval.started_at.isoformat() if user_eval.started_at else None,
                "completed_at": user_eval.completed_at.isoformat() if user_eval.completed_at else None,
                "created_at": user_eval.created_at.isoformat() if user_eval.created_at else None
            })
        
        return JSONResponse(
            content={
                "success": True,
                "data": evaluation_results,
                "total": total,
                "skip": skip,
                "limit": limit
            }
        )
    except Exception as e:
        print(f"Error getting all evaluation results: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Error retrieving evaluation results: {str(e)}",
                "data": []
            }
        )


# Routes with path parameters - defined at the end to avoid conflicts with specific routes
@router.get("/{evaluation_id}", response_model=EvaluationResponse)
async def get_evaluation(
    evaluation_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get evaluation by ID
    """
    from sqlalchemy.orm import joinedload
    
    evaluation = db.query(Evaluation).options(
        joinedload(Evaluation.questions).joinedload(Question.answers)
    ).filter(Evaluation.id == evaluation_id).first()
    
    if not evaluation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation not found"
        )
    
    # Check if user can access this evaluation
    if current_user.role.value not in ["admin", "capacitador"] and evaluation.status != EvaluationStatus.PUBLISHED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Evaluation not available"
        )
    
    return evaluation


@router.put("/{evaluation_id}", response_model=EvaluationResponse)
async def update_evaluation(
    evaluation_id: int,
    evaluation_data: EvaluationUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Update evaluation (admin and capacitador roles only)
    """
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    evaluation = db.query(Evaluation).filter(Evaluation.id == evaluation_id).first()
    
    if not evaluation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation not found"
        )
    
    # Update evaluation fields
    update_data = evaluation_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(evaluation, field, value)
    
    db.commit()
    db.refresh(evaluation)
    
    return evaluation


@router.delete("/{evaluation_id}", response_model=MessageResponse)
async def delete_evaluation(
    evaluation_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Delete evaluation (admin and capacitador roles only)
    """
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    evaluation = db.query(Evaluation).filter(Evaluation.id == evaluation_id).first()
    
    if not evaluation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation not found"
        )
    
    # Delete related user_answers first
    user_evaluations = db.query(UserEvaluation).filter(UserEvaluation.evaluation_id == evaluation_id).all()
    for user_eval in user_evaluations:
        # Delete user answers for this user evaluation
        db.query(UserAnswer).filter(UserAnswer.user_evaluation_id == user_eval.id).delete()
    
    # Delete user_evaluations
    db.query(UserEvaluation).filter(UserEvaluation.evaluation_id == evaluation_id).delete()
    
    # Now delete the evaluation (questions and answers will be deleted by cascade)
    db.delete(evaluation)
    db.commit()
    
    return MessageResponse(message="Evaluation deleted successfully")


@router.get("/{evaluation_id}/delete-validation")
async def validate_evaluation_deletion(
    evaluation_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Validate if evaluation can be deleted (check for associated courses and user submissions)
    """
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    evaluation = db.query(Evaluation).filter(Evaluation.id == evaluation_id).first()
    
    if not evaluation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation not found"
        )
    
    # Check for user submissions
    user_submissions_count = db.query(UserEvaluation).filter(
        UserEvaluation.evaluation_id == evaluation_id
    ).count()
    
    # Check if evaluation has a course associated
    has_course = evaluation.course_id is not None
    course_name = None
    if has_course:
        from app.models.course import Course
        course = db.query(Course).filter(Course.id == evaluation.course_id).first()
        course_name = course.title if course else None
    
    return {
        "can_delete": user_submissions_count == 0,
        "has_course": has_course,
        "course_name": course_name,
        "user_submissions_count": user_submissions_count,
        "warnings": [
            f"Esta evaluación tiene {user_submissions_count} respuestas de empleados" if user_submissions_count > 0 else None,
            f"Esta evaluación está asociada al curso '{course_name}'" if has_course else None
        ]
    }


@router.post("/{evaluation_id}/start", response_model=UserEvaluationResponse)
async def start_evaluation(
    evaluation_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Start an evaluation attempt
    """
    evaluation = db.query(Evaluation).filter(Evaluation.id == evaluation_id).first()
    
    if not evaluation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation not found"
        )
    
    if evaluation.status != EvaluationStatus.PUBLISHED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Evaluation is not active"
        )
    
    # Check for existing in-progress attempt
    existing_in_progress = db.query(UserEvaluation).filter(
        and_(
            UserEvaluation.user_id == current_user.id,
            UserEvaluation.evaluation_id == evaluation_id,
            UserEvaluation.status == UserEvaluationStatus.IN_PROGRESS
        )
    ).first()
    
    if existing_in_progress:
        # Return existing in-progress attempt
        return existing_in_progress
    
    # Check existing attempts count
    existing_attempts = db.query(UserEvaluation).filter(
        and_(
            UserEvaluation.user_id == current_user.id,
            UserEvaluation.evaluation_id == evaluation_id
        )
    ).count()
    
    # Check if user has exceeded max attempts
    if existing_attempts >= evaluation.max_attempts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum attempts ({evaluation.max_attempts}) exceeded"
        )
    
    # Get enrollment if this evaluation is associated with a course
    enrollment_id = None
    if evaluation.course_id:
        from app.models.enrollment import Enrollment
        enrollment = db.query(Enrollment).filter(
            and_(
                Enrollment.user_id == current_user.id,
                Enrollment.course_id == evaluation.course_id
            )
        ).first()
        
        if enrollment:
            enrollment_id = enrollment.id
    
    # Create new evaluation attempt
    from datetime import datetime, timedelta
    current_time = datetime.utcnow()
    
    # Calculate expires_at if time_limit_minutes is set
    expires_at = None
    if evaluation.time_limit_minutes:
        expires_at = current_time + timedelta(minutes=evaluation.time_limit_minutes)
    
    user_evaluation = UserEvaluation(
        user_id=current_user.id,
        evaluation_id=evaluation_id,
        enrollment_id=enrollment_id,
        attempt_number=existing_attempts + 1,
        status=UserEvaluationStatus.IN_PROGRESS,
        started_at=current_time,
        expires_at=expires_at
    )
    
    db.add(user_evaluation)
    db.commit()
    db.refresh(user_evaluation)
    
    return user_evaluation


@router.post("/{evaluation_id}/save-progress")
async def save_evaluation_progress(
    evaluation_id: int,
    progress_data: dict,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Save evaluation progress (answers) for an in-progress evaluation
    """
    # Get the evaluation
    evaluation = db.query(Evaluation).filter(Evaluation.id == evaluation_id).first()
    if not evaluation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation not found"
        )
    
    # Get the user's current evaluation attempt
    user_evaluation = db.query(UserEvaluation).filter(
        and_(
            UserEvaluation.user_id == current_user.id,
            UserEvaluation.evaluation_id == evaluation_id,
            UserEvaluation.status == UserEvaluationStatus.IN_PROGRESS
        )
    ).first()
    
    if not user_evaluation:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active evaluation attempt found"
        )
    
    # Check if evaluation has expired
    if user_evaluation.expires_at and datetime.utcnow() > user_evaluation.expires_at:
        user_evaluation.status = UserEvaluationStatus.EXPIRED
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Evaluation attempt has expired"
        )
    
    try:
        # Get user_answers from the request data
        user_answers = progress_data.get('user_answers', [])
        
        # Save or update user answers
        for answer_data in user_answers:
            question_id = answer_data.get('question_id')
            
            # Check if answer already exists
            existing_answer = db.query(UserAnswer).filter(
                and_(
                    UserAnswer.user_evaluation_id == user_evaluation.id,
                    UserAnswer.question_id == question_id
                )
            ).first()
            
            if existing_answer:
                # Update existing answer
                if 'selected_answer_ids' in answer_data:
                    existing_answer.selected_answer_ids = answer_data['selected_answer_ids']
                if 'answer_text' in answer_data:
                    existing_answer.answer_text = answer_data['answer_text']
                if 'time_spent_seconds' in answer_data:
                    existing_answer.time_spent_seconds = answer_data['time_spent_seconds']
                existing_answer.updated_at = datetime.utcnow()
            else:
                # Create new answer
                new_answer = UserAnswer(
                    user_evaluation_id=user_evaluation.id,
                    question_id=question_id,
                    selected_answer_ids=answer_data.get('selected_answer_ids'),
                    answer_text=answer_data.get('answer_text'),
                    time_spent_seconds=answer_data.get('time_spent_seconds', 0)
                )
                db.add(new_answer)
        
        # Update the user evaluation's updated_at timestamp
        user_evaluation.updated_at = datetime.utcnow()
        
        db.commit()
        
        return {
            "message": "Progress saved successfully",
            "saved_answers": len(user_answers)
        }
        
    except Exception as e:
        db.rollback()
        print(f"Error saving evaluation progress: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error saving progress"
        )


@router.get("/{evaluation_id}/attempts")
async def get_user_attempts(
    evaluation_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get user's attempts count for a specific evaluation
    """
    attempts_count = db.query(UserEvaluation).filter(
        and_(
            UserEvaluation.user_id == current_user.id,
            UserEvaluation.evaluation_id == evaluation_id
        )
    ).count()
    
    return {"attempts_count": attempts_count}


@router.post("/{evaluation_id}/reassign/{user_id}")
async def reassign_evaluation(
    evaluation_id: int,
    user_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Reassign evaluation to a user (admin only) - resets attempts
    """
    # Only admin and capacitador can reassign evaluations
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # Check if evaluation exists
    evaluation = db.query(Evaluation).filter(Evaluation.id == evaluation_id).first()
    if not evaluation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation not found"
        )
    
    # Check if user exists
    from app.models.user import User as UserModel
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # First, get the user evaluation IDs that will be deleted
    user_evaluations_to_delete = db.query(UserEvaluation.id).filter(
        and_(
            UserEvaluation.user_id == user_id,
            UserEvaluation.evaluation_id == evaluation_id
        )
    ).all()
    
    user_evaluation_ids = [ue.id for ue in user_evaluations_to_delete]
    
    # Delete related user answers first (to avoid foreign key constraint violation)
    if user_evaluation_ids:
        from app.models.evaluation import UserAnswer
        db.query(UserAnswer).filter(
            UserAnswer.user_evaluation_id.in_(user_evaluation_ids)
        ).delete(synchronize_session=False)
    
    # Then delete the user evaluations
    db.query(UserEvaluation).filter(
        and_(
            UserEvaluation.user_id == user_id,
            UserEvaluation.evaluation_id == evaluation_id
        )
    ).delete()
    
    db.commit()
    
    return {
        "success": True,
        "message": f"Evaluation reassigned successfully to user {user.email}",
        "user_id": user_id,
        "evaluation_id": evaluation_id
    }


@router.get("/{evaluation_id}/results")
async def get_evaluation_results(
    evaluation_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get current user's results for a specific evaluation
    """
    from fastapi.responses import JSONResponse
    
    try:
        # Build query with joins to get evaluation and course information
        query = db.query(
            UserEvaluation,
            Evaluation.title.label('evaluation_title'),
            Course.title.label('course_title')
        ).join(
            Evaluation, UserEvaluation.evaluation_id == Evaluation.id
        ).join(
            Course, Evaluation.course_id == Course.id
        ).filter(
            and_(
                UserEvaluation.user_id == current_user.id,
                UserEvaluation.evaluation_id == evaluation_id
            )
        )
        
        results = query.all()
        
        # Return simple dictionary to avoid Pydantic validation issues
        result = []
        for user_eval, evaluation_title, course_title in results:
            # Ensure all values are of the correct type
            result.append({
                "id": int(user_eval.id),
                "user_id": int(user_eval.user_id),
                "evaluation_id": int(user_eval.evaluation_id),
                "evaluation_title": evaluation_title,
                "course_title": course_title,
                "enrollment_id": int(user_eval.enrollment_id) if user_eval.enrollment_id else None,
                "attempt_number": int(user_eval.attempt_number),
                "status": user_eval.status.value if user_eval.status else None,
                "score": float(user_eval.score) if user_eval.score is not None else None,
                "total_points": float(user_eval.total_points) if user_eval.total_points is not None else None,
                "max_points": float(user_eval.max_points) if user_eval.max_points is not None else None,
                "percentage": float(user_eval.percentage) if user_eval.percentage is not None else None,
                "time_spent_minutes": int(user_eval.time_spent_minutes) if user_eval.time_spent_minutes is not None else None,
                "passed": bool(user_eval.passed),
                "started_at": user_eval.started_at.isoformat() if user_eval.started_at else None,
                "completed_at": user_eval.completed_at.isoformat() if user_eval.completed_at else None,
                "expires_at": user_eval.expires_at.isoformat() if user_eval.expires_at else None,
                "created_at": user_eval.created_at.isoformat() if user_eval.created_at else None,
                "updated_at": user_eval.updated_at.isoformat() if user_eval.updated_at else None
            })
        
        # Return a direct JSONResponse to bypass FastAPI validation
        return JSONResponse(
            content={
                "success": True,
                "data": result
            }
        )
    except Exception as e:
        print(f"Error getting evaluation results for evaluation {evaluation_id}: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Error retrieving evaluation results: {str(e)}",
                "data": []
            }
        )