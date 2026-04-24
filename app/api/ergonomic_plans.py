import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.dependencies import get_current_user, get_current_active_user, require_supervisor_or_admin, has_role_or_custom
from app.models.user import User, UserRole
from app.models.ergonomic_plan import ErgonomicActionPlan, ErgonomicMeasure
from app.models.assessment import HomeworkAssessment
from app.models.worker import Worker
from app.schemas.ergonomic_plan import (
    ErgonomicActionPlanCreate,
    ErgonomicActionPlanUpdate,
    ErgonomicActionPlanResponse,
    ErgonomicFollowupUpdate,
)

router = APIRouter()

ERGONOMIC_ITEMS = {
    "chair_check": "Silla ergonómica con respaldo lumbar",
    "screen_check": "Posición pantalla a nivel de ojos",
    "desk_check": "Mesa o superficie de trabajo",
    "mouse_keyboard_check": "Teclado y ratón en posición adecuada",
    "active_breaks_check": "Pausas activas / micropausas",
}

DEFAULT_MEASURES = [
    {
        "measure_type": "inmediata_sin_costo",
        "description": "Elevar pantalla con libros/resma de papel para alinear la parte superior de la pantalla a nivel de los ojos",
        "responsible": "trabajador",
        "status": "pendiente",
    },
    {
        "measure_type": "inmediata_sin_costo",
        "description": "Usar cojín o almohada lumbar para apoyo de espalda baja mientras se consigue silla adecuada",
        "responsible": "trabajador",
        "status": "pendiente",
    },
    {
        "measure_type": "inmediata_sin_costo",
        "description": "Realizar pausas activas cada 50 minutos (ejercicios de cuello, hombros y espalda)",
        "responsible": "trabajador",
        "status": "pendiente",
    },
    {
        "measure_type": "corto_plazo_empresa",
        "description": "Evaluar entrega/préstamo de silla ergonómica con apoyalumbar y altura regulable según frecuencia de teletrabajo",
        "responsible": "empresa_th_gerencia",
        "status": "pendiente",
    },
    {
        "measure_type": "corto_plazo_empresa",
        "description": "Evaluar entrega de soporte para portátil + teclado y mouse externos",
        "responsible": "empresa_sst",
        "status": "pendiente",
    },
    {
        "measure_type": "formacion_capacitacion",
        "description": 'Capacitación virtual: "Ergonomía en casa – cómo configurar tu puesto" (1 hora, plataforma SST)',
        "responsible": "empresa_sst",
        "status": "pendiente",
    },
]


