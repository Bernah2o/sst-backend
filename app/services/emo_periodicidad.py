from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Dict, Iterable, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.absenteeism import Absenteeism, EventType
from app.models.cargo import Cargo
from app.models.factor_riesgo import FactorRiesgo
from app.models.occupational_exam import OccupationalExam
from app.models.profesiograma import Profesiograma, ProfesiogramaFactor
from app.models.worker import Worker


@dataclass(frozen=True)
class CargoEpoStats:
    cargo_id: int
    total_trabajadores_activos: int
    menores_21: int
    mayores_igual_21: int
    antiguedad_menor_2_anios: int
    antiguedad_mayor_igual_2_anios: int
    sin_fecha_ingreso: int


def _safe_age(birth_date: Optional[date], today: date) -> Optional[int]:
    if birth_date is None:
        return None
    if birth_date > today:
        return None
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))


def _tenure_years(fecha_de_ingreso: Optional[date], today: date) -> Optional[float]:
    if fecha_de_ingreso is None:
        return None
    if fecha_de_ingreso > today:
        return None
    return (today - fecha_de_ingreso).days / 365.25


def compute_stats_from_workers(cargo_id: int, workers: Iterable[Worker], *, today: Optional[date] = None) -> CargoEpoStats:
    today = today or date.today()
    total = 0
    menores_21 = 0
    mayores_igual_21 = 0
    antig_menor_2 = 0
    antig_mayor_igual_2 = 0
    sin_fecha_ingreso = 0

    for w in workers:
        total += 1
        age = _safe_age(getattr(w, "birth_date", None), today)
        if age is not None:
            if age < 21:
                menores_21 += 1
            else:
                mayores_igual_21 += 1

        tenure = _tenure_years(getattr(w, "fecha_de_ingreso", None), today)
        if tenure is None:
            sin_fecha_ingreso += 1
        elif tenure < 2:
            antig_menor_2 += 1
        else:
            antig_mayor_igual_2 += 1

    return CargoEpoStats(
        cargo_id=cargo_id,
        total_trabajadores_activos=total,
        menores_21=menores_21,
        mayores_igual_21=mayores_igual_21,
        antiguedad_menor_2_anios=antig_menor_2,
        antiguedad_mayor_igual_2_anios=antig_mayor_igual_2,
        sin_fecha_ingreso=sin_fecha_ingreso,
    )


def compute_stats_for_cargo(db: Session, cargo_id: int) -> CargoEpoStats:
    workers = (
        db.query(Worker)
        .filter(Worker.cargo_id == cargo_id, Worker.is_active.is_(True))
        .all()
    )
    return compute_stats_from_workers(cargo_id, workers)


def suggest_periodicidad_emo_meses(stats: CargoEpoStats) -> int:
    if stats.total_trabajadores_activos <= 0:
        return 36
    if stats.menores_21 > 0:
        return 24
    if stats.antiguedad_menor_2_anios > 0:
        return 24
    if stats.sin_fecha_ingreso > 0:
        return 24
    return 36


def _first_day_of_month(d: date) -> date:
    return date(d.year, d.month, 1)


def _subtract_months(d: date, months: int) -> date:
    if months <= 0:
        return d
    year = d.year
    month = d.month - months
    while month <= 0:
        month += 12
        year -= 1
    return date(year, month, 1)


def _safe_rollback(db: Session) -> None:
    try:
        db.rollback()
    except Exception:
        return


@dataclass(frozen=True)
class AbsenteeismIndicators:
    window_start: date
    window_months: int
    total_eventos: int
    total_dias_incapacidad: int
    accidentes_trabajo: int
    enfermedades_laborales: int


def compute_absenteeism_indicators_for_cargo(
    db: Session,
    cargo_id: int,
    *,
    today: Optional[date] = None,
    window_months: int = 36,
) -> AbsenteeismIndicators:
    today = today or date.today()
    window_start = _subtract_months(_first_day_of_month(today), window_months)

    try:
        rows = (
            db.query(Absenteeism)
            .join(Worker, Worker.id == Absenteeism.worker_id)
            .filter(Worker.cargo_id == cargo_id, Absenteeism.start_date >= window_start)
            .all()
        )
    except Exception:
        _safe_rollback(db)
        rows = []

    total_eventos = len(rows)
    total_dias = sum(int(getattr(r, "disability_or_charged_days", 0) or 0) for r in rows)
    at = sum(1 for r in rows if getattr(r, "event_type", None) == EventType.ACCIDENTE_TRABAJO)
    el = sum(1 for r in rows if getattr(r, "event_type", None) == EventType.ENFERMEDAD_LABORAL)

    return AbsenteeismIndicators(
        window_start=window_start,
        window_months=window_months,
        total_eventos=total_eventos,
        total_dias_incapacidad=total_dias,
        accidentes_trabajo=at,
        enfermedades_laborales=el,
    )


