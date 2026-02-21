"""
Plantilla de Estándares Mínimos de SST — Resolución 0312/2019.
Fuente de verdad para los 60 estándares, códigos por grupo y lógica de normalización.
"""
from typing import List, Dict

# ─────────────────────────────────────────────────────────────────────────────
# DATOS: Los 60 estándares con su ciclo PHVA y peso en el sistema de 100 puntos
# ─────────────────────────────────────────────────────────────────────────────
TODOS_LOS_ESTANDARES: List[Dict] = [
    # ── PLANEAR — Recursos (10 pts) ──────────────────────────────────────────
    {"codigo": "1.1.1", "ciclo": "PLANEAR", "valor": 0.5,
     "descripcion": "Responsable del Sistema de Gestión de Seguridad y Salud en el Trabajo SG-SST"},
    {"codigo": "1.1.2", "ciclo": "PLANEAR", "valor": 0.5,
     "descripcion": "Responsabilidades en el Sistema de Gestión de Seguridad y Salud en el Trabajo – SG-SST"},
    {"codigo": "1.1.3", "ciclo": "PLANEAR", "valor": 0.5,
     "descripcion": "Asignación de recursos para el Sistema de Gestión en Seguridad y Salud en el Trabajo – SG-SST"},
    {"codigo": "1.1.4", "ciclo": "PLANEAR", "valor": 0.5,
     "descripcion": "Afiliación al Sistema General de Riesgos Laborales"},
    {"codigo": "1.1.5", "ciclo": "PLANEAR", "valor": 0.5,
     "descripcion": "Identificación y clasificación de trabajadores de alto riesgo y cotización para pensión especial"},
    {"codigo": "1.1.6", "ciclo": "PLANEAR", "valor": 0.5,
     "descripcion": "Conformación COPASST / Vigía"},
    {"codigo": "1.1.7", "ciclo": "PLANEAR", "valor": 0.5,
     "descripcion": "Capacitación COPASST / Vigía"},
    {"codigo": "1.1.8", "ciclo": "PLANEAR", "valor": 0.5,
     "descripcion": "Conformación Comité de Convivencia"},
    # ── PLANEAR — Capacitación (6 pts) ───────────────────────────────────────
    {"codigo": "1.2.1", "ciclo": "PLANEAR", "valor": 2.0,
     "descripcion": "Programa Capacitación promoción y prevención PYP"},
    {"codigo": "1.2.2", "ciclo": "PLANEAR", "valor": 2.0,
     "descripcion": "Inducción y Reinducción en Sistema de Gestión de Seguridad y Salud en el Trabajo SG-SST, actividades de Promoción y Prevención PyP"},
    {"codigo": "1.2.3", "ciclo": "PLANEAR", "valor": 2.0,
     "descripcion": "Responsables del SG-SST con curso (50 horas)"},
    # ── PLANEAR — Gestión Integral (15 pts) ──────────────────────────────────
    {"codigo": "2.1.1", "ciclo": "PLANEAR", "valor": 1.0,
     "descripcion": "Política del Sistema de Gestión de Seguridad y Salud en el Trabajo SG-SST firmada, fechada y comunicada al COPASST/Vigía"},
    {"codigo": "2.2.1", "ciclo": "PLANEAR", "valor": 1.0,
     "descripcion": "Objetivos definidos, claros, medibles, cuantificables, con metas, documentados, revisados del SG-SST"},
    {"codigo": "2.3.1", "ciclo": "PLANEAR", "valor": 1.0,
     "descripcion": "Evaluación e identificación de prioridades"},
    {"codigo": "2.4.1", "ciclo": "PLANEAR", "valor": 2.0,
     "descripcion": "Plan que identifica objetivos, metas, responsabilidad, recursos con cronograma y firmado"},
    {"codigo": "2.5.1", "ciclo": "PLANEAR", "valor": 2.0,
     "descripcion": "Archivo o retención documental del Sistema de Gestión en Seguridad y Salud en el Trabajo SG-SST"},
    {"codigo": "2.6.1", "ciclo": "PLANEAR", "valor": 1.0,
     "descripcion": "Rendición sobre el desempeño"},
    {"codigo": "2.7.1", "ciclo": "PLANEAR", "valor": 2.0,
     "descripcion": "La empresa identifica la normatividad vigente del sector con la cual debe cumplir"},
    {"codigo": "2.8.1", "ciclo": "PLANEAR", "valor": 1.0,
     "descripcion": "Mecanismos de comunicación, auto reporte en Sistema de Gestión de Seguridad y Salud en el Trabajo SG-SST"},
    {"codigo": "2.9.1", "ciclo": "PLANEAR", "valor": 1.0,
     "descripcion": "Identificación, evaluación, para adquisición de productos y servicios en Sistema de Gestión de Seguridad y Salud en el Trabajo SG-SST"},
    {"codigo": "2.10.1", "ciclo": "PLANEAR", "valor": 2.0,
     "descripcion": "Evaluación y selección de proveedores y contratistas"},
    {"codigo": "2.11.1", "ciclo": "PLANEAR", "valor": 1.0,
     "descripcion": "Evaluación del impacto de cambios internos y externos en el Sistema de Gestión de Seguridad y Salud en el Trabajo SG-SST"},
    # ── HACER — Gestión de la Salud / Condiciones (9 pts) ───────────────────
    {"codigo": "3.1.1", "ciclo": "HACER", "valor": 1.0,
     "descripcion": "Descripción sociodemográfica – Diagnóstico de condiciones de salud"},
    {"codigo": "3.1.2", "ciclo": "HACER", "valor": 1.0,
     "descripcion": "Actividades de Promoción y Prevención en Salud"},
    {"codigo": "3.1.3", "ciclo": "HACER", "valor": 1.0,
     "descripcion": "Información al médico de los perfiles de cargo"},
    {"codigo": "3.1.4", "ciclo": "HACER", "valor": 1.0,
     "descripcion": "Realización de los exámenes médicos ocupacionales: pre-ingreso, periódicos"},
    {"codigo": "3.1.5", "ciclo": "HACER", "valor": 1.0,
     "descripcion": "Custodia de Historias Clínicas"},
    {"codigo": "3.1.6", "ciclo": "HACER", "valor": 1.0,
     "descripcion": "Restricciones y recomendaciones médico laborales"},
    {"codigo": "3.1.7", "ciclo": "HACER", "valor": 1.0,
     "descripcion": "Estilos de vida y entornos saludables (tabaquismo, alcoholismo, farmacodependencia y obesidad)"},
    {"codigo": "3.1.8", "ciclo": "HACER", "valor": 1.0,
     "descripcion": "Agua potable, servicios sanitarios y disposición de basuras"},
    {"codigo": "3.1.9", "ciclo": "HACER", "valor": 1.0,
     "descripcion": "Eliminación adecuada de residuos sólidos, líquidos o gaseosos"},
    # ── HACER — Registro, reporte e investigación (5 pts) ───────────────────
    {"codigo": "3.2.1", "ciclo": "HACER", "valor": 2.0,
     "descripcion": "Reporte de los accidentes de trabajo y enfermedad laboral a la ARL, EPS y Dirección Territorial del Ministerio de Trabajo"},
    {"codigo": "3.2.2", "ciclo": "HACER", "valor": 2.0,
     "descripcion": "Investigación de Accidentes, Incidentes y Enfermedad Laboral"},
    {"codigo": "3.2.3", "ciclo": "HACER", "valor": 1.0,
     "descripcion": "Registro y análisis estadístico de Incidentes, Accidentes de Trabajo y Enfermedad Laboral"},
    # ── HACER — Vigilancia de condiciones de salud (6 pts) ──────────────────
    {"codigo": "3.3.1", "ciclo": "HACER", "valor": 1.0,
     "descripcion": "Medición de la frecuencia de los Incidentes, Accidentes de Trabajo y Enfermedad Laboral"},
    {"codigo": "3.3.2", "ciclo": "HACER", "valor": 1.0,
     "descripcion": "Medición de la severidad de los Accidentes de Trabajo y Enfermedad Laboral"},
    {"codigo": "3.3.3", "ciclo": "HACER", "valor": 1.0,
     "descripcion": "Medición de la mortalidad por accidentes de trabajo"},
    {"codigo": "3.3.4", "ciclo": "HACER", "valor": 1.0,
     "descripcion": "Medición de la prevalencia de incidentes, Accidentes de Trabajo y Enfermedad Laboral"},
    {"codigo": "3.3.5", "ciclo": "HACER", "valor": 1.0,
     "descripcion": "Medición de la incidencia de Incidentes, Accidentes de Trabajo y Enfermedad Laboral"},
    {"codigo": "3.3.6", "ciclo": "HACER", "valor": 1.0,
     "descripcion": "Medición del ausentismo por incidentes, Accidentes de Trabajo y Enfermedad Laboral"},
    # ── HACER — Gestión de Peligros / Identificación (15 pts) ───────────────
    {"codigo": "4.1.1", "ciclo": "HACER", "valor": 4.0,
     "descripcion": "Metodología para la identificación, evaluación y valoración de peligros"},
    {"codigo": "4.1.2", "ciclo": "HACER", "valor": 4.0,
     "descripcion": "Identificación de peligros con participación de todos los niveles de la empresa"},
    {"codigo": "4.1.3", "ciclo": "HACER", "valor": 3.0,
     "descripcion": "Identificación y priorización de la naturaleza de los peligros (Metodología adicional, cancelogénicos y otros)"},
    {"codigo": "4.1.4", "ciclo": "HACER", "valor": 4.0,
     "descripcion": "Realización mediciones ambientales, químicos, físicos y biológicos"},
    # ── HACER — Medidas de Prevención y Control (15 pts) ────────────────────
    {"codigo": "4.2.1", "ciclo": "HACER", "valor": 2.5,
     "descripcion": "Se implementan las medidas de prevención y control de peligros"},
    {"codigo": "4.2.2", "ciclo": "HACER", "valor": 2.5,
     "descripcion": "Se verifica aplicación de las medidas de prevención y control por parte de los trabajadores"},
    {"codigo": "4.2.3", "ciclo": "HACER", "valor": 2.5,
     "descripcion": "Hay procedimientos, instructivos, fichas, protocolos"},
    {"codigo": "4.2.4", "ciclo": "HACER", "valor": 2.5,
     "descripcion": "Inspección con el COPASST o Vigía"},
    {"codigo": "4.2.5", "ciclo": "HACER", "valor": 2.5,
     "descripcion": "Mantenimiento periódico de instalaciones, equipos, máquinas, herramientas"},
    {"codigo": "4.2.6", "ciclo": "HACER", "valor": 2.5,
     "descripcion": "Entrega de Elementos de Protección Personal EPP, se verifica con contratistas y subcontratistas"},
    # ── HACER — Plan de Emergencias (10 pts) ────────────────────────────────
    {"codigo": "5.1.1", "ciclo": "HACER", "valor": 5.0,
     "descripcion": "Se cuenta con el Plan de Prevención y Preparación ante emergencias"},
    {"codigo": "5.1.2", "ciclo": "HACER", "valor": 5.0,
     "descripcion": "Brigada de prevención conformada, capacitada y dotada"},
    # ── VERIFICAR — Gestión y resultados (5 pts) ─────────────────────────────
    {"codigo": "6.1.1", "ciclo": "VERIFICAR", "valor": 1.25,
     "descripcion": "Indicadores estructura, proceso y resultado"},
    {"codigo": "6.1.2", "ciclo": "VERIFICAR", "valor": 1.25,
     "descripcion": "Las empresa adelanta auditoría por lo menos una vez al año"},
    {"codigo": "6.1.3", "ciclo": "VERIFICAR", "valor": 1.25,
     "descripcion": "Revisión anual por la alta dirección, resultados y alcance de la auditoría"},
    {"codigo": "6.1.4", "ciclo": "VERIFICAR", "valor": 1.25,
     "descripcion": "Planificación auditorías con el COPASST"},
    # ── ACTUAR — Mejoramiento (10 pts) ───────────────────────────────────────
    {"codigo": "7.1.1", "ciclo": "ACTUAR", "valor": 2.5,
     "descripcion": "Definir acciones de Promoción y Prevención con base en resultados del Sistema de Gestión de Seguridad y Salud en el Trabajo SG-SST"},
    {"codigo": "7.1.2", "ciclo": "ACTUAR", "valor": 2.5,
     "descripcion": "Toma de medidas correctivas, preventivas y de mejora"},
    {"codigo": "7.1.3", "ciclo": "ACTUAR", "valor": 2.5,
     "descripcion": "Ejecución de acciones preventivas, correctivas y de mejora de la investigación de incidentes, accidentes de trabajo y enfermedad laboral"},
    {"codigo": "7.1.4", "ciclo": "ACTUAR", "valor": 2.5,
     "descripcion": "Implementar medidas y acciones correctivas de autoridades y de ARL"},
]

