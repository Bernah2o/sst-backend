"""
Schemas Pydantic para Empresa.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field

from app.schemas.sector_economico import SectorEconomicoSimple


class EmpresaCaracteristicas(BaseModel):
    """Características de la empresa para filtrado automático de normas."""
    tiene_trabajadores_independientes: bool = Field(False, description="Tiene trabajadores independientes")
    tiene_teletrabajo: bool = Field(False, description="Tiene modalidad de teletrabajo")
    tiene_trabajo_alturas: bool = Field(False, description="Tiene trabajo en alturas")
    tiene_trabajo_espacios_confinados: bool = Field(False, description="Tiene trabajo en espacios confinados")
    tiene_trabajo_caliente: bool = Field(False, description="Tiene trabajo en caliente (soldadura, etc.)")
    tiene_sustancias_quimicas: bool = Field(False, description="Maneja sustancias químicas")
    tiene_radiaciones: bool = Field(False, description="Tiene exposición a radiaciones")
    tiene_trabajo_nocturno: bool = Field(False, description="Tiene trabajo nocturno")
    tiene_menores_edad: bool = Field(False, description="Tiene trabajadores menores de edad")
    tiene_mujeres_embarazadas: bool = Field(False, description="Tiene mujeres embarazadas")
    tiene_conductores: bool = Field(False, description="Tiene conductores de vehículos")
    tiene_manipulacion_alimentos: bool = Field(False, description="Tiene manipulación de alimentos")
    tiene_maquinaria_pesada: bool = Field(False, description="Tiene maquinaria pesada")
    tiene_riesgo_electrico: bool = Field(False, description="Tiene riesgo eléctrico")
    tiene_riesgo_biologico: bool = Field(False, description="Tiene riesgo biológico")
    tiene_trabajo_excavaciones: bool = Field(False, description="Tiene trabajo en excavaciones")
    tiene_trabajo_administrativo: bool = Field(False, description="Tiene trabajo administrativo")


class EmpresaBase(BaseModel):
    """Campos base para empresa."""
    nombre: str = Field(..., min_length=1, max_length=200, description="Nombre de la empresa")
    nit: Optional[str] = Field(None, max_length=20, description="NIT de la empresa")
    razon_social: Optional[str] = Field(None, max_length=300, description="Razón social")
    direccion: Optional[str] = Field(None, max_length=300, description="Dirección")
    telefono: Optional[str] = Field(None, max_length=50, description="Teléfono")
    email: Optional[str] = Field(None, max_length=150, description="Email de contacto")
    sector_economico_id: Optional[int] = Field(None, description="ID del sector económico")


class EmpresaCreate(EmpresaBase, EmpresaCaracteristicas):
    """Schema para crear una empresa."""
    pass


class EmpresaUpdate(BaseModel):
    """Schema para actualizar una empresa."""
    nombre: Optional[str] = Field(None, min_length=1, max_length=200)
    nit: Optional[str] = Field(None, max_length=20)
    razon_social: Optional[str] = Field(None, max_length=300)
    direccion: Optional[str] = Field(None, max_length=300)
    telefono: Optional[str] = Field(None, max_length=50)
    email: Optional[str] = Field(None, max_length=150)
    sector_economico_id: Optional[int] = None
    activo: Optional[bool] = None
    # Características
    tiene_trabajadores_independientes: Optional[bool] = None
    tiene_teletrabajo: Optional[bool] = None
    tiene_trabajo_alturas: Optional[bool] = None
    tiene_trabajo_espacios_confinados: Optional[bool] = None
    tiene_trabajo_caliente: Optional[bool] = None
    tiene_sustancias_quimicas: Optional[bool] = None
    tiene_radiaciones: Optional[bool] = None
    tiene_trabajo_nocturno: Optional[bool] = None
    tiene_menores_edad: Optional[bool] = None
    tiene_mujeres_embarazadas: Optional[bool] = None
    tiene_conductores: Optional[bool] = None
    tiene_manipulacion_alimentos: Optional[bool] = None
    tiene_maquinaria_pesada: Optional[bool] = None
    tiene_riesgo_electrico: Optional[bool] = None
    tiene_riesgo_biologico: Optional[bool] = None
    tiene_trabajo_excavaciones: Optional[bool] = None
    tiene_trabajo_administrativo: Optional[bool] = None


class Empresa(EmpresaBase, EmpresaCaracteristicas):
    """Schema de respuesta para empresa."""
    id: int
    activo: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    creado_por: Optional[int] = None
    sector_economico: Optional[SectorEconomicoSimple] = None

    class Config:
        from_attributes = True


class EmpresaSimple(BaseModel):
    """Vista simplificada para selectores."""
    id: int
    nombre: str
    nit: Optional[str] = None

    class Config:
        from_attributes = True


class EmpresaResumen(BaseModel):
    """Vista resumida con estadísticas de cumplimiento."""
    id: int
    nombre: str
    nit: Optional[str] = None
    sector_economico_nombre: Optional[str] = None
    activo: bool = True
    # Estadísticas de cumplimiento
    total_normas_aplicables: int = 0
    normas_cumple: int = 0
    normas_no_cumple: int = 0
    normas_pendientes: int = 0
    porcentaje_cumplimiento: float = 0.0

    class Config:
        from_attributes = True


class EmpresaConCaracteristicas(Empresa):
    """Empresa con lista de características activas."""
    caracteristicas_activas: List[str] = []

    class Config:
        from_attributes = True