@dataclass(frozen=True)
class OccupationalExamIndicators:
    window_start: date
    window_months: int
    total_examenes: int
    apto: int
    apto_con_recomendaciones: int
    no_apto: int
    requires_follow_up: int


def compute_occupational_exam_indicators_for_cargo(
    db: Session,
    cargo_id: int,
    *,
    today: Optional[date] = None,
    window_months: int = 36,
) -> OccupationalExamIndicators:
    today = today or date.today()
    window_start = _subtract_months(_first_day_of_month(today), window_months)

    try:
        exams = (
            db.query(OccupationalExam)
            .join(Worker, Worker.id == OccupationalExam.worker_id)
            .filter(
                OccupationalExam.exam_date >= window_start,
                ((OccupationalExam.cargo_id_momento_examen == cargo_id) | (Worker.cargo_id == cargo_id)),
            )
            .all()
        )
    except Exception:
        _safe_rollback(db)
        exams = []

    total = len(exams)
    apto = sum(1 for e in exams if getattr(e, "medical_aptitude_concept", None) == "apto")
    apto_rec = sum(1 for e in exams if getattr(e, "medical_aptitude_concept", None) == "apto_con_recomendaciones")
    no_apto = sum(1 for e in exams if getattr(e, "medical_aptitude_concept", None) == "no_apto")
    follow = sum(1 for e in exams if bool(getattr(e, "requires_follow_up", False)))

    return OccupationalExamIndicators(
        window_start=window_start,
        window_months=window_months,
        total_examenes=total,
        apto=apto,
        apto_con_recomendaciones=apto_rec,
        no_apto=no_apto,
        requires_follow_up=follow,
    )


@dataclass(frozen=True)
class MatrixIndicators:
    has_profesiograma: bool
    latest_profesiograma_id: Optional[int]
    latest_fecha: Optional[date]
    has_previous: bool
    is_stable_vs_previous: Optional[bool]
    factores_count: int
    programas_sve_count: int


@dataclass(frozen=True)
class MatrixRiskItem:
    factor_riesgo_id: int
    nombre: str
    categoria: Optional[str]
    nr: int
    nivel_riesgo: Optional[str]


@dataclass(frozen=True)
class MatrixRiskSummary:
    has_matrix: bool
    factores_evaluados: int
    max_nr: Optional[int]
    conteo_por_nivel: Dict[str, int]
    top_factores: Tuple[MatrixRiskItem, ...]


def compute_matrix_risk_summary_for_cargo(
    db: Session,
    cargo_id: int,
    *,
    today: Optional[date] = None,
    top_n: int = 3,
) -> MatrixRiskSummary:
    today = today or date.today()
    try:
        latest = (
            db.query(Profesiograma)
            .filter(Profesiograma.cargo_id == cargo_id)
            .order_by(Profesiograma.fecha_creacion.desc())
            .first()
        )
    except Exception:
        _safe_rollback(db)
        latest = None

    if not latest:
        return MatrixRiskSummary(
            has_matrix=False,
            factores_evaluados=0,
            max_nr=None,
            conteo_por_nivel={},
            top_factores=tuple(),
        )

    factores = list(getattr(latest, "profesiograma_factores", []) or [])
    if not factores:
        return MatrixRiskSummary(
            has_matrix=True,
            factores_evaluados=0,
            max_nr=None,
            conteo_por_nivel={},
            top_factores=tuple(),
        )

    from app.services.gtc45 import classify_nivel_riesgo, compute_nr

    items: list[MatrixRiskItem] = []
    conteo: Dict[str, int] = {}

    for pf in factores:
        nr = compute_nr(getattr(pf, "nd", None), getattr(pf, "ne", None), getattr(pf, "nc", None))
        if nr is None:
            continue
        nivel = classify_nivel_riesgo(nr)
        if nivel:
            conteo[nivel] = conteo.get(nivel, 0) + 1

        fr = getattr(pf, "factor_riesgo", None)
        nombre = getattr(fr, "nombre", None) or f"Factor {getattr(pf, 'factor_riesgo_id', '')}"
        categoria = getattr(fr, "categoria", None)
        items.append(
            MatrixRiskItem(
                factor_riesgo_id=getattr(pf, "factor_riesgo_id", 0),
                nombre=str(nombre),
                categoria=str(categoria) if categoria is not None else None,
                nr=int(nr),
                nivel_riesgo=nivel,
            )
        )

    if not items:
        return MatrixRiskSummary(
            has_matrix=True,
            factores_evaluados=0,
            max_nr=None,
            conteo_por_nivel={},
            top_factores=tuple(),
        )

    items_sorted = sorted(items, key=lambda x: x.nr, reverse=True)
    max_nr = items_sorted[0].nr
    top = tuple(items_sorted[: max(0, top_n)])
    return MatrixRiskSummary(
        has_matrix=True,
        factores_evaluados=len(items_sorted),
        max_nr=max_nr,
        conteo_por_nivel=conteo,
        top_factores=top,
    )


