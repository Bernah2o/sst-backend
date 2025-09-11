from typing import Any, List, Dict
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form
from fastapi.responses import StreamingResponse, Response
from sqlalchemy.orm import Session
from sqlalchemy import or_
from io import BytesIO
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill
from datetime import datetime
import os
import uuid

from app.database import get_db
from app.dependencies import get_current_user, get_current_active_user, require_admin, require_supervisor_or_admin
from app.models.user import User
from app.models.worker import Worker, WorkerContract
from app.models.worker_document import WorkerDocument, DocumentCategory
from app.models.worker_novedad import WorkerNovedad, NovedadType, NovedadStatus
from app.services.firebase_storage_service import FirebaseStorageService
from app.config import settings
from app.models.occupational_exam import OccupationalExam
from app.models.seguimiento import Seguimiento, EstadoSeguimiento
from app.models.reinduction import ReinductionRecord
from app.schemas.worker import (
    Worker as WorkerSchema,
    WorkerCreate,
    WorkerUpdate,
    WorkerList,
    WorkerContract as WorkerContractSchema,
    WorkerContractCreate,
    WorkerContractUpdate,
    WorkerDocumentResponse,
    WorkerDocumentUpdate
)
from app.schemas.worker_novedad import (
    WorkerNovedadCreate,
    WorkerNovedadUpdate,
    WorkerNovedadResponse,
    WorkerNovedadList,
    WorkerNovedadApproval,
    WorkerNovedadStats
)
from app.schemas.occupational_exam import (
    OccupationalExamCreate,
    OccupationalExamUpdate,
    OccupationalExamResponse,
    OccupationalExamListResponse
)
from app.schemas.common import MessageResponse
from app.models.enrollment import Enrollment
from app.models.course import Course
from app.models.survey import Survey, UserSurvey
from app.models.evaluation import Evaluation, UserEvaluation
from app.models.reinduction import ReinductionRecord

router = APIRouter()


