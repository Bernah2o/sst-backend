from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from sqlalchemy import Boolean, CheckConstraint, Column, Date, DateTime, Enum as SQLEnum, ForeignKey, Integer, Text
from sqlalchemy.orm import relationship

from app.database import Base


class TipoRestriccion(str, Enum):
    TEMPORAL = "temporal"
    PERMANENTE = "permanente"
    CONDICIONAL = "condicional"


class EstadoImplementacion(str, Enum):
    PENDIENTE = "pendiente"
    EN_PROCESO = "en_proceso"
    IMPLEMENTADA = "implementada"
    VENCIDA = "vencida"


class RestriccionMedica(Base):
    __tablename__ = "restricciones_medicas"
    __table_args__ = (
        CheckConstraint(
            "(tipo_restriccion = 'permanente' AND fecha_fin IS NULL) OR (tipo_restriccion <> 'permanente')",
            name="ck_restricciones_medicas_permanente_sin_fecha_fin",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    worker_id = Column(Integer, ForeignKey("workers.id"), nullable=False, index=True)
    occupational_exam_id = Column(Integer, ForeignKey("occupational_exams.id"), nullable=True, index=True)

    tipo_restriccion = Column(
        SQLEnum(
            TipoRestriccion,
            values_callable=lambda x: [e.value for e in x],
            name="tiporestriccion",
        ),
        nullable=False,
    )
    descripcion = Column(Text, nullable=False)
    actividades_restringidas = Column(Text, nullable=True)
    recomendaciones = Column(Text, nullable=True)

    fecha_inicio = Column(Date, nullable=False, default=date.today)
    fecha_fin = Column(Date, nullable=True)

    activa = Column(Boolean, default=True, nullable=False, index=True)

    fecha_limite_implementacion = Column(Date, nullable=False)
    fecha_implementacion = Column(Date, nullable=True)
    estado_implementacion = Column(
        SQLEnum(
            EstadoImplementacion,
            values_callable=lambda x: [e.value for e in x],
            name="estadoimplementacionrestriccion",
        ),
        nullable=False,
        default=EstadoImplementacion.PENDIENTE,
    )
    implementada = Column(Boolean, default=False, nullable=False)

    responsable_implementacion_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    observaciones_implementacion = Column(Text, nullable=True)

    creado_por = Column(Integer, ForeignKey("users.id"), nullable=True)
    fecha_creacion = Column(DateTime, default=datetime.utcnow, nullable=False)
    modificado_por = Column(Integer, ForeignKey("users.id"), nullable=True)
    fecha_modificacion = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    trabajador = relationship("Worker", back_populates="restricciones_medicas")
    occupational_exam = relationship("OccupationalExam")
    responsable = relationship("User", foreign_keys=[responsable_implementacion_id])
    creador = relationship("User", foreign_keys=[creado_por])
    modificador = relationship("User", foreign_keys=[modificado_por])

    @property
    def dias_para_implementar(self) -> int:
        if self.implementada:
            return 0
        return (self.fecha_limite_implementacion - date.today()).days

    @property
    def esta_vencida(self) -> bool:
        return not self.implementada and date.today() > self.fecha_limite_implementacion

