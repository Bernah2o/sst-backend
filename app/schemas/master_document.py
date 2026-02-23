from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class MasterDocumentBase(BaseModel):
    empresa_id: Optional[int] = None
    tipo_documento: str
    nombre_documento: str
    version: Optional[str] = None
    codigo: str
    fecha: Optional[date] = None
    fecha_texto: Optional[str] = None
    ubicacion: Optional[str] = None
    is_active: bool = True


class MasterDocumentCreate(MasterDocumentBase):
    pass


class MasterDocumentUpdate(BaseModel):
    empresa_id: Optional[int] = None
    tipo_documento: Optional[str] = None
    nombre_documento: Optional[str] = None
    version: Optional[str] = None
    codigo: Optional[str] = None
    fecha: Optional[date] = None
    fecha_texto: Optional[str] = None
    ubicacion: Optional[str] = None
    is_active: Optional[bool] = None


class MasterDocumentResponse(MasterDocumentBase):
    id: int
    created_by: Optional[int] = None
    updated_by: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

