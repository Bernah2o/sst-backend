"""
Schemas Pydantic para Sector Económico.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class SectorEconomicoBase(BaseModel):
    """Campos base para sector económico."""
    codigo: Optional[str] = Field(None, max_length=20, description="Código del sector (ej: CIIU)")
    nombre: str = Field(..., min_length=1, max_length=200, description="Nombre del sector económico")
    descripcion: Optional[str] = Field(None, description="Descripción del sector")
    es_todos_los_sectores: bool = Field(False, description="Indica si es el sector especial 'TODOS LOS SECTORES'")


class SectorEconomicoCreate(SectorEconomicoBase):
    """Schema para crear un sector económico."""
    pass


class SectorEconomicoUpdate(BaseModel):
    """Schema para actualizar un sector económico."""
    codigo: Optional[str] = Field(None, max_length=20)
    nombre: Optional[str] = Field(None, min_length=1, max_length=200)
    descripcion: Optional[str] = None
    activo: Optional[bool] = None


class SectorEconomico(SectorEconomicoBase):
    """Schema de respuesta para sector económico."""
    id: int
    activo: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SectorEconomicoSimple(BaseModel):
    """Vista simplificada para selectores."""
    id: int
    nombre: str
    es_todos_los_sectores: bool = False

    class Config:
        from_attributes = True
