from datetime import date, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin, require_manager_access
from app.models.occupational_exam import OccupationalExam
from app.models.restriccion_medica import EstadoImplementacion, RestriccionMedica, TipoRestriccion
from app.models.worker import Worker
from app.schemas.restriccion_medica import (
    RestriccionMedicaCreate,
    RestriccionMedicaImplementar,
    RestriccionMedicaResponse,
    RestriccionMedicaUpdate,
)
from app.models.user import User


router = APIRouter()


def _update_worker_restricciones_flag(db: Session, worker_id: int) -> None:
    count = (
        db.query(RestriccionMedica)
        .filter(RestriccionMedica.worker_id == worker_id, RestriccionMedica.activa == True)  # noqa: E712
        .count()
    )
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if worker:
        worker.tiene_restricciones_activas = count > 0


@router.get("", response_model=List[RestriccionMedicaResponse])
@router.get("/", response_model=List[RestriccionMedicaResponse])
def list_restricciones_medicas(
    worker_id: Optional[int] = Query(None),
    activa: Optional[bool] = Query(None),
    estado: Optional[EstadoImplementacion] = Query(None),
    current_user: User = Depends(require_manager_access),
    db: Session = Depends(get_db),
):
    query = db.query(RestriccionMedica)
    if worker_id is not None:
        query = query.filter(RestriccionMedica.worker_id == worker_id)
    if activa is not None:
        query = query.filter(RestriccionMedica.activa == activa)
    if estado is not None:
        query = query.filter(RestriccionMedica.estado_implementacion == estado)
    return query.order_by(RestriccionMedica.fecha_inicio.desc(), RestriccionMedica.id.desc()).all()


@router.get("/vencidas", response_model=List[RestriccionMedicaResponse])
def list_restricciones_vencidas(
    current_user: User = Depends(require_manager_access),
    db: Session = Depends(get_db),
):
    hoy = date.today()
    vencidas = (
        db.query(RestriccionMedica)
        .filter(
            RestriccionMedica.activa == True,  # noqa: E712
            RestriccionMedica.implementada == False,  # noqa: E712
            RestriccionMedica.fecha_limite_implementacion < hoy,
        )
        .all()
    )
    for r in vencidas:
        if r.estado_implementacion != EstadoImplementacion.VENCIDA:
            r.estado_implementacion = EstadoImplementacion.VENCIDA
    db.commit()
    return vencidas


@router.get("/{restriccion_id}", response_model=RestriccionMedicaResponse)
def get_restriccion_medica(
    restriccion_id: int,
    current_user: User = Depends(require_manager_access),
    db: Session = Depends(get_db),
):
    r = db.query(RestriccionMedica).filter(RestriccionMedica.id == restriccion_id).first()
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restricción no encontrada")
    return r


@router.post("", response_model=RestriccionMedicaResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=RestriccionMedicaResponse, status_code=status.HTTP_201_CREATED)
def create_restriccion_medica(
    payload: RestriccionMedicaCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    worker = db.query(Worker).filter(Worker.id == payload.worker_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail="Trabajador no encontrado")

    if payload.occupational_exam_id is not None:
        exam = db.query(OccupationalExam).filter(OccupationalExam.id == payload.occupational_exam_id).first()
        if not exam:
            raise HTTPException(status_code=404, detail="Examen no encontrado")
        if exam.worker_id != payload.worker_id:
            raise HTTPException(status_code=400, detail="El examen no corresponde al trabajador")

    fecha_inicio = payload.fecha_inicio or date.today()
    fecha_limite = fecha_inicio + timedelta(days=20)

    r = RestriccionMedica(
        worker_id=payload.worker_id,
        occupational_exam_id=payload.occupational_exam_id,
        tipo_restriccion=payload.tipo_restriccion,
        descripcion=payload.descripcion,
        actividades_restringidas=payload.actividades_restringidas,
        recomendaciones=payload.recomendaciones,
        fecha_inicio=fecha_inicio,
        fecha_fin=payload.fecha_fin if payload.tipo_restriccion != TipoRestriccion.PERMANENTE else None,
        activa=True,
        fecha_limite_implementacion=fecha_limite,
        estado_implementacion=EstadoImplementacion.PENDIENTE,
        implementada=False,
        responsable_implementacion_id=payload.responsable_implementacion_id,
        creado_por=current_user.id,
        modificado_por=None,
    )
    db.add(r)
    _update_worker_restricciones_flag(db, payload.worker_id)
    db.commit()
    db.refresh(r)
    return r


@router.put("/{restriccion_id}", response_model=RestriccionMedicaResponse)
def update_restriccion_medica(
    restriccion_id: int,
    payload: RestriccionMedicaUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    r = db.query(RestriccionMedica).filter(RestriccionMedica.id == restriccion_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Restricción no encontrada")

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(r, k, v)

    if "fecha_inicio" in data:
        r.fecha_limite_implementacion = r.fecha_inicio + timedelta(days=20)

    if r.tipo_restriccion == TipoRestriccion.PERMANENTE:
        r.fecha_fin = None

    r.modificado_por = current_user.id
    db.commit()
    _update_worker_restricciones_flag(db, r.worker_id)
    db.refresh(r)
    return r


@router.put("/{restriccion_id}/implementar", response_model=RestriccionMedicaResponse)
def implementar_restriccion_medica(
    restriccion_id: int,
    payload: RestriccionMedicaImplementar,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    r = db.query(RestriccionMedica).filter(RestriccionMedica.id == restriccion_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Restricción no encontrada")
    if r.implementada:
        return r

    r.implementada = True
    r.fecha_implementacion = payload.fecha_implementacion or date.today()
    r.estado_implementacion = EstadoImplementacion.IMPLEMENTADA
    r.responsable_implementacion_id = current_user.id
    r.observaciones_implementacion = payload.observaciones_implementacion
    r.modificado_por = current_user.id
    db.commit()
    _update_worker_restricciones_flag(db, r.worker_id)
    db.refresh(r)
    return r