def _load_plan(plan_id: int, db: Session) -> ErgonomicActionPlan:
    plan = (
        db.query(ErgonomicActionPlan)
        .options(joinedload(ErgonomicActionPlan.measures), joinedload(ErgonomicActionPlan.worker))
        .filter(ErgonomicActionPlan.id == plan_id)
        .first()
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Plan ergonómico no encontrado")
    return plan


def _can_view(user: User, plan: ErgonomicActionPlan, db: Session) -> bool:
    if has_role_or_custom(user, ["admin", "supervisor"]):
        return True
    worker = db.query(Worker).filter(Worker.user_id == user.id).first()
    return worker is not None and worker.id == plan.worker_id


@router.get("", response_model=List[ErgonomicActionPlanResponse])
def list_plans(
    worker_id: Optional[int] = Query(None),
    plan_status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = db.query(ErgonomicActionPlan).options(
        joinedload(ErgonomicActionPlan.measures),
        joinedload(ErgonomicActionPlan.worker),
    )
    if not has_role_or_custom(current_user, ["admin", "supervisor"]):
        worker = db.query(Worker).filter(Worker.user_id == current_user.id).first()
        if not worker:
            return []
        query = query.filter(ErgonomicActionPlan.worker_id == worker.id)
    else:
        if worker_id:
            query = query.filter(ErgonomicActionPlan.worker_id == worker_id)
    if plan_status:
        query = query.filter(ErgonomicActionPlan.plan_status == plan_status)
    return query.order_by(ErgonomicActionPlan.created_at.desc()).all()


@router.post("", response_model=ErgonomicActionPlanResponse, status_code=status.HTTP_201_CREATED)
def create_plan(
    data: ErgonomicActionPlanCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin),
):
    assessment = db.query(HomeworkAssessment).filter(HomeworkAssessment.id == data.assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Autoevaluación no encontrada")

    existing = db.query(ErgonomicActionPlan).filter(ErgonomicActionPlan.assessment_id == data.assessment_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Ya existe un plan ergonómico para esta autoevaluación")

    # Derive non_compliant_items from assessment if not provided
    non_compliant = data.non_compliant_items
    if not non_compliant:
        items = [key for key in ERGONOMIC_ITEMS if not getattr(assessment, key, True)]
        non_compliant = json.dumps(items)

    plan = ErgonomicActionPlan(
        assessment_id=data.assessment_id,
        worker_id=data.worker_id,
        created_by=current_user.id,
        non_compliant_items=non_compliant,
        primary_risk=data.primary_risk,
        finding_description=data.finding_description,
        work_frequency=data.work_frequency,
        sst_conclusion=data.sst_conclusion,
        sst_conclusion_custom=data.sst_conclusion_custom,
        worker_accepts=data.worker_accepts,
        worker_agreement_name=data.worker_agreement_name,
        worker_agreement_date=data.worker_agreement_date,
        worker_signature=data.worker_signature,
        sst_approver_name=data.sst_approver_name,
        sst_approval_date=data.sst_approval_date,
        sst_signature=data.sst_signature,
        plan_status="OPEN",
    )
    db.add(plan)
    db.flush()

    measures_input = data.measures if data.measures is not None else []
    if not measures_input:
        # Use default measures
        for m in DEFAULT_MEASURES:
            db.add(ErgonomicMeasure(plan_id=plan.id, **m))
    else:
        for m in measures_input:
            db.add(ErgonomicMeasure(plan_id=plan.id, **m.model_dump()))

    db.commit()
    db.refresh(plan)
    return _load_plan(plan.id, db)


@router.get("/by-assessment/{assessment_id}", response_model=ErgonomicActionPlanResponse)
def get_plan_by_assessment(
    assessment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    plan = (
        db.query(ErgonomicActionPlan)
        .options(joinedload(ErgonomicActionPlan.measures), joinedload(ErgonomicActionPlan.worker))
        .filter(ErgonomicActionPlan.assessment_id == assessment_id)
        .first()
    )
    if not plan:
        raise HTTPException(status_code=404, detail="No existe plan ergonómico para esta autoevaluación")
    if not _can_view(current_user, plan, db):
        raise HTTPException(status_code=403, detail="Sin permiso")
    return plan


@router.get("/{plan_id}", response_model=ErgonomicActionPlanResponse)
def get_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    plan = _load_plan(plan_id, db)
    if not _can_view(current_user, plan, db):
        raise HTTPException(status_code=403, detail="Sin permiso")
    return plan


@router.put("/{plan_id}", response_model=ErgonomicActionPlanResponse)
def update_plan(
    plan_id: int,
    data: ErgonomicActionPlanUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin),
):
    plan = _load_plan(plan_id, db)

    for field, value in data.model_dump(exclude={"measures"}, exclude_unset=True).items():
        setattr(plan, field, value)

    if data.measures is not None:
        # Replace all measures
        db.query(ErgonomicMeasure).filter(ErgonomicMeasure.plan_id == plan_id).delete()
        for m in data.measures:
            db.add(ErgonomicMeasure(plan_id=plan_id, **m.model_dump()))

    db.commit()
    return _load_plan(plan_id, db)


@router.post("/{plan_id}/followup", response_model=ErgonomicActionPlanResponse)
def register_followup(
    plan_id: int,
    data: ErgonomicFollowupUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin),
):
    plan = _load_plan(plan_id, db)

    plan.verification_date = data.verification_date
    plan.verification_method = data.verification_method
    plan.followup_result = data.followup_result
    plan.followup_decision = data.followup_decision
    plan.final_observations = data.final_observations
    if data.sst_signature:
        plan.sst_signature = data.sst_signature
    if data.sst_approver_name:
        plan.sst_approver_name = data.sst_approver_name
    if data.sst_approval_date:
        plan.sst_approval_date = data.sst_approval_date

    if data.followup_result == "controlado":
        plan.plan_status = "CLOSED"
    elif data.followup_result in ("parcialmente_controlado", "no_controlado"):
        plan.plan_status = "IN_PROGRESS"

    db.commit()
    return _load_plan(plan_id, db)


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin),
):
    plan = db.query(ErgonomicActionPlan).filter(ErgonomicActionPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan ergonómico no encontrado")
    db.delete(plan)
    db.commit()
