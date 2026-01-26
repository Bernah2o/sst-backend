from datetime import datetime, date
from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Date, Enum as SQLEnum, Integer, String, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship

from app.database import Base


class ExamType(str, Enum):
    INGRESO = "examen_ingreso"
    PERIODICO = "examen_periodico"
    REINTEGRO = "examen_reintegro"
    RETIRO = "examen_retiro"


class MedicalAptitude(str, Enum):
    APTO = "apto"
    APTO_CON_RECOMENDACIONES = "apto_con_recomendaciones"
    NO_APTO = "no_apto"


class OccupationalExam(Base):
    __tablename__ = "occupational_exams"

    id = Column(Integer, primary_key=True, index=True)
    worker_id = Column(Integer, ForeignKey("workers.id"), nullable=False)
    
    # Información del Examen
    tipo_examen_id = Column(Integer, ForeignKey('tipos_examen.id'), nullable=False)
    exam_date = Column(Date, nullable=False)
    departamento = Column(String(50), nullable=True)
    ciudad = Column(String(50), nullable=True)
    programa = Column(String(200), nullable=True)  # Programa opcional

    afiliacion_eps_momento = Column(String(100), nullable=True)
    afiliacion_afp_momento = Column(String(100), nullable=True)
    afiliacion_arl_momento = Column(String(100), nullable=True)

    duracion_cargo_actual_meses = Column(Integer, nullable=True)
    factores_riesgo_evaluados = Column(JSON, nullable=True)
    cargo_id_momento_examen = Column(Integer, ForeignKey("cargos.id"), nullable=True)
    
    # Conclusiones y Recomendaciones
    occupational_conclusions = Column(Text)  # Conclusiones ocupacionales
    preventive_occupational_behaviors = Column(Text)  # Conductas ocupacionales a prevenir
    general_recommendations = Column(Text)  # Recomendaciones generales
    
    # Concepto Médico
    medical_aptitude_concept = Column(SQLEnum(MedicalAptitude), nullable=False)
    
    # Información adicional
    observations = Column(Text)  # Observaciones adicionales
    
    # Archivo PDF del examen
    pdf_file_path = Column(String(500), nullable=True)  # Ruta del archivo PDF del examen
    
    # Control de seguimiento
    requires_follow_up = Column(Boolean, default=False, nullable=False)  # Indica si el examen requiere seguimiento
    
    # Relaciones con Supplier y Doctor (nuevos campos)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=True)
    
    # Campos legacy para compatibilidad (se pueden eliminar gradualmente)
    examining_doctor = Column(String(200))  # Médico que realizó el examen
    medical_center = Column(String(200))  # Centro médico donde se realizó
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    worker = relationship("Worker", back_populates="occupational_exams")
    tipo_examen = relationship("TipoExamen")
    cargo_momento = relationship("Cargo", foreign_keys=[cargo_id_momento_examen])
    supplier = relationship("Supplier", back_populates="occupational_exams")
    doctor = relationship("Doctor", back_populates="occupational_exams")
    seguimientos = relationship("Seguimiento", back_populates="occupational_exam")
    
    def __repr__(self):
        return f"<OccupationalExam(id={self.id}, worker_id={self.worker_id}, tipo_examen_id={self.tipo_examen_id}, date='{self.exam_date}')>"
