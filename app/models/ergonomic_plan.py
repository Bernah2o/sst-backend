from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Date
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class ErgonomicActionPlan(Base):
    __tablename__ = "ergonomic_action_plans"

    id = Column(Integer, primary_key=True, index=True)
    assessment_id = Column(Integer, ForeignKey("homework_assessments.id", ondelete="CASCADE"), nullable=False, unique=True)
    worker_id = Column(Integer, ForeignKey("workers.id"), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    # A. Ítems no conformes (JSON array string)
    non_compliant_items = Column(Text, nullable=True)

    # B. Descripción del hallazgo
    primary_risk = Column(String(50), nullable=True)
    finding_description = Column(Text, nullable=True)

    # D. Análisis de decisión
    work_frequency = Column(String(30), nullable=True)
    sst_conclusion = Column(String(30), nullable=True)
    sst_conclusion_custom = Column(Text, nullable=True)

    # E. Acuerdo y compromiso
    worker_accepts = Column(Boolean, default=False)
    worker_agreement_name = Column(String(200), nullable=True)
    worker_agreement_date = Column(Date, nullable=True)
    worker_signature = Column(String(255), nullable=True)
    sst_approver_name = Column(String(200), nullable=True)
    sst_approval_date = Column(Date, nullable=True)
    sst_signature = Column(String(255), nullable=True)

    # F. Seguimiento y cierre
    verification_date = Column(Date, nullable=True)
    verification_method = Column(Text, nullable=True)
    followup_result = Column(String(30), nullable=True)
    followup_decision = Column(String(30), nullable=True)
    final_observations = Column(Text, nullable=True)

    plan_status = Column(String(20), default="OPEN")  # OPEN, IN_PROGRESS, CLOSED

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relaciones
    assessment = relationship("HomeworkAssessment", backref="ergonomic_plan")
    worker = relationship("Worker", backref="ergonomic_plans")
    creator = relationship("User", foreign_keys=[created_by])
    measures = relationship("ErgonomicMeasure", back_populates="plan", cascade="all, delete-orphan", order_by="ErgonomicMeasure.id")


class ErgonomicMeasure(Base):
    __tablename__ = "ergonomic_measures"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, ForeignKey("ergonomic_action_plans.id", ondelete="CASCADE"), nullable=False, index=True)

    measure_type = Column(String(40), nullable=False)
    description = Column(Text, nullable=False)
    responsible = Column(String(40), nullable=False)
    commitment_date = Column(Date, nullable=True)
    status = Column(String(20), default="pendiente")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    plan = relationship("ErgonomicActionPlan", back_populates="measures")
