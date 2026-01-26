from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.profesiograma import (
    NivelExposicion,
    NivelRiesgoCargo,
    ProfesiogramaEstado,
    TipoEvaluacionExamen,
)
from app.schemas.profesiograma_inmunizacion import ProfesiogramaInmunizacion, ProfesiogramaInmunizacionCreate

MIN_JUSTIFICACION_PERIODICIDAD_EMO_LEN = 50


class ProfesiogramaFactorBase(BaseModel):
    factor_riesgo_id: int
    nivel_exposicion: NivelExposicion
    tiempo_exposicion_horas: Decimal = Field(..., description="Horas/día")
    valor_medido: Optional[Decimal] = None
    valor_limite_permisible: Optional[Decimal] = None
    unidad_medida: Optional[str] = None
    proceso: Optional[str] = Field(None, max_length=100)
    actividad: Optional[str] = Field(None, max_length=150)
    tarea: Optional[str] = Field(None, max_length=150)
    rutinario: Optional[bool] = None
    descripcion_peligro: Optional[str] = None
    efectos_posibles: Optional[str] = None
    zona_lugar: Optional[str] = Field(None, max_length=150)
    tipo_peligro: Optional[str] = Field(None, max_length=80)
    clasificacion_peligro: Optional[str] = Field(None, max_length=120)
    controles_existentes: Optional[str] = None
    fuente: Optional[str] = None
    medio: Optional[str] = None
    individuo: Optional[str] = None
    peor_consecuencia: Optional[str] = None
    requisito_legal: Optional[str] = None
    nd: Optional[int] = None
    ne: Optional[int] = None
    nc: Optional[int] = None
    eliminacion: Optional[str] = None
    sustitucion: Optional[str] = None
    controles_ingenieria: Optional[str] = None
    controles_administrativos: Optional[str] = None
    senalizacion: Optional[str] = None
    epp_requerido: Optional[str] = None
    controles_esiae: List["ProfesiogramaControlESIAECreate"] = Field(default_factory=list)
    intervenciones: List["ProfesiogramaIntervencionCreate"] = Field(default_factory=list)

    @field_validator("nd")
    @classmethod
    def validate_nd(cls, v):
        from app.services.gtc45 import validate_nd

        validate_nd(v)
        return v

    @field_validator("ne")
    @classmethod
    def validate_ne(cls, v):
        from app.services.gtc45 import validate_ne

        validate_ne(v)
        return v

    @field_validator("nc")
    @classmethod
    def validate_nc(cls, v):
        from app.services.gtc45 import validate_nc

        validate_nc(v)
        return v

    @model_validator(mode="after")
    def validate_gtc45_completeness(self):
        values = (self.nd, self.ne, self.nc)
        if any(v is not None for v in values) and not all(v is not None for v in values):
            raise ValueError("nd, ne y nc deben enviarse juntos (todos o ninguno)")
        return self


class ProfesiogramaFactorCreate(ProfesiogramaFactorBase):
    pass


class ProfesiogramaFactor(ProfesiogramaFactorBase):
    profesiograma_id: int
    fecha_registro: datetime
    registrado_por: int
    np: Optional[int] = None
    nr: Optional[int] = None
    interpretacion_np: Optional[str] = None
    nivel_riesgo: Optional[str] = None
    color_riesgo: Optional[str] = None
    accion_riesgo: Optional[str] = None
    nivel_intervencion: Optional[str] = None
    aceptabilidad: Optional[str] = None
    controles_esiae: List["ProfesiogramaControlESIAE"] = Field(default_factory=list)
    intervenciones: List["ProfesiogramaIntervencion"] = Field(default_factory=list)

    class Config:
        from_attributes = True


class ProfesiogramaControlESIAEBase(BaseModel):
    nivel: str = Field(..., max_length=10)
    medida: Optional[str] = Field(None, max_length=150)
    descripcion: Optional[str] = None
    estado_actual: Optional[str] = Field(None, max_length=50)
    meta: Optional[str] = Field(None, max_length=150)


class ProfesiogramaControlESIAECreate(ProfesiogramaControlESIAEBase):
    pass


