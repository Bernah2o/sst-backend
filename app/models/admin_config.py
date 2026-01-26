from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.sql import func
from app.database import Base


class AdminConfig(Base):
    """Model for administrative configuration values"""
    __tablename__ = "admin_config"
    
    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(50), nullable=False, index=True)  # 'eps', 'afp', 'arl', 'position'
    display_name = Column(String(200), nullable=False)
    emo_periodicity = Column(String(50), nullable=True)  # For position category: 'anual', 'bianual', etc.
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<AdminConfig(category='{self.category}', display_name='{self.display_name}')>"


class Programas(Base):
    """Model for programs configuration"""
    __tablename__ = "programas"
    
    id = Column(Integer, primary_key=True, index=True)
    nombre_programa = Column(String(200), nullable=False)
    activo = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<Programas(nombre_programa='{self.nombre_programa}', activo={self.activo})>"


class Ocupacion(Base):
    """Model for occupations catalog"""
    __tablename__ = "ocupaciones"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), unique=True, nullable=False, index=True)
    descripcion = Column(String(255), nullable=True)
    activo = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<Ocupacion(nombre='{self.nombre}', activo={self.activo})>"
