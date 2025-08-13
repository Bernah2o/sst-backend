from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class AdminConfigBase(BaseModel):
    """Base schema for admin configuration"""
    category: str = Field(..., description="Configuration category (eps, afp, arl, position)")
    display_name: str = Field(..., description="Display name for the configuration")
    emo_periodicity: Optional[str] = Field(None, description="EMO periodicity for position category")
    is_active: bool = Field(True, description="Whether the configuration is active")


class AdminConfigCreate(AdminConfigBase):
    """Schema for creating admin configuration"""
    pass


class AdminConfigUpdate(BaseModel):
    """Schema for updating admin configuration"""
    display_name: Optional[str] = Field(None, description="Display name for the configuration")
    emo_periodicity: Optional[str] = Field(None, description="EMO periodicity for position category")
    is_active: Optional[bool] = Field(None, description="Whether the configuration is active")


class AdminConfig(AdminConfigBase):
    """Schema for admin configuration response"""
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class AdminConfigList(BaseModel):
    """Schema for listing admin configurations by category"""
    category: str
    configs: list[AdminConfig]


class ProgramasBase(BaseModel):
    """Base schema for programs"""
    nombre_programa: str = Field(..., description="Nombre del programa")
    activo: bool = Field(True, description="Si el programa está activo")


class ProgramasCreate(ProgramasBase):
    """Schema for creating programs"""
    pass


class ProgramasUpdate(BaseModel):
    """Schema for updating programs"""
    nombre_programa: Optional[str] = Field(None, description="Nombre del programa")
    activo: Optional[bool] = Field(None, description="Si el programa está activo")


class Programas(ProgramasBase):
    """Schema for programs response"""
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True