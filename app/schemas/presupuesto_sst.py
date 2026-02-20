from pydantic import BaseModel
from typing import Optional, List
from decimal import Decimal
from datetime import datetime


# ─────────────────────────────────────────────
# Mensual
# ─────────────────────────────────────────────

class PresupuestoMensualUpdate(BaseModel):
    proyectado: Optional[Decimal] = None
    ejecutado: Optional[Decimal] = None


class PresupuestoMensualResponse(BaseModel):
    id: int
    item_id: int
    mes: int
    proyectado: Decimal
    ejecutado: Decimal

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────
# Item
# ─────────────────────────────────────────────

class PresupuestoItemCreate(BaseModel):
    actividad: str
    orden: int = 999


class PresupuestoItemUpdate(BaseModel):
    actividad: Optional[str] = None
    orden: Optional[int] = None


class PresupuestoItemResponse(BaseModel):
    id: int
    categoria_id: int
    actividad: str
    es_default: bool
    orden: int
    montos_mensuales: List[PresupuestoMensualResponse] = []

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────
# Categoría
# ─────────────────────────────────────────────

class PresupuestoCategoriaResponse(BaseModel):
    id: int
    presupuesto_id: int
    categoria: str
    orden: int
    items: List[PresupuestoItemResponse] = []

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────
# Presupuesto SST (principal)
# ─────────────────────────────────────────────

class PresupuestoSSTBase(BaseModel):
    año: int
    empresa_id: Optional[int] = None
    codigo: str = "AN-SST-03"
    version: str = "1"
    titulo: Optional[str] = "CONSOLIDADO GENERAL PRESUPUESTO"
    encargado_sgsst: Optional[str] = None
    aprobado_por: Optional[str] = None


class PresupuestoSSTCreate(PresupuestoSSTBase):
    pass


class PresupuestoSSTUpdate(BaseModel):
    codigo: Optional[str] = None
    version: Optional[str] = None
    titulo: Optional[str] = None
    encargado_sgsst: Optional[str] = None
    aprobado_por: Optional[str] = None


class PresupuestoSSTResponse(PresupuestoSSTBase):
    id: int
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PresupuestoSSTDetailResponse(PresupuestoSSTResponse):
    categorias: List[PresupuestoCategoriaResponse] = []
