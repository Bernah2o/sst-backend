from typing import Optional

from pydantic import BaseModel, Field


class CriterioExclusionBase(BaseModel):
    nombre: str = Field(..., max_length=200)
    descripcion: Optional[str] = None


class CriterioExclusionCreate(CriterioExclusionBase):
    pass


class CriterioExclusionUpdate(BaseModel):
    nombre: Optional[str] = Field(None, max_length=200)
    descripcion: Optional[str] = None


class CriterioExclusion(CriterioExclusionBase):
    id: int

    class Config:
        from_attributes = True