def compute_matrix_risk_summary_from_inputs(
    db: Session,
    factores: Iterable[Tuple[int, Optional[int], Optional[int], Optional[int]]],
    *,
    top_n: int = 3,
) -> MatrixRiskSummary:
    from app.services.gtc45 import classify_nivel_riesgo, compute_nr

    factor_ids = [fid for fid, _, _, _ in factores if fid is not None]
    factor_by_id: Dict[int, FactorRiesgo] = {}
    if factor_ids:
        try:
            rows = db.query(FactorRiesgo).filter(FactorRiesgo.id.in_(factor_ids)).all()
            factor_by_id = {f.id: f for f in rows}
        except Exception:
            _safe_rollback(db)
            factor_by_id = {}

    items: list[MatrixRiskItem] = []
    conteo: Dict[str, int] = {}

    for factor_id, nd, ne, nc in factores:
        nr = compute_nr(nd, ne, nc)
        if nr is None:
            continue
        nivel = classify_nivel_riesgo(nr)
        if nivel:
            conteo[nivel] = conteo.get(nivel, 0) + 1
        fr = factor_by_id.get(int(factor_id))
        nombre = getattr(fr, "nombre", None) if fr is not None else None
        categoria = getattr(fr, "categoria", None) if fr is not None else None
        items.append(
            MatrixRiskItem(
                factor_riesgo_id=int(factor_id),
                nombre=str(nombre) if nombre else f"Factor {factor_id}",
                categoria=str(categoria) if categoria is not None else None,
                nr=int(nr),
                nivel_riesgo=nivel,
            )
        )

    if not items:
        return MatrixRiskSummary(
            has_matrix=True,
            factores_evaluados=0,
            max_nr=None,
            conteo_por_nivel={},
            top_factores=tuple(),
        )

    items_sorted = sorted(items, key=lambda x: x.nr, reverse=True)
    max_nr = items_sorted[0].nr
    top = tuple(items_sorted[: max(0, top_n)])
    return MatrixRiskSummary(
        has_matrix=True,
        factores_evaluados=len(items_sorted),
        max_nr=max_nr,
        conteo_por_nivel=conteo,
        top_factores=top,
    )


def _factor_signature(pf: ProfesiogramaFactor) -> Tuple:
    return (
        pf.factor_riesgo_id,
        pf.proceso,
        pf.actividad,
        pf.tarea,
        pf.rutinario,
        pf.zona_lugar,
        pf.tipo_peligro,
        pf.clasificacion_peligro,
        pf.controles_existentes,
        pf.fuente,
        pf.medio,
        pf.individuo,
        pf.peor_consecuencia,
        pf.requisito_legal,
        pf.nd,
        pf.ne,
        pf.nc,
        pf.unidad_medida,
    )


