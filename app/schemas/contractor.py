from typing import Optional, List
from datetime import date, datetime
from pydantic import BaseModel, EmailStr, validator, Field
from enum import Enum

from app.schemas.common import MessageResponse


class ContractorBase(BaseModel):
    # Información personal
    first_name: str
    last_name: str
    second_name: Optional[str] = None
    second_last_name: Optional[str] = None
    document_type: str
    document_number: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    birth_date: Optional[date] = None
    gender: Optional[str] = None
    
    # Información laboral
    position: Optional[str] = Field(default=None, alias="cargo")
    contract_type: Optional[str] = Field(default=None, alias="tipo_contrato")
    risk_level: Optional[str] = Field(default=None, alias="nivel_riesgo")
    fecha_de_inicio: Optional[date] = None  # Fecha de inicio del contrato
    fecha_de_finalizacion: Optional[date] = None  # Fecha de finalización del contrato
    
    # Campos adicionales de información laboral
    work_modality: Optional[str] = Field(default=None, alias="modalidad_trabajo")
    profession: Optional[str] = Field(default=None, alias="profesion")
    occupation: Optional[str] = Field(default=None, alias="ocupacion")
    contract_value: Optional[float] = Field(default=None, alias="valor_contrato")
    
    # Información de ubicación
    area_id: Optional[int] = None
    address: Optional[str] = Field(default=None, alias="direccion")
    city: Optional[str] = Field(default=None, alias="ciudad")
    department: Optional[str] = Field(default=None, alias="departamento")
    country: Optional[str] = Field(default=None, alias="pais")
    
    # Estado
    is_active: bool = Field(default=True, alias="activo")
    
    # Información médica
    blood_type: Optional[str] = Field(default=None, alias="grupo_sanguineo")
    
    # Información de seguridad social
    eps: Optional[str] = None
    afp: Optional[str] = None
    arl: Optional[str] = None
    
    # Observaciones
    observations: Optional[str] = None

    class Config:
        populate_by_name = True


class ContractorCreate(ContractorBase):
    pass


class ContractorUpdate(BaseModel):
    # Información personal
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    second_name: Optional[str] = None
    second_last_name: Optional[str] = None
    document_type: Optional[str] = Field(default=None, alias="tipo_documento")
    document_number: Optional[str] = Field(default=None, alias="numero_documento")
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    birth_date: Optional[date] = None
    gender: Optional[str] = Field(default=None, alias="genero")
    
    # Información laboral
    position: Optional[str] = Field(default=None, alias="cargo")
    # hire_date eliminado para evitar conflicto con fecha_de_inicio en el modelo
    contract_type: Optional[str] = Field(default=None, alias="tipo_contrato")
    # salary eliminado porque no existe en el modelo Contractor
    risk_level: Optional[str] = Field(default=None, alias="nivel_riesgo")
    fecha_de_inicio: Optional[date] = None  # Fecha de inicio del contrato
    fecha_de_finalizacion: Optional[date] = None  # Fecha de finalización del contrato
    
    # Campos adicionales de información laboral
    work_modality: Optional[str] = Field(default=None, alias="modalidad_trabajo")
    profession: Optional[str] = Field(default=None, alias="profesion")
    occupation: Optional[str] = Field(default=None, alias="ocupacion")
    contract_value: Optional[float] = Field(default=None, alias="valor_contrato")
    
    # Información de ubicación
    area_id: Optional[int] = None
    address: Optional[str] = Field(default=None, alias="direccion")
    city: Optional[str] = Field(default=None, alias="ciudad")
    department: Optional[str] = Field(default=None, alias="departamento")
    country: Optional[str] = Field(default=None, alias="pais")
    
    # Estado
    is_active: Optional[bool] = Field(default=None, alias="activo")
    
    # Información médica
    blood_type: Optional[str] = Field(default=None, alias="grupo_sanguineo")
    
    # Información de seguridad social
    eps: Optional[str] = None
    afp: Optional[str] = None
    arl: Optional[str] = None
    
    # Observaciones
    observations: Optional[str] = None

    class Config:
        populate_by_name = True


class ContractorResponse(ContractorBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class ContractorList(BaseModel):
    contractors: List["ContractorResponse"]
    total: int
    page: int
    size: int
    pages: int
    
    class Config:
        from_attributes = True


class ContractorListItem(BaseModel):
    id: int
    first_name: str
    last_name: str
    second_name: Optional[str] = None
    second_last_name: Optional[str] = None
    document_number: str
    email: Optional[str] = None
    phone: Optional[str] = None
    position: Optional[str] = None
    is_active: bool
    area_id: Optional[int] = None
    
    class Config:
        from_attributes = True


class ContractorDocumentResponse(BaseModel):
    id: int
    contractor_id: int
    tipo_documento: str
    nombre: str
    archivo: str
    descripcion: Optional[str] = None
    fecha_subida: datetime
    tamano_archivo: int
    tipo_contenido: str
    url_descarga: str
    
    class Config:
        from_attributes = True


class ContractorDocumentUpdate(BaseModel):
    document_type: str
    file_name: str


class ContractorContractBase(BaseModel):
    contractor_id: int
    contract_number: str
    start_date: date
    end_date: Optional[date] = None
    contract_type: str
    salary: Optional[float] = None
    position: str
    is_active: bool = True


class ContractorContractCreate(ContractorContractBase):
    pass


class ContractorContractUpdate(BaseModel):
    contract_number: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    contract_type: Optional[str] = None
    salary: Optional[float] = None
    position: Optional[str] = None
    is_active: Optional[bool] = None


class ContractorContractResponse(ContractorContractBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True