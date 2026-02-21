from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_supervisor_or_admin
from app.models.user import User
from app.models.estandares_minimos import (
    AutoevaluacionEstandares, AutoevaluacionRespuesta,
    GrupoEstandar, NivelRiesgoEmpresa, EstadoAutoevaluacion,
    NivelCumplimiento, CicloPHVA, ValorCumplimiento,
)
from app.schemas.estandares_minimos import (
    AutoevaluacionEstandaresCreate,
    AutoevaluacionEstandaresUpdate,
    AutoevaluacionEstandaresResponse,
    AutoevaluacionEstandaresDetailResponse,
    AutoevaluacionRespuestaUpdate,
    AutoevaluacionRespuestaResponse,
    DashboardEstandaresMinimos,
    CicloResumen,
)
from app.services.estandares_minimos_template import (
    determinar_grupo,
    get_plantilla_respuestas,
    calcular_puntajes,
)

router = APIRouter()

_CICLO_LABELS = {
    "PLANEAR":   "I. PLANEAR",
    "HACER":     "II. HACER",
    "VERIFICAR": "III. VERIFICAR",
    "ACTUAR":    "IV. ACTUAR",
}

# ─────────────────────────────────────────────────────────────────────────────
# AUTOEVALUACIONES (CRUD)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/", response_model=List[AutoevaluacionEstandaresResponse])
def listar_autoevaluaciones(
    año: Optional[int] = Query(None),
    empresa_id: Optional[int] = Query(None),
    estado: Optional[EstadoAutoevaluacion] = Query(None),
    grupo: Optional[GrupoEstandar] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(AutoevaluacionEstandares)
    if año:
        query = query.filter(AutoevaluacionEstandares.año == año)
    if empresa_id:
        query = query.filter(AutoevaluacionEstandares.empresa_id == empresa_id)
    if estado:
        query = query.filter(AutoevaluacionEstandares.estado == estado)
    if grupo:
        query = query.filter(AutoevaluacionEstandares.grupo == grupo)
    return query.order_by(AutoevaluacionEstandares.año.desc()).all()


@router.post("/", response_model=AutoevaluacionEstandaresDetailResponse, status_code=status.HTTP_201_CREATED)
def crear_autoevaluacion(
    data: AutoevaluacionEstandaresCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin),
):
    # Calcular grupo según Resolución 0312/2019
    grupo_str = determinar_grupo(data.num_trabajadores, data.nivel_riesgo.value)

    # Verificar que no exista ya para ese año y empresa
    existente = db.query(AutoevaluacionEstandares).filter(
        AutoevaluacionEstandares.año == data.año,
        AutoevaluacionEstandares.empresa_id == data.empresa_id,
    ).first()
    if existente:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe una autoevaluación de Estándares Mínimos para el año {data.año}"
        )

    autoevaluacion = AutoevaluacionEstandares(
        **data.model_dump(),
        grupo=GrupoEstandar(grupo_str),
        estado=EstadoAutoevaluacion.BORRADOR,
        created_by=current_user.id,
    )
    db.add(autoevaluacion)
    db.flush()

    # Poblar todas las respuestas desde la plantilla
    plantilla = get_plantilla_respuestas(grupo_str)
    for item in plantilla:
        respuesta = AutoevaluacionRespuesta(
            autoevaluacion_id=autoevaluacion.id,
            estandar_codigo=item["codigo"],
            ciclo=CicloPHVA(item["ciclo"]),
            descripcion=item["descripcion"],
            valor_maximo=item["valor"],
            valor_maximo_ajustado=item["valor_ajustado"],
            cumplimiento=ValorCumplimiento.NO_CUMPLE,
            valor_obtenido=0.0,
            orden=item["orden"],
        )
        db.add(respuesta)

    db.commit()
    db.refresh(autoevaluacion)
    return autoevaluacion


