from datetime import datetime
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field
from enum import Enum


# ============= Enums =============

class LessonNavigationType(str, Enum):
    SEQUENTIAL = "sequential"
    FREE = "free"


class LessonStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class SlideContentType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    TEXT_IMAGE = "text_image"
    QUIZ = "quiz"
    INTERACTIVE = "interactive"


class ActivityType(str, Enum):
    DRAG_DROP = "drag_drop"
    MATCHING = "matching"
    ORDERING = "ordering"
    HOTSPOT = "hotspot"
    FILL_BLANKS = "fill_blanks"


class InlineQuestionType(str, Enum):
    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"
    OPEN_TEXT = "open_text"


class LessonProgressStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


# ============= Inline Quiz Answer Schemas =============

class InlineQuizAnswerBase(BaseModel):
    answer_text: str
    is_correct: bool = False
    order_index: int = 0
    explanation: Optional[str] = None


class InlineQuizAnswerCreate(InlineQuizAnswerBase):
    pass


class InlineQuizAnswerUpdate(BaseModel):
    answer_text: Optional[str] = None
    is_correct: Optional[bool] = None
    order_index: Optional[int] = None
    explanation: Optional[str] = None


class InlineQuizAnswerResponse(InlineQuizAnswerBase):
    id: int

    class Config:
        from_attributes = True


# ============= Inline Quiz Schemas =============

class InlineQuizBase(BaseModel):
    question_text: str
    question_type: InlineQuestionType
    points: float = 1.0
    explanation: Optional[str] = None
    required_to_continue: bool = False
    show_feedback_immediately: bool = True


class InlineQuizCreate(InlineQuizBase):
    answers: List[InlineQuizAnswerCreate] = []


class InlineQuizUpdate(BaseModel):
    question_text: Optional[str] = None
    question_type: Optional[InlineQuestionType] = None
    points: Optional[float] = None
    explanation: Optional[str] = None
    required_to_continue: Optional[bool] = None
    show_feedback_immediately: Optional[bool] = None
    answers: Optional[List[InlineQuizAnswerCreate]] = None


class InlineQuizResponse(InlineQuizBase):
    id: int
    slide_id: int
    answers: List[InlineQuizAnswerResponse] = []
    created_at: datetime

    class Config:
        from_attributes = True


# ============= Lesson Slide Schemas =============

class LessonSlideBase(BaseModel):
    title: Optional[str] = None
    order_index: int = 0
    slide_type: SlideContentType
    content: Dict[str, Any] = {}
    notes: Optional[str] = None
    is_required: bool = True


class LessonSlideCreate(LessonSlideBase):
    lesson_id: Optional[int] = None
    inline_quiz: Optional[InlineQuizCreate] = None


class LessonSlideUpdate(BaseModel):
    title: Optional[str] = None
    order_index: Optional[int] = None
    slide_type: Optional[SlideContentType] = None
    content: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None
    is_required: Optional[bool] = None
    inline_quiz: Optional[InlineQuizUpdate] = None


class LessonSlideResponse(LessonSlideBase):
    id: int
    lesson_id: int
    inline_quiz: Optional[InlineQuizResponse] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============= Interactive Activity Schemas =============

class InteractiveActivityBase(BaseModel):
    title: str = Field(..., max_length=255)
    instructions: Optional[str] = None
    activity_type: ActivityType
    order_index: int = 0
    config: Dict[str, Any]
    points: float = 1.0
    max_attempts: int = 3
    show_feedback: bool = True
    time_limit_seconds: Optional[int] = None


class InteractiveActivityCreate(InteractiveActivityBase):
    lesson_id: Optional[int] = None
    slide_id: Optional[int] = None


class InteractiveActivityUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    instructions: Optional[str] = None
    activity_type: Optional[ActivityType] = None
    order_index: Optional[int] = None
    config: Optional[Dict[str, Any]] = None
    points: Optional[float] = None
    max_attempts: Optional[int] = None
    show_feedback: Optional[bool] = None
    time_limit_seconds: Optional[int] = None
    slide_id: Optional[int] = None


class InteractiveActivityResponse(InteractiveActivityBase):
    id: int
    lesson_id: int
    slide_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============= Interactive Lesson Schemas =============

class InteractiveLessonBase(BaseModel):
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    thumbnail: Optional[str] = Field(None, max_length=500)
    order_index: int = 0
    navigation_type: LessonNavigationType = LessonNavigationType.SEQUENTIAL
    is_required: bool = True
    estimated_duration_minutes: Optional[int] = None
    passing_score: float = 70.0


class InteractiveLessonCreate(InteractiveLessonBase):
    module_id: int
    slides: Optional[List[LessonSlideCreate]] = []
    activities: Optional[List[InteractiveActivityCreate]] = []


class InteractiveLessonUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    thumbnail: Optional[str] = Field(None, max_length=500)
    order_index: Optional[int] = None
    navigation_type: Optional[LessonNavigationType] = None
    status: Optional[LessonStatus] = None
    is_required: Optional[bool] = None
    estimated_duration_minutes: Optional[int] = None
    passing_score: Optional[float] = None


class InteractiveLessonResponse(InteractiveLessonBase):
    id: int
    module_id: int
    status: LessonStatus
    created_by: int
    created_at: datetime
    updated_at: datetime
    slides: List[LessonSlideResponse] = []
    activities: List[InteractiveActivityResponse] = []

    class Config:
        from_attributes = True


class InteractiveLessonListResponse(BaseModel):
    id: int
    module_id: int
    title: str
    description: Optional[str] = None
    thumbnail: Optional[str] = None
    order_index: int
    navigation_type: LessonNavigationType
    status: LessonStatus
    is_required: bool
    estimated_duration_minutes: Optional[int] = None
    passing_score: float
    created_by: int
    created_at: datetime
    updated_at: datetime
    slides_count: int = 0
    activities_count: int = 0

    class Config:
        from_attributes = True


# ============= User Progress Schemas =============

class UserSlideProgressBase(BaseModel):
    viewed: bool = False
    quiz_answered: bool = False
    quiz_correct: bool = False
    quiz_answer: Optional[Dict[str, Any]] = None
    points_earned: float = 0.0


class UserSlideProgressResponse(UserSlideProgressBase):
    id: int
    lesson_progress_id: int
    slide_id: int
    viewed_at: Optional[datetime] = None
    answered_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserLessonProgressBase(BaseModel):
    status: LessonProgressStatus = LessonProgressStatus.NOT_STARTED
    current_slide_index: int = 0
    progress_percentage: float = 0.0
    quiz_score: Optional[float] = None
    time_spent_seconds: int = 0


class UserLessonProgressResponse(UserLessonProgressBase):
    id: int
    user_id: int
    lesson_id: int
    enrollment_id: int
    quiz_total_points: float = 0.0
    quiz_earned_points: float = 0.0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    slide_progress: List[UserSlideProgressResponse] = []

    class Config:
        from_attributes = True


class UserActivityAttemptBase(BaseModel):
    attempt_number: int = 1
    user_response: Dict[str, Any]
    is_correct: bool = False
    score: float = 0.0
    time_spent_seconds: Optional[int] = None


class UserActivityAttemptResponse(UserActivityAttemptBase):
    id: int
    user_id: int
    activity_id: int
    enrollment_id: int
    feedback: Optional[Dict[str, Any]] = None
    completed_at: datetime

    class Config:
        from_attributes = True


# ============= Request/Response Schemas for API =============

class SlideViewRequest(BaseModel):
    time_spent_seconds: Optional[int] = None


class QuizSubmitRequest(BaseModel):
    selected_answer_id: Optional[int] = None  # Para multiple_choice, true_false
    text_answer: Optional[str] = None  # Para open_text
    boolean_answer: Optional[bool] = None  # Para true_false alternativo


class QuizSubmitResponse(BaseModel):
    is_correct: bool
    points_earned: float
    correct_answer_id: Optional[int] = None
    explanation: Optional[str] = None
    feedback: Optional[str] = None
    attempts_used: int = 1
    attempts_remaining: int = 0
    can_retry: bool = False
    retry_available_in_seconds: Optional[int] = None  # Segundos restantes para poder reintentar (después de agotar intentos)


class ActivitySubmitRequest(BaseModel):
    response: Dict[str, Any]  # Estructura depende del tipo de actividad
    time_spent_seconds: Optional[int] = None


class ActivitySubmitResponse(BaseModel):
    is_correct: bool
    score: float
    points_earned: float
    feedback: Optional[Dict[str, Any]] = None
    correct_solution: Optional[Dict[str, Any]] = None
    attempts_remaining: int


class LessonProgressSummary(BaseModel):
    lesson_id: int
    lesson_title: str
    status: LessonProgressStatus
    progress_percentage: float
    quiz_score: Optional[float] = None
    time_spent_seconds: int
    slides_completed: int
    total_slides: int
    activities_completed: int
    total_activities: int


class SlideReorderRequest(BaseModel):
    slide_ids: List[int]  # IDs en el nuevo orden


class LessonWithProgressResponse(InteractiveLessonResponse):
    """Lección con información de progreso del usuario"""
    user_progress: Optional[UserLessonProgressResponse] = None

    class Config:
        from_attributes = True
