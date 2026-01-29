from datetime import date, datetime
from enum import Enum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class ProfesiogramaEstado(str, Enum):
    ACTIVO = "activo"
    INACTIVO = "inactivo"
    BORRADOR = "borrador"


class NivelRiesgoCargo(str, Enum):
    BAJO = "bajo"
    MEDIO = "medio"
    ALTO = "alto"
    MUY_ALTO = "muy_alto"


class NivelExposicion(str, Enum):
    BAJO = "bajo"
    MEDIO = "medio"
    ALTO = "alto"
    MUY_ALTO = "muy_alto"


class TipoEvaluacionExamen(str, Enum):
    INGRESO = "ingreso"
    PERIODICO = "periodico"
    RETIRO = "retiro"
    CAMBIO_CARGO = "cambio_cargo"
    POST_INCAPACIDAD = "post_incapacidad"
    REINCORPORACION = "reincorporacion"


profesiograma_criterio_exclusion = Table(
    "profesiograma_criterio_exclusion",
    Base.metadata,
    Column("profesiograma_id", Integer, ForeignKey("profesiogramas.id"), primary_key=True),
    Column("criterio_exclusion_id", Integer, ForeignKey("criterios_exclusion.id"), primary_key=True),
)


class ProfesiogramaFactor(Base):
    __tablename__ = "profesiograma_factores"

    profesiograma_id = Column(Integer, ForeignKey("profesiogramas.id"), primary_key=True)
    factor_riesgo_id = Column(Integer, ForeignKey("factores_riesgo.id"), primary_key=True)

    proceso = Column(String(100))
    actividad = Column(String(150))
    tarea = Column(String(150))
    rutinario = Column(Boolean)

    descripcion_peligro = Column(Text)
    efectos_posibles = Column(Text)
    zona_lugar = Column(String(150))
    tipo_peligro = Column(String(80))
    clasificacion_peligro = Column(String(120))
    controles_existentes = Column(Text)
    fuente = Column(Text)
    medio = Column(Text)
    individuo = Column(Text)
    peor_consecuencia = Column(Text)
    requisito_legal = Column(Text)

    nivel_exposicion = Column(
        SQLEnum(
            NivelExposicion,
            values_callable=lambda x: [e.value for e in x],
            name="nivelexposicion",
        ),
        nullable=False,
    )
    tiempo_exposicion_horas = Column(Numeric(4, 2), nullable=False)
    valor_medido = Column(String(255))  # Puede ser numérico o texto (ej: "No aplica", "Contacto directo con agua")
    valor_limite_permisible = Column(String(255))  # Puede ser numérico o texto (ej: "No aplica (evaluación cualitativa)")
    unidad_medida = Column(String(50))

    nd = Column(Integer)
    ne = Column(Integer)
    nc = Column(Integer)

    eliminacion = Column(Text)
    sustitucion = Column(Text)
    controles_ingenieria = Column(Text)
    controles_administrativos = Column(Text)
    senalizacion = Column(Text)
    epp_requerido = Column(Text)

    fecha_registro = Column(DateTime, default=datetime.utcnow, nullable=False)
    registrado_por = Column(Integer, ForeignKey("users.id"), nullable=False)

    profesiograma = relationship("Profesiograma", back_populates="profesiograma_factores")
    factor_riesgo = relationship("FactorRiesgo")
    usuario_registro = relationship("User", foreign_keys=[registrado_por])
    controles_esiae = relationship(
        "ProfesiogramaControlESIAE",
        back_populates="profesiograma_factor",
        cascade="all, delete-orphan",
    )
    intervenciones = relationship(
        "ProfesiogramaIntervencion",
        back_populates="profesiograma_factor",
        cascade="all, delete-orphan",
    )

    @property
    def np(self):
        from app.services.gtc45 import compute_np

        return compute_np(self.nd, self.ne)

    @property
    def nr(self):
        from app.services.gtc45 import compute_nr

        return compute_nr(self.nd, self.ne, self.nc)

    @property
    def nivel_intervencion(self):
        from app.services.gtc45 import classify_accion_riesgo

        accion = classify_accion_riesgo(self.nr)
        if accion == "Intervención inmediata":
            return "Intervención inmediata requerida"
        return accion

    @property
    def aceptabilidad(self):
        from app.services.gtc45 import classify_aceptabilidad_txt

        return classify_aceptabilidad_txt(self.nr)

    @property
    def interpretacion_np(self):
        from app.services.gtc45 import classify_interpretacion_np

        return classify_interpretacion_np(self.np)

    @property
    def nivel_riesgo(self):
        from app.services.gtc45 import classify_nivel_riesgo

        return classify_nivel_riesgo(self.nr)

    @property
    def color_riesgo(self):
        from app.services.gtc45 import classify_color_riesgo

        return classify_color_riesgo(self.nr)

    @property
    def accion_riesgo(self):
        from app.services.gtc45 import classify_accion_riesgo

        return classify_accion_riesgo(self.nr)

    def __repr__(self):
        return (
            f"<ProfesiogramaFactor(profesiograma_id={self.profesiograma_id}, factor_riesgo_id={self.factor_riesgo_id}, nivel_exposicion='{self.nivel_exposicion}')>"
        )


