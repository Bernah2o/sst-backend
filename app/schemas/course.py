from datetime import datetime
from typing import List, Optional, Any
from pydantic import BaseModel, Field, model_validator
from enum import Enum


class CourseType(str, Enum):
    INDUCTION = "induction"
    REINDUCTION = "reinduction"
    SPECIALIZED = "specialized"
    MANDATORY = "mandatory"
    OPTIONAL = "optional"
    TRAINING = "training"


class CourseStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class MaterialType(str, Enum):
    PDF = "pdf"
    VIDEO = "video"
    LINK = "link"


# Course Material Schemas
class CourseMaterialBase(BaseModel):
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    material_type: MaterialType
    file_url: Optional[str] = Field(None, max_length=500)
    order_index: int = 0
    is_downloadable: bool = True
    is_required: bool = True


class CourseMaterialCreate(CourseMaterialBase):
    module_id: int


class CourseMaterialUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    material_type: Optional[MaterialType] = None
    file_url: Optional[str] = Field(None, max_length=500)
    order_index: Optional[int] = None
    is_downloadable: Optional[bool] = None
    is_required: Optional[bool] = None


class CourseMaterialResponse(CourseMaterialBase):
    id: int
    module_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CourseMaterialWithProgressResponse(CourseMaterialResponse):
    completed: bool = False
    progress: float = 0.0

    class Config:
        from_attributes = True


# Course Module Schemas
class CourseModuleBase(BaseModel):
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    order_index: int = 0
    duration_minutes: Optional[int] = None
    is_required: bool = True


class CourseModuleCreate(CourseModuleBase):
    pass


class CourseModuleUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    order_index: Optional[int] = None
    duration_minutes: Optional[int] = None
    is_required: Optional[bool] = None


class InteractiveLessonSummary(BaseModel):
    """Schema resumido de lección interactiva para incluir en módulos"""
    id: int
    title: str
    description: Optional[str] = None
    order_index: int = 0
    status: str = "draft"
    estimated_duration_minutes: Optional[int] = None
    is_required: bool = True
    slides_count: int = 0
    completed: bool = False
    progress_percentage: float = 0

    class Config:
        from_attributes = True

    @model_validator(mode='before')
    @classmethod
    def convert_from_orm(cls, data: Any) -> Any:
        """Convertir desde ORM a dict con valores por defecto"""
        if isinstance(data, dict):
            return data
        # Es un objeto ORM
        return {
            'id': data.id,
            'title': data.title,
            'description': data.description,
            'order_index': data.order_index,
            'status': data.status.value if hasattr(data.status, 'value') else str(data.status),
            'estimated_duration_minutes': data.estimated_duration_minutes,
            'is_required': data.is_required,
            'slides_count': data.slides_count if hasattr(data, 'slides_count') else 0,
            'completed': False,
            'progress_percentage': 0.0
        }

    @classmethod
    def from_lesson(cls, lesson, user_progress=None):
        """Crear desde un modelo de lección con progreso opcional"""
        return cls(
            id=lesson.id,
            title=lesson.title,
            description=lesson.description,
            order_index=lesson.order_index,
            status=lesson.status.value if hasattr(lesson.status, 'value') else str(lesson.status),
            estimated_duration_minutes=lesson.estimated_duration_minutes,
            is_required=lesson.is_required,
            slides_count=lesson.slides_count if hasattr(lesson, 'slides_count') else 0,
            completed=user_progress.status == "completed" if user_progress else False,
            progress_percentage=user_progress.progress_percentage if user_progress else 0
        )


class CourseModuleResponse(CourseModuleBase):
    id: int
    course_id: int
    materials: List[CourseMaterialResponse] = []
    interactive_lessons: List[InteractiveLessonSummary] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Course Schemas
class CourseBase(BaseModel):
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    course_type: CourseType
    duration_hours: Optional[float] = None
    passing_score: float = 70.0
    max_attempts: int = 3
    is_mandatory: bool = False
    thumbnail: Optional[str] = Field(None, max_length=255)
    expires_at: Optional[datetime] = None
    order_index: int = 0


class CourseCreate(CourseBase):
    pass


class CourseUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    course_type: Optional[CourseType] = None
    status: Optional[CourseStatus] = None
    duration_hours: Optional[float] = None
    passing_score: Optional[float] = None
    max_attempts: Optional[int] = None
    is_mandatory: Optional[bool] = None
    thumbnail: Optional[str] = Field(None, max_length=255)
    expires_at: Optional[datetime] = None
    order_index: Optional[int] = None


class CourseResponse(CourseBase):
    id: int
    status: CourseStatus
    created_by: int
    created_at: datetime
    updated_at: datetime
    published_at: Optional[datetime] = None
    modules: List[CourseModuleResponse] = []

    class Config:
        from_attributes = True


class CourseListResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    course_type: CourseType
    status: CourseStatus
    duration_hours: Optional[float] = None
    passing_score: float = 70.0
    max_attempts: int = 3
    is_mandatory: bool
    thumbnail: Optional[str] = None
    expires_at: Optional[datetime] = None
    order_index: int = 0
    created_by: int
    created_at: datetime
    updated_at: datetime
    published_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserCourseResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    course_type: CourseType
    status: CourseStatus
    duration_hours: Optional[float] = None
    is_mandatory: bool
    thumbnail: Optional[str] = None
    created_at: datetime
    published_at: Optional[datetime] = None
    modules: List[CourseModuleResponse] = []
    # User-specific fields
    progress: float = 0.0
    enrolled_at: Optional[datetime] = None
    completed: bool = False

    class Config:
        from_attributes = True