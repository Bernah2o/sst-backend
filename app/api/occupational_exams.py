from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from datetime import date, timedelta

from app.database import get_db
from app.dependencies import get_current_user, require_admin, require_supervisor_or_admin
from app.models.user import User
from app.models.worker import Worker
from app.models.occupational_exam import OccupationalExam
from app.models.cargo import Cargo
from app.models.notification_acknowledgment import NotificationAcknowledgment
from app.schemas.occupational_exam import (
    OccupationalExamCreate,
    OccupationalExamUpdate,
    OccupationalExamResponse,
    OccupationalExamListResponse
)
from app.schemas.common import MessageResponse, PaginatedResponse

router = APIRouter()


@router.get("/", response_model=PaginatedResponse[OccupationalExamResponse])
@router.get("", response_model=PaginatedResponse[OccupationalExamResponse])
async def get_occupational_exams(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    exam_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    result: Optional[str] = Query(None),
    worker_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """
    Obtener lista paginada de exámenes ocupacionales con filtros
    """
    # Calculate offset
    skip = (page - 1) * limit
    
    # Base query with join to get worker information
    query = db.query(OccupationalExam).join(Worker)
    
    # Apply filters
    if exam_type:
        query = query.filter(OccupationalExam.exam_type == exam_type)
    
    if worker_id:
        query = query.filter(OccupationalExam.worker_id == worker_id)
    
    if search:
        query = query.filter(
            or_(
                Worker.first_name.ilike(f"%{search}%"),
                Worker.last_name.ilike(f"%{search}%"),
                Worker.document_number.ilike(f"%{search}%")
            )
        )
    
    # Get total count
    total = query.count()
    
    # Apply pagination and ordering
    exams = query.order_by(OccupationalExam.exam_date.desc()).offset(skip).limit(limit).all()
    
    # Enrich exam data with worker information
    enriched_exams = []
    for exam in exams:
        worker = exam.worker
        
        # Calcular fecha del próximo examen basado en la periodicidad del cargo
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
            "no_apto": "no_apto"
        }
        
        exam_dict = {
            "id": exam.id,
            "worker_id": exam.worker_id,
            "worker_name": worker.full_name if worker else None,
            "worker_document": worker.document_number if worker else None,
            "worker_position": worker.position if worker else None,
            "worker_hire_date": worker.fecha_de_ingreso.isoformat() if worker and worker.fecha_de_ingreso else None,
            "exam_type": exam.exam_type,
            "exam_date": exam.exam_date.isoformat(),
            "programa": exam.programa,
            "occupational_conclusions": exam.occupational_conclusions,
            "preventive_occupational_behaviors": exam.preventive_occupational_behaviors,
            "general_recommendations": exam.general_recommendations,
            "medical_aptitude_concept": exam.medical_aptitude_concept,
            "observations": exam.observations,
            "examining_doctor": exam.examining_doctor,
            "medical_center": exam.medical_center,
            "supplier_id": exam.supplier_id,
            "doctor_id": exam.doctor_id,
            "next_exam_date": next_exam_date.isoformat(),
            
            # Campos legacy para compatibilidad con el frontend
            "status": "realizado",
            "result": result_mapping.get(exam.medical_aptitude_concept, "pendiente"),
            "restrictions": exam.general_recommendations if exam.medical_aptitude_concept == "apto_con_recomendaciones" else None,
            
            "created_at": exam.created_at.isoformat(),
            "updated_at": exam.updated_at.isoformat()
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
        "has_prev": has_prev
    }


