from datetime import datetime, date
from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Date, Enum as SQLEnum, Integer, String, Text, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property

from app.database import Base


class NovedadType(str, Enum):
    PERMISO_DIA_FAMILIA = "permiso_dia_familia"
    LICENCIA_PATERNIDAD = "licencia_paternidad"
    INCAPACIDAD_MEDICA = "incapacidad_medica"
    PERMISO_DIA_NO_REMUNERADO = "permiso_dia_no_remunerado"
    AUMENTO_SALARIO = "aumento_salario"
    LICENCIA_MATERNIDAD = "licencia_maternidad"
    HORAS_EXTRAS = "horas_extras"
    RECARGOS = "recargos"
    CAPACITACION = "capacitacion"


class NovedadStatus(str, Enum):
    PENDIENTE = "pendiente"
    APROBADA = "aprobada"
    RECHAZADA = "rechazada"
    PROCESADA = "procesada"


class WorkerNovedad(Base):
    __tablename__ = "worker_novedades"

    id = Column(Integer, primary_key=True, index=True)
    worker_id = Column(Integer, ForeignKey("workers.id"), nullable=False)
    
    # Información básica de la novedad
    tipo = Column(String(50), nullable=False)  # Using string instead of SQLEnum
    titulo = Column(String(200), nullable=False)
    descripcion = Column(Text)
    status = Column(String(20), default="pendiente", nullable=False)  # Using string instead of SQLEnum
    
    # Fechas para licencias, incapacidades y permisos
    fecha_inicio = Column(Date, nullable=True)
    fecha_fin = Column(Date, nullable=True)
    dias_calculados = Column(Integer, nullable=True)  # Calculado automáticamente
    
    # Campos monetarios para aumentos salariales, horas extras y recargos
    salario_anterior = Column(Numeric(12, 2), nullable=True)
    salario_nuevo = Column(Numeric(12, 2), nullable=True)
    monto_aumento = Column(Numeric(12, 2), nullable=True)
    
    # Para horas extras y recargos
    cantidad_horas = Column(Numeric(8, 2), nullable=True)
    valor_hora = Column(Numeric(10, 2), nullable=True)
    valor_total = Column(Numeric(12, 2), nullable=True)
    
    # Campos de auditoría
    observaciones = Column(Text)
    documento_soporte = Column(String(500))  # URL del documento de soporte
    
    # Usuario que registra/aprueba
    registrado_por = Column(Integer, ForeignKey("users.id"), nullable=False)
    aprobado_por = Column(Integer, ForeignKey("users.id"), nullable=True)
    fecha_aprobacion = Column(DateTime, nullable=True)
    
    # Control de estado
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    worker = relationship("Worker", foreign_keys=[worker_id])
    registrado_por_user = relationship("User", foreign_keys=[registrado_por])
    aprobado_por_user = relationship("User", foreign_keys=[aprobado_por])
    
    @hybrid_property
    def dias_entre_fechas(self) -> Optional[int]:
        """Calcula automáticamente los días entre fecha_inicio y fecha_fin"""
        if self.fecha_inicio and self.fecha_fin:
            return (self.fecha_fin - self.fecha_inicio).days + 1
        return None
    
    @property
    def requiere_fechas(self) -> bool:
        """Determina si el tipo de novedad requiere fechas"""
        tipos_con_fechas = [
            NovedadType.LICENCIA_PATERNIDAD,
            NovedadType.INCAPACIDAD_MEDICA,
            NovedadType.PERMISO_DIA_NO_REMUNERADO,
            NovedadType.LICENCIA_MATERNIDAD,
            NovedadType.CAPACITACION
        ]
        return self.tipo in tipos_con_fechas
    
    @property
    def requiere_montos(self) -> bool:
        """Determina si el tipo de novedad requiere campos monetarios"""
        tipos_con_montos = [
            NovedadType.AUMENTO_SALARIO,
            NovedadType.HORAS_EXTRAS,
            NovedadType.RECARGOS
        ]
        return self.tipo in tipos_con_montos
    
    @property
    def es_dia_unico(self) -> bool:
        """Determina si es una novedad de día único"""
        return self.tipo == NovedadType.PERMISO_DIA_FAMILIA
    
    def calcular_dias(self):
        """Calcula y actualiza el campo dias_calculados"""
        if self.requiere_fechas and self.fecha_inicio and self.fecha_fin:
            self.dias_calculados = (self.fecha_fin - self.fecha_inicio).days + 1
        elif self.es_dia_unico:
            self.dias_calculados = 1
    
    def calcular_nuevo_salario(self):
        """Calcula el nuevo salario basado en el aumento"""
        if self.tipo == NovedadType.AUMENTO_SALARIO and self.salario_anterior and self.monto_aumento:
            self.salario_nuevo = self.salario_anterior + self.monto_aumento
    
    def calcular_valor_total_horas(self):
        """Calcula el valor total de horas extras o recargos"""
        if self.requiere_montos and self.cantidad_horas and self.valor_hora:
            self.valor_total = self.cantidad_horas * self.valor_hora
    
    def __repr__(self):
        return f"<WorkerNovedad(id={self.id}, worker_id={self.worker_id}, tipo='{self.tipo}', status='{self.status}')>"