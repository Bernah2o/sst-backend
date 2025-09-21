from pydantic import BaseModel, field_validator, ValidationInfo
from typing import Optional
from datetime import datetime
from app.models.seguridad_social import TipoSeguridadSocial


class SeguridadSocialBase(BaseModel):
    tipo: TipoSeguridadSocial
    nombre: str
    is_active: bool = True
    
    @field_validator('nombre')
    @classmethod
    def validate_nombre(cls, v):
        if not v or not v.strip():
            raise ValueError('El nombre no puede estar vacío')
        if len(v.strip()) < 2:
            raise ValueError('El nombre debe tener al menos 2 caracteres')
        return v.strip()


class SeguridadSocialCreate(SeguridadSocialBase):
    pass


class SeguridadSocialUpdate(BaseModel):
    nombre: Optional[str] = None
    is_active: Optional[bool] = None
    
    @field_validator('nombre')
    @classmethod
    def validate_nombre(cls, v):
        if v is not None:
            if not v or not v.strip():
                raise ValueError('El nombre no puede estar vacío')
            if len(v.strip()) < 2:
                raise ValueError('El nombre debe tener al menos 2 caracteres')
            return v.strip()
        return v


class SeguridadSocial(SeguridadSocialBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class SeguridadSocialList(BaseModel):
    items: list[SeguridadSocial]
    total: int
    page: int = 1
    per_page: int = 100
    
    class Config:
        from_attributes = True