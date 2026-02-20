from typing import Any, List, Optional
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    Query,
    Request,
    UploadFile,
    File,
)
from fastapi.responses import RedirectResponse, FileResponse, StreamingResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func
from datetime import date, timedelta, datetime
import os
import uuid
from pathlib import Path
import requests
import io
import httpx
import tempfile

from app.database import get_db
from app.services.s3_storage import s3_service
from app.services.html_to_pdf import HTMLToPDFConverter
from app.dependencies import (
    get_current_user,
    require_admin,
    require_supervisor_or_admin,
)
from app.models.user import User
from app.models.worker import Worker
from app.models.occupational_exam import OccupationalExam
from app.models.cargo import Cargo
from app.models.notification_acknowledgment import NotificationAcknowledgment
from app.models.admin_config import Programas
from app.schemas.occupational_exam import (
    OccupationalExamCreate,
    OccupationalExamUpdate,
    OccupationalExamResponse,
    OccupationalExamListResponse,
)
from app.schemas.common import MessageResponse, PaginatedResponse
from app.models.seguimiento import Seguimiento, EstadoSeguimiento, ValoracionRiesgo
from app.models.profesiograma import Profesiograma, ProfesiogramaFactor, ProfesiogramaEstado

router = APIRouter()

# Mapeo de exam_type a etiquetas legibles
EXAM_TYPE_LABELS = {
    "INGRESO": "Examen de Ingreso",
    "PERIODICO": "Examen Periódico",
    "REINTEGRO": "Examen de Reintegro",
    "RETIRO": "Examen de Retiro",
}


