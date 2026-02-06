from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    JSON,
)
from sqlalchemy.orm import relationship

from app.database import Base


class LessonProgressStatus(str, Enum):
    """Estado de progreso de una lección"""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class UserLessonProgress(Base):
    """Progreso del usuario en una lección interactiva"""
    __tablename__ = "user_lesson_progress"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    lesson_id = Column(Integer, ForeignKey("interactive_lessons.id"), nullable=False)
    enrollment_id = Column(Integer, ForeignKey("enrollments.id"), nullable=False)
    status = Column(String(20), default=LessonProgressStatus.NOT_STARTED.value)
    current_slide_index = Column(Integer, default=0)
    progress_percentage = Column(Float, default=0.0)
    quiz_score = Column(Float)  # Puntuación de quizzes inline
    quiz_total_points = Column(Float, default=0.0)  # Total de puntos posibles
    quiz_earned_points = Column(Float, default=0.0)  # Puntos ganados
    time_spent_seconds = Column(Integer, default=0)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User")
    lesson = relationship("InteractiveLesson", back_populates="user_progress")
    enrollment = relationship("Enrollment")
    slide_progress = relationship(
        "UserSlideProgress",
        back_populates="lesson_progress",
        cascade="all, delete-orphan"
    )

    def start_lesson(self):
        """Inicia la lección"""
        if self.status == LessonProgressStatus.NOT_STARTED.value:
            self.status = LessonProgressStatus.IN_PROGRESS.value
            self.started_at = datetime.utcnow()

    def complete_lesson(self):
        """Completa la lección"""
        self.status = LessonProgressStatus.COMPLETED.value
        self.progress_percentage = 100.0
        self.completed_at = datetime.utcnow()

    def calculate_progress(self, total_slides: int, completed_slides: int):
        """Calcula el progreso basado en slides completados"""
        if total_slides == 0:
            self.progress_percentage = 0.0
        else:
            self.progress_percentage = (completed_slides / total_slides) * 100

        if self.progress_percentage >= 100:
            self.complete_lesson()
        elif self.progress_percentage > 0 and self.status == LessonProgressStatus.NOT_STARTED.value:
            self.start_lesson()

    def calculate_quiz_score(self):
        """Calcula la puntuación total de quizzes"""
        if self.quiz_total_points > 0:
            self.quiz_score = (self.quiz_earned_points / self.quiz_total_points) * 100
        else:
            self.quiz_score = None

    def __repr__(self):
        return f"<UserLessonProgress(user_id={self.user_id}, lesson_id={self.lesson_id}, progress={self.progress_percentage}%)>"


class UserSlideProgress(Base):
    """Progreso del usuario en un slide específico"""
    __tablename__ = "user_slide_progress"

    id = Column(Integer, primary_key=True, index=True)
    lesson_progress_id = Column(Integer, ForeignKey("user_lesson_progress.id"), nullable=False)
    slide_id = Column(Integer, ForeignKey("lesson_slides.id"), nullable=False)
    viewed = Column(Boolean, default=False)
    quiz_answered = Column(Boolean, default=False)
    quiz_correct = Column(Boolean, default=False)
    quiz_answer = Column(JSON)  # Respuesta del usuario
    quiz_attempts = Column(Integer, default=0)  # Número de intentos realizados
    points_earned = Column(Float, default=0.0)
    viewed_at = Column(DateTime)
    answered_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    lesson_progress = relationship("UserLessonProgress", back_populates="slide_progress")
    slide = relationship("LessonSlide", back_populates="user_progress")

    def mark_viewed(self):
        """Marca el slide como visto"""
        if not self.viewed:
            self.viewed = True
            self.viewed_at = datetime.utcnow()

    def submit_quiz_answer(self, answer: dict, is_correct: bool, points: float, max_attempts: int = 3):
        """Registra la respuesta del quiz inline con soporte para múltiples intentos"""
        self.quiz_attempts = (self.quiz_attempts or 0) + 1
        self.quiz_answer = answer
        self.answered_at = datetime.utcnow()

        if is_correct:
            # Si es correcta, marcar como respondido y dar puntos
            self.quiz_answered = True
            self.quiz_correct = True
            self.points_earned = points
        elif self.quiz_attempts >= max_attempts:
            # Si agotó los intentos, marcar como respondido sin puntos
            self.quiz_answered = True
            self.quiz_correct = False
            self.points_earned = 0.0
        # Si no es correcta y quedan intentos, no marcar como respondido

    def __repr__(self):
        return f"<UserSlideProgress(slide_id={self.slide_id}, viewed={self.viewed})>"


class UserActivityAttempt(Base):
    """Intento del usuario en una actividad interactiva"""
    __tablename__ = "user_activity_attempts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    activity_id = Column(Integer, ForeignKey("interactive_activities.id"), nullable=False)
    enrollment_id = Column(Integer, ForeignKey("enrollments.id"), nullable=False)
    attempt_number = Column(Integer, default=1)
    user_response = Column(JSON)  # Respuesta del usuario
    is_correct = Column(Boolean, default=False)
    score = Column(Float, default=0.0)  # Puntuación obtenida (0-100 o puntos)
    time_spent_seconds = Column(Integer)
    feedback = Column(JSON)  # Feedback detallado de la respuesta
    completed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User")
    activity = relationship("InteractiveActivity", back_populates="user_attempts")
    enrollment = relationship("Enrollment")

    def __repr__(self):
        return f"<UserActivityAttempt(activity_id={self.activity_id}, attempt={self.attempt_number}, correct={self.is_correct})>"
