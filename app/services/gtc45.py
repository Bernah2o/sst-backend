from __future__ import annotations

from typing import Optional


ALLOWED_ND = {2, 6, 10}
ALLOWED_NE = {1, 2, 3, 4}
ALLOWED_NC = {10, 25, 60, 100}


def validate_nd(value: Optional[int]) -> None:
    if value is None:
        return
    if value not in ALLOWED_ND:
        raise ValueError(f"ND inválido: {value}. Valores permitidos: {sorted(ALLOWED_ND)}")


def validate_ne(value: Optional[int]) -> None:
    if value is None:
        return
    if value not in ALLOWED_NE:
        raise ValueError(f"NE inválido: {value}. Valores permitidos: {sorted(ALLOWED_NE)}")


def validate_nc(value: Optional[int]) -> None:
    if value is None:
        return
    if value not in ALLOWED_NC:
        raise ValueError(f"NC inválido: {value}. Valores permitidos: {sorted(ALLOWED_NC)}")


def compute_np(nd: Optional[int], ne: Optional[int]) -> Optional[int]:
    if nd is None or ne is None:
        return None
    try:
        validate_nd(nd)
        validate_ne(ne)
        return nd * ne
    except ValueError:
        return None


def compute_nr(nd: Optional[int], ne: Optional[int], nc: Optional[int]) -> Optional[int]:
    if nd is None or ne is None or nc is None:
        return None
    try:
        validate_nc(nc)
    except ValueError:
        return None
    np = compute_np(nd, ne)
    if np is None:
        return None
    return np * nc


def classify_nivel_intervencion(nr: Optional[int]) -> Optional[str]:
    """Clasifica el nivel de intervención según GTC 45.

    Nivel I (600-4000): Situación crítica, corrección urgente
    Nivel II (150-599): Corregir y adoptar medidas de control
    Nivel III (40-149): Mejorar si es posible
    Nivel IV (1-39): Mantener medidas de control actuales
    """
    if nr is None:
        return None
    if nr >= 600:
        return "I"
    if nr >= 150:
        return "II"
    if nr >= 40:
        return "III"
    return "IV"


def classify_aceptabilidad(nr: Optional[int]) -> Optional[str]:
    nivel = classify_nivel_intervencion(nr)
    if nivel is None:
        return None
    if nivel in ("I", "II"):
        return "No aceptable"
    if nivel == "III":
        return "Aceptable con control"
    return "Aceptable"


def classify_interpretacion_np(np: Optional[int]) -> Optional[str]:
    if np is None:
        return None
    if np >= 24:
        return "MUY ALTO"
    if np >= 10:
        return "ALTO"
    if np >= 4:
        return "MEDIO"
    return "BAJO"


def classify_nivel_riesgo(nr: Optional[int]) -> Optional[str]:
    """Clasifica el nivel de riesgo según GTC 45.

    Nivel I (600-4000): ALTO - Situación crítica
    Nivel II (150-599): MEDIO-ALTO - Corregir urgentemente
    Nivel III (40-149): MEDIO - Mejorar controles
    Nivel IV (1-39): BAJO - Aceptable
    """
    if nr is None:
        return None
    if nr >= 600:
        return "ALTO"
    if nr >= 150:
        return "MEDIO-ALTO"
    if nr >= 40:
        return "MEDIO"
    return "BAJO"


def classify_color_riesgo(nr: Optional[int]) -> Optional[str]:
    """Clasifica el color del riesgo según GTC 45.

    Nivel I (>=600): ROJO - Situación crítica
    Nivel II (150-599): NARANJA/ROJO - Urgente
    Nivel III (40-149): AMARILLO - Mejora necesaria
    Nivel IV (1-39): VERDE - Aceptable
    """
    nivel = classify_nivel_riesgo(nr)
    if nivel is None:
        return None
    if nivel == "ALTO":
        return "ROJO"
    if nivel == "MEDIO-ALTO":
        return "NARANJA"
    if nivel == "MEDIO":
        return "AMARILLO"
    return "VERDE"


def classify_accion_riesgo(nr: Optional[int]) -> Optional[str]:
    """Clasifica la acción requerida según GTC 45.

    Nivel I (>=600): Situación crítica, corrección inmediata
    Nivel II (150-599): Corregir urgentemente
    Nivel III (40-149): Mejorar si es posible, intervención a corto plazo
    Nivel IV (1-39): Mantener medidas de control actuales
    """
    nivel = classify_nivel_riesgo(nr)
    if nivel is None:
        return None
    if nivel == "ALTO":
        return "Situación crítica - Corrección inmediata"
    if nivel == "MEDIO-ALTO":
        return "Corregir urgentemente"
    if nivel == "MEDIO":
        return "Mejorar si es posible"
    return "Mantener medidas de control"


def classify_aceptabilidad_txt(nr: Optional[int]) -> Optional[str]:
    """Clasifica la aceptabilidad del riesgo según GTC 45.

    Nivel I-II (>=150): NO ACEPTABLE - Requiere intervención urgente
    Nivel III (40-149): ACEPTABLE CON CONTROLES - Requiere mejora
    Nivel IV (1-39): ACEPTABLE - Mantener vigilancia
    """
    nivel = classify_nivel_riesgo(nr)
    if nivel is None:
        return None
    if nivel in ("ALTO", "MEDIO-ALTO"):
        return "NO ACEPTABLE"
    if nivel == "MEDIO":
        return "ACEPTABLE CON CONTROLES"
    return "ACEPTABLE"

