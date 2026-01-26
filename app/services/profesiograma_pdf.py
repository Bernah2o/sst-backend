from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from app.models.cargo import Cargo
from app.models.profesiograma import Profesiograma, ProfesiogramaFactor
from app.services.html_to_pdf import HTMLToPDFConverter


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _serialize_examen(pe) -> Dict[str, Any]:
    """Serializa un ProfesiogramaExamen para el reporte PDF."""
    tipo_examen = getattr(pe, "tipo_examen", None)
    nombre_examen = getattr(tipo_examen, "nombre", "") if tipo_examen else ""
    descripcion_examen = getattr(tipo_examen, "descripcion", "") if tipo_examen else ""

    tipo_eval = getattr(pe, "tipo_evaluacion", None)
    if hasattr(tipo_eval, "value"):
        tipo_eval = tipo_eval.value

    return {
        "nombre": nombre_examen,
        "descripcion": descripcion_examen,
        "tipo_evaluacion": str(tipo_eval) if tipo_eval else "",
        "periodicidad_meses": getattr(pe, "periodicidad_meses", None),
        "justificacion_periodicidad": getattr(pe, "justificacion_periodicidad", None),
        "obligatorio": getattr(pe, "obligatorio", True),
        "orden_realizacion": getattr(pe, "orden_realizacion", None),
        "normativa_base": getattr(pe, "normativa_base", None),
    }


def _serialize_factor(pf: ProfesiogramaFactor) -> Dict[str, Any]:
    fr = getattr(pf, "factor_riesgo", None)
    factor_nombre = getattr(fr, "nombre", "") if fr else ""
    factor_categoria = getattr(fr, "categoria", "") if fr else ""
    if hasattr(factor_categoria, "value"):
        factor_categoria = factor_categoria.value

    controles_esiae = []
    for c in getattr(pf, "controles_esiae", []) or []:
        controles_esiae.append(
            {
                "nivel": getattr(c, "nivel", ""),
                "medida": getattr(c, "medida", ""),
                "descripcion": getattr(c, "descripcion", ""),
                "estado_actual": getattr(c, "estado_actual", ""),
                "meta": getattr(c, "meta", ""),
            }
        )

    intervenciones = []
    for i in getattr(pf, "intervenciones", []) or []:
        intervenciones.append(
            {
                "tipo_control": getattr(i, "tipo_control", ""),
                "descripcion": getattr(i, "descripcion", ""),
                "responsable": getattr(i, "responsable", ""),
                "plazo": getattr(i, "plazo", ""),
            }
        )

    return {
        "factor_nombre": factor_nombre,
        "factor_categoria": str(factor_categoria) if factor_categoria is not None else "",
        "proceso": getattr(pf, "proceso", None),
        "actividad": getattr(pf, "actividad", None),
        "tarea": getattr(pf, "tarea", None),
        "nivel_exposicion": getattr(getattr(pf, "nivel_exposicion", None), "value", getattr(pf, "nivel_exposicion", None)),
        "tiempo_exposicion_horas": _to_float(getattr(pf, "tiempo_exposicion_horas", None)),
        "zona_lugar": getattr(pf, "zona_lugar", None),
        "tipo_peligro": getattr(pf, "tipo_peligro", None),
        "clasificacion_peligro": getattr(pf, "clasificacion_peligro", None),
        "descripcion_peligro": getattr(pf, "descripcion_peligro", None),
        "controles_existentes": getattr(pf, "controles_existentes", None),
        "fuente": getattr(pf, "fuente", None),
        "medio": getattr(pf, "medio", None),
        "individuo": getattr(pf, "individuo", None),
        "peor_consecuencia": getattr(pf, "peor_consecuencia", None),
        "requisito_legal": getattr(pf, "requisito_legal", None),
        "nd": getattr(pf, "nd", None),
        "ne": getattr(pf, "ne", None),
        "np": getattr(pf, "np", None),
        "interpretacion_np": getattr(pf, "interpretacion_np", None),
        "nc": getattr(pf, "nc", None),
        "nr": getattr(pf, "nr", None),
        "nivel_riesgo": getattr(pf, "nivel_riesgo", None),
        "color_riesgo": getattr(pf, "color_riesgo", None),
        "accion_riesgo": getattr(pf, "accion_riesgo", None),
        "aceptabilidad": getattr(pf, "aceptabilidad", None),
        "controles_esiae": controles_esiae,
        "intervenciones": intervenciones,
    }


def build_profesiograma_report_context(cargo: Cargo, profesiograma: Profesiograma) -> Dict[str, Any]:
    converter = HTMLToPDFConverter()
    logo_base64 = converter._load_logo_base64("logo_3.png")
    factors: List[Dict[str, Any]] = []
    for pf in list(getattr(profesiograma, "profesiograma_factores", []) or []):
        factors.append(_serialize_factor(pf))

    examenes: List[Dict[str, Any]] = []
    for pe in list(getattr(profesiograma, "examenes", []) or []):
        examenes.append(_serialize_examen(pe))

    context = {
        "logo_base64": logo_base64,
        "generated_at": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "cargo": {
            "id": getattr(cargo, "id", None),
            "nombre_cargo": getattr(cargo, "nombre_cargo", ""),
        },
        "profesiograma": {
            "id": getattr(profesiograma, "id", None),
            "version": getattr(profesiograma, "version", ""),
            "estado": getattr(getattr(profesiograma, "estado", ""), "value", str(getattr(profesiograma, "estado", ""))),
            "empresa": getattr(profesiograma, "empresa", None),
            "departamento": getattr(profesiograma, "departamento", None),
            "codigo_cargo": getattr(profesiograma, "codigo_cargo", None),
            "numero_trabajadores_expuestos": getattr(profesiograma, "numero_trabajadores_expuestos", None),
            "fecha_elaboracion": _fmt(getattr(profesiograma, "fecha_elaboracion", None)),
            "validado_por": getattr(profesiograma, "validado_por", None),
            "proxima_revision": _fmt(getattr(profesiograma, "proxima_revision", None)),
            "elaborado_por": getattr(profesiograma, "elaborado_por", None),
            "revisado_por": getattr(profesiograma, "revisado_por", None),
            "aprobado_por": getattr(profesiograma, "aprobado_por", None),
            "fecha_aprobacion": _fmt(getattr(profesiograma, "fecha_aprobacion", None)),
            "vigencia_meses": getattr(profesiograma, "vigencia_meses", None),
            "posicion_predominante": getattr(profesiograma, "posicion_predominante", ""),
            "descripcion_actividades": getattr(profesiograma, "descripcion_actividades", ""),
            "periodicidad_emo_meses": getattr(profesiograma, "periodicidad_emo_meses", None),
            "justificacion_periodicidad_emo": getattr(profesiograma, "justificacion_periodicidad_emo", None),
            "fecha_ultima_revision": _fmt(getattr(profesiograma, "fecha_ultima_revision", None)),
            "nivel_riesgo_cargo": getattr(getattr(profesiograma, "nivel_riesgo_cargo", ""), "value", str(getattr(profesiograma, "nivel_riesgo_cargo", ""))),
        },
        "factores": factors,
        "examenes": examenes,
    }
    return context


def generate_profesiograma_report_pdf(cargo: Cargo, profesiograma: Profesiograma) -> bytes:
    converter = HTMLToPDFConverter()
    context = build_profesiograma_report_context(cargo, profesiograma)
    html_content = converter.render_template("profesiograma_report.html", context)
    return converter.generate_pdf(html_content, ["profesiograma_report.css"])
