from sqlalchemy import Column, Integer, String, DateTime, Date, Text, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class SeguimientoActividad(Base):
    __tablename__ = "seguimiento_actividades"
    
    id = Column(Integer, primary_key=True, index=True)
    seguimiento_id = Column(Integer, ForeignKey("seguimientos.id"), nullable=False)
    titulo = Column(String(255), nullable=False)
    descripcion = Column(Text, nullable=True)
    tipo_fecha = Column(String(50), nullable=False)  # 'rango' para inicio/fin, 'unica' para fecha única
    fecha_inicio = Column(Date, nullable=True)  # Para tipo 'rango'
    fecha_fin = Column(Date, nullable=True)  # Para tipo 'rango'
    fecha_unica = Column(Date, nullable=True)  # Para tipo 'unica'
    estado = Column(String(50), nullable=False, default='pendiente')  # pendiente, en_progreso, completada, cancelada
    prioridad = Column(String(20), nullable=False, default='media')  # baja, media, alta, critica
    responsable = Column(String(255), nullable=True)
    observaciones = Column(Text, nullable=True)
    archivo_soporte_url = Column(String(500), nullable=True)  # URL del archivo en Firebase Storage
    archivo_soporte_nombre = Column(String(255), nullable=True)  # Nombre original del archivo
    completada_por = Column(Integer, ForeignKey("users.id"), nullable=True)
    fecha_completada = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relaciones
    seguimiento = relationship("Seguimiento", back_populates="actividades")
    usuario_completado = relationship("User", foreign_keys=[completada_por])