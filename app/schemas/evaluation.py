from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from enum import Enum


class QuestionType(str, Enum):
    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"
    OPEN_TEXT = "open_text"
    MATCHING = "matching"
    ORDERING = "ordering"


class EvaluationStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class UserEvaluationStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    EXPIRED = "expired"


# Answer Schemas
class AnswerBase(BaseModel):
    answer_text: str
    is_correct: bool = False
    order_index: int = 0
    explanation: Optional[str] = None


class AnswerCreate(AnswerBase):
    question_id: int


class AnswerUpdate(BaseModel):
    answer_text: Optional[str] = None
    is_correct: Optional[bool] = None
    order_index: Optional[int] = None
    explanation: Optional[str] = None


class AnswerResponse(AnswerBase):
    id: int
    question_id: int
    created_at: datetime

    class Config:
        # Compatibilidad Pydantic v1/v2
        from_attributes = True
        orm_mode = True


# Question Schemas
class QuestionBase(BaseModel):
    question_text: str
    question_type: QuestionType
    points: float = 1.0
    order_index: int = 0
    explanation: Optional[str] = None
    image_url: Optional[str] = Field(None, max_length=500)
    required: bool = True


class QuestionCreateForEvaluation(BaseModel):
    question_text: str
    question_type: QuestionType
    options: Optional[List[str]] = []
    correct_answer: Optional[str] = None
    points: float = 1.0
    order_index: int = 0
    explanation: Optional[str] = None
    image_url: Optional[str] = Field(None, max_length=500)
    required: bool = True


class QuestionCreate(QuestionBase):
    evaluation_id: int
    answers: List[AnswerBase] = []


class QuestionUpdate(BaseModel):
    question_text: Optional[str] = None
    question_type: Optional[QuestionType] = None
    points: Optional[float] = None
    order_index: Optional[int] = None
    explanation: Optional[str] = None
    image_url: Optional[str] = Field(None, max_length=500)
    required: Optional[bool] = None


class QuestionResponse(QuestionBase):
    id: int
    evaluation_id: int
    answers: List[AnswerResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        # Compatibilidad Pydantic v1/v2
        from_attributes = True
        orm_mode = True


# User Answer Schemas
class UserAnswerBase(BaseModel):
    question_id: int
    answer_text: Optional[str] = None
    selected_answer_ids: Optional[str] = None  # JSON array
    time_spent_seconds: Optional[int] = None


class UserAnswerCreate(UserAnswerBase):
    user_evaluation_id: int


class UserAnswerResponse(UserAnswerBase):
    id: int
    user_evaluation_id: int
    is_correct: bool
    points_earned: float
    answered_at: datetime

    class Config:
        # Compatibilidad Pydantic v1/v2
        from_attributes = True
        orm_mode = True


# User Evaluation Schemas
class UserEvaluationBase(BaseModel):
    user_id: int
    evaluation_id: int
    attempt_number: int = 1


class UserEvaluationCreate(UserEvaluationBase):
    pass


class UserEvaluationUpdate(BaseModel):
    status: Optional[UserEvaluationStatus] = None
    score: Optional[float] = None
    total_points: Optional[float] = None
    max_points: Optional[float] = None
    time_spent_minutes: Optional[int] = None
    passed: Optional[bool] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None


class UserEvaluationResponse(BaseModel):
    id: int
    user_id: int
    evaluation_id: int
    enrollment_id: Optional[int] = None
    attempt_number: int = 1
    status: UserEvaluationStatus
    score: Optional[float] = None
    total_points: Optional[float] = None
    max_points: Optional[float] = None
    percentage: Optional[float] = None
    time_spent_minutes: Optional[int] = None
    passed: bool
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        # Compatibilidad Pydantic v1/v2
        from_attributes = True
        orm_mode = True


# Evaluation Schemas
class EvaluationBase(BaseModel):
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    instructions: Optional[str] = None
    time_limit_minutes: Optional[int] = None
    passing_score: float = 70.0
    max_attempts: int = 3
    randomize_questions: bool = False
    show_results_immediately: bool = True
    allow_review: bool = True
    expires_at: Optional[datetime] = None


class EvaluationCreate(EvaluationBase):
    course_id: int
    questions: List[QuestionCreateForEvaluation] = []


class EvaluationUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    instructions: Optional[str] = None
    time_limit_minutes: Optional[int] = None
    passing_score: Optional[float] = None
    max_attempts: Optional[int] = None
    randomize_questions: Optional[bool] = None
    show_results_immediately: Optional[bool] = None
    allow_review: Optional[bool] = None
    status: Optional[EvaluationStatus] = None
    expires_at: Optional[datetime] = None
    # Permitir actualización de preguntas desde el PUT
    questions: Optional[List[QuestionCreateForEvaluation]] = None


class EvaluationResponse(EvaluationBase):
    id: int
    course_id: int
    status: EvaluationStatus
    created_by: int
    created_at: datetime
    updated_at: datetime
    published_at: Optional[datetime] = None
    questions: List[QuestionResponse] = []

    class Config:
        # Compatibilidad Pydantic v1/v2
        from_attributes = True
        orm_mode = True


class CourseInfo(BaseModel):
    id: int
    title: str
    
    class Config:
        # Compatibilidad Pydantic v1/v2
        from_attributes = True
        orm_mode = True


class EvaluationListResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    course_id: int
    course: Optional[CourseInfo] = None
    status: EvaluationStatus
    time_limit_minutes: Optional[int] = None
    passing_score: float
    max_attempts: int
    created_at: datetime
    published_at: Optional[datetime] = None

    class Config:
        # Compatibilidad Pydantic v1/v2
        from_attributes = True
        orm_mode = True


# Evaluation Submission Schema
class EvaluationSubmission(BaseModel):
    user_answers: List[UserAnswerBase]


# Answer Submission Schema
class AnswerSubmission(BaseModel):
    question_id: int
    selected_option_id: Optional[int] = None
    text_answer: Optional[str] = None
    boolean_answer: Optional[bool] = None