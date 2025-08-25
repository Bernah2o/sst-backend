from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
from enum import Enum

from app.database import Base


class TipoSeguridadSocial(str, Enum):
    EPS = "eps"
    AFP = "afp"
    ARL = "arl"


class SeguridadSocial(Base):
    __tablename__ = "seguridad_social"

    id = Column(Integer, primary_key=True, index=True)
    tipo = Column(SQLEnum(TipoSeguridadSocial), nullable=False, index=True)
    nombre = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<SeguridadSocial(id={self.id}, tipo={self.tipo}, nombre={self.nombre})>"