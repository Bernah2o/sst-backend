from sqlalchemy import (
    Column, Integer, String, Text, Boolean,
    DateTime, Numeric, ForeignKey,
)
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base


class PresupuestoSST(Base):
    __tablename__ = "presupuesto_sst"

    id = Column(Integer, primary_key=True, index=True)
    año = Column(Integer, nullable=False)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=True)
    codigo = Column(String(50), default="AN-SST-03")
    version = Column(String(20), default="1")
    titulo = Column(String(300), default="CONSOLIDADO GENERAL PRESUPUESTO")
    encargado_sgsst = Column(String(200), nullable=True)
    aprobado_por = Column(String(200), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    categorias = relationship(
        "PresupuestoCategoria",
        back_populates="presupuesto",
        cascade="all, delete-orphan",
        order_by="PresupuestoCategoria.orden",
    )


class PresupuestoCategoria(Base):
    __tablename__ = "presupuesto_categoria"

    id = Column(Integer, primary_key=True, index=True)
    presupuesto_id = Column(
        Integer, ForeignKey("presupuesto_sst.id", ondelete="CASCADE"), nullable=False
    )
    # Stored as plain string to avoid Postgres ENUM conflicts
    categoria = Column(String(40), nullable=False)
    orden = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    presupuesto = relationship("PresupuestoSST", back_populates="categorias")
    items = relationship(
        "PresupuestoItem",
        back_populates="categoria",
        cascade="all, delete-orphan",
        order_by="PresupuestoItem.orden",
    )


class PresupuestoItem(Base):
    __tablename__ = "presupuesto_item"

    id = Column(Integer, primary_key=True, index=True)
    categoria_id = Column(
        Integer, ForeignKey("presupuesto_categoria.id", ondelete="CASCADE"), nullable=False
    )
    actividad = Column(Text, nullable=False)
    es_default = Column(Boolean, default=True)
    orden = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    categoria = relationship("PresupuestoCategoria", back_populates="items")
    montos_mensuales = relationship(
        "PresupuestoMensual",
        back_populates="item",
        cascade="all, delete-orphan",
        order_by="PresupuestoMensual.mes",
    )


class PresupuestoMensual(Base):
    __tablename__ = "presupuesto_mensual"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(
        Integer, ForeignKey("presupuesto_item.id", ondelete="CASCADE"), nullable=False
    )
    mes = Column(Integer, nullable=False)  # 1-12
    proyectado = Column(Numeric(14, 2), default=0)
    ejecutado = Column(Numeric(14, 2), default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    item = relationship("PresupuestoItem", back_populates="montos_mensuales")
