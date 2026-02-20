"""
Datos semilla para el Presupuesto SST (AN-SST-03)
Basado en el documento "Consolidado General Presupuesto"
"""

CATEGORIAS_ORDER = [
    "MEDICINA_PREVENTIVA",
    "HIGIENE_INDUSTRIAL",
    "SEGURIDAD_INDUSTRIAL",
    "CAPACITACION",
    "INFRAESTRUCTURA",
]

CATEGORIA_LABELS = {
    "MEDICINA_PREVENTIVA": "Medicina Preventiva, del Trabajo y Otros",
    "HIGIENE_INDUSTRIAL": "Higiene Industrial y Manejo Ambiental",
    "SEGURIDAD_INDUSTRIAL": "Seguridad Industrial",
    "CAPACITACION": "Capacitación - Asesorías - Auditorías",
    "INFRAESTRUCTURA": "Infraestructura y Aseguramiento de la Operación",
}

DEFAULT_ITEMS: dict[str, list[str]] = {
    "MEDICINA_PREVENTIVA": [
        "Exámenes médicos (EMO, Paraclínicos y laboratorio)",
        "Vacunación",
        "Compra medicamentos para el botiquín",
    ],
    "HIGIENE_INDUSTRIAL": [
        "Mediciones de Higiene",
        "Punto Ecológico",
        "Tableros informativos",
    ],
    "SEGURIDAD_INDUSTRIAL": [
        "Compra Dotación Personal y EPP",
        "Compra y mantenimiento de extintores",
        "Compras equipos para atención emergencia",
        "Inspecciones puesto de trabajo",
        "Diagnóstico del riesgo psicosocial",
    ],
    "CAPACITACION": [
        "Asesorías - Capacitaciones",
        "Otros",
    ],
    "INFRAESTRUCTURA": [
        "Antideslizante escaleras",
        "Barandas de seguridad en escaleras",
        "Señalización",
        "Otros",
    ],
}


def get_default_items(categoria: str) -> list[str]:
    """Retorna la lista de actividades por defecto para una categoría."""
    return DEFAULT_ITEMS.get(categoria, [])
