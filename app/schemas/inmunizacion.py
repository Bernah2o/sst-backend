
from typing import Optional
from pydantic import BaseModel, Field

class InmunizacionBase(BaseModel):
    nombre: str = Field(..., max_length=100)
    descripcion: Optional[str] = None
    activo: bool = True

class InmunizacionCreate(InmunizacionBase):
    pass

class InmunizacionUpdate(BaseModel):
    nombre: Optional[str] = Field(None, max_length=100)
    descripcion: Optional[str] = None
    activo: Optional[bool] = None

class Inmunizacion(InmunizacionBase):
    id: int

    class Config:
        from_attributes = True