def compute_matrix_indicators_for_cargo(
    db: Session,
    cargo_id: int,
    *,
    today: Optional[date] = None,
) -> MatrixIndicators:
    today = today or date.today()
    try:
        profes = (
            db.query(Profesiograma)
            .filter(Profesiograma.cargo_id == cargo_id)
            .order_by(Profesiograma.fecha_creacion.desc())
            .limit(2)
            .all()
        )
    except Exception:
        _safe_rollback(db)
        profes = []
    if not profes:
        return MatrixIndicators(
            has_profesiograma=False,
            latest_profesiograma_id=None,
            latest_fecha=None,
            has_previous=False,
            is_stable_vs_previous=None,
            factores_count=0,
            programas_sve_count=0,
        )

    latest = profes[0]
    prev = profes[1] if len(profes) > 1 else None

    latest_factores = list(getattr(latest, "profesiograma_factores", []) or [])
    latest_sig = sorted(_factor_signature(pf) for pf in latest_factores)

    stable = None
    if prev is not None:
        prev_factores = list(getattr(prev, "profesiograma_factores", []) or [])
        prev_sig = sorted(_factor_signature(pf) for pf in prev_factores)
        stable = latest_sig == prev_sig

    latest_fecha = getattr(latest, "fecha_ultima_revision", None) or getattr(latest, "fecha_creacion", None)
    if isinstance(latest_fecha, date):
        fecha_out = latest_fecha
    else:
        fecha_out = getattr(latest_fecha, "date", lambda: None)()

    programas_sve = list(getattr(latest, "programas_sve", []) or [])

    return MatrixIndicators(
        has_profesiograma=True,
        latest_profesiograma_id=latest.id,
        latest_fecha=fecha_out,
        has_previous=prev is not None,
        is_stable_vs_previous=stable,
        factores_count=len(latest_factores),
        programas_sve_count=len(programas_sve),
    )


def suggest_periodicidad_emo_meses_from_db(
    db: Session,
    cargo_id: int,
    *,
    today: Optional[date] = None,
    matrix_override: Optional[MatrixRiskSummary] = None,
) -> int:
    today = today or date.today()
    stats = compute_stats_for_cargo(db, cargo_id)

    base = suggest_periodicidad_emo_meses(stats)
    if base == 24:
        return 24

    abs_stats = compute_absenteeism_indicators_for_cargo(db, cargo_id, today=today, window_months=36)
    if abs_stats.accidentes_trabajo > 0 or abs_stats.enfermedades_laborales > 0:
        return 24

    exam_stats = compute_occupational_exam_indicators_for_cargo(db, cargo_id, today=today, window_months=36)
    if exam_stats.no_apto > 0 or exam_stats.requires_follow_up > 0:
        return 24

    matriz = compute_matrix_indicators_for_cargo(db, cargo_id, today=today)
    if matrix_override is None and stats.total_trabajadores_activos > 0 and not matriz.has_profesiograma:
        return 24
    if matriz.has_previous and matriz.is_stable_vs_previous is False:
        return 24

    riesgo_matriz = matrix_override or compute_matrix_risk_summary_for_cargo(db, cargo_id, today=today)
    if riesgo_matriz.max_nr is not None and riesgo_matriz.max_nr >= 50:
        return 24

    return 36


