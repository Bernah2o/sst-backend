from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, field_validator


class AreaBase(BaseModel):
    name: str
    description: Optional[str] = None
    is_active: bool = True
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        if not v or not v.strip():
            raise ValueError('El nombre del área es requerido')
        return v.strip()


class AreaCreate(AreaBase):
    pass


class AreaUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        if v is not None and (not v or not v.strip()):
            raise ValueError('El nombre del área no puede estar vacío')
        return v.strip() if v else v


class Area(AreaBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class AreaList(BaseModel):
    items: List[Area]
    total: int
    page: int
    size: int
    pages: int
    
    class Config:
        from_attributes = True