@router.get("/", response_model=PaginatedResponse[OccupationalExamResponse])
@router.get("", response_model=PaginatedResponse[OccupationalExamResponse])
async def get_occupational_exams(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    exam_type: Optional[str] = Query(None, description="Filtro por tipo de examen (INGRESO, PERIODICO, REINTEGRO, RETIRO)"),
    result: Optional[str] = Query(None),
    worker_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    next_exam_status: Optional[str] = Query(None, description="Filtro por próximo examen: 'proximos' (próximos 30 días), 'vencidos' (ya vencidos)"),
    next_exam_year: Optional[int] = Query(None, description="Filtro por año del próximo examen (ej: 2026)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin),
) -> Any:
    """
    Obtener lista paginada de exámenes ocupacionales con filtros
    """
    # Calculate offset
    skip = (page - 1) * limit

    # Base query
    query = db.query(OccupationalExam)
    
    # 1. Optimizar consulta de conteo (evitar joins innecesarios)
    count_query = db.query(func.count(OccupationalExam.id))
    
    # Apply filters to both
    if exam_type:
        query = query.filter(OccupationalExam.exam_type == exam_type)
        count_query = count_query.filter(OccupationalExam.exam_type == exam_type)

    if result:
        result_mapping = {
            "apto": "apto",
            "apto_con_restricciones": "apto_con_recomendaciones",
            "no_apto": "no_apto",
        }
        medical_aptitude = result_mapping.get(result)
        if medical_aptitude:
            query = query.filter(OccupationalExam.medical_aptitude_concept == medical_aptitude)
            count_query = count_query.filter(OccupationalExam.medical_aptitude_concept == medical_aptitude)

    if worker_id:
        query = query.filter(OccupationalExam.worker_id == worker_id)
        count_query = count_query.filter(OccupationalExam.worker_id == worker_id)

    if search:
        # Solo unir Worker si hay búsqueda
        query = query.join(Worker, OccupationalExam.worker_id == Worker.id).filter(
            or_(
                Worker.first_name.ilike(f"%{search}%"),
                Worker.last_name.ilike(f"%{search}%"),
                Worker.document_number.ilike(f"%{search}%"),
            )
        )
        count_query = count_query.join(Worker, OccupationalExam.worker_id == Worker.id).filter(
            or_(
                Worker.first_name.ilike(f"%{search}%"),
                Worker.last_name.ilike(f"%{search}%"),
                Worker.document_number.ilike(f"%{search}%"),
            )
        )

    # Filtro por estado del próximo examen y/o por año (calculado con SQL)
    if next_exam_status in ("proximos", "vencidos") or next_exam_year:
        from sqlalchemy import case, extract
        today = date.today()
        # Unir con Worker y Cargo si no se hizo antes
        if not search:
            query = query.join(Worker, OccupationalExam.worker_id == Worker.id)
            count_query = count_query.join(Worker, OccupationalExam.worker_id == Worker.id)
        query = query.outerjoin(Cargo, Worker.cargo_id == Cargo.id)
        count_query = count_query.outerjoin(Cargo, Worker.cargo_id == Cargo.id)

        # Calcular next_exam_date usando CASE + interval (PostgreSQL)
        next_exam_expr = case(
            (Cargo.periodicidad_emo == "semestral", OccupationalExam.exam_date + timedelta(days=180)),
            (Cargo.periodicidad_emo == "bianual", OccupationalExam.exam_date + timedelta(days=730)),
            else_=OccupationalExam.exam_date + timedelta(days=365),
        )

        if next_exam_status == "proximos":
            # Próximos 30 días: next_exam_date entre hoy y hoy+30
            query = query.filter(
                and_(next_exam_expr >= today, next_exam_expr <= today + timedelta(days=30))
            )
            count_query = count_query.filter(
                and_(next_exam_expr >= today, next_exam_expr <= today + timedelta(days=30))
            )
        elif next_exam_status == "vencidos":
            # Vencidos: next_exam_date < hoy
            query = query.filter(next_exam_expr < today)
            count_query = count_query.filter(next_exam_expr < today)

        if next_exam_year:
            # Filtrar por año del próximo examen calculado
            query = query.filter(extract("year", next_exam_expr) == next_exam_year)
            count_query = count_query.filter(extract("year", next_exam_expr) == next_exam_year)

    # Get total count
    total = count_query.scalar()

    # 2. Carga ansiosa para el query principal
    query = query.options(
        joinedload(OccupationalExam.worker).joinedload(Worker.cargo_obj)
    )

    # Apply pagination and ordering
    results = (
        query.order_by(OccupationalExam.exam_date.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    # 3. Optimización N+1: Pre-cargar Profesiogramas y Factores en bloque
    # Identificar qué cargos necesitan factores de riesgo (aquellos que no los tienen en BD)
    cargos_needed = set()
    for exam in results:
        if not exam.factores_riesgo_evaluados:
            worker = exam.worker
            if worker:
                if worker.cargo_id:
                    cargos_needed.add(worker.cargo_id)
    
    prof_map = {}
    if cargos_needed:
        # Buscar profesiogramas activos para estos cargos
        active_profs = (
            db.query(Profesiograma)
            .filter(
                Profesiograma.cargo_id.in_(list(cargos_needed)),
                Profesiograma.estado == ProfesiogramaEstado.ACTIVO
            )
            .options(
                joinedload(Profesiograma.profesiograma_factores).joinedload(ProfesiogramaFactor.factor_riesgo)
            )
            .all()
        )
        # Mapear por cargo_id
        for p in active_profs:
            prof_map[p.cargo_id] = p

    # 4. Pre-cargar seguimientos en bloque para evitar N+1 desde el frontend
    exam_ids = [exam.id for exam in results]
    seguimiento_exam_ids = set()
    if exam_ids:
        seguimiento_rows = (
            db.query(Seguimiento.occupational_exam_id)
            .filter(Seguimiento.occupational_exam_id.in_(exam_ids))
            .all()
        )
        seguimiento_exam_ids = {row[0] for row in seguimiento_rows}

    # Enrich exam data with worker information (sin queries adicionales dentro del loop)
    enriched_exams = []
    for exam in results:
        worker = exam.worker
        cargo = worker.cargo_obj if worker else None
        
        # Fallback de cargo si no hay cargo_id pero hay position (solo si es necesario)
        if not cargo and worker and worker.position:
            # Esta parte aún podría causar un query por cada fila sin cargo_id
            # pero asumimos que la mayoría sí tiene cargo_id
            cargo = db.query(Cargo).filter(Cargo.nombre_cargo == worker.position).first()
        
        periodicidad = cargo.periodicidad_emo if cargo else "anual"

        if periodicidad == "semestral":
            next_exam_date = exam.exam_date + timedelta(days=180)
        elif periodicidad == "bianual":
            next_exam_date = exam.exam_date + timedelta(days=730)
        else:
            next_exam_date = exam.exam_date + timedelta(days=365)

        # ---------------------------------------------------------------------
        # Lógica de fallback para datos faltantes (producción / legacy)
        # ---------------------------------------------------------------------
        
        # 1. Calcular duración del cargo si no existe
        duracion = exam.duracion_cargo_actual_meses
        if duracion is None and worker and worker.fecha_de_ingreso:
            try:
                # Calcular diferencia en meses
                months_diff = (exam.exam_date.year - worker.fecha_de_ingreso.year) * 12 + (exam.exam_date.month - worker.fecha_de_ingreso.month)
                if exam.exam_date.day < worker.fecha_de_ingreso.day:
                    months_diff -= 1
                duracion = max(0, months_diff)
            except Exception:
                pass

        # 2. Traer factores de riesgo del profesiograma si no existen
        factores = exam.factores_riesgo_evaluados
        if not factores and cargo:
            try:
                profesiograma = prof_map.get(cargo.id)
                
                if profesiograma:
                    risk_factors_list = []
                    for pf in profesiograma.profesiograma_factores:
                        risk_factors_list.append({
                            "factor_riesgo_id": pf.factor_riesgo_id,
                            "nombre": pf.factor_riesgo.nombre,
                            "codigo": pf.factor_riesgo.codigo,
                            "categoria": pf.factor_riesgo.categoria,
                            "nivel_exposicion": pf.nivel_exposicion,
                            "tiempo_exposicion_horas": float(pf.tiempo_exposicion_horas) if pf.tiempo_exposicion_horas else 0,
                        })
                    factores = risk_factors_list
            except Exception as e:
                print(f"Error fetching legacy factors: {e}")

        # ---------------------------------------------------------------------

        # Mapear medical_aptitude_concept a result legacy
        result_mapping = {
            "apto": "apto",
            "apto_con_recomendaciones": "apto_con_restricciones",
            "no_apto": "no_apto",
        }

        exam_dict = {
            "id": exam.id,
            "worker_id": exam.worker_id,
            "worker_name": worker.full_name if worker else None,
            "worker_document": worker.document_number if worker else None,
            "worker_position": worker.position if worker else None,
            "worker_hire_date": (
                worker.fecha_de_ingreso.isoformat()
                if worker and worker.fecha_de_ingreso
                else None
            ),

            "exam_type": exam.exam_type,
            "exam_date": exam.exam_date.isoformat(),
            "departamento": exam.departamento,
            "ciudad": exam.ciudad,
            "duracion_cargo_actual_meses": duracion,
            "factores_riesgo_evaluados": factores,
            "cargo_id_momento_examen": exam.cargo_id_momento_examen,
            "programa": exam.programa,
            "occupational_conclusions": exam.occupational_conclusions,
            "preventive_occupational_behaviors": exam.preventive_occupational_behaviors,
            "general_recommendations": exam.general_recommendations,
            "medical_aptitude_concept": exam.medical_aptitude_concept,
            "observations": exam.observations,
            "examining_doctor": exam.examining_doctor,
            "medical_center": exam.medical_center,
            "pdf_file_path": exam.pdf_file_path,
            "requires_follow_up": exam.requires_follow_up or False,
            "supplier_id": exam.supplier_id,
            "doctor_id": exam.doctor_id,
            "next_exam_date": next_exam_date.isoformat(),
            # Campos legacy para compatibilidad con el frontend
            "status": "realizado",
            "result": result_mapping.get(exam.medical_aptitude_concept, "pendiente"),
            "restrictions": (
                exam.general_recommendations
                if exam.medical_aptitude_concept == "apto_con_recomendaciones"
                else None
            ),
            "created_at": exam.created_at.isoformat(),
            "updated_at": exam.updated_at.isoformat(),
            "has_seguimiento": exam.id in seguimiento_exam_ids,
        }
        enriched_exams.append(exam_dict)

    # Calculate pagination info
    pages = (total + limit - 1) // limit
    has_next = page < pages
    has_prev = page > 1

    return {
        "items": enriched_exams,
        "total": total,
        "page": page,
        "size": limit,
        "pages": pages,
        "has_next": has_next,
        "has_prev": has_prev,
    }


@router.get("/calculate-next-exam-date/{worker_id}")
async def calculate_next_exam_date(
    worker_id: int,
    exam_date: str = Query(..., description="Fecha del examen en formato YYYY-MM-DD"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin),
) -> Any:
    """
    Calcular la fecha del próximo examen basado en el trabajador y fecha del examen
    """
    try:
        from datetime import datetime

        # Obtener información del trabajador
        worker = db.query(Worker).filter(Worker.id == worker_id).first()
        if not worker:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Trabajador no encontrado"
            )

        # Obtener cargo del trabajador
        cargo = None
        if getattr(worker, "cargo_id", None):
            cargo = db.query(Cargo).filter(Cargo.id == worker.cargo_id).first()
        if not cargo:
            cargo = db.query(Cargo).filter(Cargo.nombre_cargo == worker.position).first()

        # Convertir la fecha del examen
        try:
            exam_date_obj = datetime.strptime(exam_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Formato de fecha inválido. Use YYYY-MM-DD",
            )

        # Calcular fecha del próximo examen basado en la periodicidad del cargo
        periodicidad = cargo.periodicidad_emo if cargo else "anual"

        if periodicidad == "semestral":
            next_exam_date = exam_date_obj + timedelta(days=180)  # 6 meses
        elif periodicidad == "bianual":
            next_exam_date = exam_date_obj + timedelta(days=730)  # 2 años
        else:  # anual por defecto
            next_exam_date = exam_date_obj + timedelta(days=365)  # 1 año

        # Obtener factores de riesgo del profesiograma activo
        risk_factors = []
        if cargo:
            profesiograma = db.query(Profesiograma).filter(
                Profesiograma.cargo_id == cargo.id,
                Profesiograma.estado == ProfesiogramaEstado.ACTIVO
            ).order_by(Profesiograma.version.desc()).first()

            if profesiograma:
                factors = db.query(ProfesiogramaFactor).options(
                    joinedload(ProfesiogramaFactor.factor_riesgo)
                ).filter(ProfesiogramaFactor.profesiograma_id == profesiograma.id).all()
                
                for f in factors:
                    risk_factors.append({
                        "nombre": f.factor_riesgo.nombre,
                        "categoria": f.factor_riesgo.categoria,
                        "nivel_exposicion": f.nivel_exposicion,
                        "tiempo_exposicion_horas": float(f.tiempo_exposicion_horas) if f.tiempo_exposicion_horas else 0,
                    })

        return {
            "next_exam_date": next_exam_date.isoformat(),
            "periodicidad": periodicidad,
            "worker_name": worker.full_name,
            "worker_position": worker.position,
            "cargo_name": cargo.nombre_cargo if cargo else "No especificado",
            "risk_factors": risk_factors
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error calculando fecha del próximo examen: {str(e)}",
        )


@router.post("/", response_model=OccupationalExamResponse)
@router.post("", response_model=OccupationalExamResponse)
async def create_occupational_exam(
    exam_data: OccupationalExamCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin),
) -> Any:
    """
    Crear un nuevo examen ocupacional
    """
    # Verify worker exists
    worker = db.query(Worker).filter(Worker.id == exam_data.worker_id).first()
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Trabajador no encontrado"
        )

    data = exam_data.dict()

    if not data.get("departamento") and getattr(worker, "department", None):
        data["departamento"] = worker.department
    if not data.get("ciudad") and getattr(worker, "city", None):
        data["ciudad"] = worker.city
    if not data.get("cargo_id_momento_examen") and getattr(worker, "cargo_id", None):
        data["cargo_id_momento_examen"] = worker.cargo_id

    # Calcular duración del cargo actual automáticamente (Art. 15)
    # Se usa la fecha de ingreso del trabajador y la fecha del examen
    if getattr(worker, "fecha_de_ingreso", None) and data.get("exam_date"):
        try:
            # exam_date puede ser date o str dependiendo del origen
            exam_dt = data["exam_date"]
            if isinstance(exam_dt, str):
                exam_dt = datetime.strptime(exam_dt, "%Y-%m-%d").date()
            
            # Calcular diferencia en meses: (year_diff * 12) + month_diff
            months_diff = (exam_dt.year - worker.fecha_de_ingreso.year) * 12 + (exam_dt.month - worker.fecha_de_ingreso.month)
            # Si el día del examen es menor al día de ingreso, restar un mes (no ha cumplido el mes completo)
            if exam_dt.day < worker.fecha_de_ingreso.day:
                months_diff -= 1
            
            # Asegurar que no sea negativo
            data["duracion_cargo_actual_meses"] = max(0, months_diff)
        except Exception as e:
            print(f"Error calculando duración del cargo: {e}")
            # Si falla el cálculo, se respeta el valor enviado o None

    # Auto-poblar factores de riesgo desde el profesiograma (Art. 15)
    worker_cargo_id = getattr(worker, "cargo_id", None)
    # Si no tiene cargo_id directo, intentar buscar por nombre de posición (legacy)
    cargo_obj = None
    if worker_cargo_id:
        cargo_obj = db.query(Cargo).filter(Cargo.id == worker_cargo_id).first()
    elif worker.position:
         cargo_obj = db.query(Cargo).filter(Cargo.nombre_cargo == worker.position).first()
    
    if cargo_obj:
        profesiograma = (
            db.query(Profesiograma)
            .filter(
                Profesiograma.cargo_id == cargo_obj.id,
                Profesiograma.estado == ProfesiogramaEstado.ACTIVO
            )
            .order_by(Profesiograma.version.desc())
            .first()
        )
        
        if profesiograma:
            factors = (
                db.query(ProfesiogramaFactor)
                .options(joinedload(ProfesiogramaFactor.factor_riesgo))
                .filter(ProfesiogramaFactor.profesiograma_id == profesiograma.id)
                .all()
            )
            
            risk_factors_list = []
            for pf in factors:
                risk_factors_list.append({
                    "factor_riesgo_id": pf.factor_riesgo_id,
                    "nombre": pf.factor_riesgo.nombre,
                    "codigo": pf.factor_riesgo.codigo,
                    "categoria": pf.factor_riesgo.categoria,
                    "nivel_exposicion": pf.nivel_exposicion,
                    "tiempo_exposicion_horas": float(pf.tiempo_exposicion_horas) if pf.tiempo_exposicion_horas else 0,
                })
            
            # Sobrescribir siempre con los datos del profesiograma
            data["factores_riesgo_evaluados"] = risk_factors_list
            print(f"DEBUG: Auto-populated {len(risk_factors_list)} risk factors from Profesiograma {profesiograma.id}")
        else:
             # Si no hay profesiograma activo, lista vacía o lo que venga (pero preferiblemente vacío para consistencia)
             if "factores_riesgo_evaluados" not in data:
                 data["factores_riesgo_evaluados"] = []
    else:
        if "factores_riesgo_evaluados" not in data:
             data["factores_riesgo_evaluados"] = []

    required_fields = [
        "departamento",
        "ciudad",
        # "duracion_cargo_actual_meses", # Ya no es obligatorio que venga en el payload si se calcula
        # "factores_riesgo_evaluados", # Ya no es obligatorio en payload, se calcula
        "cargo_id_momento_examen",
    ]
    missing = [k for k in required_fields if not data.get(k)]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Campos obligatorios faltantes (Art. 15)", "campos_faltantes": missing},
        )

    # Validación relajada: Si se calcularon factores, bien. Si no, permitir vacío si no hay profesiograma.
    # El usuario pidió que fuera read-only desde profesiograma, así que confiamos en la lógica de arriba.
    # if not isinstance(data.get("factores_riesgo_evaluados"), list) or len(data["factores_riesgo_evaluados"]) == 0:
    #    # Ya no lanzamos error aquí para permitir casos sin profesiograma o sin riesgos definidos aún
    #    pass

    exam = OccupationalExam(**data)
    db.add(exam)
    db.commit()
    db.refresh(exam)

    # Crear seguimiento automáticamente si requires_follow_up es True
    if exam.requires_follow_up:
        print(f"DEBUG: Creando seguimiento automático para examen nuevo {exam.id}")
        # Verificar si ya existe un seguimiento para este examen
        existing_seguimiento = (
            db.query(Seguimiento)
            .filter(Seguimiento.occupational_exam_id == exam.id)
            .first()
        )

        if not existing_seguimiento:
            # Obtener el programa, usando el del examen o buscar uno activo por defecto
            programa_name = None
            if exam.programa and exam.programa.strip():
                programa_name = exam.programa
            else:
                # Buscar un programa activo en la base de datos
                active_programa = (
                    db.query(Programas).filter(Programas.activo == True).first()
                )
                if active_programa:
                    programa_name = active_programa.nombre_programa
                else:
                    # Si no hay programas activos, usar un valor por defecto
                    programa_name = "Seguimiento Médico Ocupacional"

            print(f"DEBUG: Programa a usar para el seguimiento: {programa_name}")

            # Determinar valoración de riesgo basada en el concepto médico
            valoracion_riesgo = None
            if exam.medical_aptitude_concept == "no_apto":
                valoracion_riesgo = ValoracionRiesgo.ALTO
            elif exam.medical_aptitude_concept == "apto_con_recomendaciones":
                valoracion_riesgo = ValoracionRiesgo.MEDIO
            else:  # apto
                valoracion_riesgo = ValoracionRiesgo.BAJO

            # Construir observación general con información del examen
            observacion_parts = []
            if exam.examining_doctor:
                observacion_parts.append(f"Médico examinador: {exam.examining_doctor}")
            if exam.medical_center:
                observacion_parts.append(f"Centro médico: {exam.medical_center}")
            exam_type_label = EXAM_TYPE_LABELS.get(exam.exam_type, exam.exam_type or "Desconocido")
            observacion_parts.append(f"Tipo de examen: {exam_type_label}")

            observacion_completa = (
                "\n".join(observacion_parts) if observacion_parts else None
            )

            # Crear nuevo seguimiento con todos los datos del examen
            seguimiento_data = {
                "worker_id": worker.id,
                "occupational_exam_id": exam.id,
                "programa": programa_name,
                "nombre_trabajador": worker.full_name,
                "cedula": worker.document_number,
                "cargo": worker.position or "No especificado",
                "fecha_ingreso": worker.fecha_de_ingreso,
                "fecha_inicio": exam.exam_date,
                "estado": EstadoSeguimiento.INICIADO,
                "valoracion_riesgo": valoracion_riesgo,
                "motivo_inclusion": f"Seguimiento requerido por examen ocupacional del {exam.exam_date.strftime('%d/%m/%Y')}. Concepto médico: {exam.medical_aptitude_concept.replace('_', ' ').title()}.",
                "observacion": observacion_completa,
                # Campos copiados directamente del examen
                "conclusiones_ocupacionales": exam.occupational_conclusions,
                "conductas_ocupacionales_prevenir": exam.preventive_occupational_behaviors,
                "recomendaciones_generales": exam.general_recommendations,
                "observaciones_examen": exam.observations,
                "comentario": f"Seguimiento iniciado automáticamente desde examen ocupacional ID {exam.id}",
            }

            print(f"DEBUG: Datos del seguimiento: {seguimiento_data}")
            db_seguimiento = Seguimiento(**seguimiento_data)
            db.add(db_seguimiento)
            db.commit()
            db.refresh(db_seguimiento)
            print(f"DEBUG: Seguimiento creado exitosamente con ID: {db_seguimiento.id}")

    # Calcular fecha del próximo examen basado en la periodicidad del cargo
    cargo = None
    if getattr(worker, "cargo_id", None):
        cargo = db.query(Cargo).filter(Cargo.id == worker.cargo_id).first()
    if not cargo:
        cargo = db.query(Cargo).filter(Cargo.nombre_cargo == worker.position).first()
    periodicidad = cargo.periodicidad_emo if cargo else "anual"

    if periodicidad == "semestral":
        next_exam_date = exam.exam_date + timedelta(days=180)  # 6 meses
    elif periodicidad == "bianual":
        next_exam_date = exam.exam_date + timedelta(days=730)  # 2 años
    else:  # anual por defecto
        next_exam_date = exam.exam_date + timedelta(days=365)  # 1 año

    # Mapear medical_aptitude_concept a result legacy
    result_mapping = {
        "apto": "apto",
        "apto_con_recomendaciones": "apto_con_restricciones",
        "no_apto": "no_apto",
    }

    # Crear respuesta enriquecida con datos del trabajador
    exam_dict = {
        "id": exam.id,
        "exam_type": exam.exam_type,
        "exam_date": exam.exam_date,
        "departamento": exam.departamento,
        "ciudad": exam.ciudad,
        "duracion_cargo_actual_meses": exam.duracion_cargo_actual_meses,
        "factores_riesgo_evaluados": exam.factores_riesgo_evaluados,
        "cargo_id_momento_examen": exam.cargo_id_momento_examen,
        "programa": exam.programa,
        "occupational_conclusions": exam.occupational_conclusions,
        "preventive_occupational_behaviors": exam.preventive_occupational_behaviors,
        "general_recommendations": exam.general_recommendations,
        "medical_aptitude_concept": exam.medical_aptitude_concept,
        "observations": exam.observations,
        "examining_doctor": exam.examining_doctor,
        "medical_center": exam.medical_center,
        "pdf_file_path": exam.pdf_file_path,
        "requires_follow_up": exam.requires_follow_up or False,
        "supplier_id": exam.supplier_id,
        "doctor_id": exam.doctor_id,
        "worker_id": exam.worker_id,
        "worker_name": worker.full_name if worker else None,
        "worker_document": worker.document_number if worker else None,
        "worker_position": worker.position if worker else None,
        "worker_hire_date": (
            worker.fecha_de_ingreso.isoformat()
            if worker and worker.fecha_de_ingreso
            else None
        ),
        "next_exam_date": next_exam_date.isoformat(),
        # Campos legacy para compatibilidad con el frontend
        "status": "realizado",
        "result": result_mapping.get(exam.medical_aptitude_concept, "pendiente"),
        "restrictions": (
            exam.general_recommendations
            if exam.medical_aptitude_concept == "apto_con_recomendaciones"
            else None
        ),
        "created_at": exam.created_at,
        "updated_at": exam.updated_at,
    }

    return exam_dict


