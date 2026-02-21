import io
from datetime import datetime
from typing import List

import weasyprint
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.plan_trabajo_anual import PlanTrabajoAnual
from app.models.cronograma_pyp import (
    CronogramaPyp,
    CronogramaPypActividad,
    CronogramaPypSeguimiento,
)
from app.schemas.cronograma_pyp import (
    CronogramaPypCreate,
    CronogramaPypUpdate,
    CronogramaPypResponse,
    CronogramaPypDetailResponse,
    CronogramaPypActividadCreate,
    CronogramaPypActividadUpdate,
    CronogramaPypActividadResponse,
    CronogramaPypSeguimientoUpdate,
    CronogramaPypSeguimientoResponse,
)


router = APIRouter()


NOMBRE_MESES = [
    "",
    "Enero",
    "Febrero",
    "Marzo",
    "Abril",
    "Mayo",
    "Junio",
    "Julio",
    "Agosto",
    "Septiembre",
    "Octubre",
    "Noviembre",
    "Diciembre",
]


def _get_cronograma_or_404(db: Session, plan_id: int) -> CronogramaPyp:
    cronograma = (
        db.query(CronogramaPyp)
        .filter(CronogramaPyp.plan_trabajo_anual_id == plan_id)
        .first()
    )
    if not cronograma:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cronograma PYP no encontrado para este Plan de Trabajo Anual",
        )
    return cronograma


