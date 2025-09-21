from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, field_validator, ValidationInfo

from app.models.supplier import SupplierType, SupplierStatus


class DoctorBase(BaseModel):
    first_name: str
    last_name: str
    document_number: Optional[str] = None
    medical_license: str
    specialty: Optional[str] = None
    sub_specialty: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    years_experience: Optional[int] = None
    observations: Optional[str] = None
    is_active: bool = True

    @field_validator('years_experience')
    @classmethod
    def validate_years_experience(cls, v):
        if v is not None and v < 0:
            raise ValueError('Los años de experiencia no pueden ser negativos')
        return v


class DoctorCreate(DoctorBase):
    supplier_id: int


class DoctorUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    document_number: Optional[str] = None
    medical_license: Optional[str] = None
    specialty: Optional[str] = None
    sub_specialty: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    years_experience: Optional[int] = None
    observations: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator('years_experience')
    @classmethod
    def validate_years_experience(cls, v):
        if v is not None and v < 0:
            raise ValueError('Los años de experiencia no pueden ser negativos')
        return v


class SupplierInfo(BaseModel):
    id: int
    name: str
    supplier_type: str
    
    class Config:
        from_attributes = True


class Doctor(DoctorBase):
    id: int
    supplier_id: int
    full_name: str
    created_at: datetime
    updated_at: datetime
    supplier: Optional[SupplierInfo] = None

    class Config:
        from_attributes = True


class DoctorList(BaseModel):
    id: int
    first_name: str
    last_name: str
    full_name: str
    document_number: Optional[str] = None
    medical_license: str
    specialty: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    is_active: bool
    supplier: Optional[SupplierInfo] = None

    class Config:
        from_attributes = True


class SupplierBase(BaseModel):
    name: str
    nit: str
    supplier_type: str
    status: str = "active"
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    department: Optional[str] = None
    country: str = "Colombia"
    website: Optional[str] = None
    description: Optional[str] = None
    observations: Optional[str] = None
    health_registration: Optional[str] = None
    accreditation: Optional[str] = None
    is_active: bool = True

    @field_validator('supplier_type')
    @classmethod
    def validate_supplier_type(cls, v):
        valid_types = ["medical_center", "laboratory", "clinic", "hospital", "other"]
        if v not in valid_types:
            raise ValueError(f'Tipo de proveedor debe ser uno de: {", ".join(valid_types)}')
        return v

    @field_validator('status')
    @classmethod
    def validate_status(cls, v):
        valid_statuses = ["active", "inactive", "suspended"]
        if v not in valid_statuses:
            raise ValueError(f'Estado debe ser uno de: {", ".join(valid_statuses)}')
        return v


class SupplierCreate(SupplierBase):
    pass


class SupplierUpdate(BaseModel):
    name: Optional[str] = None
    nit: Optional[str] = None
    supplier_type: Optional[str] = None
    status: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    department: Optional[str] = None
    country: Optional[str] = None
    website: Optional[str] = None
    description: Optional[str] = None
    observations: Optional[str] = None
    health_registration: Optional[str] = None
    accreditation: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator('supplier_type')
    @classmethod
    def validate_supplier_type(cls, v):
        if v is not None:
            valid_types = ["medical_center", "laboratory", "clinic", "hospital", "other"]
            if v not in valid_types:
                raise ValueError(f'Tipo de proveedor debe ser uno de: {", ".join(valid_types)}')
        return v

    @field_validator('status')
    @classmethod
    def validate_status(cls, v):
        if v is not None:
            valid_statuses = ["active", "inactive", "suspended"]
            if v not in valid_statuses:
                raise ValueError(f'Estado debe ser uno de: {", ".join(valid_statuses)}')
        return v


class Supplier(SupplierBase):
    id: int
    doctors: List[DoctorList] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SupplierList(BaseModel):
    id: int
    name: str
    nit: str
    supplier_type: str
    status: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    city: Optional[str] = None
    department: Optional[str] = None
    is_active: bool
    doctors_count: Optional[int] = 0

    class Config:
        from_attributes = True


class SupplierWithDoctors(SupplierList):
    doctors: List[DoctorList] = []

    class Config:
        from_attributes = True