# ─────────────────────────────────────────────────────────────────────────────
# GRUPOS: subconjuntos aplicables según tamaño de empresa y nivel de riesgo
# ─────────────────────────────────────────────────────────────────────────────

# < 10 trabajadores, Riesgo I/II/III
CODIGOS_GRUPO_7: List[str] = [
    "1.1.1", "1.1.4", "1.2.1", "2.4.1", "3.1.4", "4.1.1", "4.2.1",
]

# 11-50 trabajadores, Riesgo I/II/III
CODIGOS_GRUPO_21: List[str] = [
    "1.1.1", "1.1.4", "1.1.6", "1.1.8",
    "1.2.1", "2.1.1", "2.4.1", "2.5.1",
    "3.1.1", "3.1.2", "3.1.4", "3.1.6",
    "3.2.1", "3.2.2",
    "3.3.1", "3.3.2", "3.3.3",
    "4.1.1", "4.1.2", "4.2.1", "4.2.5",
]


# ─────────────────────────────────────────────────────────────────────────────
# LÓGICA
# ─────────────────────────────────────────────────────────────────────────────

def determinar_grupo(num_trabajadores: int, nivel_riesgo: str) -> str:
    """Retorna el GrupoEstandar según Resolución 0312/2019."""
    if nivel_riesgo in ("IV", "V"):
        return "GRUPO_60"
    if num_trabajadores <= 10:
        return "GRUPO_7"
    elif num_trabajadores <= 50:
        return "GRUPO_21"
    else:
        return "GRUPO_60"


