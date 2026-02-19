"""
API endpoints para Empresas.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from app.database import get_db
from app.dependencies import get_current_active_user, require_admin, require_supervisor_or_admin
from app.models.empresa import Empresa
from app.models.sector_economico import SectorEconomico
from app.models.matriz_legal import MatrizLegalCumplimiento, EstadoCumplimiento
from app.models.user import User
from app.schemas.empresa import (
    Empresa as EmpresaSchema,
    EmpresaCreate,
    EmpresaUpdate,
    EmpresaSimple,
    EmpresaResumen,
)
from app.schemas.common import MessageResponse
from app.services.matriz_legal_service import MatrizLegalService

router = APIRouter()


@router.get("/", response_model=List[EmpresaResumen])
def list_empresas(
    activo: Optional[bool] = Query(None, description="Filtrar por estado activo"),
    q: Optional[str] = Query(None, description="Buscar por nombre o NIT"),
    current_user: User = Depends(require_supervisor_or_admin),
    db: Session = Depends(get_db),
):
    """Lista todas las empresas con resumen de cumplimiento."""
    query = db.query(Empresa).options(
        joinedload(Empresa.sector_economico)
    )

    if activo is not None:
        query = query.filter(Empresa.activo == activo)

    if q:
        search = f"%{q}%"
        query = query.filter(
            (Empresa.nombre.ilike(search)) |
            (Empresa.nit.ilike(search))
        )

    empresas = query.order_by(Empresa.nombre).all()

    # Calcular estadísticas de cumplimiento para cada empresa
    result = []
    for empresa in empresas:
        # Obtener conteos de cumplimiento
        stats = db.query(
            MatrizLegalCumplimiento.estado,
            func.count(MatrizLegalCumplimiento.id)
        ).filter(
            MatrizLegalCumplimiento.empresa_id == empresa.id,
            MatrizLegalCumplimiento.aplica_empresa == True
        ).group_by(MatrizLegalCumplimiento.estado).all()

        por_estado = {e.value: 0 for e in EstadoCumplimiento}
        for estado, count in stats:
            if estado:
                # estado es un string (no enum) porque se almacena como String en la DB
                estado_key = estado.value if hasattr(estado, 'value') else estado
                if estado_key in por_estado:
                    por_estado[estado_key] = count

        total = sum(por_estado.values()) - por_estado.get('no_aplica', 0)
        cumple = por_estado.get('cumple', 0)
        porcentaje = (cumple / total * 100) if total > 0 else 0

        result.append(EmpresaResumen(
            id=empresa.id,
            nombre=empresa.nombre,
            nit=empresa.nit,
            sector_economico_nombre=empresa.sector_economico.nombre if empresa.sector_economico else None,
            activo=empresa.activo,
            total_normas_aplicables=total,
            normas_cumple=cumple,
            normas_no_cumple=por_estado.get('no_cumple', 0),
            normas_pendientes=por_estado.get('pendiente', 0),
            porcentaje_cumplimiento=round(porcentaje, 2),
        ))

    return result


@router.get("/activas", response_model=List[EmpresaSimple])
def list_empresas_activas(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Lista solo las empresas activas (para selectores)."""
    return db.query(Empresa).filter(
        Empresa.activo == True
    ).order_by(Empresa.nombre).all()


@router.get("/{empresa_id}", response_model=EmpresaSchema)
def get_empresa(
    empresa_id: int,
    current_user: User = Depends(require_supervisor_or_admin),
    db: Session = Depends(get_db),
):
    """Obtiene una empresa por ID con todos sus detalles."""
    empresa = db.query(Empresa).options(
        joinedload(Empresa.sector_economico)
    ).filter(
        Empresa.id == empresa_id
    ).first()

    if not empresa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa no encontrada"
        )

    return empresa


