
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.inmunizacion import Inmunizacion as InmunizacionSchema

class ProfesiogramaInmunizacionCreate(BaseModel):
    inmunizacion_id: int = Field(..., description="ID de la inmunización del catálogo")


class ProfesiogramaInmunizacion(BaseModel):
    id: int
    profesiograma_id: int
    inmunizacion_id: int
    inmunizacion: Optional[InmunizacionSchema] = None

    class Config:
        from_attributes = True
