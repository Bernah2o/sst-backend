from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class CustomRoleBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=50, description="Nombre único del rol")
    display_name: str = Field(..., min_length=1, max_length=100, description="Nombre para mostrar del rol")
    description: Optional[str] = Field(None, description="Descripción del rol")
    is_active: bool = Field(True, description="Si el rol está activo")


class CustomRoleCreate(CustomRoleBase):
    pass


class CustomRoleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    display_name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    is_active: Optional[bool] = None


class CustomRoleResponse(CustomRoleBase):
    id: int
    is_system_role: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CustomRoleList(BaseModel):
    id: int
    name: str
    display_name: str
    description: Optional[str] = None
    is_system_role: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RolePermissionAssignment(BaseModel):
    permission_ids: List[int] = Field(..., description="Lista de IDs de permisos a asignar")


class RolePermissionResponse(BaseModel):
    id: int
    role_id: int
    permission_id: int
    permission: dict  # Será la información del permiso

    class Config:
        from_attributes = True