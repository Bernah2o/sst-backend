"""
Plantilla estándar del Programa de Capacitaciones PR-SST-01.
Basado en el documento oficial del SG-SST.
"""

TODOS_LOS_MESES = list(range(1, 13))

NOMBRE_MESES = [
    "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
]

CICLO_LABELS = {
    "I_PLANEAR": "I. PLANEAR",
    "II_HACER": "II. HACER",
    "III_VERIFICAR": "III. VERIFICAR",
    "IV_ACTUAR": "IV. ACTUAR",
}

INDICADOR_INFO = {
    "CUMPLIMIENTO": {
        "nombre": "Cumplimiento",
        "formula": "No. de Actividades Ejecutadas / No. de Actividades Programadas x 100%",
        "meta": 90.0,
        "frecuencia": "TRIMESTRAL",
    },
    "COBERTURA": {
        "nombre": "Cobertura",
        "formula": "No. de trabajadores que participan en la actividad / No. de trabajadores programados x 100%",
        "meta": 80.0,
        "frecuencia": "TRIMESTRAL",
    },
    "EFICACIA": {
        "nombre": "Eficacia",
        "formula": "Número de evaluaciones eficaces / Número de personas evaluadas x 100%",
        "meta": 90.0,
        "frecuencia": "TRIMESTRAL",
    },
}


