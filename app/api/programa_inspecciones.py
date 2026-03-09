from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_supervisor_or_admin
from app.models.user import User
from app.models.programa_inspecciones import (
    ProgramaInspecciones, InspeccionProgramada, InspeccionSeguimiento,
    EstadoPrograma, TipoInspeccion, FrecuenciaInspeccion, CicloInspeccion,
)
from app.schemas.programa_inspecciones import (
    ProgramaInspeccionesCreate, ProgramaInspeccionesUpdate, ProgramaInspeccionesResponse,
    ProgramaInspeccionesDetailResponse,
    InspeccionProgramadaCreate, InspeccionProgramadaUpdate, InspeccionProgramadaResponse,
    InspeccionSeguimientoUpdate, InspeccionSeguimientoResponse,
    IndicadoresPrograma, IndicadorMes,
)

router = APIRouter()

NOMBRE_MESES = [
    "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
]


# =====================================================================
# PROGRAMAS
# =====================================================================

@router.get("/", response_model=List[ProgramaInspeccionesResponse])
def listar_programas(
    año: Optional[int] = Query(None),
    empresa_id: Optional[int] = Query(None),
    estado: Optional[EstadoPrograma] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(ProgramaInspecciones)
    if año:
        query = query.filter(ProgramaInspecciones.año == año)
    if empresa_id:
        query = query.filter(ProgramaInspecciones.empresa_id == empresa_id)
    if estado:
        query = query.filter(ProgramaInspecciones.estado == estado)
    return query.order_by(ProgramaInspecciones.año.desc()).all()


@router.post("/", response_model=ProgramaInspeccionesResponse, status_code=status.HTTP_201_CREATED)
def crear_programa(
    data: ProgramaInspeccionesCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin),
):
    existente = db.query(ProgramaInspecciones).filter(
        ProgramaInspecciones.año == data.año,
        ProgramaInspecciones.empresa_id == data.empresa_id,
    ).first()
    if existente:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe un Programa de Inspecciones para el año {data.año}",
        )
    programa = ProgramaInspecciones(**data.model_dump(), created_by=current_user.id)
    db.add(programa)
    db.commit()
    db.refresh(programa)
    return programa


@router.get("/{programa_id}", response_model=ProgramaInspeccionesDetailResponse)
def obtener_programa(
    programa_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    programa = db.query(ProgramaInspecciones).filter(ProgramaInspecciones.id == programa_id).first()
    if not programa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Programa no encontrado")
    return programa


@router.put("/{programa_id}", response_model=ProgramaInspeccionesResponse)
def actualizar_programa(
    programa_id: int,
    data: ProgramaInspeccionesUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin),
):
    programa = db.query(ProgramaInspecciones).filter(ProgramaInspecciones.id == programa_id).first()
    if not programa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Programa no encontrado")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(programa, field, value)
    db.commit()
    db.refresh(programa)
    return programa


@router.delete("/{programa_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_programa(
    programa_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin),
):
    programa = db.query(ProgramaInspecciones).filter(ProgramaInspecciones.id == programa_id).first()
    if not programa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Programa no encontrado")
    db.delete(programa)
    db.commit()


# =====================================================================
# INSPECCIONES
# =====================================================================

@router.get("/{programa_id}/inspecciones", response_model=List[InspeccionProgramadaResponse])
def listar_inspecciones(
    programa_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    programa = db.query(ProgramaInspecciones).filter(ProgramaInspecciones.id == programa_id).first()
    if not programa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Programa no encontrado")
    return (
        db.query(InspeccionProgramada)
        .filter(InspeccionProgramada.programa_id == programa_id)
        .order_by(InspeccionProgramada.orden)
        .all()
    )


@router.post(
    "/{programa_id}/inspecciones",
    response_model=InspeccionProgramadaResponse,
    status_code=status.HTTP_201_CREATED,
)
def crear_inspeccion(
    programa_id: int,
    data: InspeccionProgramadaCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin),
):
    programa = db.query(ProgramaInspecciones).filter(ProgramaInspecciones.id == programa_id).first()
    if not programa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Programa no encontrado")

    inspeccion = InspeccionProgramada(programa_id=programa_id, **data.model_dump())
    db.add(inspeccion)
    db.flush()

    # Crear 12 seguimientos mensuales vacíos
    for mes in range(1, 13):
        db.add(InspeccionSeguimiento(inspeccion_id=inspeccion.id, mes=mes))

    db.commit()
    db.refresh(inspeccion)
    return inspeccion


