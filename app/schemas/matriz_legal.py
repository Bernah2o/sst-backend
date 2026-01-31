"""
Schemas Pydantic para Matriz Legal SST.

Incluye schemas para:
- Normas legales
- Cumplimiento por empresa
- Importaciones de Excel
- Dashboard y estadísticas
"""

from datetime import date, datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from app.models.matriz_legal import (
    AmbitoAplicacion, EstadoNorma, EstadoCumplimiento, EstadoImportacion
)


# ===================== NORMAS =====================

class MatrizLegalNormaAplicabilidad(BaseModel):
    """Campos de aplicabilidad de una norma."""
    aplica_trabajadores_independientes: bool = False
    aplica_teletrabajo: bool = False
    aplica_trabajo_alturas: bool = False
    aplica_espacios_confinados: bool = False
    aplica_trabajo_caliente: bool = False
    aplica_sustancias_quimicas: bool = False
    aplica_radiaciones: bool = False
    aplica_trabajo_nocturno: bool = False
    aplica_menores_edad: bool = False
    aplica_mujeres_embarazadas: bool = False
    aplica_conductores: bool = False
    aplica_manipulacion_alimentos: bool = False
    aplica_maquinaria_pesada: bool = False
    aplica_riesgo_electrico: bool = False
    aplica_riesgo_biologico: bool = False
    aplica_trabajo_excavaciones: bool = False
    aplica_trabajo_administrativo: bool = False
    aplica_general: bool = True


class MatrizLegalNormaBase(BaseModel):
    """Campos base para norma legal."""
    ambito_aplicacion: AmbitoAplicacion = AmbitoAplicacion.NACIONAL
    sector_economico_id: Optional[int] = None
    sector_economico_texto: Optional[str] = Field(None, max_length=200)
    clasificacion_norma: str = Field(..., min_length=1, max_length=150)
    tema_general: str = Field(..., min_length=1, max_length=200)
    subtema_riesgo_especifico: Optional[str] = Field(None, max_length=300)
    anio: int = Field(..., ge=1900, le=2100)
    tipo_norma: str = Field(..., min_length=1, max_length=100, description="Ley, Decreto, Resolución, etc.")
    numero_norma: str = Field(..., min_length=1, max_length=50)
    fecha_expedicion: Optional[date] = None
    expedida_por: Optional[str] = Field(None, max_length=200)
    descripcion_norma: Optional[str] = None
    articulo: Optional[str] = Field(None, max_length=100)
    estado: EstadoNorma = EstadoNorma.VIGENTE
    info_adicional: Optional[str] = None
    descripcion_articulo_exigencias: Optional[str] = None


class MatrizLegalNormaCreate(MatrizLegalNormaBase, MatrizLegalNormaAplicabilidad):
    """Schema para crear una norma manualmente."""
    pass


class MatrizLegalNormaUpdate(BaseModel):
    """Schema para actualizar una norma."""
    ambito_aplicacion: Optional[AmbitoAplicacion] = None
    clasificacion_norma: Optional[str] = Field(None, max_length=150)
    tema_general: Optional[str] = Field(None, max_length=200)
    subtema_riesgo_especifico: Optional[str] = None
    estado: Optional[EstadoNorma] = None
    descripcion_articulo_exigencias: Optional[str] = None
    # Campos de aplicabilidad editables
    aplica_trabajadores_independientes: Optional[bool] = None
    aplica_teletrabajo: Optional[bool] = None
    aplica_trabajo_alturas: Optional[bool] = None
    aplica_espacios_confinados: Optional[bool] = None
    aplica_trabajo_caliente: Optional[bool] = None
    aplica_sustancias_quimicas: Optional[bool] = None
    aplica_radiaciones: Optional[bool] = None
    aplica_trabajo_nocturno: Optional[bool] = None
    aplica_menores_edad: Optional[bool] = None
    aplica_mujeres_embarazadas: Optional[bool] = None
    aplica_conductores: Optional[bool] = None
    aplica_manipulacion_alimentos: Optional[bool] = None
    aplica_maquinaria_pesada: Optional[bool] = None
    aplica_riesgo_electrico: Optional[bool] = None
    aplica_riesgo_biologico: Optional[bool] = None
    aplica_trabajo_excavaciones: Optional[bool] = None
    aplica_trabajo_administrativo: Optional[bool] = None
    aplica_general: Optional[bool] = None
    activo: Optional[bool] = None