@router.get("/calculate-next-exam-date/{worker_id}")
async def calculate_next_exam_date(
    worker_id: int,
    exam_date: str = Query(..., description="Fecha del examen en formato YYYY-MM-DD"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
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
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Trabajador no encontrado"
            )
        
        # Obtener cargo del trabajador
        cargo = db.query(Cargo).filter(Cargo.nombre_cargo == worker.position).first()
        
        # Convertir la fecha del examen
        try:
            exam_date_obj = datetime.strptime(exam_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Formato de fecha inválido. Use YYYY-MM-DD"
            )
        
        # Calcular fecha del próximo examen basado en la periodicidad del cargo
        periodicidad = cargo.periodicidad_emo if cargo else "anual"
        
        if periodicidad == "semestral":
            next_exam_date = exam_date_obj + timedelta(days=180)  # 6 meses
        elif periodicidad == "bianual":
            next_exam_date = exam_date_obj + timedelta(days=730)  # 2 años
        else:  # anual por defecto
            next_exam_date = exam_date_obj + timedelta(days=365)  # 1 año
        
        return {
            "next_exam_date": next_exam_date.isoformat(),
            "periodicidad": periodicidad,
            "worker_name": worker.full_name,
            "worker_position": worker.position,
            "cargo_name": cargo.nombre_cargo if cargo else "No especificado"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error calculando fecha del próximo examen: {str(e)}"
        )


@router.post("/", response_model=OccupationalExamResponse)
@router.post("", response_model=OccupationalExamResponse)
async def create_occupational_exam(
    exam_data: OccupationalExamCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """
    Crear un nuevo examen ocupacional
    """
    # Verify worker exists
    worker = db.query(Worker).filter(Worker.id == exam_data.worker_id).first()
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trabajador no encontrado"
        )
    
    # Create exam
    exam = OccupationalExam(**exam_data.dict())
    db.add(exam)
    db.commit()
    db.refresh(exam)
    
    # Calcular fecha del próximo examen basado en la periodicidad del cargo
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
        "supplier_id": exam.supplier_id,
        "doctor_id": exam.doctor_id,
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


@router.get("/{exam_id}", response_model=OccupationalExamResponse)
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
        "supplier_id": exam.supplier_id,
        "doctor_id": exam.doctor_id,
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


@router.put("/{exam_id}", response_model=OccupationalExamResponse)
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
    
    update_data = exam_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(exam, field, value)
    
    db.commit()
    db.refresh(exam)
    
    return exam


@router.delete("/{exam_id}", response_model=MessageResponse)
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


@router.get("/{exam_id}/certificate")
async def get_exam_certificate(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """
    Descargar certificado de examen ocupacional
    """
    exam = db.query(OccupationalExam).filter(OccupationalExam.id == exam_id).first()
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Examen ocupacional no encontrado"
        )
    
    # TODO: Implement certificate generation
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Generación de certificados no implementada"
    )


@router.post("/acknowledge-notification/{exam_id}", response_model=MessageResponse)
async def acknowledge_exam_notification(
    exam_id: int,
    worker_id: int = Query(..., description="ID del trabajador"),
    notification_type: str = Query(..., description="Tipo de notificación: first_notification, reminder, overdue"),
    request: Request = None,
    db: Session = Depends(get_db)
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
            detail="Examen ocupacional no encontrado"
        )
    
    # Verificar que el trabajador existe y está asociado al examen
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trabajador no encontrado"
        )
    
    if exam.worker_id != worker_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El examen no pertenece al trabajador especificado"
        )
    
    # Verificar que no existe ya una confirmación para este examen y tipo de notificación
    existing_ack = db.query(NotificationAcknowledgment).filter(
        and_(
            NotificationAcknowledgment.worker_id == worker_id,
            NotificationAcknowledgment.occupational_exam_id == exam_id,
            NotificationAcknowledgment.notification_type == notification_type
        )
    ).first()
    
    if existing_ack:
        return {
            "message": "La notificación ya había sido confirmada anteriormente",
            "success": True
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
        stops_notifications=True
    )
    
    db.add(acknowledgment)
    db.commit()
    db.refresh(acknowledgment)
    
    return {
        "message": f"Confirmación de recepción registrada exitosamente. No recibirá más notificaciones de tipo '{notification_type}' para este examen.",
        "success": True
    }