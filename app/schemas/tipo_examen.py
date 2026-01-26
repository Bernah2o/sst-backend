from typing import Optional

from pydantic import BaseModel, Field


class TipoExamenBase(BaseModel):
    nombre: str = Field(..., max_length=150)
    descripcion: Optional[str] = None
    activo: bool = True


class TipoExamenCreate(TipoExamenBase):
    pass


class TipoExamenUpdate(BaseModel):
    nombre: Optional[str] = Field(None, max_length=150)
    descripcion: Optional[str] = None
    activo: Optional[bool] = None


class TipoExamen(TipoExamenBase):
    id: int

    class Config:
        from_attributes = True

