from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class CargoBase(BaseModel):
    """Esquema base para cargos"""
    nombre_cargo: str = Field(..., description="Nombre del cargo/posición")
    periodicidad_emo: Optional[str] = Field(None, description="Periodicidad de exámenes médicos ocupacionales")
    activo: bool = Field(True, description="Si el cargo está activo")


class CargoCreate(CargoBase):
    """Esquema para crear cargos"""
    pass


class CargoUpdate(BaseModel):
    """Esquema para actualizar cargos"""
    nombre_cargo: Optional[str] = Field(None, description="Nombre del cargo/posición")
    periodicidad_emo: Optional[str] = Field(None, description="Periodicidad de exámenes médicos ocupacionales")
    activo: Optional[bool] = Field(None, description="Si el cargo está activo")


class Cargo(CargoBase):
    """Esquema para respuesta de cargos"""
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class CargoList(BaseModel):
    """Esquema para listar cargos"""
    cargos: list[Cargo]
    total: int