class MatrizLegalNorma(MatrizLegalNormaBase, MatrizLegalNormaAplicabilidad):
    """Schema de respuesta para norma legal."""
    id: int
    version: int
    activo: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    # Campos derivados
    sector_economico_nombre: Optional[str] = None
    identificador_completo: Optional[str] = None

    class Config:
        from_attributes = True


class MatrizLegalNormaSimple(BaseModel):
    """Vista simplificada para listados."""
    id: int
    tipo_norma: str
    numero_norma: str
    anio: int
    articulo: Optional[str] = None
    clasificacion_norma: str
    tema_general: str
    estado: EstadoNorma

    class Config:
        from_attributes = True


class MatrizLegalNormaConCumplimiento(MatrizLegalNorma):
    """Norma con estado de cumplimiento para una empresa específica."""
    cumplimiento_id: Optional[int] = None
    estado_cumplimiento: Optional[EstadoCumplimiento] = None
    aplica_empresa: bool = True
    evidencia_cumplimiento: Optional[str] = None
    observaciones: Optional[str] = None
    plan_accion: Optional[str] = None
    responsable: Optional[str] = None
    fecha_compromiso: Optional[date] = None
    fecha_ultima_evaluacion: Optional[datetime] = None

    class Config:
        from_attributes = True


# ===================== CUMPLIMIENTO =====================

class MatrizLegalCumplimientoBase(BaseModel):
    """Campos base para cumplimiento."""
    estado: EstadoCumplimiento = EstadoCumplimiento.PENDIENTE
    evidencia_cumplimiento: Optional[str] = None
    observaciones: Optional[str] = None
    plan_accion: Optional[str] = None
    responsable: Optional[str] = Field(None, max_length=150)
    fecha_compromiso: Optional[date] = None
    seguimiento: Optional[str] = None
    aplica_empresa: bool = True
    justificacion_no_aplica: Optional[str] = None
    fecha_proxima_revision: Optional[date] = None


class MatrizLegalCumplimientoCreate(MatrizLegalCumplimientoBase):
    """Schema para crear un cumplimiento."""
    empresa_id: int
    norma_id: int


class MatrizLegalCumplimientoUpdate(BaseModel):
    """Schema para actualizar un cumplimiento."""
    estado: Optional[EstadoCumplimiento] = None
    evidencia_cumplimiento: Optional[str] = None
    observaciones: Optional[str] = None
    plan_accion: Optional[str] = None
    responsable: Optional[str] = Field(None, max_length=150)
    fecha_compromiso: Optional[date] = None
    seguimiento: Optional[str] = None
    aplica_empresa: Optional[bool] = None
    justificacion_no_aplica: Optional[str] = None
    fecha_proxima_revision: Optional[date] = None


class MatrizLegalCumplimiento(MatrizLegalCumplimientoBase):
    """Schema de respuesta para cumplimiento."""
    id: int
    empresa_id: int
    norma_id: int
    fecha_ultima_evaluacion: Optional[datetime] = None
    evaluado_por: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    # Campos derivados
    tiene_plan_accion: bool = False
    esta_vencido: bool = False

    class Config:
        from_attributes = True


class MatrizLegalCumplimientoBulkUpdate(BaseModel):
    """Para actualizar múltiples cumplimientos a la vez."""
    cumplimiento_ids: List[int] = Field(..., min_length=1)
    estado: EstadoCumplimiento