@router.get("/report/pdf")
async def generate_occupational_exam_report_pdf(
    worker_id: Optional[int] = Query(None, description="ID del trabajador específico"),
    exam_type: Optional[str] = Query(None, description="Tipo de examen (INGRESO, PERIODICO, REINTEGRO, RETIRO)"),
    start_date: Optional[date] = Query(None, description="Fecha de inicio del rango"),
    end_date: Optional[date] = Query(None, description="Fecha de fin del rango"),
    include_overdue: bool = Query(True, description="Incluir exámenes vencidos"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin),
) -> StreamingResponse:
    """
    Generar reporte PDF de exámenes ocupacionales con estadísticas y listados
    """
    try:
        # Obtener todos los trabajadores activos
        workers_query = db.query(Worker).filter(Worker.is_active == True)
        if worker_id:
            workers_query = workers_query.filter(Worker.id == worker_id)

        workers = workers_query.all()
        total_workers = len(workers)

        # Obtener exámenes ocupacionales con filtros
        exams_query = db.query(OccupationalExam).join(Worker)

        if worker_id:
            exams_query = exams_query.filter(OccupationalExam.worker_id == worker_id)

        if exam_type:
            exams_query = exams_query.filter(OccupationalExam.exam_type == exam_type)

        if start_date:
            exams_query = exams_query.filter(OccupationalExam.exam_date >= start_date)

        if end_date:
            exams_query = exams_query.filter(OccupationalExam.exam_date <= end_date)

        exams = exams_query.order_by(OccupationalExam.exam_date.desc()).all()

        # Calcular próximos exámenes y vencidos
        today = date.today()
        pending_exams = []
        overdue_exams = []

        for worker in workers:
            # Obtener el último examen del trabajador
            last_exam = (
                db.query(OccupationalExam)
                .filter(OccupationalExam.worker_id == worker.id)
                .order_by(OccupationalExam.exam_date.desc())
                .first()
            )

            if last_exam:
                # Calcular fecha del próximo examen basado en la periodicidad del cargo
                cargo = None
                if getattr(worker, "cargo_id", None):
                    cargo = db.query(Cargo).filter(Cargo.id == worker.cargo_id).first()
                if not cargo:
                    cargo = db.query(Cargo).filter(Cargo.nombre_cargo == worker.position).first()
                periodicidad = cargo.periodicidad_emo if cargo else "anual"

                if periodicidad == "semestral":
                    next_exam_date = last_exam.exam_date + timedelta(
                        days=180
                    )  # 6 meses
                elif periodicidad == "bianual":
                    next_exam_date = last_exam.exam_date + timedelta(days=730)  # 2 años
                else:  # anual por defecto
                    next_exam_date = last_exam.exam_date + timedelta(days=365)  # 1 año

                days_difference = (next_exam_date - today).days

                exam_data = {
                    "worker_name": f"{worker.first_name} {worker.last_name}",
                    "worker_document": worker.document_number,
                    "cargo": worker.position or "No especificado",
                    "last_exam_date": last_exam.exam_date.strftime("%d/%m/%Y"),
                    "next_exam_date": next_exam_date.strftime("%d/%m/%Y"),
                    "exam_type": EXAM_TYPE_LABELS.get(last_exam.exam_type, last_exam.exam_type or "Desconocido"),
                }

                if days_difference < 0:
                    # Examen vencido
                    exam_data["days_overdue"] = abs(days_difference)
                    overdue_exams.append(exam_data)
                elif days_difference <= 15:
                    # Examen próximo (próximos 15 días)
                    exam_data["days_until_exam"] = days_difference
                    pending_exams.append(exam_data)
            else:
                # Trabajador sin exámenes - necesita examen de ingreso
                exam_data = {
                    "worker_name": f"{worker.first_name} {worker.last_name}",
                    "worker_document": worker.document_number,
                    "cargo": worker.position or "No especificado",
                    "last_exam_date": "Sin examen",
                    "next_exam_date": "Inmediato",
                    "days_until_exam": 0,
                    "exam_type": "Examen de Ingreso",
                }
                pending_exams.append(exam_data)

        # Preparar estadísticas
        statistics = {
            "total_workers": total_workers,
            "total_exams": len(exams),
            "pending_exams": len(pending_exams),
            "overdue_exams": len(overdue_exams),
        }

        # Preparar contexto para la plantilla
        context = {
            "generated_at": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "statistics": statistics,
            "total_pending": len(pending_exams),
            "total_overdue": len(overdue_exams),
            "pending_exams": pending_exams,
            "overdue_exams": overdue_exams if include_overdue else [],
            "logo_base64": None,  # Se puede agregar el logo más tarde
        }

        # Generar PDF usando HTMLToPDFConverter
        converter = HTMLToPDFConverter()
        pdf_content = await converter.generate_pdf_from_template(
            "occupational_exam_report.html", context
        )

        # Crear nombre del archivo
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"reporte_examenes_ocupacionales_{timestamp}.pdf"

        # Configurar headers para la respuesta
        headers = {
            "Content-Type": "application/pdf",
            "Content-Disposition": f"attachment; filename={filename}",
        }

        return StreamingResponse(
            io.BytesIO(pdf_content), media_type="application/pdf", headers=headers
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generando el reporte de exámenes ocupacionales: {str(e)}",
        )


