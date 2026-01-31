"""
Modelo de Empresa para la Matriz Legal SST.
Configuración de empresas con características para filtrado de normas aplicables.
"""

from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class Empresa(Base):
    """
    Configuración de la empresa para filtrado de normas aplicables.
    Cada empresa tiene un sector económico y características que determinan
    qué normas legales le aplican.
    """
    __tablename__ = "empresas"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(200), nullable=False, unique=True, index=True)
    nit = Column(String(20), nullable=True, unique=True, index=True)
    razon_social = Column(String(300), nullable=True)
    direccion = Column(String(300), nullable=True)
    telefono = Column(String(50), nullable=True)
    email = Column(String(150), nullable=True)

    # Sector económico principal
    sector_economico_id = Column(Integer, ForeignKey("sectores_economicos.id"), nullable=True)

    # Características de la empresa para filtrado automático de normas
    # Cada característica corresponde a un tipo de norma específica
    tiene_trabajadores_independientes = Column(Boolean, default=False, nullable=False)
    tiene_teletrabajo = Column(Boolean, default=False, nullable=False)
    tiene_trabajo_alturas = Column(Boolean, default=False, nullable=False)
    tiene_trabajo_espacios_confinados = Column(Boolean, default=False, nullable=False)
    tiene_trabajo_caliente = Column(Boolean, default=False, nullable=False)
    tiene_sustancias_quimicas = Column(Boolean, default=False, nullable=False)
    tiene_radiaciones = Column(Boolean, default=False, nullable=False)
    tiene_trabajo_nocturno = Column(Boolean, default=False, nullable=False)
    tiene_menores_edad = Column(Boolean, default=False, nullable=False)
    tiene_mujeres_embarazadas = Column(Boolean, default=False, nullable=False)
    tiene_conductores = Column(Boolean, default=False, nullable=False)
    tiene_manipulacion_alimentos = Column(Boolean, default=False, nullable=False)
    tiene_maquinaria_pesada = Column(Boolean, default=False, nullable=False)
    tiene_riesgo_electrico = Column(Boolean, default=False, nullable=False)
    tiene_riesgo_biologico = Column(Boolean, default=False, nullable=False)
    tiene_trabajo_excavaciones = Column(Boolean, default=False, nullable=False)
    tiene_trabajo_administrativo = Column(Boolean, default=False, nullable=False)

    # Metadatos
    activo = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    creado_por = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Relaciones
    sector_economico = relationship("SectorEconomico", back_populates="empresas")
    cumplimientos = relationship(
        "MatrizLegalCumplimiento",
        back_populates="empresa",
        cascade="all, delete-orphan"
    )
    creador = relationship("User", foreign_keys=[creado_por])

    def __repr__(self):
        return f"<Empresa(id={self.id}, nombre='{self.nombre}', nit='{self.nit}')>"

    def get_caracteristicas_activas(self) -> list:
        """Retorna lista de características activas de la empresa."""
        caracteristicas = []
        campos = [
            ('tiene_trabajadores_independientes', 'Trabajadores Independientes'),
            ('tiene_teletrabajo', 'Teletrabajo'),
            ('tiene_trabajo_alturas', 'Trabajo en Alturas'),
            ('tiene_trabajo_espacios_confinados', 'Espacios Confinados'),
            ('tiene_trabajo_caliente', 'Trabajo Caliente'),
            ('tiene_sustancias_quimicas', 'Sustancias Químicas'),
            ('tiene_radiaciones', 'Radiaciones'),
            ('tiene_trabajo_nocturno', 'Trabajo Nocturno'),
            ('tiene_menores_edad', 'Menores de Edad'),
            ('tiene_mujeres_embarazadas', 'Mujeres Embarazadas'),
            ('tiene_conductores', 'Conductores'),
            ('tiene_manipulacion_alimentos', 'Manipulación de Alimentos'),
            ('tiene_maquinaria_pesada', 'Maquinaria Pesada'),
            ('tiene_riesgo_electrico', 'Riesgo Eléctrico'),
            ('tiene_riesgo_biologico', 'Riesgo Biológico'),
            ('tiene_trabajo_excavaciones', 'Trabajo en Excavaciones'),
            ('tiene_trabajo_administrativo', 'Trabajo Administrativo'),
        ]
        for campo, nombre in campos:
            if getattr(self, campo, False):
                caracteristicas.append(nombre)
        return caracteristicas