class MatrizLegalCumplimientoHistorial(BaseModel):
    """Historial de cambios de un cumplimiento."""
    id: int
    cumplimiento_id: int
    estado_anterior: Optional[str] = None
    estado_nuevo: str
    observaciones: Optional[str] = None
    created_at: datetime
    creado_por: int
    usuario_nombre: Optional[str] = None

    class Config:
        from_attributes = True


# ===================== IMPORTACIÓN =====================

class MatrizLegalImportacionPreview(BaseModel):
    """Preview antes de confirmar importación."""
    total_filas: int
    normas_nuevas_preview: int
    normas_existentes_preview: int
    errores_validacion: List[Dict] = []
    columnas_detectadas: List[str] = []
    columnas_mapeadas: Dict[str, Optional[str]] = {}  # Original -> Mapeado (o None si no mapea)
    muestra_datos: List[Dict] = []


class MatrizLegalImportacionResult(BaseModel):
    """Resultado de una importación."""
    id: int
    nombre_archivo: str
    fecha_importacion: datetime
    estado: EstadoImportacion
    total_filas: int
    normas_nuevas: int
    normas_actualizadas: int
    normas_sin_cambios: int
    errores: int
    log_errores: Optional[str] = None
    creado_por: int

    class Config:
        from_attributes = True


class MatrizLegalImportacionSimple(BaseModel):
    """Vista simplificada de importación para listados."""
    id: int
    nombre_archivo: str
    fecha_importacion: datetime
    estado: EstadoImportacion
    total_filas: int
    normas_nuevas: int
    errores: int

    class Config:
        from_attributes = True


# ===================== DASHBOARD Y ESTADÍSTICAS =====================

class MatrizLegalEstadisticasPorEstado(BaseModel):
    """Conteo de normas por estado de cumplimiento."""
    cumple: int = 0
    no_cumple: int = 0
    pendiente: int = 0
    no_aplica: int = 0
    en_proceso: int = 0


class MatrizLegalEstadisticas(BaseModel):
    """Estadísticas de cumplimiento para una empresa."""
    empresa_id: int
    empresa_nombre: str
    total_normas_aplicables: int
    por_estado: MatrizLegalEstadisticasPorEstado
    porcentaje_cumplimiento: float = Field(..., ge=0, le=100)
    normas_con_plan_accion: int
    normas_vencidas: int  # Con fecha_compromiso pasada y no cumple


class MatrizLegalDashboard(BaseModel):
    """Dashboard completo de matriz legal para una empresa."""
    estadisticas: MatrizLegalEstadisticas
    ultimas_evaluaciones: List[Dict] = []
    normas_criticas: List[MatrizLegalNormaConCumplimiento] = []  # No cumple sin plan
    proximas_revisiones: List[Dict] = []
    importaciones_recientes: List[MatrizLegalImportacionSimple] = []


class MatrizLegalResumenGlobal(BaseModel):
    """Resumen global de todas las empresas."""
    total_empresas: int
    total_normas: int
    empresas_con_incumplimientos: int
    promedio_cumplimiento: float


# ===================== PAGINACIÓN =====================

class PaginatedMatrizLegalNormas(BaseModel):
    """Respuesta paginada de normas."""
    items: List[MatrizLegalNorma]
    total: int
    page: int
    size: int
    pages: int
    has_next: bool
    has_prev: bool


class PaginatedMatrizLegalNormasConCumplimiento(BaseModel):
    """Respuesta paginada de normas con cumplimiento."""
    items: List[MatrizLegalNormaConCumplimiento]
    total: int
    page: int
    size: int
    pages: int
    has_next: bool
    has_prev: bool


class PaginatedImportaciones(BaseModel):
    """Respuesta paginada de importaciones."""
    items: List[MatrizLegalImportacionResult]
    total: int
    page: int
    size: int
    pages: int
    has_next: bool
    has_prev: bool