class ProfesiogramaControlESIAE(ProfesiogramaControlESIAEBase):
    id: int

    class Config:
        from_attributes = True


class ProfesiogramaIntervencionBase(BaseModel):
    tipo_control: str = Field(..., max_length=20)
    descripcion: Optional[str] = None
    responsable: Optional[str] = Field(None, max_length=100)
    plazo: Optional[str] = Field(None, max_length=60)


class ProfesiogramaIntervencionCreate(ProfesiogramaIntervencionBase):
    pass


class ProfesiogramaIntervencion(ProfesiogramaIntervencionBase):
    id: int

    class Config:
        from_attributes = True


class ProfesiogramaExamenBase(BaseModel):
    tipo_examen_id: int
    tipo_evaluacion: TipoEvaluacionExamen
    periodicidad_meses: Optional[int] = None
    justificacion_periodicidad: Optional[str] = None
    obligatorio: bool = True
    orden_realizacion: Optional[int] = None
    normativa_base: Optional[str] = Field(None, max_length=200)

    @model_validator(mode="after")
    def validate_periodicidad(self):
        if self.tipo_evaluacion == TipoEvaluacionExamen.PERIODICO:
            if self.periodicidad_meses is None:
                raise ValueError("periodicidad_meses es obligatoria para tipo_evaluacion='periodico'")
        else:
            if self.periodicidad_meses is not None:
                raise ValueError("periodicidad_meses debe ser null si tipo_evaluacion no es 'periodico'")
        return self

    @field_validator("periodicidad_meses")
    @classmethod
    def validate_periodicidad_values(cls, v):
        if v is None:
            return v
        if v not in (6, 12, 24, 36):
            raise ValueError("periodicidad_meses debe estar en (6, 12, 24, 36)")
        return v


class ProfesiogramaExamenCreate(ProfesiogramaExamenBase):
    pass


class ProfesiogramaExamen(ProfesiogramaExamenBase):
    profesiograma_id: int

    class Config:
        from_attributes = True


class ProfesiogramaBase(BaseModel):
    version: str = Field("1.0", max_length=10)
    estado: ProfesiogramaEstado = ProfesiogramaEstado.ACTIVO

    empresa: Optional[str] = Field(None, max_length=150)
    departamento: Optional[str] = Field(None, max_length=100)
    codigo_cargo: Optional[str] = Field(None, max_length=50)
    numero_trabajadores_expuestos: Optional[int] = None
    fecha_elaboracion: Optional[date] = None
    validado_por: Optional[str] = Field(None, max_length=150)
    proxima_revision: Optional[date] = None

    elaborado_por: Optional[str] = Field(None, max_length=150)
    revisado_por: Optional[str] = Field(None, max_length=150)
    aprobado_por: Optional[str] = Field(None, max_length=150)
    fecha_aprobacion: Optional[date] = None
    vigencia_meses: Optional[int] = None

    posicion_predominante: str = Field(..., max_length=50)
    descripcion_actividades: str

    periodicidad_emo_meses: int
    justificacion_periodicidad_emo: Optional[str] = None
    fecha_ultima_revision: date

    nivel_riesgo_cargo: NivelRiesgoCargo

    @field_validator("periodicidad_emo_meses")
    @classmethod
    def validate_periodicidad_emo_values(cls, v):
        if v not in (6, 12, 24, 36):
            raise ValueError("periodicidad_emo_meses debe estar en (6, 12, 24, 36)")
        return v

    @model_validator(mode="after")
    def validate_justificacion_periodicidad_emo(self):
        if self.periodicidad_emo_meses > 12:
            if self.justificacion_periodicidad_emo and len(self.justificacion_periodicidad_emo.strip()) < MIN_JUSTIFICACION_PERIODICIDAD_EMO_LEN:
                raise ValueError(
                    f"justificacion_periodicidad_emo debe tener mínimo {MIN_JUSTIFICACION_PERIODICIDAD_EMO_LEN} caracteres si periodicidad_emo_meses > 12"
                )
        return self


