from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from enum import Enum


class SurveyStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    CLOSED = "closed"
    ARCHIVED = "archived"


class SurveyQuestionType(str, Enum):
    MULTIPLE_CHOICE = "multiple_choice"
    SINGLE_CHOICE = "single_choice"
    TEXT = "text"
    TEXTAREA = "textarea"
    RATING = "rating"
    YES_NO = "yes_no"
    SCALE = "scale"


class UserSurveyStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    EXPIRED = "expired"


# Survey Question Schemas
class SurveyQuestionBase(BaseModel):
    question_text: str
    question_type: SurveyQuestionType
    options: Optional[str] = None  # JSON array
    is_required: bool = False
    order_index: int = 0
    min_value: Optional[int] = None
    max_value: Optional[int] = None
    placeholder_text: Optional[str] = Field(None, max_length=255)


class SurveyQuestionCreate(SurveyQuestionBase):
    survey_id: int


class SurveyQuestionUpdate(BaseModel):
    question_text: Optional[str] = None
    question_type: Optional[SurveyQuestionType] = None
    options: Optional[str] = None
    is_required: Optional[bool] = None
    order_index: Optional[int] = None
    min_value: Optional[int] = None
    max_value: Optional[int] = None
    placeholder_text: Optional[str] = Field(None, max_length=255)


class SurveyQuestionResponse(SurveyQuestionBase):
    id: int
    survey_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# User Survey Answer Schemas
class UserSurveyAnswerBase(BaseModel):
    question_id: int
    answer_text: Optional[str] = None
    answer_value: Optional[int] = None
    selected_options: Optional[str] = None  # JSON array


class UserSurveyAnswerCreate(UserSurveyAnswerBase):
    user_survey_id: int


class UserSurveyAnswerResponse(UserSurveyAnswerBase):
    id: int
    user_survey_id: int
    answered_at: datetime

    class Config:
        from_attributes = True


# User Survey Schemas
class UserSurveyBase(BaseModel):
    survey_id: int
    user_id: Optional[int] = None  # Nullable for anonymous surveys
    anonymous_token: Optional[str] = Field(None, max_length=255)


class UserSurveyCreate(UserSurveyBase):
    pass


class UserSurveyUpdate(BaseModel):
    status: Optional[UserSurveyStatus] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class UserSurveyResponse(UserSurveyBase):
    id: int
    status: UserSurveyStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    answers: List[UserSurveyAnswerResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Survey Schemas
class SurveyBase(BaseModel):
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    instructions: Optional[str] = None
    is_anonymous: bool = False
    allow_multiple_responses: bool = False
    closes_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None


class SurveyCreate(SurveyBase):
    status: Optional[SurveyStatus] = SurveyStatus.DRAFT
    course_id: Optional[int] = None
    is_course_survey: bool = False
    required_for_completion: bool = False
    questions: Optional[List[SurveyQuestionBase]] = []


class SurveyUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    instructions: Optional[str] = None
    is_anonymous: Optional[bool] = None
    allow_multiple_responses: Optional[bool] = None
    status: Optional[SurveyStatus] = None
    course_id: Optional[int] = None
    is_course_survey: Optional[bool] = None
    required_for_completion: Optional[bool] = None
    closes_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    questions: Optional[List[SurveyQuestionBase]] = None


class SurveyResponse(SurveyBase):
    id: int
    status: SurveyStatus
    course_id: Optional[int] = None
    is_course_survey: bool = False
    required_for_completion: bool = False
    course: Optional[dict] = None  # Will contain {"id": int, "title": str}
    created_by: int
    created_at: datetime
    updated_at: datetime
    published_at: Optional[datetime] = None
    questions: List[SurveyQuestionResponse] = []

    class Config:
        from_attributes = True


class SurveyListResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    status: SurveyStatus
    is_anonymous: bool
    course_id: Optional[int] = None
    is_course_survey: bool = False
    required_for_completion: bool = False
    course: Optional[dict] = None  # Will contain {"id": int, "title": str}
    created_at: datetime
    published_at: Optional[datetime] = None
    closes_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# Survey Submission Schema
class SurveySubmission(BaseModel):
    answers: List[UserSurveyAnswerBase]
    anonymous_token: Optional[str] = None


# Survey Statistics Schema
class SurveyStatistics(BaseModel):
    survey_id: int
    total_responses: int
    completion_rate: float
    average_completion_time: Optional[float] = None  # in minutes
    question_statistics: List[dict] = []  # Question-specific stats


# Enhanced Answer Schema for better presentation
class AnswerDetail(BaseModel):
    question_id: int
    question_text: str
    question_type: str
    answer_text: Optional[str] = None
    answer_value: Optional[int] = None
    selected_options: Optional[str] = None
    display_value: str  # Formatted value for display
    is_answered: bool = True

    class Config:
        from_attributes = True


# Employee Response Schema for detailed results
class EmployeeResponse(BaseModel):
    user_id: int
    employee_name: str
    employee_email: str
    cargo: Optional[str] = None
    telefono: Optional[str] = None
    submission_date: Optional[datetime] = None
    submission_status: str = "completed"
    response_time_minutes: Optional[float] = None
    answers: List[AnswerDetail] = []  # Structured list of answers
    completion_percentage: float = 100.0

    class Config:
        from_attributes = True


# Detailed Survey Results Schema
class SurveyDetailedResults(BaseModel):
    survey_id: int
    survey_title: str
    survey_description: Optional[str] = None
    course_title: Optional[str] = None
    total_responses: int
    completed_responses: int
    completion_rate: float
    questions: List[SurveyQuestionResponse] = []
    employee_responses: List[EmployeeResponse] = []

    class Config:
        from_attributes = True


# Survey Presentation Schema (for public display)
class SurveyPresentation(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    instructions: Optional[str] = None
    is_anonymous: bool
    allow_multiple_responses: bool
    questions: List[SurveyQuestionResponse] = []
    closes_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    class Config:
        from_attributes = True