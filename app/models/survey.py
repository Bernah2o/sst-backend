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
)
from sqlalchemy.orm import relationship

from app.database import Base


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


class Survey(Base):
    __tablename__ = "surveys"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    instructions = Column(Text)
    is_anonymous = Column(Boolean, default=False)
    allow_multiple_responses = Column(Boolean, default=False)
    status = Column(SQLEnum(SurveyStatus), default=SurveyStatus.DRAFT)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=True)  # Link to course
    is_course_survey = Column(Boolean, default=False)  # True if this is a course satisfaction survey
    required_for_completion = Column(Boolean, default=False)  # True if required to complete course
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    published_at = Column(DateTime)
    closes_at = Column(DateTime)
    expires_at = Column(DateTime)

    # Relationships
    creator = relationship("User", foreign_keys=[created_by])
    course = relationship("Course", back_populates="surveys")
    questions = relationship("SurveyQuestion", back_populates="survey", cascade="all, delete-orphan")
    user_surveys = relationship("UserSurvey", back_populates="survey")

    def __repr__(self):
        return f"<Survey(id={self.id}, title='{self.title}', status='{self.status}')>"


class SurveyQuestion(Base):
    __tablename__ = "survey_questions"

    id = Column(Integer, primary_key=True, index=True)
    survey_id = Column(Integer, ForeignKey("surveys.id"), nullable=False)
    question_text = Column(Text, nullable=False)
    question_type = Column(SQLEnum(SurveyQuestionType), nullable=False)
    options = Column(Text)  # JSON array of options for multiple choice
    is_required = Column(Boolean, default=False)
    order_index = Column(Integer, default=0)
    min_value = Column(Integer)  # For rating/scale questions
    max_value = Column(Integer)  # For rating/scale questions
    placeholder_text = Column(String(255))  # For text inputs
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    survey = relationship("Survey", back_populates="questions")
    user_answers = relationship("UserSurveyAnswer", back_populates="question")

    def __repr__(self):
        return f"<SurveyQuestion(id={self.id}, type='{self.question_type}', survey_id={self.survey_id})>"


class UserSurvey(Base):
    __tablename__ = "user_surveys"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Nullable for anonymous surveys
    survey_id = Column(Integer, ForeignKey("surveys.id"), nullable=False)
    enrollment_id = Column(Integer, ForeignKey("enrollments.id"), nullable=True)  # Link to course enrollment
    status = Column(SQLEnum(UserSurveyStatus), default=UserSurveyStatus.NOT_STARTED)
    anonymous_token = Column(String(255))  # For anonymous surveys
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="user_surveys")
    survey = relationship("Survey", back_populates="user_surveys")
    enrollment = relationship("Enrollment")
    answers = relationship("UserSurveyAnswer", back_populates="user_survey")

    def __repr__(self):
        return f"<UserSurvey(id={self.id}, user_id={self.user_id}, survey_id={self.survey_id})>"


class UserSurveyAnswer(Base):
    __tablename__ = "user_survey_answers"

    id = Column(Integer, primary_key=True, index=True)
    user_survey_id = Column(Integer, ForeignKey("user_surveys.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("survey_questions.id"), nullable=False)
    answer_text = Column(Text)  # For text answers
    answer_value = Column(Integer)  # For rating/scale answers
    selected_options = Column(Text)  # JSON array of selected options
    answered_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user_survey = relationship("UserSurvey", back_populates="answers")
    question = relationship("SurveyQuestion", back_populates="user_answers")

    def __repr__(self):
        return f"<UserSurveyAnswer(id={self.id}, question_id={self.question_id})>"