from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, EmailStr, field_validator, ValidationInfo

from app.models.worker import Gender, DocumentType, ContractType, RiskLevel, BloodType, WorkModality
from app.models.worker_document import DocumentCategory
from app.models.user import UserRole


class WorkerContractBase(BaseModel):
    start_date: date
    end_date: Optional[date] = None
    description: Optional[str] = None


class WorkerContractCreate(WorkerContractBase):
    pass


class WorkerContractUpdate(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    description: Optional[str] = None


class WorkerContract(WorkerContractBase):
    id: int
    worker_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# Esquemas para documentos de trabajadores
class WorkerDocumentBase(BaseModel):
    title: str
    description: Optional[str] = None
    category: DocumentCategory


class WorkerDocumentCreate(WorkerDocumentBase):
    pass


class WorkerDocumentUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[DocumentCategory] = None
    is_active: Optional[bool] = None


class WorkerDocument(WorkerDocumentBase):
    id: int
    worker_id: int
    file_name: str
    file_url: str
    file_size: Optional[int] = None
    file_type: Optional[str] = None
    uploaded_by: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class WorkerDocumentResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    category: DocumentCategory
    file_name: str
    file_url: str
    file_size: Optional[int] = None
    file_type: Optional[str] = None
    uploaded_by: int
    uploader_name: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class WorkerBase(BaseModel):
    photo: Optional[str] = None
    gender: Gender
    document_type: DocumentType
    document_number: str
    first_name: str
    last_name: str
    birth_date: date
    email: EmailStr
    phone: Optional[str] = None
    contract_type: ContractType
    work_modality: Optional[WorkModality] = None
    profession: Optional[str] = None
    risk_level: RiskLevel
    position: str
    cargo_id: Optional[int] = None
    occupation: Optional[str] = None
    salary_ibc: Optional[float] = None
    fecha_de_ingreso: Optional[date] = None
    fecha_de_retiro: Optional[date] = None
    eps: Optional[str] = None
    afp: Optional[str] = None
    arl: Optional[str] = None
    country: str = "Colombia"
    department: Optional[str] = None
    city: Optional[str] = None
    direccion: Optional[str] = None
    blood_type: Optional[BloodType] = None
    observations: Optional[str] = None
    area_id: Optional[int] = None
    is_active: bool = True
    assigned_role: UserRole = UserRole.EMPLOYEE
    
    @field_validator('birth_date')
    @classmethod
    def validate_birth_date(cls, v):
        if v > date.today():
            raise ValueError('La fecha de nacimiento no puede ser futura')
        return v
    
    @field_validator('salary_ibc')
    @classmethod
    def validate_salary(cls, v):
        if v is not None and v < 0:
            raise ValueError('El salario/IBC no puede ser negativo')
        return v


class WorkerCreate(WorkerBase):
    pass


class WorkerUpdate(BaseModel):
    photo: Optional[str] = None
    gender: Optional[Gender] = None
    document_type: Optional[DocumentType] = None
    document_number: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    birth_date: Optional[date] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    contract_type: Optional[ContractType] = None
    work_modality: Optional[WorkModality] = None
    profession: Optional[str] = None
    risk_level: Optional[RiskLevel] = None
    position: Optional[str] = None
    cargo_id: Optional[int] = None
    occupation: Optional[str] = None
    salary_ibc: Optional[float] = None
    fecha_de_ingreso: Optional[date] = None
    fecha_de_retiro: Optional[date] = None
    eps: Optional[str] = None
    afp: Optional[str] = None
    arl: Optional[str] = None
    country: Optional[str] = None
    department: Optional[str] = None
    city: Optional[str] = None
    direccion: Optional[str] = None
    blood_type: Optional[BloodType] = None
    observations: Optional[str] = None
    area_id: Optional[int] = None
    is_active: Optional[bool] = None
    assigned_role: Optional[UserRole] = None
    
    @field_validator('birth_date')
    @classmethod
    def validate_birth_date(cls, v):
        if v is not None and v > date.today():
            raise ValueError('La fecha de nacimiento no puede ser futura')
        return v
    
    @field_validator('salary_ibc')
    @classmethod
    def validate_salary(cls, v):
        if v is not None and v < 0:
            raise ValueError('El salario/IBC no puede ser negativo')
        return v


class Worker(WorkerBase):
    id: int
    age: int  # Calculado automáticamente
    full_name: str
    contracts: List[WorkerContract] = []
    is_registered: bool
    user_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class WorkerList(BaseModel):
    id: int
    first_name: str
    last_name: str
    full_name: str
    document_number: str
    email: str
    position: str
    cargo_id: Optional[int] = None
    department: Optional[str] = None
    direccion: Optional[str] = None
    age: int
    risk_level: RiskLevel
    fecha_de_ingreso: Optional[date] = None
    is_active: bool
    assigned_role: UserRole
    is_registered: bool
    photo: Optional[str] = None
    area_id: Optional[int] = None
    area_name: Optional[str] = None
    # Legacy fields for compatibility
    cedula: Optional[str] = None
    base_salary: Optional[float] = None
    
    class Config:
        from_attributes = True
