from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, UploadFile, File
from fastapi.responses import RedirectResponse, FileResponse, StreamingResponse
from sqlalchemy.orm import Session
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
    
    if result:
        # Map result filter to medical_aptitude_concept values
        result_mapping = {
            "apto": "apto",
            "apto_con_restricciones": "apto_con_recomendaciones",
            "no_apto": "no_apto"
        }
        medical_aptitude = result_mapping.get(result)
        if medical_aptitude:
            query = query.filter(OccupationalExam.medical_aptitude_concept == medical_aptitude)
    
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
            "pdf_file_path": exam.pdf_file_path,  # Campo que faltaba
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
        "pdf_file_path": exam.pdf_file_path,  # Campo faltante agregado
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


@router.get("/report/pdf")
async def generate_occupational_exam_report_pdf(
    worker_id: Optional[int] = Query(None, description="ID del trabajador específico"),
    exam_type: Optional[str] = Query(None, description="Tipo de examen"),
    start_date: Optional[date] = Query(None, description="Fecha de inicio del rango"),
    end_date: Optional[date] = Query(None, description="Fecha de fin del rango"),
    include_overdue: bool = Query(True, description="Incluir exámenes vencidos"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
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
            last_exam = db.query(OccupationalExam).filter(
                OccupationalExam.worker_id == worker.id
            ).order_by(OccupationalExam.exam_date.desc()).first()
            
            if last_exam:
                # Calcular fecha del próximo examen basado en la periodicidad del cargo
                cargo = db.query(Cargo).filter(Cargo.nombre_cargo == worker.position).first()
                periodicidad = cargo.periodicidad_emo if cargo else "anual"
                
                if periodicidad == "semestral":
                    next_exam_date = last_exam.exam_date + timedelta(days=180)  # 6 meses
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
                    "exam_type": last_exam.exam_type.replace("_", " ").title()
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
                    "exam_type": "Examen de Ingreso"
                }
                pending_exams.append(exam_data)
        
        # Preparar estadísticas
        statistics = {
            "total_workers": total_workers,
            "total_exams": len(exams),
            "pending_exams": len(pending_exams),
            "overdue_exams": len(overdue_exams)
        }
        
        # Preparar contexto para la plantilla
        context = {
            "generated_at": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "statistics": statistics,
            "total_pending": len(pending_exams),
            "total_overdue": len(overdue_exams),
            "pending_exams": pending_exams,
            "overdue_exams": overdue_exams if include_overdue else [],
            "logo_base64": None  # Se puede agregar el logo más tarde
        }
        
        # Generar PDF usando HTMLToPDFConverter
        converter = HTMLToPDFConverter()
        pdf_content = await converter.generate_pdf_from_template(
            "occupational_exam_report.html",
            context
        )
        
        # Crear nombre del archivo
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"reporte_examenes_ocupacionales_{timestamp}.pdf"
        
        # Configurar headers para la respuesta
        headers = {
            "Content-Type": "application/pdf",
            "Content-Disposition": f"attachment; filename={filename}"
        }
        
        return StreamingResponse(
            io.BytesIO(pdf_content),
            media_type="application/pdf",
            headers=headers
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generando el reporte de exámenes ocupacionales: {str(e)}"
        )


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
        "pdf_file_path": exam.pdf_file_path,  # Campo faltante agregado
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
    
    # Calcular fecha del próximo examen basado en la periodicidad del cargo
    worker = exam.worker
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
        "pdf_file_path": exam.pdf_file_path,  # Campo incluido
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


@router.post("/upload-pdf", response_model=dict)
async def upload_pdf_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """
    Cargar archivo PDF temporal para exámenes ocupacionales
    """
    # Verificar que el archivo es un PDF
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se permiten archivos PDF"
        )
    
    # Verificar el tipo de contenido
    if file.content_type != 'application/pdf':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo debe ser un PDF válido"
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
            headers=file.headers
        )
        
        # Subir archivo a S3 Storage como examen médico temporal
        result = await s3_service.upload_medical_exam(
            worker_id=0,  # ID temporal para archivos temporales
            file=temp_file,
            exam_type="temp"
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error al subir archivo: {result.get('error', 'Error desconocido')}"
            )
        
        return {
            "message": "Archivo PDF cargado exitosamente",
            "file_path": result["file_url"],
            "file_key": result["file_key"],
            "original_filename": file.filename,
            "success": True
        }
        
    except Exception as e:
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al cargar el archivo: {str(e)}"
        )


@router.post("/{exam_id}/upload-pdf", response_model=MessageResponse)
async def upload_exam_pdf(
    exam_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """
    Cargar archivo PDF para un examen ocupacional
    """
    # Verificar que el examen existe
    exam = db.query(OccupationalExam).filter(OccupationalExam.id == exam_id).first()
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Examen ocupacional no encontrado"
        )
    
    # Verificar que el archivo es un PDF
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se permiten archivos PDF"
        )
    
    # Verificar el tipo de contenido
    if file.content_type != 'application/pdf':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo debe ser un PDF válido"
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
            headers=file.headers
        )
        
        # Subir archivo a S3 Storage como examen médico
        result = await s3_service.upload_medical_exam(
            worker_id=exam.worker_id,
            file=temp_file,
            exam_type="ocupacional"
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error al subir archivo: {result.get('error', 'Error desconocido')}"
            )
        
        # Eliminar archivo anterior de S3 Storage si existe
        if exam.pdf_file_path:
            try:
                # Extraer la clave del archivo desde la URL de S3
                # Formato esperado: https://bucket-name.s3.amazonaws.com/path/to/file
                if "s3.amazonaws.com" in exam.pdf_file_path:
                    old_file_key = exam.pdf_file_path.split('.com/')[-1]
                    s3_service.delete_file(old_file_key)
            except Exception as e:
                # Ignorar errores al eliminar archivo anterior
                pass
        
        # Actualizar la URL del archivo en la base de datos
        exam.pdf_file_path = result["file_url"]
        db.commit()
        
        return {
            "message": "Archivo PDF cargado exitosamente",
            "success": True
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al cargar el archivo: {str(e)}"
        )