def generate_justificacion_periodicidad_emo(
    stats: CargoEpoStats,
    periodicidad_emo_meses: int,
    *,
    today: Optional[date] = None,
) -> str:
    today = today or date.today()
    periodicidad_label = f"{periodicidad_emo_meses} meses"

    criterios_24 = []
    criterios_36 = []
    pendientes = [
        "Cambios recientes en perfil de riesgo o ambiente laboral",
        "Hallazgos/alteraciones en evaluaciones anteriores",
        "Indicadores epidemiológicos (accidentalidad, enfermedad laboral, ausentismo) últimos 24-36 meses",
        "Programa(s) de vigilancia epidemiológica aplicable(s)",
    ]

    if stats.menores_21 > 0:
        criterios_24.append(f"Trabajadores menores de 21 años: {stats.menores_21}")
    else:
        criterios_36.append("Población trabajadora con edad ≥ 21 años (según registros disponibles)")

    if stats.antiguedad_menor_2_anios > 0:
        criterios_24.append(f"Trabajadores con antigüedad < 2 años en la función: {stats.antiguedad_menor_2_anios}")
    else:
        criterios_36.append("Antigüedad ≥ 2 años en el cargo (según registros disponibles)")

    if stats.sin_fecha_ingreso > 0:
        criterios_24.append(f"Faltan fechas de ingreso para {stats.sin_fecha_ingreso} trabajador(es) (no se soporta 36 meses sin evidencia)")

    lines = []
    lines.append(f"Justificación técnica de periodicidad de EMO ({periodicidad_label}) para cargo {stats.cargo_id}.")
    lines.append("")
    lines.append(f"Base: criterios técnicos derivados del SG-SST y Resolución 1843 de 2025 (edad, antigüedad, exposición y vigilancia).")
    lines.append(f"Fecha de análisis: {today.isoformat()}. Población expuesta considerada: {stats.total_trabajadores_activos} trabajador(es) activo(s).")
    lines.append("")
    lines.append("Criterios evaluados automáticamente (a partir de registros de trabajador):")
    if periodicidad_emo_meses == 24:
        if criterios_24:
            for c in criterios_24:
                lines.append(f"- {c}.")
        else:
            lines.append("- No se identificaron criterios automáticos que obliguen 24 meses; requiere soporte SG-SST adicional.")
    elif periodicidad_emo_meses == 36:
        if criterios_36:
            for c in criterios_36:
                lines.append(f"- {c}.")
        if criterios_24:
            for c in criterios_24:
                lines.append(f"- {c}.")
            lines.append("- Nota: con estos criterios, 36 meses podría no ser soportable sin evidencia adicional.")
    else:
        lines.append("- Periodicidad diferente a 24/36; este borrador aplica principalmente para 24 vs 36 meses.")

    lines.append("")
    lines.append("Evidencias SG-SST recomendadas para soportar la decisión (no evaluadas automáticamente en el sistema):")
    for p in pendientes:
        lines.append(f"- {p}.")

    result = "\n".join(lines).strip()
    if len(result) < 60:
        result = result + "\n\nSoporte: IPVR vigente, indicadores epidemiológicos y programas de vigilancia aplicables."
    return result