@router.get("/{eval_id}", response_model=AutoevaluacionEstandaresDetailResponse)
def obtener_autoevaluacion(
    eval_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    autoevaluacion = db.query(AutoevaluacionEstandares).filter(
        AutoevaluacionEstandares.id == eval_id
    ).first()
    if not autoevaluacion:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Autoevaluación no encontrada")
    return autoevaluacion


@router.put("/{eval_id}", response_model=AutoevaluacionEstandaresResponse)
def actualizar_autoevaluacion(
    eval_id: int,
    data: AutoevaluacionEstandaresUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    autoevaluacion = db.query(AutoevaluacionEstandares).filter(
        AutoevaluacionEstandares.id == eval_id
    ).first()
    if not autoevaluacion:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Autoevaluación no encontrada")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(autoevaluacion, field, value)

    db.commit()
    db.refresh(autoevaluacion)
    return autoevaluacion


@router.delete("/{eval_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_autoevaluacion(
    eval_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin),
):
    autoevaluacion = db.query(AutoevaluacionEstandares).filter(
        AutoevaluacionEstandares.id == eval_id
    ).first()
    if not autoevaluacion:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Autoevaluación no encontrada")
    db.delete(autoevaluacion)
    db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# RESPUESTAS INDIVIDUALES
# ─────────────────────────────────────────────────────────────────────────────

@router.put("/{eval_id}/respuestas/{respuesta_id}", response_model=AutoevaluacionRespuestaResponse)
def actualizar_respuesta(
    eval_id: int,
    respuesta_id: int,
    data: AutoevaluacionRespuestaUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    autoevaluacion = db.query(AutoevaluacionEstandares).filter(
        AutoevaluacionEstandares.id == eval_id
    ).first()
    if not autoevaluacion:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Autoevaluación no encontrada")

    respuesta = db.query(AutoevaluacionRespuesta).filter(
        AutoevaluacionRespuesta.id == respuesta_id,
        AutoevaluacionRespuesta.autoevaluacion_id == eval_id,
    ).first()
    if not respuesta:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Respuesta no encontrada")

    # Actualizar campos
    respuesta.cumplimiento = data.cumplimiento
    respuesta.justificacion_no_aplica = data.justificacion_no_aplica
    respuesta.observaciones = data.observaciones

    # Calcular valor obtenido
    cumpl_val = data.cumplimiento.value if hasattr(data.cumplimiento, "value") else str(data.cumplimiento)
    if cumpl_val in ("cumple_totalmente", "no_aplica"):
        respuesta.valor_obtenido = respuesta.valor_maximo_ajustado
    else:
        respuesta.valor_obtenido = 0.0

    db.flush()

    # Recalcular y cachear scores del padre en la misma transacción
    todas_respuestas = db.query(AutoevaluacionRespuesta).filter(
        AutoevaluacionRespuesta.autoevaluacion_id == eval_id
    ).all()
    puntajes = calcular_puntajes(todas_respuestas)
    for field, val in puntajes.items():
        if field == "nivel_cumplimiento":
            setattr(autoevaluacion, field, NivelCumplimiento(val))
        else:
            setattr(autoevaluacion, field, val)

    db.commit()
    db.refresh(respuesta)
    return respuesta


# ─────────────────────────────────────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{eval_id}/dashboard", response_model=DashboardEstandaresMinimos)
def obtener_dashboard(
    eval_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    autoevaluacion = db.query(AutoevaluacionEstandares).filter(
        AutoevaluacionEstandares.id == eval_id
    ).first()
    if not autoevaluacion:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Autoevaluación no encontrada")

    respuestas = db.query(AutoevaluacionRespuesta).filter(
        AutoevaluacionRespuesta.autoevaluacion_id == eval_id
    ).all()

    # Acumuladores por ciclo
    ciclos_data: dict = {
        c: {
            "puntaje_maximo": 0.0,
            "puntaje_obtenido": 0.0,
            "cumplen": 0,
            "no_cumplen": 0,
            "no_aplican": 0,
            "total": 0,
        }
        for c in ["PLANEAR", "HACER", "VERIFICAR", "ACTUAR"]
    }
    estandares_criticos: List[str] = []

    for r in respuestas:
        ciclo_val = r.ciclo.value if hasattr(r.ciclo, "value") else str(r.ciclo)
        cumpl_val = r.cumplimiento.value if hasattr(r.cumplimiento, "value") else str(r.cumplimiento)

        cd = ciclos_data[ciclo_val]
        cd["puntaje_maximo"] += r.valor_maximo_ajustado
        cd["puntaje_obtenido"] += r.valor_obtenido
        cd["total"] += 1

        if cumpl_val == "cumple_totalmente":
            cd["cumplen"] += 1
        elif cumpl_val == "no_aplica":
            cd["no_aplican"] += 1
        else:
            cd["no_cumplen"] += 1
            estandares_criticos.append(r.estandar_codigo)

    # Construir lista de CicloResumen
    ciclos_resumen: List[CicloResumen] = []
    for ciclo_key in ["PLANEAR", "HACER", "VERIFICAR", "ACTUAR"]:
        cd = ciclos_data[ciclo_key]
        pct = round((cd["puntaje_obtenido"] / cd["puntaje_maximo"] * 100), 1) if cd["puntaje_maximo"] > 0 else 0.0
        ciclos_resumen.append(CicloResumen(
            ciclo=ciclo_key,
            label=_CICLO_LABELS[ciclo_key],
            puntaje_maximo=round(cd["puntaje_maximo"], 2),
            puntaje_obtenido=round(cd["puntaje_obtenido"], 2),
            porcentaje=pct,
            total_estandares=cd["total"],
            cumplen=cd["cumplen"],
            no_cumplen=cd["no_cumplen"],
            no_aplican=cd["no_aplican"],
        ))

    total_r = len(respuestas)
    total_cumplen = sum(c.cumplen for c in ciclos_resumen)
    total_no_cumplen = sum(c.no_cumplen for c in ciclos_resumen)
    total_no_aplican = sum(c.no_aplican for c in ciclos_resumen)

    return DashboardEstandaresMinimos(
        autoevaluacion_id=eval_id,
        año=autoevaluacion.año,
        grupo=autoevaluacion.grupo,
        num_trabajadores=autoevaluacion.num_trabajadores,
        nivel_riesgo=autoevaluacion.nivel_riesgo,
        puntaje_total=autoevaluacion.puntaje_total,
        nivel_cumplimiento=autoevaluacion.nivel_cumplimiento,
        ciclos=ciclos_resumen,
        total_estandares=total_r,
        total_cumplen=total_cumplen,
        total_no_cumplen=total_no_cumplen,
        total_no_aplican=total_no_aplican,
        estandares_criticos=sorted(estandares_criticos),
    )