def get_plantilla_actividades(año: int) -> list:
    """
    Retorna la lista estándar de actividades para el Programa de Capacitaciones.
    Cada elemento incluye: ciclo, nombre, encargado, recursos, horas, meses_programados, orden.
    """
    actividades = [

        # ─── I. PLANEAR ───────────────────────────────────────────────────────
        {
            "ciclo": "I_PLANEAR",
            "nombre": "Establecer objetivos y metas",
            "encargado": "Responsable del SG-SST",
            "recursos": "Económicos, Humanos",
            "horas": 2,
            "meses_programados": [1],
        },
        {
            "ciclo": "I_PLANEAR",
            "nombre": "Establecer indicadores de gestión",
            "encargado": "Responsable del SG-SST",
            "recursos": "Económicos, Humanos",
            "horas": 2,
            "meses_programados": [1],
        },
        {
            "ciclo": "I_PLANEAR",
            "nombre": "Establecer los mecanismos para controlar el riesgo",
            "encargado": "Responsable del SG-SST",
            "recursos": "Económicos, Técnicos, Humanos",
            "horas": 4,
            "meses_programados": [1],
        },

        # ─── II. HACER ────────────────────────────────────────────────────────
        {
            "ciclo": "II_HACER",
            "nombre": "Inducción SST",
            "encargado": "Responsable del SG-SST",
            "recursos": "Económicos, Técnicos, Humanos",
            "horas": 4,
            "meses_programados": [1, 4, 7, 10],
        },
        {
            "ciclo": "II_HACER",
            "nombre": "Capacitación de Uso y manejo de extintores",
            "encargado": "Responsable del SG-SST / ARL",
            "recursos": "Económicos, Técnicos, Humanos",
            "horas": 2,
            "meses_programados": [2],
        },
        {
            "ciclo": "II_HACER",
            "nombre": "Trabajo en alturas",
            "encargado": "Responsable del SG-SST / ARL",
            "recursos": "Económicos, Técnicos, Humanos",
            "horas": 8,
            "meses_programados": [3],
        },
        {
            "ciclo": "II_HACER",
            "nombre": "Actores viales y señales de tránsito",
            "encargado": "Responsable del SG-SST / ARL",
            "recursos": "Económicos, Técnicos, Humanos",
            "horas": 2,
            "meses_programados": [2],
        },
        {
            "ciclo": "II_HACER",
            "nombre": "Conservación Auditiva",
            "encargado": "Responsable del SG-SST / ARL / IPS",
            "recursos": "Económicos, Técnicos, Humanos",
            "horas": 2,
            "meses_programados": [4],
        },
        {
            "ciclo": "II_HACER",
            "nombre": "Taller de comunicación efectiva",
            "encargado": "Responsable del SG-SST",
            "recursos": "Económicos, Humanos",
            "horas": 2,
            "meses_programados": [5],
        },
        {
            "ciclo": "II_HACER",
            "nombre": "Capacitación \"Prevención desórdenes musculo esqueléticos\"",
            "encargado": "Responsable del SG-SST / ARL",
            "recursos": "Económicos, Técnicos, Humanos",
            "horas": 2,
            "meses_programados": [3],
        },
        {
            "ciclo": "II_HACER",
            "nombre": "Capacitación \"Higiene Postural en la conducción\"",
            "encargado": "Responsable del SG-SST / ARL",
            "recursos": "Económicos, Técnicos, Humanos",
            "horas": 2,
            "meses_programados": [6],
        },
        {
            "ciclo": "II_HACER",
            "nombre": "Charla beneficio del ejercicio físico",
            "encargado": "Responsable del SG-SST",
            "recursos": "Económicos, Humanos",
            "horas": 1,
            "meses_programados": [5],
        },
        {
            "ciclo": "II_HACER",
            "nombre": "Estilos de vida saludable",
            "encargado": "Responsable del SG-SST / ARL / IPS",
            "recursos": "Económicos, Técnicos, Humanos",
            "horas": 2,
            "meses_programados": [6],
        },
        {
            "ciclo": "II_HACER",
            "nombre": "Como no convertirse una víctima de asalto y/o atraco",
            "encargado": "Responsable del SG-SST",
            "recursos": "Económicos, Humanos",
            "horas": 2,
            "meses_programados": [7],
        },
        {
            "ciclo": "II_HACER",
            "nombre": "Normas de tránsito. Lista de chequeo del vehículo, documentos del conductor y del vehículo",
            "encargado": "Responsable del SG-SST / ARL",
            "recursos": "Económicos, Técnicos, Humanos",
            "horas": 2,
            "meses_programados": [4],
        },
        {
            "ciclo": "II_HACER",
            "nombre": "Trabajo en equipo",
            "encargado": "Responsable del SG-SST",
            "recursos": "Económicos, Humanos",
            "horas": 2,
            "meses_programados": [8],
        },
        {
            "ciclo": "II_HACER",
            "nombre": "Publicación en prevención del consumo de alcohol tabaco y sustancias psicoactivas",
            "encargado": "Responsable del SG-SST / ARL",
            "recursos": "Económicos, Técnicos, Humanos",
            "horas": 2,
            "meses_programados": [9],
        },
        {
            "ciclo": "II_HACER",
            "nombre": "Capacitación: Ley 1010 Acoso Laboral",
            "encargado": "Responsable del SG-SST",
            "recursos": "Económicos, Humanos",
            "horas": 2,
            "meses_programados": [10],
        },
        {
            "ciclo": "II_HACER",
            "nombre": "Campaña sobre adecuado uso de herramientas manuales cortopunzantes y su riesgo asociado",
            "encargado": "Responsable del SG-SST / ARL",
            "recursos": "Económicos, Técnicos, Humanos",
            "horas": 2,
            "meses_programados": [11],
        },
        {
            "ciclo": "II_HACER",
            "nombre": "Publicación sobre adecuado lavado de manos y gel antibacterial",
            "encargado": "Responsable del SG-SST",
            "recursos": "Económicos, Humanos",
            "horas": 1,
            "meses_programados": [3, 9],
        },
        {
            "ciclo": "II_HACER",
            "nombre": "Capacitación sobre uso adecuado de elementos de protección personal",
            "encargado": "Responsable del SG-SST",
            "recursos": "Económicos, Técnicos, Humanos",
            "horas": 2,
            "meses_programados": [4],
        },
        {
            "ciclo": "II_HACER",
            "nombre": "Campaña de seguridad vial",
            "encargado": "Responsable del SG-SST / ARL",
            "recursos": "Económicos, Técnicos, Humanos",
            "horas": 4,
            "meses_programados": [7],
        },
        {
            "ciclo": "II_HACER",
            "nombre": "Capacitación brigadas de emergencia",
            "encargado": "Responsable del SG-SST / ARL",
            "recursos": "Económicos, Técnicos, Humanos",
            "horas": 8,
            "meses_programados": [7],
        },
        {
            "ciclo": "II_HACER",
            "nombre": "Capacitación en inspecciones planeadas y diligenciamiento de preoperacionales",
            "encargado": "Responsable del SG-SST",
            "recursos": "Económicos, Técnicos, Humanos",
            "horas": 2,
            "meses_programados": [5],
        },
        {
            "ciclo": "II_HACER",
            "nombre": "Capacitación en Manejo defensivo Legislación de transporte - Código nacional de tránsito y señalización vial - Lecciones aprendidas de accidentes e incidentes viales, Cansancio y fatiga",
            "encargado": "Responsable del SG-SST / ARL",
            "recursos": "Económicos, Técnicos, Humanos",
            "horas": 8,
            "meses_programados": [8],
        },
        {
            "ciclo": "II_HACER",
            "nombre": "Capacitación Primeros Auxilios para conductores, Orden y aseo, EPP's",
            "encargado": "Responsable del SG-SST / ARL",
            "recursos": "Económicos, Técnicos, Humanos",
            "horas": 8,
            "meses_programados": [9],
        },
        {
            "ciclo": "II_HACER",
            "nombre": "Procedimientos operativos normalizados",
            "encargado": "Responsable del SG-SST",
            "recursos": "Económicos, Técnicos, Humanos",
            "horas": 4,
            "meses_programados": [10],
        },
        {
            "ciclo": "II_HACER",
            "nombre": "Capacitación Control de Incendios para conductores, inspección de equipos, Identificación, análisis de peligros y riesgos - Aspectos e impactos ambientales - Reporte de actos y condiciones inseguros",
            "encargado": "Responsable del SG-SST / ARL",
            "recursos": "Económicos, Técnicos, Humanos",
            "horas": 4,
            "meses_programados": [11],
        },
        {
            "ciclo": "II_HACER",
            "nombre": "Mecánica Básica",
            "encargado": "Responsable del SG-SST",
            "recursos": "Económicos, Técnicos, Humanos",
            "horas": 4,
            "meses_programados": [6],
        },
        {
            "ciclo": "II_HACER",
            "nombre": "Capacitación en Transporte de Mercancías Peligrosas (Definiciones y conceptos básicos, clasificación UN, Rotulado, manejo e interpretación de hojas de seguridad y tarjetas de emergencia)",
            "encargado": "Responsable del SG-SST / ARL",
            "recursos": "Económicos, Técnicos, Humanos",
            "horas": 8,
            "meses_programados": [5],
        },
        {
            "ciclo": "II_HACER",
            "nombre": "Capacitación en manejo defensivo",
            "encargado": "Responsable del SG-SST / ARL",
            "recursos": "Económicos, Técnicos, Humanos",
            "horas": 8,
            "meses_programados": [2],
        },
        {
            "ciclo": "II_HACER",
            "nombre": "Capacitar al personal en alistamiento e inspección de vehículos",
            "encargado": "Responsable del SG-SST",
            "recursos": "Económicos, Técnicos, Humanos",
            "horas": 4,
            "meses_programados": [3],
        },
        {
            "ciclo": "II_HACER",
            "nombre": "Capacitación en trabajo en alturas (conductores)",
            "encargado": "Responsable del SG-SST / ARL",
            "recursos": "Económicos, Técnicos, Humanos",
            "horas": 8,
            "meses_programados": [12],
        },

        # ─── III. VERIFICAR ───────────────────────────────────────────────────
        {
            "ciclo": "III_VERIFICAR",
            "nombre": "Seguimiento a Indicadores",
            "encargado": "Responsable del SG-SST",
            "recursos": "Económicos, Humanos",
            "horas": 2,
            "meses_programados": [3, 6, 9, 12],
        },
        {
            "ciclo": "III_VERIFICAR",
            "nombre": "Seguimiento a las acciones tomadas frente a los hallazgos",
            "encargado": "Responsable del SG-SST",
            "recursos": "Económicos, Humanos",
            "horas": 2,
            "meses_programados": [3, 6, 9, 12],
        },

        # ─── IV. ACTUAR ───────────────────────────────────────────────────────
        {
            "ciclo": "IV_ACTUAR",
            "nombre": "Implementación de acciones correctivas y preventivas",
            "encargado": "Responsable del SG-SST",
            "recursos": "Económicos, Humanos",
            "horas": 2,
            "meses_programados": TODOS_LOS_MESES,
        },
    ]

    for idx, act in enumerate(actividades):
        act["orden"] = idx

    return actividades