def generate_justificacion_periodicidad_emo_from_db(
    db: Session,
    cargo_id: int,
    periodicidad_emo_meses: int,
    *,
    today: Optional[date] = None,
    matrix_override: Optional[MatrixRiskSummary] = None,
    matrix_label: Optional[str] = None,
    formato: str = "breve",
) -> str:
    today = today or date.today()
    cargo_nombre: Optional[str] = None
    try:
        cargo = db.query(Cargo).filter(Cargo.id == cargo_id).first()
        cargo_nombre = getattr(cargo, "nombre_cargo", None) if cargo is not None else None
    except Exception:
        _safe_rollback(db)
        cargo_nombre = None

    stats = compute_stats_for_cargo(db, cargo_id)
    recomendada = suggest_periodicidad_emo_meses_from_db(db, cargo_id, today=today, matrix_override=matrix_override)

    window_months = 36 if periodicidad_emo_meses == 36 else 24
    abs_stats = compute_absenteeism_indicators_for_cargo(db, cargo_id, today=today, window_months=window_months)
    exam_stats = compute_occupational_exam_indicators_for_cargo(db, cargo_id, today=today, window_months=window_months)
    matriz = compute_matrix_indicators_for_cargo(db, cargo_id, today=today)
    riesgo_matriz = matrix_override or compute_matrix_risk_summary_for_cargo(db, cargo_id, today=today)

    fmt = (formato or "breve").strip().lower()
    if fmt not in ("breve", "detallado"):
        fmt = "breve"

    if fmt == "breve":
        nivel_txt = None
        if riesgo_matriz.max_nr is not None:
            from app.services.gtc45 import classify_nivel_riesgo

            nivel_txt = classify_nivel_riesgo(riesgo_matriz.max_nr)
        stable_txt = "N/D"
        if matriz.has_previous and matriz.is_stable_vs_previous is not None:
            stable_txt = "estable" if matriz.is_stable_vs_previous else "cambios"

        label = f" ({matrix_label})" if matrix_label else ""
        top_txt = "N/D"
        if riesgo_matriz.top_factores:
            top_txt = ", ".join(f"{i.nombre} (NR {i.nr})" for i in riesgo_matriz.top_factores)

        cargo_ref = f"{cargo_nombre} (ID {cargo_id})" if cargo_nombre else f"ID {cargo_id}"

        line1 = (
            f"Justificación técnica para definir periodicidad de EMO en {periodicidad_emo_meses} meses "
            f"para el cargo {cargo_ref}, con fundamento en SG-SST y Resolución 1843 de 2025."
        )
        line2 = (
            f"Soportes (según registros del sistema): población expuesta {stats.total_trabajadores_activos} trabajador(es) activo(s) "
            f"(menores de 21: {stats.menores_21}; antigüedad < 2 años: {stats.antiguedad_menor_2_anios}). "
            f"Indicadores últimos {window_months} meses: AT {abs_stats.accidentes_trabajo}, EL {abs_stats.enfermedades_laborales}; "
            f"EMO no apto {exam_stats.no_apto}, seguimientos {exam_stats.requires_follow_up}."
        )
        if riesgo_matriz.max_nr is not None:
            line3 = (
                f"Validación IPVR (GTC 45){label}: NR máximo {riesgo_matriz.max_nr}"
                f"{f' ({nivel_txt})' if nivel_txt else ''}; principales riesgos: {top_txt}. "
                f"Profesiograma en sistema: {'sí' if matriz.has_profesiograma else 'no'} ({stable_txt})."
            )
        else:
            line3 = (
                f"Validación IPVR (GTC 45){label}: no es posible calcular NR por datos incompletos (ND/NE/NC). "
                f"Profesiograma en sistema: {'sí' if matriz.has_profesiograma else 'no'} ({stable_txt})."
            )

        if periodicidad_emo_meses == recomendada:
            line4 = f"Conclusión: se define periodicidad de EMO en {periodicidad_emo_meses} meses."
        else:
            line4 = (
                f"Conclusión: con la evidencia disponible, se soporta periodicidad de EMO en {recomendada} meses; "
                f"{periodicidad_emo_meses} meses no es soportable sin evidencia adicional o ajuste del IPVR."
            )

        result = "\n".join([line1, line2, line3, line4]).strip()
        if len(result) < 60:
            result += "\nSoportes: IPVR vigente, indicadores epidemiológicos y PVE aplicables."
        return result

    lines = []
    lines.append(f"Justificación técnica de periodicidad de EMO ({periodicidad_emo_meses} meses) para cargo {cargo_id}.")
    lines.append("")
    lines.append("Marco técnico-normativo:")
    lines.append("- Criterios del SG-SST (IPVR/Profesiograma, vigilancia epidemiológica, indicadores).")
    lines.append("- Resolución 1843 de 2025 (criterios por edad/antigüedad/estado de salud y soporte documentado).")
    lines.append(f"- Fecha de análisis: {today.isoformat()}. Población expuesta considerada: {stats.total_trabajadores_activos} trabajador(es) activo(s).")
    lines.append("")
    lines.append("Resultados disponibles en el sistema (últimos {} meses desde {}):".format(abs_stats.window_months, abs_stats.window_start.isoformat()))
    lines.append(f"- Edad < 21: {stats.menores_21}; antigüedad < 2 años: {stats.antiguedad_menor_2_anios}; sin fecha de ingreso: {stats.sin_fecha_ingreso}.")
    lines.append(
        f"- Ausentismo: eventos={abs_stats.total_eventos}, días incapacidad/cargados={abs_stats.total_dias_incapacidad}, "
        f"AT={abs_stats.accidentes_trabajo}, EL={abs_stats.enfermedades_laborales}."
    )
    lines.append(
        f"- EMO registradas: total={exam_stats.total_examenes} (apto={exam_stats.apto}, "
        f"apto con recomendaciones={exam_stats.apto_con_recomendaciones}, no apto={exam_stats.no_apto}), "
        f"con seguimiento requerido={exam_stats.requires_follow_up}."
    )
    if matriz.has_profesiograma:
        stable_txt = "No evaluado" if matriz.is_stable_vs_previous is None else ("Sí" if matriz.is_stable_vs_previous else "No")
        lines.append(
            f"- IPVR/Profesiograma: profesiograma_id={matriz.latest_profesiograma_id}, factores={matriz.factores_count}, "
            f"programas SVE={matriz.programas_sve_count}, estable vs versión anterior={stable_txt}."
        )
    else:
        lines.append("- IPVR/Profesiograma: sin registros previos para el cargo en el sistema.")

    if riesgo_matriz.has_matrix and riesgo_matriz.max_nr is not None:
        resumen_top = "; ".join(
            f"{i.nombre} (NR={i.nr}{', ' + i.nivel_riesgo if i.nivel_riesgo else ''})" for i in riesgo_matriz.top_factores
        )
        label = f" ({matrix_label})" if matrix_label else ""
        lines.append(
            f"- Validación matriz (GTC 45){label}: factores evaluados={riesgo_matriz.factores_evaluados}, NR máximo={riesgo_matriz.max_nr}. "
            f"Top riesgos: {resumen_top}."
        )
    elif riesgo_matriz.has_matrix:
        label = f" ({matrix_label})" if matrix_label else ""
        lines.append(f"- Validación matriz (GTC 45){label}: no hay factores con ND/NE/NC completos para calcular NR.")
    else:
        lines.append("- Validación matriz (GTC 45): no disponible (sin profesiograma/matriz para el cargo).")

    lines.append("")
    lines.append("Criterios técnicos aplicados (según lineamientos internos 24 vs 36):")

    criterios_24 = []
    criterios_36 = []

    if stats.menores_21 > 0:
        criterios_24.append("Existe población menor de 21 años.")
    else:
        criterios_36.append("Población ≥ 21 años (según registros disponibles).")

    if stats.antiguedad_menor_2_anios > 0:
        criterios_24.append("Existe población con antigüedad < 2 años en el cargo.")
    else:
        criterios_36.append("Antigüedad ≥ 2 años (según registros disponibles).")

    if stats.sin_fecha_ingreso > 0:
        criterios_24.append("Hay trabajadores sin fecha de ingreso registrada (no se soporta 36 sin evidencia).")

    if abs_stats.accidentes_trabajo > 0 or abs_stats.enfermedades_laborales > 0:
        criterios_24.append("Se registran eventos AT/EL en el período (indicador epidemiológico relevante).")
    else:
        criterios_36.append("No se registran eventos AT/EL en el período analizado (según ausentismo).")

    if exam_stats.no_apto > 0 or exam_stats.requires_follow_up > 0:
        criterios_24.append("Se evidencian hallazgos clínicos relevantes (no apto y/o seguimientos requeridos).")
    else:
        criterios_36.append("Sin hallazgos críticos registrados en EMO (según registros disponibles).")

    if riesgo_matriz.has_matrix and riesgo_matriz.max_nr is not None:
        if riesgo_matriz.max_nr < 50:
            criterios_36.append("IPVR/Profesiograma con nivel de riesgo global tolerable (NR < 50 en matriz GTC 45).")
        else:
            criterios_24.append("IPVR/Profesiograma evidencia niveles de riesgo que requieren seguimiento más cercano (NR ≥ 50 en matriz GTC 45).")
    elif matrix_override is None and not riesgo_matriz.has_matrix and stats.total_trabajadores_activos > 0:
        criterios_24.append("No hay evidencia IPVR/Profesiograma en el sistema para soportar intervalo máximo (36 meses).")

    if matriz.has_previous and matriz.is_stable_vs_previous is False:
        criterios_24.append("El IPVR/Profesiograma presenta cambios frente a la versión anterior (perfil de riesgo no estable).")
    elif matriz.has_previous and matriz.is_stable_vs_previous is True:
        criterios_36.append("El IPVR/Profesiograma se mantiene estable frente a la versión anterior.")

    if periodicidad_emo_meses == 24:
        for c in criterios_24:
            lines.append(f"- {c}")
        if not criterios_24:
            lines.append("- No se identificaron criterios automáticos que obliguen 24 meses; requiere soporte SG-SST adicional.")
    elif periodicidad_emo_meses == 36:
        for c in criterios_36:
            lines.append(f"- {c}")
        if criterios_24:
            lines.append("- Observación: se identificaron criterios que podrían justificar 24 meses:")
            for c in criterios_24:
                lines.append(f"  - {c}")

    lines.append("")
    lines.append(f"Recomendación del sistema (con la evidencia disponible): {recomendada} meses.")
    lines.append("Evidencias SG-SST a anexar/validar (si aplica): IPVR vigente, cambios de procesos, indicadores por área, y PVE aplicables.")

    result = "\n".join(lines).strip()
    if len(result) < 60:
        result = result + "\n\nSoporte: IPVR vigente, indicadores epidemiológicos y programas de vigilancia aplicables."
    return result


def suggest_periodicidad_and_justificacion(db: Session, cargo_id: int) -> Tuple[int, CargoEpoStats, str]:
    stats = compute_stats_for_cargo(db, cargo_id)
    periodicidad = suggest_periodicidad_emo_meses(stats)
    justificacion = generate_justificacion_periodicidad_emo(stats, periodicidad)
    return periodicidad, stats, justificacion
