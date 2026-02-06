from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SQLEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
)
from sqlalchemy.orm import relationship

from app.database import Base


class LessonNavigationType(str, Enum):
    """Tipo de navegación en la lección"""
    SEQUENTIAL = "sequential"  # Solo siguiente/anterior
    FREE = "free"  # Navegación libre entre slides


class LessonStatus(str, Enum):
    """Estado de la lección interactiva"""
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class SlideContentType(str, Enum):
    """Tipo de contenido del slide"""
    TEXT = "text"  # Contenido de texto rico
    IMAGE = "image"  # Imagen con descripción
    VIDEO = "video"  # Video embebido
    TEXT_IMAGE = "text_image"  # Texto + Imagen
    QUIZ = "quiz"  # Quiz inline (pregunta en el slide)
    INTERACTIVE = "interactive"  # Actividad interactiva


class ActivityType(str, Enum):
    """Tipo de actividad interactiva"""
    DRAG_DROP = "drag_drop"  # Arrastrar elementos a zonas
    MATCHING = "matching"  # Emparejar conceptos
    ORDERING = "ordering"  # Ordenar secuencia
    HOTSPOT = "hotspot"  # Click en zonas de imagen
    FILL_BLANKS = "fill_blanks"  # Llenar espacios en blanco


class QuestionType(str, Enum):
    """Tipo de pregunta para quiz inline"""
    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"
    OPEN_TEXT = "open_text"


class InteractiveLesson(Base):
    """Lección interactiva con slides y actividades"""
    __tablename__ = "interactive_lessons"

    id = Column(Integer, primary_key=True, index=True)
    module_id = Column(Integer, ForeignKey("course_modules.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    thumbnail = Column(String(500))
    order_index = Column(Integer, default=0)
    navigation_type = Column(
        SQLEnum(LessonNavigationType),
        default=LessonNavigationType.SEQUENTIAL
    )
    status = Column(SQLEnum(LessonStatus), default=LessonStatus.DRAFT)
    is_required = Column(Boolean, default=True)
    estimated_duration_minutes = Column(Integer)
    passing_score = Column(Float, default=70.0)  # Para quizzes inline
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    module = relationship("CourseModule", back_populates="interactive_lessons")
    creator = relationship("User", foreign_keys=[created_by])
    slides = relationship(
        "LessonSlide",
        back_populates="lesson",
        cascade="all, delete-orphan",
        order_by="LessonSlide.order_index"
    )
    activities = relationship(
        "InteractiveActivity",
        back_populates="lesson",
        cascade="all, delete-orphan",
        order_by="InteractiveActivity.order_index"
    )
    user_progress = relationship(
        "UserLessonProgress",
        back_populates="lesson",
        cascade="all, delete-orphan"
    )

    @property
    def slides_count(self) -> int:
        """Número de slides en la lección"""
        return len(self.slides) if self.slides else 0

    @property
    def activities_count(self) -> int:
        """Número de actividades en la lección"""
        return len(self.activities) if self.activities else 0

    def __repr__(self):
        return f"<InteractiveLesson(id={self.id}, title='{self.title}')>"


class LessonSlide(Base):
    """Slide individual de una lección interactiva"""
    __tablename__ = "lesson_slides"

    id = Column(Integer, primary_key=True, index=True)
    lesson_id = Column(Integer, ForeignKey("interactive_lessons.id"), nullable=False)
    title = Column(String(255))
    order_index = Column(Integer, default=0)
    slide_type = Column(SQLEnum(SlideContentType), nullable=False)

    # Content fields (JSON para flexibilidad)
    # Estructura varía según slide_type:
    # TEXT: {"html": "<p>Contenido</p>", "background_color": "#fff"}
    # IMAGE: {"url": "...", "alt_text": "...", "caption": "..."}
    # VIDEO: {"url": "...", "provider": "youtube|vimeo|local", "autoplay": false}
    # TEXT_IMAGE: {"text": "...", "image_url": "...", "layout": "left|right|top|bottom"}
    content = Column(JSON)

    notes = Column(Text)  # Notas del instructor
    is_required = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    lesson = relationship("InteractiveLesson", back_populates="slides")
    inline_quiz = relationship(
        "InlineQuiz",
        back_populates="slide",
        uselist=False,
        cascade="all, delete-orphan"
    )
    user_progress = relationship(
        "UserSlideProgress",
        back_populates="slide",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<LessonSlide(id={self.id}, title='{self.title}', type='{self.slide_type}')>"


class InlineQuiz(Base):
    """Quiz integrado en un slide"""
    __tablename__ = "inline_quizzes"

    id = Column(Integer, primary_key=True, index=True)
    slide_id = Column(Integer, ForeignKey("lesson_slides.id"), nullable=False, unique=True)
    question_text = Column(Text, nullable=False)
    question_type = Column(SQLEnum(QuestionType), nullable=False)
    points = Column(Float, default=1.0)
    explanation = Column(Text)  # Feedback después de responder
    required_to_continue = Column(Boolean, default=False)  # Debe responder para avanzar
    show_feedback_immediately = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    slide = relationship("LessonSlide", back_populates="inline_quiz")
    answers = relationship(
        "InlineQuizAnswer",
        back_populates="quiz",
        cascade="all, delete-orphan",
        order_by="InlineQuizAnswer.order_index"
    )

    def __repr__(self):
        return f"<InlineQuiz(id={self.id}, type='{self.question_type}')>"


class InlineQuizAnswer(Base):
    """Respuesta de un quiz inline"""
    __tablename__ = "inline_quiz_answers"

    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(Integer, ForeignKey("inline_quizzes.id"), nullable=False)
    answer_text = Column(Text, nullable=False)
    is_correct = Column(Boolean, default=False)
    order_index = Column(Integer, default=0)
    explanation = Column(Text)  # Explicación específica de esta respuesta

    # Relationships
    quiz = relationship("InlineQuiz", back_populates="answers")

    def __repr__(self):
        return f"<InlineQuizAnswer(id={self.id}, is_correct={self.is_correct})>"


class InteractiveActivity(Base):
    """Actividad interactiva (drag & drop, matching, etc.)"""
    __tablename__ = "interactive_activities"

    id = Column(Integer, primary_key=True, index=True)
    lesson_id = Column(Integer, ForeignKey("interactive_lessons.id"), nullable=False)
    slide_id = Column(Integer, ForeignKey("lesson_slides.id"), nullable=True)  # Opcional
    title = Column(String(255), nullable=False)
    instructions = Column(Text)
    activity_type = Column(SQLEnum(ActivityType), nullable=False)
    order_index = Column(Integer, default=0)

    # Configuración de la actividad (JSON)
    # Estructura varía según activity_type:
    # DRAG_DROP: {"items": [...], "zones": [...], "background_image": "..."}
    # MATCHING: {"pairs": [...], "shuffle_right": true}
    # ORDERING: {"items": [...]}
    # HOTSPOT: {"image_url": "...", "hotspots": [...], "question": "..."}
    # FILL_BLANKS: {"text": "...", "blanks": [...]}
    config = Column(JSON, nullable=False)

    points = Column(Float, default=1.0)
    max_attempts = Column(Integer, default=3)
    show_feedback = Column(Boolean, default=True)
    time_limit_seconds = Column(Integer)  # Opcional
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    lesson = relationship("InteractiveLesson", back_populates="activities")
    slide = relationship("LessonSlide")
    user_attempts = relationship(
        "UserActivityAttempt",
        back_populates="activity",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<InteractiveActivity(id={self.id}, title='{self.title}', type='{self.activity_type}')>"
