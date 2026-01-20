from datetime import datetime, date
from enum import Enum
from typing import Optional, List

from sqlalchemy import Boolean, Column, DateTime, Date, Enum as SQLEnum, Integer, String, Text, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property

from app.database import Base
from app.models.user import UserRole


class Gender(str, Enum):
    MALE = "masculino"
    FEMALE = "femenino"
    OTHER = "otro"


class DocumentType(str, Enum):
    CEDULA = "cedula"
    PASSPORT = "pasaporte"
    OTHER = "otro"
    SPECIAL_PERMIT = "permiso_especial_permanencia"


class ContractType(str, Enum):
    INDEFINITE = "indefinido"
    FIXED = "fijo"
    SERVICES = "prestacion_servicios"
    WORK_LABOR = "obra_labor"


class WorkModality(str, Enum):
    ON_SITE = "trabajo_presencial"
    REMOTE = "trabajo_remoto"
    TELEWORK = "teletrabajo"
    HOME_OFFICE = "trabajo_en_casa"
    MOBILE = "trabajo_movil_itinerante"


class RiskLevel(str, Enum):
    LEVEL_I = "nivel_1"
    LEVEL_II = "nivel_2"
    LEVEL_III = "nivel_3"
    LEVEL_IV = "nivel_4"
    LEVEL_V = "nivel_5"


class BloodType(str, Enum):
    A_POSITIVE = "A+"
    A_NEGATIVE = "A-"
    B_POSITIVE = "B+"
    B_NEGATIVE = "B-"
    AB_POSITIVE = "AB+"
    AB_NEGATIVE = "AB-"
    O_POSITIVE = "O+"
    O_NEGATIVE = "O-"


class EPS(str, Enum):
    ALIANSALUD = "Aliansalud EPS"
    ANAS_WAYUU = "Anas Wayuu EPSI"
    ASMET_SALUD = "Asmet Salud EPS"
    CAPITAL_SALUD = "Capital Salud EPS-S"
    CAPRESOCA = "Capresoca EPS"
    COMFACHOCO = "Comfachocó"
    COMFAORIENTE = "Comfaoriente"
    COMPENSAR = "Compensar EPS"
    COOSALUD = "Coosalud EPS"
    DUSAKAWI = "Dusakawi EPSI"
    EPS_FAMILIAR = "EPS Familiar de Colombia"
    EPS_SANITAS = "EPS Sanitas"
    EPS_SURA = "EPS Sura"
    FAMISANAR = "Famisanar"
    MALLAMAS = "Mallamas EPSI"
    MUTUAL_SER = "Mutual SER"
    NUEVA_EPS = "Nueva EPS"
    PIJAOS_SALUD = "Pijaos Salud EPSI"
    SALUD_MIA = "Salud Mía"
    SALUD_TOTAL = "Salud Total EPS"
    SAVIA_SALUD = "Savia Salud EPS"
    SOS = "Servicio Occidental de Salud (SOS) EPS"


class AFP(str, Enum):
    PORVENIR = "Porvenir"
    PROTECCION = "Protección"
    COLFONDOS = "Colfondos"
    SKANDIA = "Skandia"
    COLPENSIONES = "Colpensiones (Régimen de Prima Media)"


class ARL(str, Enum):
    ARL_SURA = "ARL Sura"
    ARL_POSITIVA = "ARL Positiva"
    ARL_COLMENA = "ARL Colmena Seguros"
    ARL_BOLIVAR = "ARL Seguros Bolívar"
    ARL_EQUIDAD = "ARL La Equidad Seguros"
    ARL_MAPFRE = "ARL Mapfre"
    ARL_ALFA = "ARL Alfa"