@router.delete("/{exam_id}/pdf", response_model=MessageResponse)
async def delete_exam_pdf(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """
    Eliminar archivo PDF de un examen ocupacional
    """
    # Verificar que el examen existe
    exam = db.query(OccupationalExam).filter(OccupationalExam.id == exam_id).first()
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Examen ocupacional no encontrado"
        )
    
    if not exam.pdf_file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No hay archivo PDF asociado a este examen"
        )
    
    # Eliminar archivo de S3 Storage
    try:
        # Extraer la clave del archivo desde la URL de S3
        # Formato esperado: https://bucket-name.s3.amazonaws.com/path/to/file
        if "s3.amazonaws.com" in exam.pdf_file_path:
            file_key = exam.pdf_file_path.split('.com/')[-1]
            result = s3_service.delete_file(file_key)
            
            if not result["success"]:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Error al eliminar el archivo de S3 Storage: {result.get('error', 'Error desconocido')}"
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="URL de archivo no válida para S3 Storage"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al eliminar el archivo: {str(e)}"
        )
    
    # Limpiar la ruta en la base de datos
    exam.pdf_file_path = None
    db.commit()
    
    return {
        "message": "Archivo PDF eliminado exitosamente",
        "success": True
    }


@router.get("/{exam_id}/pdf")
async def get_exam_pdf(
    exam_id: int,
    download: bool = Query(False, description="Si es True, fuerza la descarga del archivo"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
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
            detail="Examen ocupacional no encontrado"
        )
    
    if not exam.pdf_file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No hay archivo PDF asociado a este examen"
        )
    
    # Si es una URL de S3 Storage, descargar y servir el archivo
    if exam.pdf_file_path.startswith('http') and "s3.amazonaws.com" in exam.pdf_file_path:
        try:
            # Extraer la clave del archivo desde la URL de S3
            file_key = exam.pdf_file_path.split('.com/')[-1]
            
            # Obtener URL firmada para descarga desde S3
            signed_url_result = s3_service.get_signed_url(file_key, expiration=3600)
            
            if not signed_url_result["success"]:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Error al generar URL de descarga: {signed_url_result.get('error', 'Error desconocido')}"
                )
            
            async with httpx.AsyncClient() as client:
                response = await client.get(signed_url_result["signed_url"])
                response.raise_for_status()
                
                # Crear un stream de bytes
                pdf_content = io.BytesIO(response.content)
                
                # Configurar headers para la respuesta
                headers = {
                    "Content-Type": "application/pdf",
                }
                
                if download:
                    # Para forzar descarga
                    filename = f"Examen_Ocupacional_{exam.worker_name.replace(' ', '_') if exam.worker_name else exam_id}.pdf"
                    headers["Content-Disposition"] = f"attachment; filename={filename}"
                else:
                    # Para previsualización en el navegador
                    headers["Content-Disposition"] = "inline"
                
                return StreamingResponse(
                    io.BytesIO(response.content),
                    media_type="application/pdf",
                    headers=headers
                )
                
        except httpx.HTTPError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error al obtener el archivo PDF desde S3: {str(e)}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error interno al procesar el archivo PDF desde S3: {str(e)}"
            )
    
    # Si es una ruta local (legacy), manejar como antes
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Archivo no encontrado"
    )


@router.get("/{exam_id}/medical-recommendation-report")
async def generate_medical_recommendation_report(
    exam_id: int,
    download: bool = Query(True, description="Set to true to download the file with a custom filename"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
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
        from app.services.medical_recommendation_generator import MedicalRecommendationGenerator
        
        # Crear un seguimiento temporal para usar con el generador existente
        # Esto es necesario porque el generador actual espera un seguimiento
        from app.models.seguimiento import Seguimiento
        
        # Buscar si existe un seguimiento para este trabajador
        seguimiento = db.query(Seguimiento).filter(Seguimiento.worker_id == exam.worker_id).first()
        
        if not seguimiento:
            # Crear un seguimiento temporal si no existe
            seguimiento = Seguimiento(
                worker_id=exam.worker_id,
                fecha_seguimiento=exam.exam_date,
                observaciones=f"Seguimiento generado automáticamente para examen ocupacional {exam_id}",
                valoracion_riesgo="medio",
                recomendaciones=exam.general_recommendations or "Sin recomendaciones específicas"
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
            response_params = {
                "path": local_filepath,
                "media_type": "application/pdf"
            }
            
            # Si se solicita descarga, agregar un nombre de archivo personalizado
            if download:
                filename = f"notificacion_medica_{worker.document_number}_{exam_id}.pdf"
                response_params["filename"] = filename
            
            return FileResponse(**response_params)
        else:
            # Es una URL de Firebase/S3, redirigir o descargar
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
                        headers["Content-Disposition"] = f"attachment; filename={filename}"
                    else:
                        headers["Content-Disposition"] = "inline"
                    
                    return StreamingResponse(
                        io.BytesIO(response.content),
                        media_type="application/pdf",
                        headers=headers
                    )
            else:
                raise HTTPException(status_code=500, detail="Error procesando la URL del archivo")
                
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generando el reporte médico: {str(e)}"
        )