@router.post("/", response_model=EmpresaSchema, status_code=status.HTTP_201_CREATED)
def create_empresa(
    payload: EmpresaCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Crea una nueva empresa."""
    # Verificar que no exista una con el mismo nombre
    existing = db.query(Empresa).filter(
        func.upper(Empresa.nombre) == payload.nombre.upper()
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe una empresa con ese nombre"
        )

    # Verificar NIT único si se proporciona
    if payload.nit:
        existing_nit = db.query(Empresa).filter(
            Empresa.nit == payload.nit
        ).first()
        if existing_nit:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe una empresa con ese NIT"
            )

    # Verificar que el sector económico existe
    if payload.sector_economico_id:
        sector = db.query(SectorEconomico).filter(
            SectorEconomico.id == payload.sector_economico_id
        ).first()
        if not sector:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Sector económico no encontrado"
            )

    empresa = Empresa(
        **payload.model_dump(),
        creado_por=current_user.id
    )
    db.add(empresa)
    db.commit()
    db.refresh(empresa)

    return empresa


@router.put("/{empresa_id}", response_model=EmpresaSchema)
def update_empresa(
    empresa_id: int,
    payload: EmpresaUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Actualiza una empresa."""
    empresa = db.query(Empresa).filter(
        Empresa.id == empresa_id
    ).first()

    if not empresa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa no encontrada"
        )

    # Verificar nombre único si se está actualizando
    if payload.nombre:
        existing = db.query(Empresa).filter(
            func.upper(Empresa.nombre) == payload.nombre.upper(),
            Empresa.id != empresa_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe una empresa con ese nombre"
            )

    # Verificar NIT único si se está actualizando
    if payload.nit:
        existing_nit = db.query(Empresa).filter(
            Empresa.nit == payload.nit,
            Empresa.id != empresa_id
        ).first()
        if existing_nit:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe una empresa con ese NIT"
            )

    # Verificar sector económico si se está actualizando
    if payload.sector_economico_id:
        sector = db.query(SectorEconomico).filter(
            SectorEconomico.id == payload.sector_economico_id
        ).first()
        if not sector:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Sector económico no encontrado"
            )

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(empresa, key, value)

    db.commit()
    db.refresh(empresa)

    return empresa


@router.delete("/{empresa_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_empresa(
    empresa_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Elimina una empresa."""
    empresa = db.query(Empresa).filter(
        Empresa.id == empresa_id
    ).first()

    if not empresa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa no encontrada"
        )

    # Verificar si tiene cumplimientos asociados
    cumplimientos_count = db.query(func.count(MatrizLegalCumplimiento.id)).filter(
        MatrizLegalCumplimiento.empresa_id == empresa_id
    ).scalar()

    if cumplimientos_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede eliminar la empresa porque tiene {cumplimientos_count} registros de cumplimiento asociados. Considere desactivarla en su lugar."
        )

    db.delete(empresa)
    db.commit()

    return None


@router.post("/{empresa_id}/sincronizar-normas", response_model=MessageResponse)
def sincronizar_normas_empresa(
    empresa_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Sincroniza las normas aplicables a una empresa.
    Crea registros de cumplimiento pendiente para normas nuevas.
    """
    empresa = db.query(Empresa).filter(Empresa.id == empresa_id).first()
    if not empresa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa no encontrada"
        )

    service = MatrizLegalService(db)
    result = service.sincronizar_cumplimientos_empresa(empresa_id, current_user.id)

    return MessageResponse(
        message=f"Sincronización completada. Total normas aplicables: {result['total_normas_aplicables']}, "
                f"Existentes: {result['cumplimientos_existentes']}, Nuevos: {result['nuevos_creados']}, "
                f"Reactivados: {result['reactivados']}, Desactivados: {result['desactivados']}"
    )


@router.get("/{empresa_id}/caracteristicas", response_model=List[str])
def get_caracteristicas_empresa(
    empresa_id: int,
    current_user: User = Depends(require_supervisor_or_admin),
    db: Session = Depends(get_db),
):
    """Obtiene la lista de características activas de una empresa."""
    empresa = db.query(Empresa).filter(Empresa.id == empresa_id).first()
    if not empresa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa no encontrada"
        )

    return empresa.get_caracteristicas_activas()
