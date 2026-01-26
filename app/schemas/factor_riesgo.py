from typing import Optional

from pydantic import BaseModel, Field

from app.models.factor_riesgo import CategoriaFactorRiesgo


class FactorRiesgoBase(BaseModel):
    codigo: str = Field(..., max_length=20)
    nombre: str = Field(..., max_length=100)
    categoria: CategoriaFactorRiesgo
    descripcion: Optional[str] = None
    nivel_accion: Optional[str] = Field(None, max_length=100)
    periodicidad_sugerida_meses: Optional[int] = None
    normativa_aplicable: Optional[str] = Field(None, max_length=200)
    examenes_sugeridos: Optional[list] = None
    unidad_medida: Optional[str] = Field(None, max_length=50)
    simbolo_unidad: Optional[str] = Field(None, max_length=20)
    instrumento_medida: Optional[str] = Field(None, max_length=80)
    requiere_sve: bool = False
    tipo_sve: Optional[str] = Field(None, max_length=50)
    activo: bool = True


class FactorRiesgoCreate(FactorRiesgoBase):
    pass


class FactorRiesgoUpdate(BaseModel):
    codigo: Optional[str] = Field(None, max_length=20)
    nombre: Optional[str] = Field(None, max_length=100)
    categoria: Optional[CategoriaFactorRiesgo] = None
    descripcion: Optional[str] = None
    nivel_accion: Optional[str] = Field(None, max_length=100)
    periodicidad_sugerida_meses: Optional[int] = None
    normativa_aplicable: Optional[str] = Field(None, max_length=200)
    examenes_sugeridos: Optional[list] = None
    unidad_medida: Optional[str] = Field(None, max_length=50)
    simbolo_unidad: Optional[str] = Field(None, max_length=20)
    instrumento_medida: Optional[str] = Field(None, max_length=80)
    requiere_sve: Optional[bool] = None
    tipo_sve: Optional[str] = Field(None, max_length=50)
    activo: Optional[bool] = None


class FactorRiesgo(FactorRiesgoBase):
    id: int

    class Config:
        from_attributes = True
