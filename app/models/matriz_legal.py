"""
Modelos para la Matriz Legal de Seguridad y Salud en el Trabajo.

Este módulo contiene los modelos para:
- MatrizLegalImportacion: Registro de importaciones de archivos Excel
- MatrizLegalNorma: Normas legales importadas del archivo ARL
- MatrizLegalNormaHistorial: Historial de versiones de normas
- MatrizLegalCumplimiento: Seguimiento del cumplimiento por empresa
- MatrizLegalCumplimientoHistorial: Auditoría de cambios en cumplimiento
"""

from datetime import date, datetime
from enum import Enum
from sqlalchemy import (
    Boolean, Column, Date, DateTime,
    ForeignKey, Integer, String, Text, UniqueConstraint
)
from sqlalchemy.orm import relationship

from app.database import Base


# ===================== ENUMERACIONES =====================

class AmbitoAplicacion(str, Enum):
    """Ámbito de aplicación de la norma."""
    NACIONAL = "nacional"
    DEPARTAMENTAL = "departamental"
    MUNICIPAL = "municipal"
    INTERNACIONAL = "internacional"


class EstadoNorma(str, Enum):
    """Estado de vigencia de la norma."""
    VIGENTE = "vigente"
    DEROGADA = "derogada"
    MODIFICADA = "modificada"


class EstadoCumplimiento(str, Enum):
    """Estado de cumplimiento de una norma por parte de la empresa."""
    PENDIENTE = "pendiente"
    CUMPLE = "cumple"
    NO_CUMPLE = "no_cumple"
    NO_APLICA = "no_aplica"
    EN_PROCESO = "en_proceso"


class EstadoImportacion(str, Enum):
    """Estado de una importación de archivo Excel."""
    EN_PROCESO = "en_proceso"
    COMPLETADA = "completada"
    FALLIDA = "fallida"
    PARCIAL = "parcial"


# ===================== MODELOS =====================

class MatrizLegalImportacion(Base):
    """
    Registro de importaciones de archivos Excel de la ARL.
    Guarda estadísticas y log de cada importación.
    """
    __tablename__ = "matriz_legal_importaciones"

    id = Column(Integer, primary_key=True, index=True)

    nombre_archivo = Column(String(255), nullable=False)
    fecha_importacion = Column(DateTime, default=datetime.utcnow, nullable=False)
    estado = Column(
        String(20),
        default=EstadoImportacion.EN_PROCESO.value,
        nullable=False
    )

    # Estadísticas de la importación
    total_filas = Column(Integer, default=0)
    normas_nuevas = Column(Integer, default=0)
    normas_actualizadas = Column(Integer, default=0)
    normas_sin_cambios = Column(Integer, default=0)
    errores = Column(Integer, default=0)

    # Detalles de errores
    log_errores = Column(Text, nullable=True)

    creado_por = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relaciones
    usuario = relationship("User")
    normas = relationship("MatrizLegalNorma", back_populates="importacion")

    def __repr__(self):
        return f"<MatrizLegalImportacion(id={self.id}, archivo='{self.nombre_archivo}', estado='{self.estado}')>"