@router.get("/{exam_id}", response_model=OccupationalExamResponse)
async def get_occupational_exam(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin),
) -> Any:
    """
    Obtener un examen ocupacional por ID con información del trabajador
    """
    exam = (
        db.query(OccupationalExam)
        .join(Worker)
        .filter(OccupationalExam.id == exam_id)
        .first()
    )
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Examen ocupacional no encontrado",
        )

    # Calcular fecha del próximo examen basado en periodicidad del cargo
    worker = exam.worker
    cargo = None
    if getattr(worker, "cargo_id", None):
        cargo = db.query(Cargo).filter(Cargo.id == worker.cargo_id).first()
    if not cargo:
        cargo = db.query(Cargo).filter(Cargo.nombre_cargo == worker.position).first()
    periodicidad = cargo.periodicidad_emo if cargo else "anual"

    if periodicidad == "semestral":
        next_exam_date = exam.exam_date + timedelta(days=180)
    elif periodicidad == "bianual":
        next_exam_date = exam.exam_date + timedelta(days=730)
    else:
        next_exam_date = exam.exam_date + timedelta(days=365)

    # Mapear medical_aptitude_concept a result legacy
    result_mapping = {
        "apto": "apto",
        "apto_con_recomendaciones": "apto_con_restricciones",
        "no_apto": "no_apto",
    }

    # ---------------------------------------------------------------------
    # Lógica de fallback para datos faltantes (producción / legacy)
    # ---------------------------------------------------------------------
    
    # 1. Calcular duración del cargo si no existe
    duracion = exam.duracion_cargo_actual_meses
    if duracion is None and worker and worker.fecha_de_ingreso:
        try:
            # Calcular diferencia en meses
            months_diff = (exam.exam_date.year - worker.fecha_de_ingreso.year) * 12 + (exam.exam_date.month - worker.fecha_de_ingreso.month)
            if exam.exam_date.day < worker.fecha_de_ingreso.day:
                months_diff -= 1
            duracion = max(0, months_diff)
        except Exception:
            pass

    # 2. Traer factores de riesgo del profesiograma si no existen
    factores = exam.factores_riesgo_evaluados
    if not factores and cargo:
        try:
            profesiograma = (
                db.query(Profesiograma)
                .filter(
                    Profesiograma.cargo_id == cargo.id,
                    Profesiograma.estado == ProfesiogramaEstado.ACTIVO
                )
                .order_by(Profesiograma.version.desc())
                .first()
            )
            
            if profesiograma:
                prof_factors = (
                    db.query(ProfesiogramaFactor)
                    .options(joinedload(ProfesiogramaFactor.factor_riesgo))
                    .filter(ProfesiogramaFactor.profesiograma_id == profesiograma.id)
                    .all()
                )
                
                risk_factors_list = []
                for pf in prof_factors:
                    risk_factors_list.append({
                        "factor_riesgo_id": pf.factor_riesgo_id,
                        "nombre": pf.factor_riesgo.nombre,
                        "codigo": pf.factor_riesgo.codigo,
                        "categoria": pf.factor_riesgo.categoria,
                        "nivel_exposicion": pf.nivel_exposicion,
                        "tiempo_exposicion_horas": float(pf.tiempo_exposicion_horas) if pf.tiempo_exposicion_horas else 0,
                    })
                factores = risk_factors_list
        except Exception as e:
            print(f"Error fetching legacy factors: {e}")

    # ---------------------------------------------------------------------

    # Crear respuesta enriquecida con datos del trabajador
    exam_dict = {
        "id": exam.id,
        "exam_type": exam.exam_type,
        "exam_date": exam.exam_date,
        "departamento": exam.departamento,
        "ciudad": exam.ciudad,
        "duracion_cargo_actual_meses": duracion,
        "factores_riesgo_evaluados": factores,
        "cargo_id_momento_examen": exam.cargo_id_momento_examen,
        "programa": exam.programa,
        "occupational_conclusions": exam.occupational_conclusions,
        "preventive_occupational_behaviors": exam.preventive_occupational_behaviors,
        "general_recommendations": exam.general_recommendations,
        "medical_aptitude_concept": exam.medical_aptitude_concept,
        "observations": exam.observations,
        "examining_doctor": exam.examining_doctor,
        "medical_center": exam.medical_center,
        "pdf_file_path": exam.pdf_file_path,
        "requires_follow_up": exam.requires_follow_up or False,
        "supplier_id": exam.supplier_id,
        "doctor_id": exam.doctor_id,
        "worker_id": exam.worker_id,
        "worker_name": worker.full_name if worker else None,
        "worker_document": worker.document_number if worker else None,
        "worker_position": worker.position if worker else None,
        "worker_hire_date": (
            worker.fecha_de_ingreso.isoformat()
            if worker and worker.fecha_de_ingreso
            else None
        ),
        "next_exam_date": next_exam_date.isoformat(),
        # Campos legacy para compatibilidad con el frontend
        "status": "realizado",
        "result": result_mapping.get(exam.medical_aptitude_concept, "pendiente"),
        "restrictions": (
            exam.general_recommendations
            if exam.medical_aptitude_concept == "apto_con_recomendaciones"
            else None
        ),
        "created_at": exam.created_at,
        "updated_at": exam.updated_at,
    }

    return exam_dict


