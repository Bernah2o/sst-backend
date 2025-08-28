from sqlalchemy import Column, Integer, String, Date, Text, ForeignKey, Enum, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property
from app.database import Base
import enum
from datetime import datetime


class EventMonth(enum.Enum):
    ENERO = "enero"
    FEBRERO = "febrero"
    MARZO = "marzo"
    ABRIL = "abril"
    MAYO = "mayo"
    JUNIO = "junio"
    JULIO = "julio"
    AGOSTO = "agosto"
    SEPTIEMBRE = "septiembre"
    OCTUBRE = "octubre"
    NOVIEMBRE = "noviembre"
    DICIEMBRE = "diciembre"


class EventType(enum.Enum):
    ACCIDENTE_TRABAJO = "ACCIDENTE DE TRABAJO"
    ENFERMEDAD_LABORAL = "ENFERMEDAD LABORAL"
    ACCIDENTE_COMUN = "ACCIDENTE COMÚN"
    ENFERMEDAD_GENERAL = "ENFERMEDAD GENERAL"


class Absenteeism(Base):
    __tablename__ = "absenteeism"

    id = Column(Integer, primary_key=True, index=True)
    
    # Mes del evento
    event_month = Column(Enum(EventMonth), nullable=False)
    
    # Relación con trabajador
    worker_id = Column(Integer, ForeignKey("workers.id"), nullable=False)
    worker = relationship("Worker", back_populates="absenteeism_records")
    
    # Tipo de evento
    event_type = Column(Enum(EventType), nullable=False)
    
    # Periodo de incapacidad
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    
    # Días de incapacidad
    disability_days = Column(Integer, nullable=False)
    
    # Prórroga
    extension = Column(Integer, default=0)
    
    # Días cargados
    charged_days = Column(Integer, default=0)
    
    # Días de incapacidad o días cargados
    disability_or_charged_days = Column(Integer, nullable=True)
    
    # Código diagnóstico
    diagnostic_code = Column(String(20), nullable=False)
    
    # Descripción de la categoría de la condición de salud
    health_condition_description = Column(Text, nullable=False)
    
    # Observaciones
    observations = Column(Text)
    
    # Costos asegurados A.T.
    insured_costs_at = Column(Numeric(15, 2), default=0)
    
    # Costos asegurados A.C. - E.G.
    insured_costs_ac_eg = Column(Numeric(15, 2), default=0)
    
    # Costos asumidos A.T.
    assumed_costs_at = Column(Numeric(15, 2), default=0)
    
    # Costos asumidos A.C. - E.G.
    assumed_costs_ac_eg = Column(Numeric(15, 2), default=0)
    
    # Campos calculados como propiedades híbridas
    @hybrid_property
    def cedula(self):
        """Obtiene la cédula del trabajador asociado"""
        return self.worker.cedula if self.worker else None
    
    @hybrid_property
    def cargo(self):
        """Obtiene el cargo del trabajador asociado"""
        return self.worker.cargo if self.worker else None
    
    @hybrid_property
    def base_salary(self):
        """Obtiene el salario base del trabajador asociado"""
        return self.worker.salario if self.worker else 0
    
    @hybrid_property
    def daily_base_salary(self):
        """Calcula el salario base diario (salario / 30 días)"""
        if self.worker and self.worker.salario:
            return self.worker.salario / 30
        return 0
    
    @hybrid_property
    def total_disability_days(self):
        """Calcula el total de días de incapacidad entre fecha inicial y final"""
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days + 1
        return 0
    
    def __repr__(self):
        return f"<Absenteeism(id={self.id}, worker_id={self.worker_id}, event_type={self.event_type}, start_date={self.start_date})>"