@router.post("/{plan_id}/cronograma-pyp", response_model=CronogramaPypResponse)
def crear_cronograma_pyp(
    plan_id: int,
    payload: CronogramaPypCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    plan = db.query(PlanTrabajoAnual).filter(PlanTrabajoAnual.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan no encontrado")

    existente = (
        db.query(CronogramaPyp)
        .filter(CronogramaPyp.plan_trabajo_anual_id == plan_id)
        .first()
    )
    if existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un cronograma PYP para este plan",
        )

    cronograma = CronogramaPyp(
        plan_trabajo_anual_id=plan_id,
        año=plan.año,
        empresa_id=plan.empresa_id,
        codigo=payload.codigo,
        version=payload.version,
        objetivo=payload.objetivo,
        alcance=payload.alcance,
        encargado_sgsst=payload.encargado_sgsst,
        aprobado_por=payload.aprobado_por,
        created_by=getattr(current_user, "id", None),
    )
    db.add(cronograma)
    db.commit()
    db.refresh(cronograma)
    return cronograma


@router.get("/{plan_id}/cronograma-pyp", response_model=CronogramaPypDetailResponse)
def obtener_cronograma_pyp(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cronograma = _get_cronograma_or_404(db, plan_id)
    return cronograma


@router.put("/{plan_id}/cronograma-pyp", response_model=CronogramaPypResponse)
def actualizar_cronograma_pyp(
    plan_id: int,
    payload: CronogramaPypUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cronograma = _get_cronograma_or_404(db, plan_id)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(cronograma, field, value)

    db.commit()
    db.refresh(cronograma)
    return cronograma


@router.delete("/{plan_id}/cronograma-pyp")
def eliminar_cronograma_pyp(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cronograma = _get_cronograma_or_404(db, plan_id)
    db.delete(cronograma)
    db.commit()
    return {"message": "Cronograma PYP eliminado"}


@router.get(
    "/{plan_id}/cronograma-pyp/actividades",
    response_model=List[CronogramaPypActividadResponse],
)
def listar_actividades_pyp(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cronograma = _get_cronograma_or_404(db, plan_id)
    return (
        db.query(CronogramaPypActividad)
        .filter(CronogramaPypActividad.cronograma_id == cronograma.id)
        .order_by(CronogramaPypActividad.orden)
        .all()
    )


@router.post(
    "/{plan_id}/cronograma-pyp/actividades",
    response_model=CronogramaPypActividadResponse,
)
def crear_actividad_pyp(
    plan_id: int,
    payload: CronogramaPypActividadCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cronograma = _get_cronograma_or_404(db, plan_id)

    actividad = CronogramaPypActividad(
        cronograma_id=cronograma.id,
        actividad=payload.actividad,
        poblacion_objetivo=payload.poblacion_objetivo,
        responsable=payload.responsable,
        indicador=payload.indicador,
        recursos=payload.recursos,
        observaciones=payload.observaciones,
        orden=payload.orden,
    )
    db.add(actividad)
    db.commit()
    db.refresh(actividad)

    for mes in range(1, 13):
        db.add(CronogramaPypSeguimiento(actividad_id=actividad.id, mes=mes))
    db.commit()
    db.refresh(actividad)
    return actividad


@router.put(
    "/{plan_id}/cronograma-pyp/actividades/{actividad_id}",
    response_model=CronogramaPypActividadResponse,
)
def actualizar_actividad_pyp(
    plan_id: int,
    actividad_id: int,
    payload: CronogramaPypActividadUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cronograma = _get_cronograma_or_404(db, plan_id)
    actividad = (
        db.query(CronogramaPypActividad)
        .filter(
            CronogramaPypActividad.id == actividad_id,
            CronogramaPypActividad.cronograma_id == cronograma.id,
        )
        .first()
    )
    if not actividad:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Actividad no encontrada")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(actividad, field, value)

    db.commit()
    db.refresh(actividad)
    return actividad


@router.delete("/{plan_id}/cronograma-pyp/actividades/{actividad_id}")
def eliminar_actividad_pyp(
    plan_id: int,
    actividad_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cronograma = _get_cronograma_or_404(db, plan_id)
    actividad = (
        db.query(CronogramaPypActividad)
        .filter(
            CronogramaPypActividad.id == actividad_id,
            CronogramaPypActividad.cronograma_id == cronograma.id,
        )
        .first()
    )
    if not actividad:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Actividad no encontrada")
    db.delete(actividad)
    db.commit()
    return {"message": "Actividad eliminada"}


@router.put(
    "/{plan_id}/cronograma-pyp/actividades/{actividad_id}/seguimiento/{mes}",
    response_model=CronogramaPypSeguimientoResponse,
)
def actualizar_seguimiento_pyp(
    plan_id: int,
    actividad_id: int,
    mes: int,
    payload: CronogramaPypSeguimientoUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if mes < 1 or mes > 12:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mes inválido")

    cronograma = _get_cronograma_or_404(db, plan_id)
    actividad = (
        db.query(CronogramaPypActividad)
        .filter(
            CronogramaPypActividad.id == actividad_id,
            CronogramaPypActividad.cronograma_id == cronograma.id,
        )
        .first()
    )
    if not actividad:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Actividad no encontrada")

    seg = (
        db.query(CronogramaPypSeguimiento)
        .filter(
            CronogramaPypSeguimiento.actividad_id == actividad_id,
            CronogramaPypSeguimiento.mes == mes,
        )
        .first()
    )
    if not seg:
        seg = CronogramaPypSeguimiento(actividad_id=actividad_id, mes=mes)
        db.add(seg)
        db.commit()
        db.refresh(seg)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(seg, field, value)
    db.commit()
    db.refresh(seg)
    return seg


@router.get("/{plan_id}/cronograma-pyp/exportar/pdf")
def exportar_cronograma_pyp_pdf(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cronograma = _get_cronograma_or_404(db, plan_id)

    actividades = (
        db.query(CronogramaPypActividad)
        .filter(CronogramaPypActividad.cronograma_id == cronograma.id)
        .order_by(CronogramaPypActividad.orden)
        .all()
    )
    act_ids = [a.id for a in actividades]
    segs_list = (
        db.query(CronogramaPypSeguimiento)
        .filter(CronogramaPypSeguimiento.actividad_id.in_(act_ids))
        .all()
        if act_ids
        else []
    )
    seg_dict = {}
    for s in segs_list:
        seg_dict.setdefault(s.actividad_id, {})[s.mes] = s

    meses_abrev = [
        "",
        "Ene",
        "Feb",
        "Mar",
        "Abr",
        "May",
        "Jun",
        "Jul",
        "Ago",
        "Sep",
        "Oct",
        "Nov",
        "Dic",
    ]

    month_ths = "".join(
        f'<th colspan="2" class="mes-hdr">{meses_abrev[m]}</th>' for m in range(1, 13)
    )
    pe_ths = "<th class=\"pe\">P</th><th class=\"pe\">E</th>" * 12

    body_rows = ""
    for act in actividades:
        segs = seg_dict.get(act.id, {})
        cells = ""
        for m in range(1, 13):
            s = segs.get(m)
            prog = s.programada if s else False
            ejec = s.ejecutada if s else False
            p_cls = "pe-both" if (prog and ejec) else ("pe-prog" if prog else "pe-empty")
            e_cls = "pe-exec" if ejec else "pe-empty"
            cells += (
                f'<td class="pe {p_cls}">{"✓" if prog else ""}</td>'
                f'<td class="pe {e_cls}">{"✓" if ejec else ""}</td>'
            )

        body_rows += (
            "<tr>"
            f'<td class="act">{act.actividad}</td>'
            f'<td class="pob">{act.poblacion_objetivo or ""}</td>'
            f'<td class="resp">{act.responsable or ""}</td>'
            f'{cells}'
            f'<td class="obs">{act.observaciones or ""}</td>'
            "</tr>\n"
        )

    encargado_html = (
        f'<span><b>Encargado SG-SST:</b> {cronograma.encargado_sgsst}</span>'
        if cronograma.encargado_sgsst
        else ""
    )
    aprobado_html = (
        f'<span><b>Aprobado por:</b> {cronograma.aprobado_por}</span>'
        if cronograma.aprobado_por
        else ""
    )
    now = datetime.now().strftime("%d/%m/%Y %H:%M")

    html = f"""<!DOCTYPE html>
<html lang=\"es\">
<head>
<meta charset=\"UTF-8\">
<title>Cronograma PYP {cronograma.año}</title>
<style>
  @page {{ size: A4 landscape; margin: 8mm 6mm; }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: Arial, Helvetica, sans-serif; font-size: 6.5pt; color: #212121; }}
  h1 {{ text-align: center; font-size: 10.5pt; color: #1A237E; margin-bottom: 2mm; font-weight: bold; }}
  .meta {{ background: #E8EAF6; padding: 1.5mm 2mm; border-radius: 2px; margin-bottom: 2mm; }}
  .meta span {{ margin-right: 5mm; }}
  table {{ width: 100%; border-collapse: collapse; table-layout: fixed; }}
  th, td {{ border: 0.3pt solid #9E9E9E; padding: 0.8mm; vertical-align: top; overflow: hidden; word-break: break-word; }}
  thead th {{ background: #37474F; color: #fff; font-weight: bold; text-align: center; vertical-align: middle; }}
  .mes-hdr {{ font-size: 5.5pt; }}
  .pe {{ text-align: center; font-weight: bold; font-size: 6pt; width: 4mm; }}
  .act {{ width: 55mm; }}
  .pob {{ width: 32mm; font-size: 5.5pt; }}
  .resp {{ width: 22mm; font-size: 5.5pt; }}
  .obs {{ width: 18mm; font-size: 5.5pt; }}
  .pe-prog {{ background: #FFF9C4; }}
  .pe-exec {{ background: #C8E6C9; color: #1B5E20; }}
  .pe-both {{ background: #A5D6A7; color: #1B5E20; }}
  .footer {{ margin-top: 2mm; font-size: 5pt; color: #757575; text-align: right; }}
</style>
</head>
<body>
  <h1>CRONOGRAMA DE PROMOCI\u00d3N Y PREVENCI\u00d3N (PYP) &mdash; {cronograma.año}</h1>
  <div class=\"meta\">
    <span><b>C\u00f3digo:</b> {cronograma.codigo}</span>
    <span><b>Versi\u00f3n:</b> {cronograma.version}</span>
    <span><b>Plan:</b> {cronograma.plan_trabajo_anual_id}</span>
    {encargado_html}{aprobado_html}
  </div>
  <table>
    <thead>
      <tr>
        <th rowspan=\"2\" style=\"width:55mm\">Actividad</th>
        <th rowspan=\"2\" style=\"width:32mm\">Poblaci\u00f3n objetivo</th>
        <th rowspan=\"2\" style=\"width:22mm\">Responsable</th>
        {month_ths}
        <th rowspan=\"2\" style=\"width:18mm\">Obs.</th>
      </tr>
      <tr>{pe_ths}</tr>
    </thead>
    <tbody>
{body_rows}
    </tbody>
  </table>
  <div class=\"footer\">Generado: {now} &bull; Sistema SG-SST &bull; {cronograma.codigo}</div>
</body>
</html>"""

    pdf_bytes = weasyprint.HTML(string=html).write_pdf(
        metadata={
            "title": f"Cronograma PYP {cronograma.año}",
            "author": "Sistema SG-SST",
        },
        pdf_version=(1, 7),
        compress=True,
    )

    filename = f"cronograma_pyp_{cronograma.año}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
