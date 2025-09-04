from datetime import datetime
from enum import Enum
from typing import Optional, List

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class SupplierType(str, Enum):
    MEDICAL_CENTER = "medical_center"
    LABORATORY = "laboratory"
    CLINIC = "clinic"
    HOSPITAL = "hospital"
    OTHER = "other"


class SupplierStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class Supplier(Base):
    """Modelo para proveedores de servicios médicos"""
    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True, index=True)
    
    # Información básica del proveedor
    name = Column(String(255), nullable=False, index=True)
    nit = Column(String(50), unique=True, nullable=False, index=True)
    supplier_type = Column(String(50), nullable=False)  # Usando String en lugar de Enum para flexibilidad
    status = Column(String(20), default="active", nullable=False)
    
    # Información de contacto
    email = Column(String(255), index=True)
    phone = Column(String(20))
    address = Column(Text)
    city = Column(String(100))
    department = Column(String(100))
    country = Column(String(100), default="Colombia")
    
    # Información adicional
    website = Column(String(255))
    description = Column(Text)
    observations = Column(Text)
    
    # Información de habilitación
    health_registration = Column(String(100))  # Registro de habilitación en salud
    accreditation = Column(String(100))  # Acreditación
    
    # Metadatos
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    doctors = relationship("Doctor", back_populates="supplier", cascade="all, delete-orphan")
    occupational_exams = relationship("OccupationalExam", back_populates="supplier")
    
    def __repr__(self):
        return f"<Supplier(id={self.id}, name='{self.name}', type='{self.supplier_type}')>"


class Doctor(Base):
    """Modelo para médicos asociados a proveedores"""
    __tablename__ = "doctors"

    id = Column(Integer, primary_key=True, index=True)
    
    # Información personal
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    document_number = Column(String(50), nullable=True, index=True)
    
    # Información profesional
    medical_license = Column(String(50), unique=True, nullable=False, index=True)
    specialty = Column(String(100))
    sub_specialty = Column(String(100))
    
    # Información de contacto
    email = Column(String(255), index=True)
    phone = Column(String(20))
    
    # Información adicional
    years_experience = Column(Integer)
    observations = Column(Text)
    
    # Relación con proveedor
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    
    # Metadatos
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    supplier = relationship("Supplier", back_populates="doctors")
    occupational_exams = relationship("OccupationalExam", back_populates="doctor")
    
    @property
    def full_name(self) -> str:
        """Retorna el nombre completo del médico"""
        return f"{self.first_name} {self.last_name}"
    
    def __repr__(self):
        return f"<Doctor(id={self.id}, name='{self.full_name}', license='{self.medical_license}')>"