def _normalizar_pesos(estandares: List[Dict]) -> List[Dict]:
    """Escala los pesos de un subconjunto para que sumen 100."""
    suma_total = sum(e["valor"] for e in estandares)
    resultado = []
    for est in estandares:
        ajustado = round((est["valor"] / suma_total) * 100, 4)
        resultado.append({**est, "valor_ajustado": ajustado})
    return resultado


def get_plantilla_respuestas(grupo: str) -> List[Dict]:
    """
    Retorna la lista ordenada de ítems lista para insertar como AutoevaluacionRespuesta.
    Cada dict incluye: codigo, ciclo, descripcion, valor (original), valor_ajustado, orden.
    """
    if grupo == "GRUPO_60":
        # Los pesos ya suman 100; valor_ajustado = valor original
        return [
            {**e, "valor_ajustado": e["valor"], "orden": idx}
            for idx, e in enumerate(TODOS_LOS_ESTANDARES)
        ]

    codigos = CODIGOS_GRUPO_7 if grupo == "GRUPO_7" else CODIGOS_GRUPO_21
    # Preservar el orden definido en TODOS_LOS_ESTANDARES
    subset = [e for e in TODOS_LOS_ESTANDARES if e["codigo"] in codigos]
    normalizados = _normalizar_pesos(subset)
    return [
        {**e, "orden": idx}
        for idx, e in enumerate(normalizados)
    ]