@router.put("/{exam_id}", response_model=OccupationalExamResponse)
async def update_occupational_exam(
    exam_id: int,
    exam_data: OccupationalExamUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin),
) -> Any:
    """
    Actualizar un examen ocupacional
    """
    exam = db.query(OccupationalExam).filter(OccupationalExam.id == exam_id).first()
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Examen ocupacional no encontrado",
        )

    update_data = exam_data.dict(exclude_unset=True)

    # Recalcular duración si cambia la fecha del examen
    if "exam_date" in update_data:
        worker = exam.worker
        if worker and worker.fecha_de_ingreso:
            try:
                exam_dt = update_data["exam_date"]
                # Calcular diferencia en meses
                months_diff = (exam_dt.year - worker.fecha_de_ingreso.year) * 12 + (exam_dt.month - worker.fecha_de_ingreso.month)
                if exam_dt.day < worker.fecha_de_ingreso.day:
                    months_diff -= 1
                update_data["duracion_cargo_actual_meses"] = max(0, months_diff)
            except Exception as e:
                print(f"Error recalculando duración del cargo en update: {e}")

    # Guardar el valor anterior de requires_follow_up antes de actualizar
    previous_requires_follow_up = exam.requires_follow_up

    # Verificar si requires_follow_up está siendo actualizado a True
    requires_follow_up_being_set = (
        "requires_follow_up" in update_data
        and update_data["requires_follow_up"] is True
    )

    # Aplicar actualizaciones
    for field, value in update_data.items():
        setattr(exam, field, value)

    db.commit()
    db.refresh(exam)

    # Crear seguimiento automáticamente si requires_follow_up se estableció como True
    # y no existía previamente (o cambió de False a True)
    if requires_follow_up_being_set and (previous_requires_follow_up is not True):
        print(f"DEBUG: requires_follow_up establecido a True para examen {exam.id}")
        worker = exam.worker
        if worker:
            print(f"DEBUG: Worker encontrado: {worker.full_name} (ID: {worker.id})")
            # Verificar si ya existe un seguimiento activo para este examen
            existing_seguimiento = (
                db.query(Seguimiento)
                .filter(Seguimiento.occupational_exam_id == exam.id)
                .first()
            )

            if not existing_seguimiento:
                print(f"DEBUG: No existe seguimiento previo, creando nuevo seguimiento")
                # Obtener el programa, usando el del examen o buscar uno activo por defecto
                programa_name = None
                if exam.programa and exam.programa.strip():
                    programa_name = exam.programa
                else:
                    # Buscar un programa activo en la base de datos
                    active_programa = (
                        db.query(Programas).filter(Programas.activo == True).first()
                    )
                    if active_programa:
                        programa_name = active_programa.nombre_programa
                    else:
                        # Si no hay programas activos, usar un valor por defecto
                        programa_name = "Seguimiento Médico Ocupacional"

                print(f"DEBUG: Programa a usar para el seguimiento: {programa_name}")

                # Determinar valoración de riesgo basada en el concepto médico
                valoracion_riesgo = None
                if exam.medical_aptitude_concept == "no_apto":
                    valoracion_riesgo = ValoracionRiesgo.ALTO
                elif exam.medical_aptitude_concept == "apto_con_recomendaciones":
                    valoracion_riesgo = ValoracionRiesgo.MEDIO
                else:  # apto
                    valoracion_riesgo = ValoracionRiesgo.BAJO

                # Construir observación general con información del examen
                observacion_parts = []
                if exam.examining_doctor:
                    observacion_parts.append(
                        f"Médico examinador: {exam.examining_doctor}"
                    )
                if exam.medical_center:
                    observacion_parts.append(f"Centro médico: {exam.medical_center}")
                exam_type_label = EXAM_TYPE_LABELS.get(exam.exam_type, exam.exam_type or "Desconocido")
                observacion_parts.append(f"Tipo de examen: {exam_type_label}")

                observacion_completa = (
                    "\n".join(observacion_parts) if observacion_parts else None
                )

                # Crear nuevo seguimiento con todos los datos del examen
                seguimiento_data = {
                    "worker_id": worker.id,
                    "occupational_exam_id": exam.id,
                    "programa": programa_name,
                    "nombre_trabajador": worker.full_name,
                    "cedula": worker.document_number,
                    "cargo": worker.position or "No especificado",
                    "fecha_ingreso": worker.fecha_de_ingreso,
                    "fecha_inicio": exam.exam_date,
                    "estado": EstadoSeguimiento.INICIADO,
                    "valoracion_riesgo": valoracion_riesgo,
                    "motivo_inclusion": f"Seguimiento requerido por examen ocupacional del {exam.exam_date.strftime('%d/%m/%Y')}. Concepto médico: {exam.medical_aptitude_concept.replace('_', ' ').title()}.",
                    "observacion": observacion_completa,
                    # Campos copiados directamente del examen
                    "conclusiones_ocupacionales": exam.occupational_conclusions,
                    "conductas_ocupacionales_prevenir": exam.preventive_occupational_behaviors,
                    "recomendaciones_generales": exam.general_recommendations,
                    "observaciones_examen": exam.observations,
                    "comentario": f"Seguimiento iniciado automáticamente desde examen ocupacional ID {exam.id}",
                }

                print(f"DEBUG: Datos del seguimiento: {seguimiento_data}")
                db_seguimiento = Seguimiento(**seguimiento_data)
                db.add(db_seguimiento)
                db.commit()
                db.refresh(db_seguimiento)
                print(
                    f"DEBUG: Seguimiento creado exitosamente con ID: {db_seguimiento.id}"
                )
            else:
                print(f"DEBUG: Ya existe seguimiento con ID: {existing_seguimiento.id}")
        else:
            print(f"DEBUG: No se encontró worker para el examen {exam.id}")

    # Calcular fecha del próximo examen basado en la periodicidad del cargo
    worker = exam.worker
    cargo = None
    if getattr(worker, "cargo_id", None):
        cargo = db.query(Cargo).filter(Cargo.id == worker.cargo_id).first()
    if not cargo:
        cargo = db.query(Cargo).filter(Cargo.nombre_cargo == worker.position).first()
    periodicidad = cargo.periodicidad_emo if cargo else "anual"

    from datetime import timedelta

    if periodicidad == "semestral":
        next_exam_date = exam.exam_date + timedelta(days=180)  # 6 meses
    elif periodicidad == "bianual":
        next_exam_date = exam.exam_date + timedelta(days=730)  # 2 años
    else:  # anual por defecto
        next_exam_date = exam.exam_date + timedelta(days=365)  # 1 año

    # Mapear medical_aptitude_concept a result legacy
    result_mapping = {
        "apto": "apto",
        "apto_con_recomendaciones": "apto_con_restricciones",
        "no_apto": "no_apto",
    }

    # Crear respuesta enriquecida con datos del trabajador
    exam_dict = {
        "id": exam.id,
        "exam_type": exam.exam_type,
        "exam_date": exam.exam_date,
        "departamento": exam.departamento,
        "ciudad": exam.ciudad,
        "duracion_cargo_actual_meses": exam.duracion_cargo_actual_meses,
        "factores_riesgo_evaluados": exam.factores_riesgo_evaluados,
        "cargo_id_momento_examen": exam.cargo_id_momento_examen,
        "programa": exam.programa,
        "occupational_conclusions": exam.occupational_conclusions,
        "preventive_occupational_behaviors": exam.preventive_occupational_behaviors,
        "general_recommendations": exam.general_recommendations,
        "medical_aptitude_concept": exam.medical_aptitude_concept,
        "observations": exam.observations,
        "examining_doctor": exam.examining_doctor,
        "medical_center": exam.medical_center,
        "pdf_file_path": exam.pdf_file_path,
        "requires_follow_up": exam.requires_follow_up,
        "supplier_id": exam.supplier_id,
        "doctor_id": exam.doctor_id,
        "worker_id": exam.worker_id,
        "worker_name": worker.full_name if worker else None,
        "worker_document": worker.document_number if worker else None,
        "worker_position": worker.position if worker else None,
        "worker_hire_date": (
            worker.fecha_de_ingreso.isoformat()
            if worker and worker.fecha_de_ingreso
            else None
        ),
        "next_exam_date": next_exam_date.isoformat(),
        # Campos legacy para compatibilidad con el frontend
        "status": "realizado",
        "result": result_mapping.get(exam.medical_aptitude_concept, "pendiente"),
        "restrictions": (
            exam.general_recommendations
            if exam.medical_aptitude_concept == "apto_con_recomendaciones"
            else None
        ),
        "created_at": exam.created_at,
        "updated_at": exam.updated_at,
    }

    return exam_dict