class ProfesiogramaControlESIAE(Base):
    __tablename__ = "profesiograma_controles_esiae"

    id = Column(Integer, primary_key=True, index=True)
    profesiograma_id = Column(Integer, nullable=False)
    factor_riesgo_id = Column(Integer, nullable=False)

    nivel = Column(String(10), nullable=False)
    medida = Column(String(150))
    descripcion = Column(Text)
    estado_actual = Column(String(50))
    meta = Column(String(150))

    __table_args__ = (
        ForeignKeyConstraint(
            ["profesiograma_id", "factor_riesgo_id"],
            ["profesiograma_factores.profesiograma_id", "profesiograma_factores.factor_riesgo_id"],
            ondelete="CASCADE",
        ),
    )

    profesiograma_factor = relationship(
        "ProfesiogramaFactor",
        back_populates="controles_esiae",
    )


class ProfesiogramaIntervencion(Base):
    __tablename__ = "profesiograma_intervenciones"

    id = Column(Integer, primary_key=True, index=True)
    profesiograma_id = Column(Integer, nullable=False)
    factor_riesgo_id = Column(Integer, nullable=False)

    tipo_control = Column(String(20), nullable=False)
    descripcion = Column(Text)
    responsable = Column(String(100))
    plazo = Column(String(60))

    __table_args__ = (
        ForeignKeyConstraint(
            ["profesiograma_id", "factor_riesgo_id"],
            ["profesiograma_factores.profesiograma_id", "profesiograma_factores.factor_riesgo_id"],
            ondelete="CASCADE",
        ),
    )

    profesiograma_factor = relationship(
        "ProfesiogramaFactor",
        back_populates="intervenciones",
    )