def calcular_puntajes(respuestas: list) -> dict:
    """
    Recalcula los scores cacheados a partir de los objetos AutoevaluacionRespuesta.
    Retorna dict con claves: puntaje_total, puntaje_planear, puntaje_hacer,
    puntaje_verificar, puntaje_actuar, nivel_cumplimiento.
    """
    totales: Dict[str, float] = {
        "PLANEAR": 0.0, "HACER": 0.0, "VERIFICAR": 0.0, "ACTUAR": 0.0
    }
    for r in respuestas:
        ciclo_val = r.ciclo.value if hasattr(r.ciclo, "value") else str(r.ciclo)
        cumpl_val = r.cumplimiento.value if hasattr(r.cumplimiento, "value") else str(r.cumplimiento)
        if cumpl_val in ("cumple_totalmente", "no_aplica"):
            pts = r.valor_maximo_ajustado
        else:
            pts = 0.0
        totales[ciclo_val] = totales.get(ciclo_val, 0.0) + pts

    total = sum(totales.values())
    if total < 60:
        nivel = "critico"
    elif total <= 85:
        nivel = "moderadamente_aceptable"
    else:
        nivel = "aceptable"

    return {
        "puntaje_total":     round(total, 2),
        "puntaje_planear":   round(totales.get("PLANEAR", 0.0), 2),
        "puntaje_hacer":     round(totales.get("HACER", 0.0), 2),
        "puntaje_verificar": round(totales.get("VERIFICAR", 0.0), 2),
        "puntaje_actuar":    round(totales.get("ACTUAR", 0.0), 2),
        "nivel_cumplimiento": nivel,
    }
