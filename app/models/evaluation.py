from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    Float,
)
from sqlalchemy.orm import relationship

from app.database import Base


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


class Evaluation(Base):
    __tablename__ = "evaluations"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    instructions = Column(Text)
    time_limit_minutes = Column(Integer)  # Time limit in minutes
    passing_score = Column(Float, default=70.0)
    max_attempts = Column(Integer, default=3)
    randomize_questions = Column(Boolean, default=False)
    show_results_immediately = Column(Boolean, default=True)
    allow_review = Column(Boolean, default=True)
    status = Column(SQLEnum(EvaluationStatus), default=EvaluationStatus.DRAFT)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    published_at = Column(DateTime)
    expires_at = Column(DateTime)

    # Relationships
    course = relationship("Course", back_populates="evaluations")
    creator = relationship("User", foreign_keys=[created_by], overlaps="created_evaluations")
    questions = relationship("Question", back_populates="evaluation", cascade="all, delete-orphan")
    user_evaluations = relationship("UserEvaluation", back_populates="evaluation")

    def __repr__(self):
        return f"<Evaluation(id={self.id}, title='{self.title}', course_id={self.course_id})>"


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    evaluation_id = Column(Integer, ForeignKey("evaluations.id"), nullable=False)
    question_text = Column(Text, nullable=False)
    question_type = Column(SQLEnum(QuestionType), nullable=False)
    points = Column(Float, default=1.0)
    order_index = Column(Integer, default=0)
    explanation = Column(Text)  # Explanation for the correct answer
    image_url = Column(String(500))  # Optional image for the question
    required = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    evaluation = relationship("Evaluation", back_populates="questions")
    answers = relationship("Answer", back_populates="question", cascade="all, delete-orphan")
    user_answers = relationship("UserAnswer", back_populates="question")

    def __repr__(self):
        return f"<Question(id={self.id}, type='{self.question_type}', evaluation_id={self.evaluation_id})>"


class Answer(Base):
    __tablename__ = "answers"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    answer_text = Column(Text, nullable=False)
    is_correct = Column(Boolean, default=False)
    order_index = Column(Integer, default=0)
    explanation = Column(Text)  # Explanation for this answer option
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    question = relationship("Question", back_populates="answers")

    def __repr__(self):
        return f"<Answer(id={self.id}, is_correct={self.is_correct}, question_id={self.question_id})>"


class UserEvaluation(Base):
    __tablename__ = "user_evaluations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    evaluation_id = Column(Integer, ForeignKey("evaluations.id"), nullable=False)
    enrollment_id = Column(Integer, ForeignKey("enrollments.id"), nullable=True)  # Link to course enrollment
    attempt_number = Column(Integer, default=1)
    status = Column(SQLEnum(UserEvaluationStatus), default=UserEvaluationStatus.NOT_STARTED)
    score = Column(Float)  # Final score points
    total_points = Column(Float)  # Total points earned
    max_points = Column(Float)  # Maximum possible points
    percentage = Column(Float)  # Score percentage
    time_spent_minutes = Column(Integer)  # Time spent in minutes
    passed = Column(Boolean, default=False)
    is_best_attempt = Column(Boolean, default=False)  # Mark the best attempt for this user/evaluation
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="user_evaluations")
    evaluation = relationship("Evaluation", back_populates="user_evaluations")
    enrollment = relationship("Enrollment")
    user_answers = relationship("UserAnswer", back_populates="user_evaluation")

    def __repr__(self):
        return f"<UserEvaluation(id={self.id}, user_id={self.user_id}, score={self.score})>"


class UserAnswer(Base):
    __tablename__ = "user_answers"

    id = Column(Integer, primary_key=True, index=True)
    user_evaluation_id = Column(Integer, ForeignKey("user_evaluations.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    answer_text = Column(Text)  # For open text questions
    selected_answer_ids = Column(Text)  # JSON array of selected answer IDs
    is_correct = Column(Boolean, default=False)
    points_earned = Column(Float, default=0.0)
    time_spent_seconds = Column(Integer)
    answered_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user_evaluation = relationship("UserEvaluation", back_populates="user_answers")
    question = relationship("Question", back_populates="user_answers")

    def __repr__(self):
        return f"<UserAnswer(id={self.id}, question_id={self.question_id}, is_correct={self.is_correct})>"