@router.delete("/{exam_id}", response_model=MessageResponse)
async def delete_occupational_exam(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> Any:
    """
    Eliminar un examen ocupacional (solo administradores)
    """
    exam = db.query(OccupationalExam).filter(OccupationalExam.id == exam_id).first()
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Examen ocupacional no encontrado",
        )

    db.delete(exam)
    db.commit()

    return MessageResponse(message="Examen ocupacional eliminado exitosamente")


@router.get("/{exam_id}/certificate")
async def get_exam_certificate(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin),
) -> Any:
    """
    Descargar certificado de examen ocupacional
    """
    exam = db.query(OccupationalExam).filter(OccupationalExam.id == exam_id).first()
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Examen ocupacional no encontrado",
        )

    # TODO: Implement certificate generation
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Generación de certificados no implementada",
    )


@router.post("/acknowledge-notification/{exam_id}", response_model=MessageResponse)
async def acknowledge_exam_notification(
    exam_id: int,
    worker_id: int = Query(..., description="ID del trabajador"),
    notification_type: str = Query(
        ..., description="Tipo de notificación: first_notification, reminder, overdue"
    ),
    request: Request = None,
    db: Session = Depends(get_db),
) -> Any:
    """
    Procesar confirmación de recepción de notificación de examen ocupacional.
    Este endpoint es llamado cuando el trabajador hace clic en "Recibido" en el email.
    """
    # Verificar que el examen existe
    exam = db.query(OccupationalExam).filter(OccupationalExam.id == exam_id).first()
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Examen ocupacional no encontrado",
        )

    # Verificar que el trabajador existe y está asociado al examen
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Trabajador no encontrado"
        )

    if exam.worker_id != worker_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El examen no pertenece al trabajador especificado",
        )

    # Verificar que no existe ya una confirmación para este examen y tipo de notificación
    existing_ack = (
        db.query(NotificationAcknowledgment)
        .filter(
            and_(
                NotificationAcknowledgment.worker_id == worker_id,
                NotificationAcknowledgment.occupational_exam_id == exam_id,
                NotificationAcknowledgment.notification_type == notification_type,
            )
        )
        .first()
    )

    if existing_ack:
        return {
            "message": "La notificación ya había sido confirmada anteriormente",
            "success": True,
        }

    # Obtener información de la request para auditoría
    ip_address = None
    user_agent = None
    if request:
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")

    # Crear el registro de confirmación
    acknowledgment = NotificationAcknowledgment(
        worker_id=worker_id,
        occupational_exam_id=exam_id,
        notification_type=notification_type,
        ip_address=ip_address,
        user_agent=user_agent,
        stops_notifications=True,
    )

    db.add(acknowledgment)
    db.commit()
    db.refresh(acknowledgment)

    return {
        "message": f"Confirmación de recepción registrada exitosamente. No recibirá más notificaciones de tipo '{notification_type}' para este examen.",
        "success": True,
    }


