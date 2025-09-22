from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, UploadFile, File
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from datetime import date, timedelta
import os
import uuid
from pathlib import Path
import requests

from app.database import get_db
from app.services.firebase_storage_service import firebase_storage_service
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
    
    # Generar nombre único para el archivo en Firebase Storage
    file_extension = Path(file.filename).suffix
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    firebase_path = f"occupational_exams/temp/{unique_filename}"
    
    try:
        # Leer el contenido del archivo
        content = await file.read()
        
        # Subir archivo a Firebase Storage
        public_url = firebase_storage_service.upload_from_bytes(
            file_bytes=content,
            destination_path=firebase_path,
            content_type=file.content_type
        )
        
        return {
            "message": "Archivo PDF cargado exitosamente",
            "file_path": public_url,
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
    
    # Generar nombre único para el archivo en Firebase Storage
    file_extension = Path(file.filename).suffix
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    firebase_path = f"occupational_exams/{exam_id}/{unique_filename}"
    
    try:
        # Leer el contenido del archivo
        content = await file.read()
        
        # Subir archivo a Firebase Storage
        public_url = firebase_storage_service.upload_from_bytes(
            file_bytes=content,
            destination_path=firebase_path,
            content_type=file.content_type
        )
        
        # Eliminar archivo anterior de Firebase Storage si existe
        if exam.pdf_file_path:
            try:
                # Extraer la ruta de Firebase desde la URL
                old_firebase_path = exam.pdf_file_path.split('/')[-2:]  # Obtener las últimas dos partes de la ruta
                old_firebase_path = '/'.join(old_firebase_path)
                firebase_storage_service.delete_file(old_firebase_path)
            except Exception as e:
                # Ignorar errores al eliminar archivo anterior
                pass
        
        # Actualizar la URL del archivo en la base de datos
        exam.pdf_file_path = public_url
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
    
    # Eliminar archivo de Firebase Storage
    try:
        # Extraer la ruta de Firebase desde la URL
        # Asumiendo que la URL tiene el formato: https://storage.googleapis.com/bucket/path/to/file
        firebase_path = exam.pdf_file_path.split('/')[-2:]  # Obtener las últimas dos partes de la ruta
        firebase_path = '/'.join(firebase_path)
        
        success = firebase_storage_service.delete_file(firebase_path)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al eliminar el archivo de Firebase Storage"
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
    
    # Si es una URL de Firebase Storage, descargar y servir el archivo
    if exam.pdf_file_path.startswith('http'):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(exam.pdf_file_path)
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
                detail=f"Error al obtener el archivo PDF: {str(e)}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error interno al procesar el archivo PDF: {str(e)}"
            )
    
    # Si es una ruta local (legacy), manejar como antes
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Archivo no encontrado"
    )