class ProfesiogramaCreate(ProfesiogramaBase):
    factores: List[ProfesiogramaFactorCreate] = Field(default_factory=list)
    examenes: List[ProfesiogramaExamenCreate] = Field(default_factory=list)
    criterios_exclusion_ids: List[int] = Field(default_factory=list)
    inmunizaciones: List[ProfesiogramaInmunizacionCreate] = Field(default_factory=list)


class ProfesiogramaUpdate(BaseModel):
    version: Optional[str] = Field(None, max_length=10)
    estado: Optional[ProfesiogramaEstado] = None
    empresa: Optional[str] = Field(None, max_length=150)
    departamento: Optional[str] = Field(None, max_length=100)
    codigo_cargo: Optional[str] = Field(None, max_length=50)
    numero_trabajadores_expuestos: Optional[int] = None
    fecha_elaboracion: Optional[date] = None
    validado_por: Optional[str] = Field(None, max_length=150)
    proxima_revision: Optional[date] = None
    elaborado_por: Optional[str] = Field(None, max_length=150)
    revisado_por: Optional[str] = Field(None, max_length=150)
    aprobado_por: Optional[str] = Field(None, max_length=150)
    fecha_aprobacion: Optional[date] = None
    vigencia_meses: Optional[int] = None
    posicion_predominante: Optional[str] = Field(None, max_length=50)
    descripcion_actividades: Optional[str] = None
    periodicidad_emo_meses: Optional[int] = None
    justificacion_periodicidad_emo: Optional[str] = None
    fecha_ultima_revision: Optional[date] = None
    nivel_riesgo_cargo: Optional[NivelRiesgoCargo] = None
    factores: Optional[List[ProfesiogramaFactorCreate]] = None
    examenes: Optional[List[ProfesiogramaExamenCreate]] = None
    criterios_exclusion_ids: Optional[List[int]] = None
    inmunizaciones: Optional[List[ProfesiogramaInmunizacionCreate]] = None

    @model_validator(mode="after")
    def validate_justificacion_periodicidad_emo(self):
        if self.periodicidad_emo_meses is not None:
            if self.periodicidad_emo_meses not in (6, 12, 24, 36):
                raise ValueError("periodicidad_emo_meses debe estar en (6, 12, 24, 36)")
            if self.periodicidad_emo_meses > 12:
                if self.justificacion_periodicidad_emo and len(self.justificacion_periodicidad_emo.strip()) < MIN_JUSTIFICACION_PERIODICIDAD_EMO_LEN:
                    raise ValueError(
                        f"justificacion_periodicidad_emo debe tener mínimo {MIN_JUSTIFICACION_PERIODICIDAD_EMO_LEN} caracteres si periodicidad_emo_meses > 12"
                    )
        return self


class Profesiograma(ProfesiogramaBase):
    id: int
    cargo_id: int
    creado_por: int
    fecha_creacion: datetime
    modificado_por: Optional[int] = None
    fecha_modificacion: Optional[datetime] = None

    factores: List[ProfesiogramaFactor] = Field(default_factory=list)
    profesiograma_factores: List[ProfesiogramaFactor] = Field(default_factory=list)
    examenes: List[ProfesiogramaExamen] = Field(default_factory=list)
    criterios_exclusion_ids: List[int] = Field(default_factory=list)
    inmunizaciones: List[ProfesiogramaInmunizacion] = Field(default_factory=list)

    class Config:
        from_attributes = True


class ProfesiogramaEmoSuggestion(BaseModel):
    cargo_id: int
    periodicidad_sugerida: int
    periodicidad_borrador: int
    numero_trabajadores_expuestos: int
    menores_21: int
    antiguedad_menor_2_anios: int
    sin_fecha_ingreso: int
    justificacion_periodicidad_emo_borrador: str


class ProfesiogramaEmoFactorInput(BaseModel):
    factor_riesgo_id: int
    nd: Optional[int] = None
    ne: Optional[int] = None
    nc: Optional[int] = None


class ProfesiogramaEmoJustificacionRequest(BaseModel):
    periodicidad_emo_meses: int
    formato: str = "breve"
    factores: List[ProfesiogramaEmoFactorInput] = Field(default_factory=list)