@router.post("/upload-pdf", response_model=dict)
async def upload_pdf_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin),
) -> Any:
    """
    Cargar archivo PDF temporal para exámenes ocupacionales
    """
    # Verificar que el archivo es un PDF
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se permiten archivos PDF",
        )

    # Verificar el tipo de contenido
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo debe ser un PDF válido",
        )

    try:
        # Crear un UploadFile temporal para S3
        from fastapi import UploadFile
        from io import BytesIO

        # Leer el contenido del archivo
        content = await file.read()

        # Crear un nuevo UploadFile para S3
        temp_file = UploadFile(
            filename=file.filename,
            file=BytesIO(content),
            size=len(content),
            headers=file.headers,
        )

        # Subir archivo a S3 Storage como examen médico temporal
        result = await s3_service.upload_medical_exam(
            worker_id=0,  # ID temporal para archivos temporales
            file=temp_file,
            exam_type="temp",
        )

        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error al subir archivo: {result.get('error', 'Error desconocido')}",
            )

        return {
            "message": "Archivo PDF cargado exitosamente",
            "file_path": result["file_url"],
            "file_key": result["file_key"],
            "original_filename": file.filename,
            "success": True,
        }

    except Exception as e:

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al cargar el archivo: {str(e)}",
        )


@router.post("/{exam_id}/upload-pdf", response_model=MessageResponse)
async def upload_exam_pdf(
    exam_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin),
) -> Any:
    """
    Cargar archivo PDF para un examen ocupacional
    """
    # Verificar que el examen existe
    exam = db.query(OccupationalExam).filter(OccupationalExam.id == exam_id).first()
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Examen ocupacional no encontrado",
        )

    # Verificar que el archivo es un PDF
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se permiten archivos PDF",
        )

    # Verificar el tipo de contenido
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo debe ser un PDF válido",
        )

    try:
        # Crear un UploadFile temporal para S3
        from fastapi import UploadFile
        from io import BytesIO

        # Leer el contenido del archivo
        content = await file.read()

        # Crear un nuevo UploadFile para S3
        temp_file = UploadFile(
            filename=file.filename,
            file=BytesIO(content),
            size=len(content),
            headers=file.headers,
        )

        # Subir archivo a S3 Storage como examen médico
        result = await s3_service.upload_medical_exam(
            worker_id=exam.worker_id, file=temp_file, exam_type="ocupacional"
        )

        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error al subir archivo: {result.get('error', 'Error desconocido')}",
            )

        # Eliminar archivo anterior de S3 Storage si existe
        if exam.pdf_file_path:
            try:
                # Extraer la clave del archivo desde la URL de S3
                # Formato esperado: https://bucket-name.s3.amazonaws.com/path/to/file
                if "s3.amazonaws.com" in exam.pdf_file_path:
                    old_file_key = exam.pdf_file_path.split(".com/")[-1]
                    s3_service.delete_file(old_file_key)
            except Exception as e:
                # Ignorar errores al eliminar archivo anterior
                pass

        # Actualizar la URL del archivo en la base de datos
        exam.pdf_file_path = result["file_url"]
        db.commit()

        return {"message": "Archivo PDF cargado exitosamente", "success": True}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al cargar el archivo: {str(e)}",
        )


@router.delete("/{exam_id}/pdf", response_model=MessageResponse)
async def delete_exam_pdf(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin),
) -> Any:
    """
    Eliminar archivo PDF de un examen ocupacional
    """
    # Verificar que el examen existe
    exam = db.query(OccupationalExam).filter(OccupationalExam.id == exam_id).first()
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Examen ocupacional no encontrado",
        )

    if not exam.pdf_file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No hay archivo PDF asociado a este examen",
        )

    # Eliminar archivo de S3 Storage
    try:
        # Extraer la clave del archivo desde la URL de S3
        # Formato esperado: https://bucket-name.s3.amazonaws.com/path/to/file
        if "s3.amazonaws.com" in exam.pdf_file_path:
            file_key = exam.pdf_file_path.split(".com/")[-1]
            result = s3_service.delete_file(file_key)

            if not result["success"]:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Error al eliminar el archivo de S3 Storage: {result.get('error', 'Error desconocido')}",
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="URL de archivo no válida para S3 Storage",
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al eliminar el archivo: {str(e)}",
        )

    # Limpiar la ruta en la base de datos
    exam.pdf_file_path = None
    db.commit()

    return {"message": "Archivo PDF eliminado exitosamente", "success": True}