@router.put("/inspecciones/{inspeccion_id}", response_model=InspeccionProgramadaResponse)
def actualizar_inspeccion(
    inspeccion_id: int,
    data: InspeccionProgramadaUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin),
):
    inspeccion = db.query(InspeccionProgramada).filter(InspeccionProgramada.id == inspeccion_id).first()
    if not inspeccion:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inspección no encontrada")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(inspeccion, field, value)
    db.commit()
    db.refresh(inspeccion)
    return inspeccion


@router.delete("/inspecciones/{inspeccion_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_inspeccion(
    inspeccion_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin),
):
    inspeccion = db.query(InspeccionProgramada).filter(InspeccionProgramada.id == inspeccion_id).first()
    if not inspeccion:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inspección no encontrada")
    db.delete(inspeccion)
    db.commit()


# =====================================================================
# SEGUIMIENTO MENSUAL (P/E)
# =====================================================================

@router.put(
    "/inspecciones/{inspeccion_id}/seguimiento/{mes}",
    response_model=InspeccionSeguimientoResponse,
)
def actualizar_seguimiento(
    inspeccion_id: int,
    mes: int,
    data: InspeccionSeguimientoUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if mes < 1 or mes > 12:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El mes debe estar entre 1 y 12",
        )
    inspeccion = db.query(InspeccionProgramada).filter(InspeccionProgramada.id == inspeccion_id).first()
    if not inspeccion:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inspección no encontrada")

    seguimiento = db.query(InspeccionSeguimiento).filter(
        InspeccionSeguimiento.inspeccion_id == inspeccion_id,
        InspeccionSeguimiento.mes == mes,
    ).first()

    if not seguimiento:
        seguimiento = InspeccionSeguimiento(inspeccion_id=inspeccion_id, mes=mes)
        db.add(seguimiento)

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(seguimiento, field, value)

    db.commit()
    db.refresh(seguimiento)
    return seguimiento


# =====================================================================
# INDICADORES (Cumplimiento y Eficacia)
# =====================================================================

@router.get("/{programa_id}/indicadores", response_model=IndicadoresPrograma)
def obtener_indicadores(
    programa_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    programa = db.query(ProgramaInspecciones).filter(ProgramaInspecciones.id == programa_id).first()
    if not programa:
        raise HTTPException(status_code=404, detail="Programa no encontrado")

    seguimientos = (
        db.query(InspeccionSeguimiento)
        .join(InspeccionProgramada)
        .filter(InspeccionProgramada.programa_id == programa_id)
        .all()
    )

    meses_data: dict = {
        m: {"programadas": 0, "ejecutadas": 0, "reportadas": 0, "intervenidas": 0}
        for m in range(1, 13)
    }
    for s in seguimientos:
        if s.programada:
            meses_data[s.mes]["programadas"] += 1
        if s.ejecutada:
            meses_data[s.mes]["ejecutadas"] += 1
        meses_data[s.mes]["reportadas"] += s.condiciones_peligrosas_reportadas or 0
        meses_data[s.mes]["intervenidas"] += s.condiciones_peligrosas_intervenidas or 0

    meses_indicadores = []
    for mes in range(1, 13):
        d = meses_data[mes]
        pct_cum = round(d["ejecutadas"] / d["programadas"] * 100, 1) if d["programadas"] > 0 else 0.0
        pct_efi = round(d["intervenidas"] / d["reportadas"] * 100, 1) if d["reportadas"] > 0 else 0.0
        meses_indicadores.append(IndicadorMes(
            mes=mes,
            nombre_mes=NOMBRE_MESES[mes],
            programadas=d["programadas"],
            ejecutadas=d["ejecutadas"],
            pct_cumplimiento=pct_cum,
            condiciones_reportadas=d["reportadas"],
            condiciones_intervenidas=d["intervenidas"],
            pct_eficacia=pct_efi,
        ))

    tot_prog = sum(m.programadas for m in meses_indicadores)
    tot_ejec = sum(m.ejecutadas for m in meses_indicadores)
    tot_rep = sum(m.condiciones_reportadas for m in meses_indicadores)
    tot_int = sum(m.condiciones_intervenidas for m in meses_indicadores)

    return IndicadoresPrograma(
        total_programadas=tot_prog,
        total_ejecutadas=tot_ejec,
        pct_cumplimiento_global=round(tot_ejec / tot_prog * 100, 1) if tot_prog > 0 else 0.0,
        total_condiciones_reportadas=tot_rep,
        total_condiciones_intervenidas=tot_int,
        pct_eficacia_global=round(tot_int / tot_rep * 100, 1) if tot_rep > 0 else 0.0,
        meses=meses_indicadores,
    )
