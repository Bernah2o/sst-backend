from datetime import datetime, date
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Enum, Date
from sqlalchemy.orm import relationship
from app.database import Base
import enum

class EstadoSeguimiento(str, enum.Enum):
    INICIADO = "iniciado"
    TERMINADO = "terminado"

class ValoracionRiesgo(str, enum.Enum):
    BAJO = "bajo"
    MEDIO = "medio"
    ALTO = "alto"
    MUY_ALTO = "muy_alto"

class Seguimiento(Base):
    __tablename__ = "seguimientos"
    
    id = Column(Integer, primary_key=True, index=True)
    worker_id = Column(Integer, ForeignKey("workers.id"), nullable=False)
    occupational_exam_id = Column(Integer, ForeignKey("occupational_exams.id"), nullable=True)
    programa = Column(String(200), nullable=False)
    
    # Información del trabajador (campos calculados/copiados)
    nombre_trabajador = Column(String(200), nullable=False)
    cedula = Column(String(50), nullable=False)
    cargo = Column(String(200), nullable=False)
    fecha_ingreso = Column(Date, nullable=True)
    
    # Estado del seguimiento
    estado = Column(
        Enum(EstadoSeguimiento, name="estadoseguimiento_enum", values_callable=lambda x: [e.value for e in x]), 
        default=EstadoSeguimiento.INICIADO, 
        nullable=False
    )
    
    # Atributos de gestión del seguimiento
    valoracion_riesgo = Column(
        Enum(ValoracionRiesgo, name="valoracionriesgo_enum", values_callable=lambda x: [e.value for e in x]), 
        nullable=True
    )
    fecha_inicio = Column(Date, nullable=True)
    fecha_final = Column(Date, nullable=True)
    observacion = Column(Text, nullable=True)
    motivo_inclusion = Column(Text, nullable=True)
    
    # Campos del examen ocupacional
    conclusiones_ocupacionales = Column(Text, nullable=True)
    conductas_ocupacionales_prevenir = Column(Text, nullable=True)
    recomendaciones_generales = Column(Text, nullable=True)
    observaciones_examen = Column(Text, nullable=True)
    comentario = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    worker = relationship("Worker", back_populates="seguimientos")
    occupational_exam = relationship("OccupationalExam", back_populates="seguimientos")
    actividades = relationship("SeguimientoActividad", back_populates="seguimiento", cascade="all, delete-orphan")