class Profesiograma(Base):
    __tablename__ = "profesiogramas"
    __table_args__ = (
        UniqueConstraint("cargo_id", "version", name="uq_profesiogramas_cargo_id_version"),
        CheckConstraint("periodicidad_emo_meses IN (6, 12, 24, 36)", name="ck_profesiogramas_periodicidad"),
        CheckConstraint(
            "periodicidad_emo_meses <= 12 OR justificacion_periodicidad_emo IS NOT NULL",
            name="ck_profesiogramas_justificacion_periodicidad",
        ),
        CheckConstraint(
            "periodicidad_emo_meses <= 12 OR char_length(trim(justificacion_periodicidad_emo)) >= 50",
            name="ck_profesiogramas_justificacion_periodicidad_minlen",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    cargo_id = Column(Integer, ForeignKey("cargos.id"), nullable=False, index=True)
    version = Column(String(10), default="1.0", nullable=False)
    estado = Column(
        SQLEnum(
            ProfesiogramaEstado,
            values_callable=lambda x: [e.value for e in x],
            name="profesiogramaestado",
        ),
        default=ProfesiogramaEstado.ACTIVO,
        nullable=False,
    )

    empresa = Column(String(150))
    departamento = Column(String(100))
    codigo_cargo = Column(String(50))
    numero_trabajadores_expuestos = Column(Integer)
    fecha_elaboracion = Column(Date)
    validado_por = Column(String(150))
    proxima_revision = Column(Date)

    elaborado_por = Column(String(150))
    revisado_por = Column(String(150))
    aprobado_por = Column(String(150))
    fecha_aprobacion = Column(Date)
    vigencia_meses = Column(Integer)

    posicion_predominante = Column(String(50), nullable=False)
    descripcion_actividades = Column(Text, nullable=False)

    periodicidad_emo_meses = Column(Integer, nullable=False)
    justificacion_periodicidad_emo = Column(Text)
    fecha_ultima_revision = Column(Date, default=date.today, nullable=False)

    nivel_riesgo_cargo = Column(
        SQLEnum(
            NivelRiesgoCargo,
            values_callable=lambda x: [e.value for e in x],
            name="nivelriesgocargo",
        ),
        nullable=False,
    )

    creado_por = Column(Integer, ForeignKey("users.id"), nullable=False)
    fecha_creacion = Column(DateTime, default=datetime.utcnow, nullable=False)
    modificado_por = Column(Integer, ForeignKey("users.id"), nullable=True)
    fecha_modificacion = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    cargo = relationship("Cargo", back_populates="profesiogramas")
    creador = relationship("User", foreign_keys=[creado_por])
    modificador = relationship("User", foreign_keys=[modificado_por])

    profesiograma_factores = relationship(
        "ProfesiogramaFactor",
        back_populates="profesiograma",
        cascade="all, delete-orphan",
        overlaps="factores_riesgo,profesiograma"
    )
    factores_riesgo = relationship(
        "FactorRiesgo",
        secondary="profesiograma_factores",
        back_populates="profesiogramas",
        overlaps="profesiograma_factores,factor_riesgo,profesiograma",
        viewonly=True
    )
    criterios_exclusion = relationship(
        "CriterioExclusion",
        secondary=profesiograma_criterio_exclusion,
        back_populates="profesiogramas",
    )

    examenes = relationship(
        "ProfesiogramaExamen",
        back_populates="profesiograma",
        cascade="all, delete-orphan",
        overlaps="tipos_examen,profesiogramas",
    )
    tipos_examen = relationship(
        "TipoExamen",
        secondary="profesiograma_examenes",
        back_populates="profesiogramas",
        overlaps="examenes,profesiograma_examenes,tipo_examen",
    )

    inmunizaciones = relationship(
        "ProfesiogramaInmunizacion",
        back_populates="profesiograma",
        cascade="all, delete-orphan",
    )
    programas_sve = relationship(
        "ProgramaSVE",
        back_populates="profesiograma",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Profesiograma(id={self.id}, cargo_id={self.cargo_id}, version='{self.version}', estado='{self.estado}')>"


class ProfesiogramaExamen(Base):
    __tablename__ = "profesiograma_examenes"
    __table_args__ = (
        CheckConstraint(
            "(tipo_evaluacion = 'periodico' AND periodicidad_meses IS NOT NULL) OR (tipo_evaluacion <> 'periodico' AND periodicidad_meses IS NULL)",
            name="ck_profesiograma_examenes_periodicidad_por_tipo",
        ),
        CheckConstraint(
            "periodicidad_meses IS NULL OR periodicidad_meses IN (6, 12, 24, 36)",
            name="ck_profesiograma_examenes_periodicidad_valida",
        ),
    )

    profesiograma_id = Column(Integer, ForeignKey("profesiogramas.id"), primary_key=True)
    tipo_examen_id = Column(Integer, ForeignKey("tipos_examen.id"), primary_key=True)
    tipo_evaluacion = Column(
        SQLEnum(
            TipoEvaluacionExamen,
            values_callable=lambda x: [e.value for e in x],
            name="tipoevaluacionexamen",
        ),
        primary_key=True,
    )

    periodicidad_meses = Column(Integer)
    justificacion_periodicidad = Column(Text)

    obligatorio = Column(Boolean, default=True, nullable=False)
    orden_realizacion = Column(Integer)
    normativa_base = Column(String(200))

    profesiograma = relationship(
        "Profesiograma",
        back_populates="examenes",
        overlaps="tipos_examen,profesiogramas",
    )
    tipo_examen = relationship(
        "TipoExamen",
        back_populates="profesiograma_examenes",
        overlaps="profesiogramas,tipos_examen",
    )

    def __repr__(self):
        return (
            f"<ProfesiogramaExamen(profesiograma_id={self.profesiograma_id}, tipo_examen_id={self.tipo_examen_id}, tipo_evaluacion='{self.tipo_evaluacion}', obligatorio={self.obligatorio})>"
        )