class MatrizLegalNorma(Base):
    """
    Normas legales importadas del archivo Excel de la ARL.
    Contiene toda la información de la norma y campos de aplicabilidad
    para filtrado automático.
    """
    __tablename__ = "matriz_legal_normas"
    __table_args__ = (
        UniqueConstraint(
            'tipo_norma', 'numero_norma', 'articulo',
            name='uq_matriz_legal_norma_tipo_numero_articulo'
        ),
    )

    id = Column(Integer, primary_key=True, index=True)

    # Datos del Excel ARL
    ambito_aplicacion = Column(
        String(20),
        nullable=False,
        index=True,
        default=AmbitoAplicacion.NACIONAL.value
    )

    # Sector económico (puede ser "TODOS LOS SECTORES" o uno específico)
    sector_economico_id = Column(Integer, ForeignKey("sectores_economicos.id"), nullable=True)
    sector_economico_texto = Column(String(200))  # Texto original del Excel

    clasificacion_norma = Column(String(150), nullable=False, index=True)
    tema_general = Column(String(200), nullable=False, index=True)
    subtema_riesgo_especifico = Column(String(300), nullable=True)

    # Datos de la legislación
    anio = Column(Integer, nullable=False, index=True)
    tipo_norma = Column(String(100), nullable=False, index=True)  # Ley, Decreto, Resolución, etc.
    numero_norma = Column(String(50), nullable=False, index=True)
    fecha_expedicion = Column(Date, nullable=True)
    expedida_por = Column(String(200), nullable=True)
    descripcion_norma = Column(Text, nullable=True)
    articulo = Column(String(100), nullable=True, index=True)  # Puede ser "Todo", "Art. 1", etc.
    estado = Column(
        String(20),
        default=EstadoNorma.VIGENTE.value,
        nullable=False
    )
    info_adicional = Column(Text, nullable=True)  # Campo "Info" del Excel
    descripcion_articulo_exigencias = Column(Text, nullable=True)  # "Descripción del artículo que aplica"

    # Campos para características específicas (filtrado automático)
    # Si aplica_X es True, la norma SOLO aplica a empresas que tienen esa característica
    aplica_trabajadores_independientes = Column(Boolean, default=False, nullable=False)
    aplica_teletrabajo = Column(Boolean, default=False, nullable=False)
    aplica_trabajo_alturas = Column(Boolean, default=False, nullable=False)
    aplica_espacios_confinados = Column(Boolean, default=False, nullable=False)
    aplica_trabajo_caliente = Column(Boolean, default=False, nullable=False)
    aplica_sustancias_quimicas = Column(Boolean, default=False, nullable=False)
    aplica_radiaciones = Column(Boolean, default=False, nullable=False)
    aplica_trabajo_nocturno = Column(Boolean, default=False, nullable=False)
    aplica_menores_edad = Column(Boolean, default=False, nullable=False)
    aplica_mujeres_embarazadas = Column(Boolean, default=False, nullable=False)
    aplica_conductores = Column(Boolean, default=False, nullable=False)
    aplica_manipulacion_alimentos = Column(Boolean, default=False, nullable=False)
    aplica_maquinaria_pesada = Column(Boolean, default=False, nullable=False)
    aplica_riesgo_electrico = Column(Boolean, default=False, nullable=False)
    aplica_riesgo_biologico = Column(Boolean, default=False, nullable=False)
    aplica_trabajo_excavaciones = Column(Boolean, default=False, nullable=False)
    aplica_trabajo_administrativo = Column(Boolean, default=False, nullable=False)

    # Si aplica_general es True, la norma aplica a TODAS las empresas
    # independientemente de sus características específicas
    aplica_general = Column(Boolean, default=True, nullable=False)

    # Versionado y trazabilidad
    version = Column(Integer, default=1, nullable=False)
    importacion_id = Column(Integer, ForeignKey("matriz_legal_importaciones.id"), nullable=True)
    hash_contenido = Column(String(64), nullable=True)  # SHA256 para detectar cambios

    activo = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    sector_economico = relationship("SectorEconomico", back_populates="normas")
    cumplimientos = relationship(
        "MatrizLegalCumplimiento",
        back_populates="norma",
        cascade="all, delete-orphan"
    )
    importacion = relationship("MatrizLegalImportacion", back_populates="normas")
    historial = relationship(
        "MatrizLegalNormaHistorial",
        back_populates="norma",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<MatrizLegalNorma(id={self.id}, tipo='{self.tipo_norma}', numero='{self.numero_norma}')>"

    @property
    def identificador_completo(self) -> str:
        """Retorna identificador legible de la norma (ej: 'Resolución 0312 de 2019')."""
        return f"{self.tipo_norma} {self.numero_norma} de {self.anio}"

    def tiene_caracteristicas_especificas(self) -> bool:
        """Verifica si la norma tiene alguna característica específica activada."""
        campos = [
            self.aplica_trabajadores_independientes,
            self.aplica_teletrabajo,
            self.aplica_trabajo_alturas,
            self.aplica_espacios_confinados,
            self.aplica_trabajo_caliente,
            self.aplica_sustancias_quimicas,
            self.aplica_radiaciones,
            self.aplica_trabajo_nocturno,
            self.aplica_menores_edad,
            self.aplica_mujeres_embarazadas,
            self.aplica_conductores,
            self.aplica_manipulacion_alimentos,
            self.aplica_maquinaria_pesada,
            self.aplica_riesgo_electrico,
            self.aplica_riesgo_biologico,
            self.aplica_trabajo_excavaciones,
            self.aplica_trabajo_administrativo,
        ]
        return any(campos)


class MatrizLegalNormaHistorial(Base):
    """
    Historial de versiones de normas.
    Se crea un registro cada vez que una norma se actualiza en una importación.
    """
    __tablename__ = "matriz_legal_normas_historial"

    id = Column(Integer, primary_key=True, index=True)
    norma_id = Column(Integer, ForeignKey("matriz_legal_normas.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False)

    # Snapshot de los datos en esa versión
    datos_json = Column(Text, nullable=False)  # JSON con todos los campos

    motivo_cambio = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    creado_por = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Relaciones
    norma = relationship("MatrizLegalNorma", back_populates="historial")
    usuario = relationship("User")

    def __repr__(self):
        return f"<MatrizLegalNormaHistorial(norma_id={self.norma_id}, version={self.version})>"


class MatrizLegalCumplimiento(Base):
    """
    Seguimiento del cumplimiento de normas por empresa.
    Cada empresa tiene un registro de cumplimiento por cada norma que le aplica.
    """
    __tablename__ = "matriz_legal_cumplimientos"
    __table_args__ = (
        UniqueConstraint('empresa_id', 'norma_id', name='uq_cumplimiento_empresa_norma'),
    )

    id = Column(Integer, primary_key=True, index=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    norma_id = Column(Integer, ForeignKey("matriz_legal_normas.id"), nullable=False, index=True)

    # Evaluación del cumplimiento
    estado = Column(
        String(20),
        default=EstadoCumplimiento.PENDIENTE.value,
        nullable=False,
        index=True
    )
    evidencia_cumplimiento = Column(Text, nullable=True)
    observaciones = Column(Text, nullable=True)

    # Plan de acción (cuando no cumple o está en proceso)
    plan_accion = Column(Text, nullable=True)
    responsable = Column(String(150), nullable=True)
    fecha_compromiso = Column(Date, nullable=True)
    seguimiento = Column(Text, nullable=True)

    # Fechas de revisión
    fecha_ultima_evaluacion = Column(DateTime, nullable=True)
    fecha_proxima_revision = Column(Date, nullable=True)
    evaluado_por = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Si la norma aplica o no a esta empresa específica
    # El usuario puede marcar una norma como "no aplica" con justificación
    aplica_empresa = Column(Boolean, default=True, nullable=False)
    justificacion_no_aplica = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    empresa = relationship("Empresa", back_populates="cumplimientos")
    norma = relationship("MatrizLegalNorma", back_populates="cumplimientos")
    evaluador = relationship("User", foreign_keys=[evaluado_por])
    historial = relationship(
        "MatrizLegalCumplimientoHistorial",
        back_populates="cumplimiento",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<MatrizLegalCumplimiento(empresa_id={self.empresa_id}, norma_id={self.norma_id}, estado='{self.estado}')>"

    @property
    def tiene_plan_accion(self) -> bool:
        """Verifica si tiene un plan de acción definido."""
        return bool(self.plan_accion and self.plan_accion.strip())

    @property
    def esta_vencido(self) -> bool:
        """Verifica si el plan de acción está vencido."""
        if self.fecha_compromiso and self.estado in [EstadoCumplimiento.NO_CUMPLE, EstadoCumplimiento.EN_PROCESO]:
            return self.fecha_compromiso < date.today()
        return False


class MatrizLegalCumplimientoHistorial(Base):
    """
    Historial de cambios en evaluaciones de cumplimiento.
    Permite auditar quién y cuándo evaluó cada norma.
    """
    __tablename__ = "matriz_legal_cumplimientos_historial"

    id = Column(Integer, primary_key=True, index=True)
    cumplimiento_id = Column(
        Integer,
        ForeignKey("matriz_legal_cumplimientos.id"),
        nullable=False,
        index=True
    )

    estado_anterior = Column(String(50), nullable=True)
    estado_nuevo = Column(String(50), nullable=False)
    observaciones = Column(Text, nullable=True)

    # Campos adicionales para auditoría completa
    evidencia_anterior = Column(Text, nullable=True)
    evidencia_nueva = Column(Text, nullable=True)
    plan_accion_anterior = Column(Text, nullable=True)
    plan_accion_nuevo = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    creado_por = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Relaciones
    cumplimiento = relationship("MatrizLegalCumplimiento", back_populates="historial")
    usuario = relationship("User")

    def __repr__(self):
        return f"<MatrizLegalCumplimientoHistorial(cumplimiento_id={self.cumplimiento_id}, cambio='{self.estado_anterior}'->{self.estado_nuevo}')>"