@router.get("/{exam_id}/pdf")
async def get_exam_pdf(
    exam_id: int,
    download: bool = Query(
        False, description="Si es True, fuerza la descarga del archivo"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin),
) -> Any:
    """
    Obtener/descargar archivo PDF de un examen ocupacional
    """
    import httpx
    from fastapi.responses import StreamingResponse
    import io

    # Verificar que el examen existe
    exam = db.query(OccupationalExam).filter(OccupationalExam.id == exam_id).first()
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Examen ocupacional no encontrado",
        )

    if not exam.pdf_file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No hay archivo PDF asociado a este examen",
        )

    if exam.pdf_file_path.startswith("http") and "s3.amazonaws.com" in exam.pdf_file_path:
        try:
            file_key = exam.pdf_file_path.split(".com/")[-1]
            signed_url = s3_service.get_file_url(file_key, expiration=3600)
            if not signed_url:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="No se pudo generar URL firmada para S3",
                )
            async with httpx.AsyncClient() as client:
                response = await client.get(signed_url)
                response.raise_for_status()
            headers = {
                "Content-Type": "application/pdf",
            }
            if download:
                worker = exam.worker
                worker_name = (worker.full_name.replace(" ", "_") if worker and getattr(worker, "full_name", None) else None)
                filename = f"Examen_Ocupacional_{worker_name or exam_id}.pdf"
                headers["Content-Disposition"] = f"attachment; filename={filename}"
            else:
                headers["Content-Disposition"] = "inline"
            return StreamingResponse(
                io.BytesIO(response.content),
                media_type="application/pdf",
                headers=headers,
            )
        except httpx.HTTPError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error al obtener el archivo PDF desde S3: {str(e)}",
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error interno al procesar el archivo PDF desde S3: {str(e)}",
            )

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="URL de PDF no válida para S3",
    )

    # Ruta local (legacy) no soportada
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Archivo no encontrado",
    )


@router.get("/{exam_id}/medical-recommendation-report")
async def generate_medical_recommendation_report(
    exam_id: int,
    download: bool = Query(
        True, description="Set to true to download the file with a custom filename"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin),
) -> FileResponse:
    """
    Generar y descargar PDF de notificación de recomendaciones médicas para un examen ocupacional
    """
    # Verificar que el examen existe
    exam = db.query(OccupationalExam).filter(OccupationalExam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Examen ocupacional no encontrado")

    # Verificar que el trabajador existe
    worker = db.query(Worker).filter(Worker.id == exam.worker_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail="Trabajador no encontrado")

    try:
        # Importar el generador de reportes médicos
        from app.services.medical_recommendation_generator import (
            MedicalRecommendationGenerator,
        )

        # Crear un seguimiento temporal para usar con el generador existente
        # Esto es necesario porque el generador actual espera un seguimiento
        from app.models.seguimiento import Seguimiento

        # Buscar si existe un seguimiento para este trabajador
        seguimiento = (
            db.query(Seguimiento)
            .filter(Seguimiento.worker_id == exam.worker_id)
            .first()
        )

        if not seguimiento:
            # Crear un seguimiento temporal si no existe
            seguimiento = Seguimiento(
                worker_id=exam.worker_id,
                programa="examen_ocupacional",
                nombre_trabajador=f"{worker.first_name} {worker.last_name}",
                cedula=worker.document_number,
                cargo=worker.position or "No especificado",
                fecha_inicio=exam.exam_date,
                observacion=f"Seguimiento generado automáticamente para examen ocupacional {exam_id}",
                valoracion_riesgo="medio",
                recomendaciones_generales=exam.general_recommendations
                or "Sin recomendaciones específicas",
            )
            db.add(seguimiento)
            db.commit()
            db.refresh(seguimiento)

        # Generar el PDF usando el servicio existente
        generator = MedicalRecommendationGenerator(db)
        filepath = await generator.generate_medical_recommendation_pdf(seguimiento.id)

        # Si el archivo se guardó localmente, devolverlo como FileResponse
        if filepath.startswith("/medical_reports/"):
            # Es una ruta local
            local_filepath = filepath.replace("/medical_reports/", "medical_reports/")
            if not os.path.exists(local_filepath):
                raise HTTPException(status_code=404, detail="Archivo PDF no encontrado")

            # Preparar parámetros de respuesta
            response_params = {"path": local_filepath, "media_type": "application/pdf"}

            # Si se solicita descarga, agregar un nombre de archivo personalizado
            if download:
                filename = f"notificacion_medica_{worker.document_number}_{exam_id}.pdf"
                response_params["filename"] = filename

            return FileResponse(**response_params)
        else:
            
            if filepath.startswith("http"):
                # Descargar el archivo desde la URL y devolverlo
                async with httpx.AsyncClient() as client:
                    response = await client.get(filepath)
                    response.raise_for_status()

                    # Crear un stream de bytes
                    pdf_content = io.BytesIO(response.content)

                    # Configurar headers para la respuesta
                    headers = {
                        "Content-Type": "application/pdf",
                    }

                    if download:
                        filename = f"notificacion_medica_{worker.document_number}_{exam_id}.pdf"
                        headers["Content-Disposition"] = (
                            f"attachment; filename={filename}"
                        )
                    else:
                        headers["Content-Disposition"] = "inline"

                    return StreamingResponse(
                        io.BytesIO(response.content),
                        media_type="application/pdf",
                        headers=headers,
                    )
            else:
                raise HTTPException(
                    status_code=500, detail="Error procesando la URL del archivo"
                )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error generando el reporte médico: {str(e)}"
        )


@router.post("/{exam_id}/create-follow-up", response_model=MessageResponse)
async def create_follow_up_from_exam(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin),
) -> Any:
    """
    Crear seguimiento desde un examen ocupacional
    """
    # Verificar que el examen existe
    exam = db.query(OccupationalExam).filter(OccupationalExam.id == exam_id).first()
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Examen ocupacional no encontrado",
        )

    # Verificar que el examen requiere seguimiento
    if not exam.requires_follow_up:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este examen no está marcado para requerir seguimiento",
        )

    # Verificar que el trabajador existe
    worker = db.query(Worker).filter(Worker.id == exam.worker_id).first()
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Trabajador no encontrado"
        )

    # Verificar si ya existe un seguimiento para este examen
    existing_follow_up = (
        db.query(Seguimiento)
        .filter(
            and_(
                Seguimiento.worker_id == exam.worker_id,
                Seguimiento.occupational_exam_id == exam_id,
            )
        )
        .first()
    )

    if existing_follow_up:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un seguimiento para este examen",
        )

    try:
        # Crear el seguimiento basado en el examen ocupacional
        new_follow_up = Seguimiento(
            worker_id=exam.worker_id,
            occupational_exam_id=exam_id,
            programa=exam.programa or "seguimiento_examen_ocupacional",
            nombre_trabajador=f"{worker.first_name} {worker.last_name}",
            cedula=worker.document_number,
            cargo=worker.position or "No especificado",
            fecha_inicio=exam.exam_date,
            observacion=f"Seguimiento generado desde examen ocupacional {exam_id}",
            valoracion_riesgo="medio",  # Valor por defecto, se puede ajustar
            recomendaciones_generales=exam.general_recommendations
            or "Sin recomendaciones específicas",
            estado="activo",
        )

        db.add(new_follow_up)
        db.commit()
        db.refresh(new_follow_up)

        return {
            "message": f"Seguimiento creado exitosamente para el examen {exam_id}",
            "follow_up_id": new_follow_up.id,
            "success": True,
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al crear el seguimiento: {str(e)}",
        )


@router.patch("/{exam_id}/toggle-follow-up", response_model=MessageResponse)
async def toggle_follow_up_requirement(
    exam_id: int,
    requires_follow_up: bool,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin),
) -> Any:
    """
    Marcar o desmarcar un examen ocupacional para requerir seguimiento
    """
    # Verificar que el examen existe
    exam = db.query(OccupationalExam).filter(OccupationalExam.id == exam_id).first()
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Examen ocupacional no encontrado",
        )

    try:
        # Actualizar el campo requires_follow_up
        exam.requires_follow_up = requires_follow_up
        db.commit()

        action = "marcado" if requires_follow_up else "desmarcado"
        return {
            "message": f"Examen {action} para seguimiento exitosamente",
            "requires_follow_up": requires_follow_up,
            "success": True,
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al actualizar el examen: {str(e)}",
        )