@router.get("/", response_model=List[WorkerList])
@router.get("", response_model=List[WorkerList])
async def get_workers(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: str = Query(None, description="Buscar por nombre, documento o email"),
    is_active: bool = Query(None, description="Filtrar por estado activo"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """
    Obtener lista de trabajadores con filtros opcionales
    """
    query = db.query(Worker)
    
    # Filtro de búsqueda
    if search:
        search_filter = or_(
            Worker.first_name.ilike(f"%{search}%"),
            Worker.last_name.ilike(f"%{search}%"),
            Worker.document_number.ilike(f"%{search}%"),
            Worker.email.ilike(f"%{search}%")
        )
        query = query.filter(search_filter)
    
    # Filtro por estado activo
    if is_active is not None:
        query = query.filter(Worker.is_active == is_active)
    
    workers = query.offset(skip).limit(limit).all()
    return workers


@router.post("/", response_model=WorkerSchema)
@router.post("", response_model=WorkerSchema)
async def create_worker(
    worker_data: WorkerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """
    Crear un nuevo trabajador
    """
    # Verificar si ya existe un trabajador con el mismo documento o email
    existing_worker = db.query(Worker).filter(
        or_(
            Worker.document_number == worker_data.document_number,
            Worker.email == worker_data.email
        )
    ).first()
    
    if existing_worker:
        if existing_worker.document_number == worker_data.document_number:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe un trabajador con este número de documento"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe un trabajador con este email"
            )
    
    # Crear el trabajador
    worker = Worker(**worker_data.dict())
    db.add(worker)
    db.commit()
    db.refresh(worker)
    
    return worker


@router.get("/basic{trailing_slash:path}", response_model=List[WorkerList])
async def get_workers_basic(
    trailing_slash: str = "",
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: str = Query(None, description="Buscar por nombre, documento o email"),
    is_active: bool = Query(None, description="Filtrar por estado activo"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Obtener lista básica de trabajadores (sin restricciones de rol)
    """
    query = db.query(Worker)
    
    # Filtro de búsqueda
    if search:
        search_filter = or_(
            Worker.first_name.ilike(f"%{search}%"),
            Worker.last_name.ilike(f"%{search}%"),
            Worker.document_number.ilike(f"%{search}%"),
            Worker.email.ilike(f"%{search}%")
        )
        query = query.filter(search_filter)
    
    # Filtro por estado activo
    if is_active is not None:
        query = query.filter(Worker.is_active == is_active)
    
    workers = query.offset(skip).limit(limit).all()
    return workers


@router.get("/{worker_id}", response_model=WorkerSchema)
async def get_worker(
    worker_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """
    Obtener un trabajador por ID
    """
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trabajador no encontrado"
        )
    return worker


@router.get("/{worker_id}/detailed-info")
async def get_worker_detailed_info(
    worker_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """
    Obtener información detallada de un trabajador incluyendo cursos, encuestas y evaluaciones
    """
    # Obtener información del trabajador
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trabajador no encontrado"
        )
    
    # Get course enrollments with progress
    enrollments = db.query(Enrollment).filter(Enrollment.user_id == worker.user_id).all()
    courses = []
    for enrollment in enrollments:
        course = enrollment.course
        
        courses.append({
            "enrollment_id": enrollment.id,
            "course_id": course.id,
            "course_title": course.title,
            "enrollment_date": enrollment.enrolled_at.isoformat() if enrollment.enrolled_at else None,
            "completion_date": enrollment.completed_at.isoformat() if enrollment.completed_at else None,
            "status": enrollment.status,
            "progress_percentage": enrollment.progress or 0
        })
    
    # Obtener encuestas del trabajador
    surveys_query = db.query(
        UserSurvey.id.label('user_survey_id'),
        Survey.id.label('survey_id'),
        Survey.title.label('survey_title'),
        UserSurvey.completed_at,
        UserSurvey.status
    ).join(
        Survey, UserSurvey.survey_id == Survey.id
    ).filter(
        UserSurvey.user_id == worker.user_id
    ).all()
    
    surveys = []
    for survey in surveys_query:
        surveys.append({
            "user_survey_id": survey.user_survey_id,
            "survey_id": survey.survey_id,
            "survey_title": survey.survey_title,
            "status": survey.status,
            "completed_at": survey.completed_at.isoformat() if survey.completed_at else None
        })
    
    # Obtener evaluaciones del trabajador
    evaluations_query = db.query(
        UserEvaluation.id.label('user_evaluation_id'),
        Evaluation.id.label('evaluation_id'),
        Evaluation.title.label('evaluation_title'),
        UserEvaluation.score,
        UserEvaluation.max_points,
        UserEvaluation.passed,
        UserEvaluation.completed_at,
        UserEvaluation.status
    ).join(
        Evaluation, UserEvaluation.evaluation_id == Evaluation.id
    ).filter(
        UserEvaluation.user_id == worker.user_id
    ).all()
    
    evaluations = []
    for evaluation in evaluations_query:
        evaluations.append({
            "user_evaluation_id": evaluation.user_evaluation_id,
            "evaluation_id": evaluation.evaluation_id,
            "evaluation_title": evaluation.evaluation_title,
            "score": evaluation.score,
            "max_points": evaluation.max_points,
            "passed": evaluation.passed,
            "completed_at": evaluation.completed_at.isoformat() if evaluation.completed_at else None,
            "status": evaluation.status
        })
    
    return {
        "worker": {
            "id": worker.id,
            "full_name": f"{worker.first_name} {worker.last_name}",
            "document_number": worker.document_number,
            "email": worker.email,
            "position": worker.position,
            "department": worker.department,
            "is_active": worker.is_active,
            "user_id": worker.user_id
        },
        "courses": courses,
        "surveys": surveys,
        "evaluations": evaluations
    }


@router.put("/{worker_id}", response_model=WorkerSchema)
async def update_worker(
    worker_id: int,
    worker_data: WorkerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """
    Actualizar un trabajador
    """
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trabajador no encontrado"
        )
    
    # Verificar duplicados si se actualiza documento o email
    update_data = worker_data.dict(exclude_unset=True)
    
    if "document_number" in update_data or "email" in update_data:
        existing_worker = db.query(Worker).filter(
            Worker.id != worker_id,
            or_(
                Worker.document_number == update_data.get("document_number", worker.document_number),
                Worker.email == update_data.get("email", worker.email)
            )
        ).first()
        
        if existing_worker:
            if existing_worker.document_number == update_data.get("document_number"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Ya existe otro trabajador con este número de documento"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Ya existe otro trabajador con este email"
                )
    
    # Verificar si se está actualizando la fecha de ingreso
    fecha_ingreso_changed = "fecha_de_ingreso" in update_data and update_data["fecha_de_ingreso"] != worker.fecha_de_ingreso
    
    # Actualizar campos
    for field, value in update_data.items():
        setattr(worker, field, value)
    
    db.commit()
    db.refresh(worker)
    
    # Si se actualizó la fecha de ingreso, regenerar registros de reinducción
    if fecha_ingreso_changed and worker.fecha_de_ingreso:
        try:
            from app.services.reinduction_service import ReinductionService
            from app.models.reinduction import ReinductionRecord, ReinductionStatus
            
            service = ReinductionService(db)
            
            # Eliminar registros existentes que no estén completados
            existing_records = db.query(ReinductionRecord).filter(
                ReinductionRecord.worker_id == worker_id,
                ReinductionRecord.status.in_([
                    ReinductionStatus.PENDING,
                    ReinductionStatus.SCHEDULED,
                    ReinductionStatus.IN_PROGRESS,
                    ReinductionStatus.OVERDUE
                ])
            ).all()
            
            for record in existing_records:
                db.delete(record)
            
            db.commit()
            
            # Regenerar registros faltantes
            service.generate_missing_reinduction_records(worker_id=worker_id)
            
            print(f"Registros de reinducción regenerados para trabajador {worker_id} debido a cambio en fecha de ingreso")
            
        except Exception as e:
            print(f"Error al regenerar registros de reinducción para trabajador {worker_id}: {str(e)}")
            # No fallar la actualización del trabajador por este error
    
    return worker


@router.delete("/{worker_id}", response_model=MessageResponse)
async def delete_worker(
    worker_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
) -> Any:
    """
    Eliminar un trabajador (solo administradores)
    """
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trabajador no encontrado"
        )
    
    db.delete(worker)
    db.commit()
    
    return MessageResponse(message="Trabajador eliminado exitosamente")


# Endpoints para contratos
@router.post("/{worker_id}/contracts", response_model=WorkerContractSchema)
async def create_worker_contract(
    worker_id: int,
    contract_data: WorkerContractCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """
    Crear un nuevo contrato para un trabajador
    """
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trabajador no encontrado"
        )
    
    contract = WorkerContract(
        worker_id=worker_id,
        **contract_data.dict()
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)
    
    return contract


@router.get("/{worker_id}/contracts", response_model=List[WorkerContractSchema])
async def get_worker_contracts(
    worker_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """
    Obtener todos los contratos de un trabajador
    """
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trabajador no encontrado"
        )
    
    return worker.contracts


@router.put("/contracts/{contract_id}", response_model=WorkerContractSchema)
async def update_worker_contract(
    contract_id: int,
    contract_data: WorkerContractUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """
    Actualizar un contrato de trabajador
    """
    contract = db.query(WorkerContract).filter(WorkerContract.id == contract_id).first()
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contrato no encontrado"
        )
    
    update_data = contract_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(contract, field, value)
    
    db.commit()
    db.refresh(contract)
    
    return contract


@router.delete("/contracts/{contract_id}", response_model=MessageResponse)
async def delete_worker_contract(
    contract_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
) -> Any:
    """
    Eliminar un contrato de trabajador (solo administradores)
    """
    contract = db.query(WorkerContract).filter(WorkerContract.id == contract_id).first()
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contrato no encontrado"
        )
    
    db.delete(contract)
    db.commit()
    
    return MessageResponse(message="Contrato eliminado exitosamente")


@router.get("/check-document/{document_number}", response_model=Dict[str, Any])
async def check_worker_document(
    document_number: str,
    db: Session = Depends(get_db)
) -> Any:
    """
    Verificar si un número de documento corresponde a un trabajador registrado
    y devolver sus datos completos
    """
    worker = db.query(Worker).filter(
        Worker.document_number == document_number,
        Worker.is_active == True
    ).first()
    
    if not worker:
        return {
            "exists": False,
            "worker": None
        }
    
    return {
        "exists": True,
        "is_registered": worker.is_registered,
        "assigned_role": worker.assigned_role,
        "worker": {
            "id": worker.id,
            "first_name": worker.first_name,
            "last_name": worker.last_name,
            "email": worker.email,
            "phone": worker.phone,
            "department": worker.department,
            "position": worker.position,
            "fecha_de_ingreso": worker.fecha_de_ingreso.isoformat() if worker.fecha_de_ingreso else None,
            "document_type": worker.document_type,
            "document_number": worker.document_number
        }
    }


@router.post("/validate-employee", response_model=Dict[str, Any])
async def validate_employee_credentials(
    credentials: Dict[str, str],
    db: Session = Depends(get_db)
) -> Any:
    """
    Validar que tanto el número de documento como el correo electrónico
    correspondan a un trabajador registrado por el administrador
    """
    document_number = credentials.get("document_number")
    email = credentials.get("email")
    
    if not document_number or not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Se requiere número de documento y correo electrónico"
        )
    
    worker = db.query(Worker).filter(
        Worker.document_number == document_number,
        Worker.email == email,
        Worker.is_active == True
    ).first()
    
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró un trabajador activo con ese número de documento y correo electrónico. Solo los empleados registrados por el administrador pueden crear una cuenta."
        )
    
    # Check if worker is already registered with a verified account
    if worker.is_registered and worker.user_id:
        # Check if the existing user is already verified
        from app.models.user import User
        existing_user = db.query(User).filter(User.id == worker.user_id).first()
        if existing_user and existing_user.is_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Este empleado ya tiene una cuenta registrada en el sistema. Puede iniciar sesión directamente."
            )
    
    return {
        "valid": True,
        "worker_id": worker.id,
        "assigned_role": worker.assigned_role,
        "full_name": worker.full_name
    }


# Endpoints para exámenes ocupacionales
@router.post("/{worker_id}/occupational-exams", response_model=OccupationalExamResponse)
async def create_occupational_exam(
    worker_id: int,
    exam_data: OccupationalExamCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """
    Crear un nuevo examen ocupacional para un trabajador
    """
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trabajador no encontrado"
        )
    
    exam = OccupationalExam(
        worker_id=worker_id,
        **exam_data.dict(exclude={"worker_id"})
    )
    db.add(exam)
    db.commit()
    db.refresh(exam)
    
    # Crear seguimiento automáticamente si se asigna un programa
    if exam.programa and exam.programa.strip():
        # Verificar si ya existe un seguimiento activo para este programa
        existing_seguimiento = db.query(Seguimiento).filter(
            Seguimiento.worker_id == worker_id,
            Seguimiento.programa == exam.programa,
            Seguimiento.estado == EstadoSeguimiento.INICIADO
        ).first()
        
        if not existing_seguimiento:
            # Crear nuevo seguimiento automáticamente
            seguimiento = Seguimiento(
                worker_id=worker_id,
                programa=exam.programa,
                nombre_trabajador=worker.full_name,
                cedula=worker.document_number,
                cargo=worker.position,
                fecha_ingreso=worker.fecha_de_ingreso,
                estado=EstadoSeguimiento.INICIADO,
                # Copiar datos del examen ocupacional
                conclusiones_ocupacionales=exam.occupational_conclusions,
                conductas_ocupacionales_prevenir=exam.preventive_occupational_behaviors,
                recomendaciones_generales=exam.general_recommendations,
                observaciones_examen=exam.observations
            )
            db.add(seguimiento)
            db.commit()
    
    # Calcular fecha del próximo examen (1 año después)
    from datetime import timedelta
    next_exam_date = exam.exam_date + timedelta(days=365)
    
    # Mapear medical_aptitude_concept a result legacy
    result_mapping = {
        "apto": "apto",
        "apto_con_recomendaciones": "apto_con_restricciones",
        "no_apto": "no_apto"
    }
    
    # Crear respuesta enriquecida con datos del trabajador
    exam_dict = {
        "id": exam.id,
        "exam_type": exam.exam_type,
        "exam_date": exam.exam_date,
        "programa": exam.programa,
        "occupational_conclusions": exam.occupational_conclusions,
        "preventive_occupational_behaviors": exam.preventive_occupational_behaviors,
        "general_recommendations": exam.general_recommendations,
        "medical_aptitude_concept": exam.medical_aptitude_concept,
        "observations": exam.observations,
        "examining_doctor": exam.examining_doctor,
        "medical_center": exam.medical_center,
        "worker_id": exam.worker_id,
        "worker_name": worker.full_name if worker else None,
        "worker_document": worker.document_number if worker else None,
        "worker_position": worker.position if worker else None,
        "worker_hire_date": worker.fecha_de_ingreso.isoformat() if worker and worker.fecha_de_ingreso else None,
        "next_exam_date": next_exam_date.isoformat(),
        
        # Campos legacy para compatibilidad con el frontend
        "status": "realizado",
        "result": result_mapping.get(exam.medical_aptitude_concept, "pendiente"),
        "restrictions": exam.general_recommendations if exam.medical_aptitude_concept == "apto_con_recomendaciones" else None,
        
        "created_at": exam.created_at,
        "updated_at": exam.updated_at
    }
    
    return exam_dict


@router.get("/{worker_id}/occupational-exams", response_model=List[OccupationalExamResponse])
async def get_worker_occupational_exams(
    worker_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """
    Obtener todos los exámenes ocupacionales de un trabajador ordenados por fecha descendente
    """
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trabajador no encontrado"
        )
    
    # Ordenar exámenes por fecha descendente (más reciente primero)
    exams = db.query(OccupationalExam).filter(
        OccupationalExam.worker_id == worker_id
    ).order_by(OccupationalExam.exam_date.desc()).all()
    
    return exams


@router.get("/occupational-exams/{exam_id}", response_model=OccupationalExamResponse)
async def get_occupational_exam(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """
    Obtener un examen ocupacional por ID con información del trabajador
    """
    exam = db.query(OccupationalExam).join(Worker).filter(OccupationalExam.id == exam_id).first()
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Examen ocupacional no encontrado"
        )
    
    # Calcular fecha del próximo examen (1 año después)
    from datetime import timedelta
    next_exam_date = exam.exam_date + timedelta(days=365)
    
    # Mapear medical_aptitude_concept a result legacy
    result_mapping = {
        "apto": "apto",
        "apto_con_recomendaciones": "apto_con_restricciones",
        "no_apto": "no_apto"
    }
    
    # Crear respuesta enriquecida con datos del trabajador
    worker = exam.worker
    exam_dict = {
        "id": exam.id,
        "exam_type": exam.exam_type,
        "exam_date": exam.exam_date,
        "programa": exam.programa,
        "occupational_conclusions": exam.occupational_conclusions,
        "preventive_occupational_behaviors": exam.preventive_occupational_behaviors,
        "general_recommendations": exam.general_recommendations,
        "medical_aptitude_concept": exam.medical_aptitude_concept,
        "observations": exam.observations,
        "examining_doctor": exam.examining_doctor,
        "medical_center": exam.medical_center,
        "worker_id": exam.worker_id,
        "worker_name": worker.full_name if worker else None,
        "worker_document": worker.document_number if worker else None,
        "worker_position": worker.position if worker else None,
        "worker_hire_date": worker.fecha_de_ingreso.isoformat() if worker and worker.fecha_de_ingreso else None,
        "next_exam_date": next_exam_date.isoformat(),
        
        # Campos legacy para compatibilidad con el frontend
        "status": "realizado",
        "result": result_mapping.get(exam.medical_aptitude_concept, "pendiente"),
        "restrictions": exam.general_recommendations if exam.medical_aptitude_concept == "apto_con_recomendaciones" else None,
        
        "created_at": exam.created_at,
        "updated_at": exam.updated_at
    }
    
    return exam_dict


@router.put("/occupational-exams/{exam_id}", response_model=OccupationalExamResponse)
async def update_occupational_exam(
    exam_id: int,
    exam_data: OccupationalExamUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """
    Actualizar un examen ocupacional
    """
    exam = db.query(OccupationalExam).filter(OccupationalExam.id == exam_id).first()
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Examen ocupacional no encontrado"
        )
    
    # Guardar el programa anterior para comparar
    old_programa = exam.programa
    
    update_data = exam_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(exam, field, value)
    
    db.commit()
    db.refresh(exam)
    
    # Crear seguimiento automáticamente si se asigna un programa nuevo
    if exam.programa and exam.programa.strip() and exam.programa != old_programa:
        worker = db.query(Worker).filter(Worker.id == exam.worker_id).first()
        if worker:
            # Verificar si ya existe un seguimiento activo para este programa
            existing_seguimiento = db.query(Seguimiento).filter(
                Seguimiento.worker_id == exam.worker_id,
                Seguimiento.programa == exam.programa,
                Seguimiento.estado == EstadoSeguimiento.INICIADO
            ).first()
            
            if not existing_seguimiento:
                # Crear nuevo seguimiento automáticamente
                seguimiento = Seguimiento(
                    worker_id=exam.worker_id,
                    programa=exam.programa,
                    nombre_trabajador=worker.full_name,
                    cedula=worker.document_number,
                    cargo=worker.position,
                    fecha_ingreso=worker.fecha_de_ingreso,
                    estado=EstadoSeguimiento.INICIADO,
                    # Copiar datos del examen ocupacional
                    conclusiones_ocupacionales=exam.occupational_conclusions,
                    conductas_ocupacionales_prevenir=exam.preventive_occupational_behaviors,
                    recomendaciones_generales=exam.general_recommendations,
                    observaciones_examen=exam.observations
                )
                db.add(seguimiento)
                db.commit()
    
    # Calcular fecha del próximo examen (1 año después)
    from datetime import timedelta
    next_exam_date = exam.exam_date + timedelta(days=365)
    
    # Obtener información del trabajador para la respuesta
    worker = db.query(Worker).filter(Worker.id == exam.worker_id).first()
    
    # Mapear medical_aptitude_concept a result legacy
    result_mapping = {
        "apto": "apto",
        "apto_con_recomendaciones": "apto_con_restricciones",
        "no_apto": "no_apto"
    }
    
    # Crear respuesta enriquecida con datos del trabajador
    exam_dict = {
        "id": exam.id,
        "exam_type": exam.exam_type,
        "exam_date": exam.exam_date,
        "programa": exam.programa,
        "occupational_conclusions": exam.occupational_conclusions,
        "preventive_occupational_behaviors": exam.preventive_occupational_behaviors,
        "general_recommendations": exam.general_recommendations,
        "medical_aptitude_concept": exam.medical_aptitude_concept,
        "observations": exam.observations,
        "examining_doctor": exam.examining_doctor,
        "medical_center": exam.medical_center,
        "worker_id": exam.worker_id,
        "worker_name": worker.full_name if worker else None,
        "worker_document": worker.document_number if worker else None,
        "worker_position": worker.position if worker else None,
        "worker_hire_date": worker.fecha_de_ingreso.isoformat() if worker and worker.fecha_de_ingreso else None,
        "next_exam_date": next_exam_date.isoformat(),
        
        # Campos legacy para compatibilidad con el frontend
        "status": "realizado",
        "result": result_mapping.get(exam.medical_aptitude_concept, "pendiente"),
        "restrictions": exam.general_recommendations if exam.medical_aptitude_concept == "apto_con_recomendaciones" else None,
        
        "created_at": exam.created_at,
        "updated_at": exam.updated_at
    }
    
    return exam_dict


@router.delete("/occupational-exams/{exam_id}", response_model=MessageResponse)
async def delete_occupational_exam(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
) -> Any:
    """
    Eliminar un examen ocupacional (solo administradores)
    """
    exam = db.query(OccupationalExam).filter(OccupationalExam.id == exam_id).first()
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Examen ocupacional no encontrado"
        )
    
    db.delete(exam)
    db.commit()
    
    return MessageResponse(message="Examen ocupacional eliminado exitosamente")


@router.get("/export/excel")
async def export_workers_to_excel(
    search: str = Query(None, description="Buscar por nombre, documento o email"),
    is_active: bool = Query(None, description="Filtrar por estado activo"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> StreamingResponse:
    """
    Exportar trabajadores a Excel
    """
    # Obtener trabajadores con los mismos filtros que el endpoint principal
    query = db.query(Worker)
    
    # Filtro de búsqueda
    if search:
        search_filter = or_(
            Worker.first_name.ilike(f"%{search}%"),
            Worker.last_name.ilike(f"%{search}%"),
            Worker.document_number.ilike(f"%{search}%"),
            Worker.email.ilike(f"%{search}%")
        )
        query = query.filter(search_filter)
    
    # Filtro por estado activo
    if is_active is not None:
        query = query.filter(Worker.is_active == is_active)
    
    workers = query.all()
    
    # Crear el archivo Excel
    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.title = "Trabajadores"
    
    # Definir estilos
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
    header_alignment = Alignment(horizontal="center", vertical="center")
    
    # Encabezados
    headers = [
        "ID", "Nombre", "Apellido", "Tipo Documento", "Número Documento", 
        "Email", "Teléfono", "Fecha Nacimiento", "Género", "Ciudad", 
        "Departamento", "País", "Cargo", "Fecha Ingreso", "Tipo Contrato", 
        "Modalidad Trabajo", "Profesión", "Nivel Riesgo", "Ocupación", 
        "Salario IBC", "EPS", "AFP", "ARL", "Tipo Sangre", "Observaciones", 
        "Estado", "Rol Asignado", "Fecha Creación"
    ]
    
    # Escribir encabezados
    for col, header in enumerate(headers, 1):
        cell = worksheet.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
    
    # Escribir datos de trabajadores
    for row, worker in enumerate(workers, 2):
        worksheet.cell(row=row, column=1, value=worker.id)
        worksheet.cell(row=row, column=2, value=worker.first_name)
        worksheet.cell(row=row, column=3, value=worker.last_name)
        worksheet.cell(row=row, column=4, value=worker.document_type)
        worksheet.cell(row=row, column=5, value=worker.document_number)
        worksheet.cell(row=row, column=6, value=worker.email)
        worksheet.cell(row=row, column=7, value=worker.phone)
        worksheet.cell(row=row, column=8, value=worker.birth_date.strftime("%Y-%m-%d") if worker.birth_date else "")
        worksheet.cell(row=row, column=9, value=worker.gender)
        worksheet.cell(row=row, column=10, value=worker.city)
        worksheet.cell(row=row, column=11, value=worker.department)
        worksheet.cell(row=row, column=12, value=worker.country)
        worksheet.cell(row=row, column=13, value=worker.position)
        worksheet.cell(row=row, column=14, value=worker.fecha_de_ingreso.strftime("%Y-%m-%d") if worker.fecha_de_ingreso else "")
        worksheet.cell(row=row, column=15, value=worker.contract_type)
        worksheet.cell(row=row, column=16, value=worker.work_modality)
        worksheet.cell(row=row, column=17, value=worker.profession)
        worksheet.cell(row=row, column=18, value=worker.risk_level)
        worksheet.cell(row=row, column=19, value=worker.occupation)
        worksheet.cell(row=row, column=20, value=float(worker.salary_ibc) if worker.salary_ibc else "")
        worksheet.cell(row=row, column=21, value=worker.eps)
        worksheet.cell(row=row, column=22, value=worker.afp)
        worksheet.cell(row=row, column=23, value=worker.arl)
        worksheet.cell(row=row, column=24, value=worker.blood_type)
        worksheet.cell(row=row, column=25, value=worker.observations)
        worksheet.cell(row=row, column=26, value="Activo" if worker.is_active else "Inactivo")
        worksheet.cell(row=row, column=27, value=worker.assigned_role)
        worksheet.cell(row=row, column=28, value=worker.created_at.strftime("%Y-%m-%d %H:%M:%S") if worker.created_at else "")
    
    # Ajustar ancho de columnas
    for column in worksheet.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 50)
        worksheet.column_dimensions[column_letter].width = adjusted_width
    
    # Guardar en memoria
    excel_buffer = BytesIO()
    workbook.save(excel_buffer)
    excel_buffer.seek(0)
    
    # Generar nombre de archivo con timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"trabajadores_{timestamp}.xlsx"
    
    # Retornar como respuesta de streaming
    return StreamingResponse(
        BytesIO(excel_buffer.read()),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# Endpoints para documentos de trabajadores
@router.post("/{worker_id}/documents", response_model=WorkerDocumentResponse)
async def upload_worker_document(
    worker_id: int,
    title: str = Form(...),
    category: str = Form(...),
    description: str = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Subir un documento para un trabajador específico"""
    # Verificar que el trabajador existe
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail="Trabajador no encontrado")
    
    # Mapear categorías del frontend a los valores del enum
    category_mapping = {
        "Identificación": DocumentCategory.IDENTIFICATION,
        "identificacion": DocumentCategory.IDENTIFICATION,
        "Contrato": DocumentCategory.CONTRACT,
        "contrato": DocumentCategory.CONTRACT,
        "Médico": DocumentCategory.MEDICAL,
        "medico": DocumentCategory.MEDICAL,
        "Capacitación": DocumentCategory.TRAINING,
        "capacitacion": DocumentCategory.TRAINING,
        "Certificación": DocumentCategory.CERTIFICATION,
        "certificacion": DocumentCategory.CERTIFICATION,
        "Personal": DocumentCategory.PERSONAL,
        "personal": DocumentCategory.PERSONAL,
        "Otro": DocumentCategory.OTHER,
        "otro": DocumentCategory.OTHER
    }
    
    # Validar y convertir la categoría
    if category not in category_mapping:
        valid_categories = list(category_mapping.keys())
        raise HTTPException(
            status_code=400, 
            detail=f"Categoría no válida. Las categorías válidas son: {', '.join(valid_categories)}"
        )
    
    document_category = category_mapping[category]
    
    # Validar tipo de archivo
    allowed_types = [
        "application/pdf",
        "image/jpeg", "image/jpg", "image/png", "image/gif",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    ]
    
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400, 
            detail="Tipo de archivo no permitido. Solo se permiten PDF, imágenes, Word y Excel."
        )
    
    # Generar nombre único para el archivo
    file_extension = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    
    try:
        # Leer el contenido del archivo
        file_content = await file.read()
        
        # Convertir bytes a BytesIO para Firebase Storage
        file_stream = BytesIO(file_content)
        
        # Subir a Firebase Storage
        storage_service = FirebaseStorageService()
        file_path = f"worker_documents/{worker_id}/{unique_filename}"
        file_url = storage_service.upload_file(file_stream, file_path, file.content_type)
        
        # Crear registro en la base de datos
        db_document = WorkerDocument(
            worker_id=worker_id,
            title=title,
            description=description,
            category=document_category,
            file_name=file.filename,
            file_url=file_url,
            file_size=len(file_content),
            file_type=file.content_type,
            uploaded_by=current_user.id
        )
        
        db.add(db_document)
        db.commit()
        db.refresh(db_document)
        
        # Obtener información del usuario que subió el archivo
        uploader = db.query(User).filter(User.id == current_user.id).first()
        
        # Crear respuesta
        response_data = WorkerDocumentResponse(
            id=db_document.id,
            title=db_document.title,
            description=db_document.description,
            category=db_document.category,
            file_name=db_document.file_name,
            file_url=db_document.file_url,
            file_size=db_document.file_size,
            file_type=db_document.file_type,
            uploaded_by=db_document.uploaded_by,
            uploader_name=f"{uploader.first_name} {uploader.last_name}" if uploader else None,
            is_active=db_document.is_active,
            created_at=db_document.created_at,
            updated_at=db_document.updated_at
        )
        
        return response_data
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al subir el documento: {str(e)}")


@router.get("/{worker_id}/documents", response_model=List[WorkerDocumentResponse])
def get_worker_documents(
    worker_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtener todos los documentos de un trabajador"""
    # Verificar que el trabajador existe
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail="Trabajador no encontrado")
    
    # Obtener documentos activos
    documents = db.query(WorkerDocument).filter(
        WorkerDocument.worker_id == worker_id,
        WorkerDocument.is_active == True
    ).order_by(WorkerDocument.created_at.desc()).all()
    
    # Crear respuesta con información del usuario que subió cada documento
    response_documents = []
    for doc in documents:
        uploader = db.query(User).filter(User.id == doc.uploaded_by).first()
        response_data = WorkerDocumentResponse(
            id=doc.id,
            title=doc.title,
            description=doc.description,
            category=doc.category,
            file_name=doc.file_name,
            file_url=doc.file_url,
            file_size=doc.file_size,
            file_type=doc.file_type,
            uploaded_by=doc.uploaded_by,
            uploader_name=f"{uploader.first_name} {uploader.last_name}" if uploader else None,
            is_active=doc.is_active,
            created_at=doc.created_at,
            updated_at=doc.updated_at
        )
        response_documents.append(response_data)
    
    return response_documents


@router.get("/{worker_id}/documents/{document_id}", response_model=WorkerDocumentResponse)
def get_worker_document(
    worker_id: int,
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtener un documento específico de un trabajador"""
    # Verificar que el trabajador existe
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail="Trabajador no encontrado")
    
    # Obtener el documento
    document = db.query(WorkerDocument).filter(
        WorkerDocument.id == document_id,
        WorkerDocument.worker_id == worker_id,
        WorkerDocument.is_active == True
    ).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    
    # Obtener información del usuario que subió el documento
    uploader = db.query(User).filter(User.id == document.uploaded_by).first()
    
    response_data = WorkerDocumentResponse(
        id=document.id,
        title=document.title,
        description=document.description,
        category=document.category,
        file_name=document.file_name,
        file_url=document.file_url,
        file_size=document.file_size,
        file_type=document.file_type,
        uploaded_by=document.uploaded_by,
        uploader_name=f"{uploader.first_name} {uploader.last_name}" if uploader else None,
        is_active=document.is_active,
        created_at=document.created_at,
        updated_at=document.updated_at
    )
    
    return response_data


@router.put("/{worker_id}/documents/{document_id}", response_model=WorkerDocumentResponse)
def update_worker_document(
    worker_id: int,
    document_id: int,
    document_update: WorkerDocumentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Actualizar información de un documento"""
    # Verificar que el trabajador existe
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail="Trabajador no encontrado")
    
    # Obtener el documento
    document = db.query(WorkerDocument).filter(
        WorkerDocument.id == document_id,
        WorkerDocument.worker_id == worker_id
    ).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    
    # Actualizar campos
    update_data = document_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(document, field, value)
    
    document.updated_at = datetime.utcnow()
    
    try:
        db.commit()
        db.refresh(document)
        
        # Obtener información del usuario que subió el documento
        uploader = db.query(User).filter(User.id == document.uploaded_by).first()
        
        response_data = WorkerDocumentResponse(
            id=document.id,
            title=document.title,
            description=document.description,
            category=document.category,
            file_name=document.file_name,
            file_url=document.file_url,
            file_size=document.file_size,
            file_type=document.file_type,
            uploaded_by=document.uploaded_by,
            uploader_name=f"{uploader.first_name} {uploader.last_name}" if uploader else None,
            is_active=document.is_active,
            created_at=document.created_at,
            updated_at=document.updated_at
        )
        
        return response_data
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al actualizar el documento: {str(e)}")


@router.delete("/{worker_id}/documents/{document_id}")
def delete_worker_document(
    worker_id: int,
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Eliminar un documento (soft delete)"""
    # Verificar que el trabajador existe
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail="Trabajador no encontrado")
    
    # Obtener el documento
    document = db.query(WorkerDocument).filter(
        WorkerDocument.id == document_id,
        WorkerDocument.worker_id == worker_id
    ).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    
    # Eliminar archivo del storage de Firebase
    if document.file_path:
        try:
            firebase_storage_service = FirebaseStorageService()
            firebase_storage_service.delete_file(document.file_path)
        except Exception as e:
            # Log el error pero continúa con la eliminación del registro
            print(f"Error al eliminar archivo del storage: {str(e)}")
    
    # Soft delete
    document.is_active = False
    document.updated_at = datetime.utcnow()
    
    try:
        db.commit()
        return {"message": "Documento eliminado exitosamente"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al eliminar el documento: {str(e)}")


@router.get("/{worker_id}/documents/{document_id}/download")
async def download_worker_document(
    worker_id: int,
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Descargar un documento"""
    # Verificar que el trabajador existe
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail="Trabajador no encontrado")
    
    # Obtener el documento
    document = db.query(WorkerDocument).filter(
        WorkerDocument.id == document_id,
        WorkerDocument.worker_id == worker_id,
        WorkerDocument.is_active == True
    ).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    
    try:
        # Descargar desde Firebase Storage
        storage_service = FirebaseStorageService()
        file_content = storage_service.download_file(document.file_url)
        
        return Response(
            content=file_content,
            media_type=document.file_type or "application/octet-stream",
            headers={
                "Content-Disposition": f"attachment; filename={document.file_name}"
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al descargar el documento: {str(e)}")


@router.get("/{worker_id}/reinduction-history")
async def get_worker_reinduction_history(
    worker_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    Obtener historial de reinducciones de un trabajador específico
    """
    # Verificar que el trabajador existe
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trabajador no encontrado"
        )
    
    # Verificar permisos: el trabajador solo puede ver su propio historial
    # Los supervisores y admins pueden ver cualquier historial
    user_worker = db.query(Worker).filter(Worker.user_id == current_user.id).first()
    if (current_user.role.value not in ["admin", "supervisor"] and 
        (not user_worker or user_worker.id != worker_id)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para ver este historial"
        )
    
    # Obtener registros de reinducción ordenados por fecha descendente
    reinduction_records = db.query(ReinductionRecord).filter(
        ReinductionRecord.worker_id == worker_id
    ).order_by(ReinductionRecord.created_at.desc()).all()
    
    # Formatear respuesta
    history = []
    for record in reinduction_records:
        history.append({
            "id": record.id,
            "year": record.year,
            "status": record.status.value,
            "due_date": record.due_date.isoformat() if record.due_date else None,
            "completed_date": record.completed_date.isoformat() if record.completed_date else None,
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "updated_at": record.updated_at.isoformat() if record.updated_at else None
        })
    
    return {
        "worker_id": worker_id,
        "worker_name": worker.full_name,
        "total_records": len(history),
        "reinduction_history": history
    }


# ==================== ENDPOINTS DE NOVEDADES ====================

@router.post("/{worker_id}/novedades", response_model=WorkerNovedadResponse)
async def create_worker_novedad(
    worker_id: int,
    novedad_data: WorkerNovedadCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """Crear una nueva novedad para un trabajador"""
    
    # Verificar que el trabajador existe
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail="Trabajador no encontrado")
    
    # Validar que worker_id coincida
    if novedad_data.worker_id != worker_id:
        raise HTTPException(status_code=400, detail="El worker_id no coincide")
    
    # Crear la novedad
    novedad = WorkerNovedad(
        worker_id=worker_id,
        tipo=novedad_data.tipo,
        titulo=novedad_data.titulo,
        descripcion=novedad_data.descripcion,
        fecha_inicio=novedad_data.fecha_inicio,
        fecha_fin=novedad_data.fecha_fin,
        salario_anterior=novedad_data.salario_anterior,
        monto_aumento=novedad_data.monto_aumento,
        cantidad_horas=novedad_data.cantidad_horas,
        valor_hora=novedad_data.valor_hora,
        observaciones=novedad_data.observaciones,
        documento_soporte=novedad_data.documento_soporte,
        registrado_por=current_user.id
    )
    
    # Calcular campos automáticos
    novedad.calcular_dias()
    novedad.calcular_nuevo_salario()
    novedad.calcular_valor_total_horas()
    
    db.add(novedad)
    db.commit()
    db.refresh(novedad)
    
    # Preparar respuesta con información adicional
    response_data = WorkerNovedadResponse.from_orm(novedad)
    response_data.worker_name = worker.full_name
    response_data.worker_document = worker.document_number
    response_data.registrado_por_name = current_user.full_name if hasattr(current_user, 'full_name') else f"{current_user.first_name} {current_user.last_name}"
    
    return response_data


@router.get("/{worker_id}/novedades", response_model=List[WorkerNovedadList])
async def get_worker_novedades(
    worker_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    tipo: NovedadType = Query(None, description="Filtrar por tipo de novedad"),
    status: NovedadStatus = Query(None, description="Filtrar por estado"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Obtener todas las novedades de un trabajador"""
    
    # Verificar que el trabajador existe
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail="Trabajador no encontrado")
    
    # Construir query
    query = db.query(WorkerNovedad).filter(
        WorkerNovedad.worker_id == worker_id,
        WorkerNovedad.is_active == True
    )
    
    # Aplicar filtros
    if tipo:
        query = query.filter(WorkerNovedad.tipo == tipo)
    if status:
        query = query.filter(WorkerNovedad.status == status)
    
    # Ordenar por fecha de creación descendente
    query = query.order_by(WorkerNovedad.created_at.desc())
    
    # Aplicar paginación
    novedades = query.offset(skip).limit(limit).all()
    
    # Preparar respuesta con información adicional
    result = []
    for novedad in novedades:
        registrado_por_user = db.query(User).filter(User.id == novedad.registrado_por).first()
        registrado_por_name = "Usuario desconocido"
        if registrado_por_user:
            registrado_por_name = getattr(registrado_por_user, 'full_name', f"{registrado_por_user.first_name} {registrado_por_user.last_name}")
        
        # Obtener información del aprobador si existe
        aprobado_por_name = None
        if novedad.aprobado_por:
            aprobado_por_user = db.query(User).filter(User.id == novedad.aprobado_por).first()
            if aprobado_por_user:
                aprobado_por_name = getattr(aprobado_por_user, 'full_name', f"{aprobado_por_user.first_name} {aprobado_por_user.last_name}")
        
        novedad_data = WorkerNovedadList(
            id=novedad.id,
            worker_id=novedad.worker_id,
            worker_name=worker.full_name,
            worker_document=worker.document_number,
            tipo=novedad.tipo,
            titulo=novedad.titulo,
            status=novedad.status,
            fecha_inicio=novedad.fecha_inicio,
            fecha_fin=novedad.fecha_fin,
            dias_calculados=novedad.dias_calculados,
            monto_aumento=novedad.monto_aumento,
            valor_total=novedad.valor_total,
            registrado_por_name=registrado_por_name,
            aprobado_por_name=aprobado_por_name,
            fecha_aprobacion=novedad.fecha_aprobacion,
            created_at=novedad.created_at
        )
        result.append(novedad_data)
    
    return result


@router.get("/novedades", response_model=List[WorkerNovedadList])
async def get_all_novedades(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    tipo: NovedadType = Query(None, description="Filtrar por tipo de novedad"),
    status: NovedadStatus = Query(None, description="Filtrar por estado"),
    search: str = Query(None, description="Buscar por nombre o documento del trabajador"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """Obtener todas las novedades del sistema"""
    
    # Construir query con join a workers
    query = db.query(WorkerNovedad).join(Worker).filter(
        WorkerNovedad.is_active == True
    )
    
    # Aplicar filtros
    if tipo:
        query = query.filter(WorkerNovedad.tipo == tipo)
    if status:
        query = query.filter(WorkerNovedad.status == status)
    if search:
        query = query.filter(
            or_(
                Worker.first_name.ilike(f"%{search}%"),
                Worker.last_name.ilike(f"%{search}%"),
                Worker.document_number.ilike(f"%{search}%")
            )
        )
    
    # Ordenar por fecha de creación descendente
    query = query.order_by(WorkerNovedad.created_at.desc())
    
    # Aplicar paginación
    novedades = query.offset(skip).limit(limit).all()
    
    # Preparar respuesta
    result = []
    for novedad in novedades:
        worker = novedad.worker
        registrado_por_user = db.query(User).filter(User.id == novedad.registrado_por).first()
        registrado_por_name = "Usuario desconocido"
        if registrado_por_user:
            registrado_por_name = getattr(registrado_por_user, 'full_name', f"{registrado_por_user.first_name} {registrado_por_user.last_name}")
        
        # Obtener información del aprobador si existe
        aprobado_por_name = None
        if novedad.aprobado_por:
            aprobado_por_user = db.query(User).filter(User.id == novedad.aprobado_por).first()
            if aprobado_por_user:
                aprobado_por_name = getattr(aprobado_por_user, 'full_name', f"{aprobado_por_user.first_name} {aprobado_por_user.last_name}")
        
        novedad_data = WorkerNovedadList(
            id=novedad.id,
            worker_id=novedad.worker_id,
            worker_name=worker.full_name,
            worker_document=worker.document_number,
            tipo=novedad.tipo,
            titulo=novedad.titulo,
            status=novedad.status,
            fecha_inicio=novedad.fecha_inicio,
            fecha_fin=novedad.fecha_fin,
            dias_calculados=novedad.dias_calculados,
            monto_aumento=novedad.monto_aumento,
            valor_total=novedad.valor_total,
            registrado_por_name=registrado_por_name,
            aprobado_por_name=aprobado_por_name,
            fecha_aprobacion=novedad.fecha_aprobacion,
            created_at=novedad.created_at
        )
        result.append(novedad_data)
    
    return result


@router.get("/novedades/{novedad_id}", response_model=WorkerNovedadResponse)
async def get_novedad(
    novedad_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Obtener una novedad específica"""
    
    novedad = db.query(WorkerNovedad).filter(
        WorkerNovedad.id == novedad_id,
        WorkerNovedad.is_active == True
    ).first()
    
    if not novedad:
        raise HTTPException(status_code=404, detail="Novedad no encontrada")
    
    # Preparar respuesta con información adicional
    worker = novedad.worker
    registrado_por_user = db.query(User).filter(User.id == novedad.registrado_por).first()
    aprobado_por_user = None
    if novedad.aprobado_por:
        aprobado_por_user = db.query(User).filter(User.id == novedad.aprobado_por).first()
    
    response_data = WorkerNovedadResponse.from_orm(novedad)
    response_data.worker_name = worker.full_name
    response_data.worker_document = worker.document_number
    
    if registrado_por_user:
        response_data.registrado_por_name = getattr(registrado_por_user, 'full_name', f"{registrado_por_user.first_name} {registrado_por_user.last_name}")
    
    if aprobado_por_user:
        response_data.aprobado_por_name = getattr(aprobado_por_user, 'full_name', f"{aprobado_por_user.first_name} {aprobado_por_user.last_name}")
    
    return response_data


@router.put("/novedades/{novedad_id}", response_model=WorkerNovedadResponse)
async def update_novedad(
    novedad_id: int,
    novedad_data: WorkerNovedadUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """Actualizar una novedad"""
    
    novedad = db.query(WorkerNovedad).filter(
        WorkerNovedad.id == novedad_id,
        WorkerNovedad.is_active == True
    ).first()
    
    if not novedad:
        raise HTTPException(status_code=404, detail="Novedad no encontrada")
    
    # Verificar que la novedad esté en estado pendiente para poder editarla
    if novedad.status != NovedadStatus.PENDIENTE:
        raise HTTPException(status_code=400, detail="Solo se pueden editar novedades en estado pendiente")
    
    # Actualizar campos
    update_data = novedad_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(novedad, field, value)
    
    # Recalcular campos automáticos
    novedad.calcular_dias()
    novedad.calcular_nuevo_salario()
    novedad.calcular_valor_total_horas()
    
    db.commit()
    db.refresh(novedad)
    
    # Preparar respuesta
    worker = novedad.worker
    response_data = WorkerNovedadResponse.from_orm(novedad)
    response_data.worker_name = worker.full_name
    response_data.worker_document = worker.document_number
    
    return response_data


@router.post("/novedades/{novedad_id}/approve", response_model=WorkerNovedadResponse)
async def approve_reject_novedad(
    novedad_id: int,
    approval_data: WorkerNovedadApproval,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """Aprobar o rechazar una novedad"""
    
    novedad = db.query(WorkerNovedad).filter(
        WorkerNovedad.id == novedad_id,
        WorkerNovedad.is_active == True
    ).first()
    
    if not novedad:
        raise HTTPException(status_code=404, detail="Novedad no encontrada")
    
    # Verificar que la novedad esté pendiente
    if novedad.status != NovedadStatus.PENDIENTE:
        raise HTTPException(status_code=400, detail="Solo se pueden aprobar/rechazar novedades pendientes")
    
    # Actualizar estado
    novedad.status = approval_data.status
    novedad.aprobado_por = current_user.id
    novedad.fecha_aprobacion = datetime.utcnow()
    
    if approval_data.observaciones:
        novedad.observaciones = approval_data.observaciones
    
    # Si es un aumento de salario aprobado, actualizar el salario del trabajador
    if (approval_data.status == NovedadStatus.APROBADA and 
        novedad.tipo == NovedadType.AUMENTO_SALARIO and 
        novedad.salario_nuevo):
        
        worker = novedad.worker
        worker.salary_ibc = float(novedad.salario_nuevo)
        novedad.status = NovedadStatus.PROCESADA  # Marcar como procesada
    
    db.commit()
    db.refresh(novedad)
    
    # Preparar respuesta
    worker = novedad.worker
    response_data = WorkerNovedadResponse.from_orm(novedad)
    response_data.worker_name = worker.full_name
    response_data.worker_document = worker.document_number
    response_data.aprobado_por_name = getattr(current_user, 'full_name', f"{current_user.first_name} {current_user.last_name}")
    
    return response_data


@router.delete("/novedades/{novedad_id}", response_model=MessageResponse)
async def delete_novedad(
    novedad_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
) -> Any:
    """Eliminar una novedad (soft delete)"""
    
    novedad = db.query(WorkerNovedad).filter(
        WorkerNovedad.id == novedad_id,
        WorkerNovedad.is_active == True
    ).first()
    
    if not novedad:
        raise HTTPException(status_code=404, detail="Novedad no encontrada")
    
    # Soft delete
    novedad.is_active = False
    
    db.commit()
    
    return {"message": "Novedad eliminada exitosamente"}


@router.get("/{worker_id}/novedades/stats", response_model=WorkerNovedadStats)
async def get_worker_novedades_stats(
    worker_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Obtener estadísticas de novedades de un trabajador específico"""
    
    # Verificar que el trabajador existe
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail="Trabajador no encontrado")
    
    # Verificar permisos: el trabajador solo puede ver sus propias estadísticas
    # Los supervisores y admins pueden ver cualquier estadística
    user_worker = db.query(Worker).filter(Worker.user_id == current_user.id).first()
    if (current_user.role.value not in ["admin", "supervisor"] and 
        (not user_worker or user_worker.id != worker_id)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para ver estas estadísticas"
        )
    
    # Contar por estado para este trabajador específico
    base_query = db.query(WorkerNovedad).filter(
        WorkerNovedad.worker_id == worker_id,
        WorkerNovedad.is_active == True
    )
    
    total_novedades = base_query.count()
    pendientes = base_query.filter(WorkerNovedad.status == NovedadStatus.PENDIENTE).count()
    aprobadas = base_query.filter(WorkerNovedad.status == NovedadStatus.APROBADA).count()
    rechazadas = base_query.filter(WorkerNovedad.status == NovedadStatus.RECHAZADA).count()
    procesadas = base_query.filter(WorkerNovedad.status == NovedadStatus.PROCESADA).count()
    
    # Contar por tipo para este trabajador específico
    por_tipo = {}
    for tipo in NovedadType:
        count = base_query.filter(WorkerNovedad.tipo == tipo).count()
        por_tipo[tipo.value] = count
    
    return WorkerNovedadStats(
        total_novedades=total_novedades,
        pendientes=pendientes,
        aprobadas=aprobadas,
        rechazadas=rechazadas,
        procesadas=procesadas,
        por_tipo=por_tipo
    )


@router.get("/novedades/stats/summary", response_model=WorkerNovedadStats)
async def get_novedades_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """Obtener estadísticas de novedades"""
    
    # Contar por estado
    total_novedades = db.query(WorkerNovedad).filter(WorkerNovedad.is_active == True).count()
    pendientes = db.query(WorkerNovedad).filter(
        WorkerNovedad.is_active == True,
        WorkerNovedad.status == NovedadStatus.PENDIENTE
    ).count()
    aprobadas = db.query(WorkerNovedad).filter(
        WorkerNovedad.is_active == True,
        WorkerNovedad.status == NovedadStatus.APROBADA
    ).count()
    rechazadas = db.query(WorkerNovedad).filter(
        WorkerNovedad.is_active == True,
        WorkerNovedad.status == NovedadStatus.RECHAZADA
    ).count()
    procesadas = db.query(WorkerNovedad).filter(
        WorkerNovedad.is_active == True,
        WorkerNovedad.status == NovedadStatus.PROCESADA
    ).count()
    
    # Contar por tipo
    por_tipo = {}
    for tipo in NovedadType:
        count = db.query(WorkerNovedad).filter(
            WorkerNovedad.is_active == True,
            WorkerNovedad.tipo == tipo
        ).count()
        por_tipo[tipo.value] = count
    
    return WorkerNovedadStats(
        total_novedades=total_novedades,
        pendientes=pendientes,
        aprobadas=aprobadas,
        rechazadas=rechazadas,
        procesadas=procesadas,
        por_tipo=por_tipo
    )