class Contractor(Base):
    __tablename__ = "contractors"

    id = Column(Integer, primary_key=True, index=True)
    
    # Información Personal
    photo = Column(String(255))  # URL de la foto
    gender = Column(SQLEnum(Gender), nullable=False)
    document_type = Column(SQLEnum(DocumentType), nullable=False)
    document_number = Column(String(50), unique=True, nullable=False, index=True)
    first_name = Column(String(100), nullable=False)
    second_name = Column(String(100), nullable=True)  # Segundo nombre (opcional)
    last_name = Column(String(100), nullable=False)
    second_last_name = Column(String(100), nullable=True)  # Segundo apellido (opcional)
    birth_date = Column(Date, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    phone = Column(String(20))
    
    # Información Laboral
    contract_type = Column(SQLEnum(ContractType), nullable=False)
    work_modality = Column(SQLEnum(WorkModality), nullable=True)
    profession = Column(String(100))
    risk_level = Column(SQLEnum(RiskLevel), nullable=False)
    position = Column(String(100), nullable=False)
    occupation = Column(String(100))
    contract_value = Column(Numeric(12, 2))  # Valor del contrato
    fecha_de_inicio = Column(Date, nullable=True)  # Fecha de inicio del contrato
    fecha_de_finalizacion = Column(Date, nullable=True)  # Fecha de finalización del contrato
    
    # Área de trabajo
    area_id = Column(Integer, ForeignKey("areas.id"), nullable=True)
    
    # Seguridad Social (valores dinámicos desde admin_config)
    eps = Column(String(100))  # Entidad Promotora de Salud
    afp = Column(String(100))  # Administradora de Fondos de Pensiones
    arl = Column(String(100))  # Administradora de Riesgos Laborales
    
    # Ubicación
    country = Column(String(100), default="Colombia")
    department = Column(String(100))
    city = Column(String(100))
    direccion = Column(String(255))  # Dirección completa del contratista
    
    # Información Médica
    blood_type = Column(SQLEnum(BloodType))
    
    # Observaciones
    observations = Column(Text)
    
    # Estado
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Rol asignado (solo empleado para contratistas)
    assigned_role = Column(SQLEnum(UserRole), default=UserRole.EMPLOYEE, nullable=False)
    
    # Indica si el contratista ya se registró en el sistema
    is_registered = Column(Boolean, default=False, nullable=False)
    
    # ID del usuario creado cuando se registra
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    contracts = relationship("ContractorContract", back_populates="contractor", cascade="all, delete-orphan")
    documents = relationship("ContractorDocument", back_populates="contractor", cascade="all, delete-orphan")
    user = relationship("User", foreign_keys=[user_id])
    area_obj = relationship("Area", back_populates="contractors")
    
    # Relación con cursos (solo cursos, no otros módulos)
    enrollments = relationship("Enrollment", back_populates="contractor", cascade="all, delete-orphan")
    
    @hybrid_property
    def age(self) -> int:
        """Calcula la edad automáticamente basada en la fecha de nacimiento"""
        today = date.today()
        return today.year - self.birth_date.year - ((today.month, today.day) < (self.birth_date.month, self.birth_date.day))
    
    @property
    def full_name(self) -> str:
        names = [self.first_name]
        if self.second_name:
            names.append(self.second_name)
        names.append(self.last_name)
        if self.second_last_name:
            names.append(self.second_last_name)
        return " ".join(names)
    
    @property
    def cedula(self) -> str:
        """Legacy field - returns document_number for compatibility"""
        return self.document_number
    
    @property
    def cargo(self) -> str:
        """Legacy field - returns position for compatibility"""
        return self.position
    
    @property
    def contract_amount(self) -> Optional[float]:
        """Returns contract_value for compatibility"""
        return float(self.contract_value) if self.contract_value else None
    
    @property
    def is_contract_active(self) -> bool:
        """Determina si el contrato está activo basado en las fechas"""
        if not self.fecha_de_inicio:
            return False
        
        today = date.today()
        if self.fecha_de_finalizacion:
            return self.fecha_de_inicio <= today <= self.fecha_de_finalizacion
        return self.fecha_de_inicio <= today
    
    def __repr__(self):
        return f"<Contractor(id={self.id}, name='{self.full_name}', document='{self.document_number}')>"


class ContractorContract(Base):
    __tablename__ = "contractor_contracts"
    
    id = Column(Integer, primary_key=True, index=True)
    contractor_id = Column(Integer, ForeignKey("contractors.id"), nullable=False)
    
    # Información del Contrato
    start_date = Column(Date, nullable=False)
    end_date = Column(Date)  # Puede ser null para contratos indefinidos
    contract_value = Column(Numeric(12, 2))  # Valor del contrato
    description = Column(Text)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    contractor = relationship("Contractor", back_populates="contracts")
    
    @property
    def is_active(self) -> bool:
        """Determina si el contrato está activo basado en las fechas"""
        today = date.today()
        if self.end_date:
            return self.start_date <= today <= self.end_date
        return self.start_date <= today
    
    def __repr__(self):
        return f"<ContractorContract(id={self.id}, contractor_id={self.contractor_id}, start='{self.start_date}', end='{self.end_date}')>"


class ContractorDocument(Base):
    __tablename__ = "contractor_documents"
    
    id = Column(Integer, primary_key=True, index=True)
    contractor_id = Column(Integer, ForeignKey("contractors.id"), nullable=False)
    
    # Información del Documento
    document_type = Column(String(100), nullable=False)  # arl, eps, afp, otros
    document_name = Column(String(255), nullable=False)
    file_path = Column(String(500))  # URL del archivo en Storage
    file_size = Column(Integer)  # Tamaño del archivo en bytes
    content_type = Column(String(100))  # Tipo MIME del archivo
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    contractor = relationship("Contractor", back_populates="documents")
    
    def __repr__(self):
        return f"<ContractorDocument(id={self.id}, contractor_id={self.contractor_id}, type='{self.document_type}')>"