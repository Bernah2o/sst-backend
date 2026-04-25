import os
from app.services.email_service import EmailService
from app.services.auth import auth_service
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form
import base64
from app.utils.storage import storage_manager
import re
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from datetime import datetime, date
import json

from app.database import get_db
from app.dependencies import get_current_user, require_supervisor_or_admin
from app.models.user import User, UserRole
from app.models.assessment import HomeworkAssessment, ErgonomicSelfInspection
from app.models.worker import Worker
from app.schemas.assessment import (
    HomeworkAssessment as AssessmentSchema,
    HomeworkAssessmentCreate,
    BulkAssessmentCreate,
    ErgonomicSelfInspection as ErgonomicSelfInspectionSchema,
    ErgonomicSelfInspectionCreate,
)
from app.services.html_to_pdf import HTMLToPDFConverter
from fastapi.responses import StreamingResponse
from io import BytesIO

router = APIRouter()

def sanitize_filename(filename: str) -> str:
    return re.sub(r'[^a-zA-Z0-9._-]', '_', filename)



@router.post("/homework/upload")
async def upload_assessment_photo(
    worker_id: int = Form(...),
    photo_type: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user) # Cualquier usuario logueado puede subir si tiene permiso
):
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail="Trabajador no encontrado")
        
    # Verificar permisos: Admin/Supervisor o el propio trabajador
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPERVISOR]:
        associated_worker = db.query(Worker).filter(Worker.user_id == current_user.id).first()
        if not associated_worker or associated_worker.id != worker_id:
             raise HTTPException(status_code=403, detail="No tiene permiso para subir archivos para este trabajador")

    # Construir ruta: Autoevaluación Trabajo en Casa/{worker_name}/fotos/
    worker_name = sanitize_filename(f"{worker.first_name}_{worker.last_name}")
    folder = f"Autoevaluacion_Trabajo_en_Casa/{worker_name}/fotos"
    
    try:
        # Renombrar archivo con el tipo de foto para organización
        extension = os.path.splitext(file.filename)[1]
        file.filename = f"{photo_type}{extension}"

        # Subir archivo
        result = await storage_manager.upload_file(file, folder=folder, keep_original_name=True)
        
        return {
            "url": result["url"],
            "filename": result["filename"],
            "type": photo_type
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al subir archivo: {str(e)}")


@router.post("/homework", response_model=AssessmentSchema)
async def create_homework_assessment(
    assessment: HomeworkAssessmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verificar trabajador
    worker = db.query(Worker).filter(Worker.id == assessment.worker_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail="Trabajador no encontrado")


    # Procesar firma si viene en base64
    if assessment.worker_signature and assessment.worker_signature.startswith('data:image'):
        try:
            # Decodificar base64
            header, encoded = assessment.worker_signature.split(",", 1)
            data = base64.b64decode(encoded)
            
            # Nombre de carpeta
            worker_name = sanitize_filename(f"{worker.first_name}_{worker.last_name}")
            folder = f"Autoevaluacion_Trabajo_en_Casa/{worker_name}"
            
            # Subir bytes
            result = await storage_manager.upload_bytes(data, filename="firma.png", folder=folder, content_type="image/png")
            assessment.worker_signature = result["url"]
        except Exception as e:
            print(f"Error subiendo firma: {e}")
            raise HTTPException(status_code=500, detail=f"Error al subir la firma: {str(e)}")

    # Procesar fotos y adjuntos
    photos_json = json.dumps(assessment.photos) if assessment.photos else None
    attachments_json = json.dumps(assessment.attachments) if assessment.attachments else None

    db_assessment = HomeworkAssessment(
        worker_id=assessment.worker_id,
        evaluation_date=assessment.evaluation_date,
        lighting_check=assessment.lighting_check,
        lighting_obs=assessment.lighting_obs,
        ventilation_check=assessment.ventilation_check,
        ventilation_obs=assessment.ventilation_obs,
        desk_check=assessment.desk_check,
        desk_obs=assessment.desk_obs,
        chair_check=assessment.chair_check,
        chair_obs=assessment.chair_obs,
        screen_check=assessment.screen_check,
        screen_obs=assessment.screen_obs,
        mouse_keyboard_check=assessment.mouse_keyboard_check,
        mouse_keyboard_obs=assessment.mouse_keyboard_obs,
        space_check=assessment.space_check,
        space_obs=assessment.space_obs,
        floor_check=assessment.floor_check,
        floor_obs=assessment.floor_obs,
        noise_check=assessment.noise_check,
        noise_obs=assessment.noise_obs,
        connectivity_check=assessment.connectivity_check,
        connectivity_obs=assessment.connectivity_obs,
        equipment_check=assessment.equipment_check,
        equipment_obs=assessment.equipment_obs,
        confidentiality_check=assessment.confidentiality_check,
        confidentiality_obs=assessment.confidentiality_obs,
        active_breaks_check=assessment.active_breaks_check,
        active_breaks_obs=assessment.active_breaks_obs,
        psychosocial_check=assessment.psychosocial_check,
        psychosocial_obs=assessment.psychosocial_obs,
        sst_observations=assessment.sst_observations,
        home_address=assessment.home_address,
        status="COMPLETED", # Si se crea desde el form, ya está completo
        photos_data=photos_json,
        attachments_data=attachments_json,
        worker_signature=assessment.worker_signature,
        sst_signature=assessment.sst_signature,
        created_by=current_user.id,
        sst_management_data=assessment.sst_management_data
    )
    
    db.add(db_assessment)
    db.commit()
    db.refresh(db_assessment)

    # Cargar la relación worker
    db.refresh(db_assessment, ['worker'])
    return db_assessment

@router.put("/homework/{assessment_id}", response_model=AssessmentSchema)
async def update_homework_assessment(
    assessment_id: int,
    assessment: HomeworkAssessmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_assessment = db.query(HomeworkAssessment).filter(HomeworkAssessment.id == assessment_id).first()
    if not db_assessment:
        raise HTTPException(status_code=404, detail="Evaluación no encontrada")
    
    # Verificar permisos (mismo usuario o admin)
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPERVISOR]:
        worker = db.query(Worker).filter(Worker.user_id == current_user.id).first()
        if not worker or db_assessment.worker_id != worker.id:
            raise HTTPException(status_code=403, detail="No tiene permiso para actualizar esta evaluación")


    # Procesar firma si viene en base64
    if assessment.worker_signature and assessment.worker_signature.startswith('data:image'):
        try:
            worker = db_assessment.worker # Usar relación
            # Decodificar base64
            header, encoded = assessment.worker_signature.split(",", 1)
            data = base64.b64decode(encoded)
            
            # Nombre de carpeta
            worker_name = sanitize_filename(f"{worker.first_name}_{worker.last_name}")
            folder = f"Autoevaluacion_Trabajo_en_Casa/{worker_name}"
            
            # Subir bytes
            result = await storage_manager.upload_bytes(data, filename="firma.png", folder=folder, content_type="image/png")
            assessment.worker_signature = result["url"]
        except Exception as e:
            print(f"Error subiendo firma: {e}")
            raise HTTPException(status_code=500, detail=f"Error al subir la firma: {str(e)}")
    
    # Actualizar campos
    db_assessment.evaluation_date = assessment.evaluation_date
    db_assessment.lighting_check = assessment.lighting_check
    db_assessment.lighting_obs = assessment.lighting_obs
    db_assessment.ventilation_check = assessment.ventilation_check
    db_assessment.ventilation_obs = assessment.ventilation_obs
    db_assessment.desk_check = assessment.desk_check
    db_assessment.desk_obs = assessment.desk_obs
    db_assessment.chair_check = assessment.chair_check
    db_assessment.chair_obs = assessment.chair_obs
    db_assessment.screen_check = assessment.screen_check
    db_assessment.screen_obs = assessment.screen_obs
    db_assessment.mouse_keyboard_check = assessment.mouse_keyboard_check
    db_assessment.mouse_keyboard_obs = assessment.mouse_keyboard_obs
    db_assessment.space_check = assessment.space_check
    db_assessment.space_obs = assessment.space_obs
    db_assessment.floor_check = assessment.floor_check
    db_assessment.floor_obs = assessment.floor_obs
    db_assessment.noise_check = assessment.noise_check
    db_assessment.noise_obs = assessment.noise_obs
    db_assessment.connectivity_check = assessment.connectivity_check
    db_assessment.connectivity_obs = assessment.connectivity_obs
    db_assessment.equipment_check = assessment.equipment_check
    db_assessment.equipment_obs = assessment.equipment_obs
    db_assessment.confidentiality_check = assessment.confidentiality_check
    db_assessment.confidentiality_obs = assessment.confidentiality_obs
    db_assessment.active_breaks_check = assessment.active_breaks_check
    db_assessment.active_breaks_obs = assessment.active_breaks_obs
    db_assessment.psychosocial_check = assessment.psychosocial_check
    db_assessment.psychosocial_obs = assessment.psychosocial_obs
    db_assessment.sst_observations = assessment.sst_observations
    db_assessment.home_address = assessment.home_address
    db_assessment.status = "COMPLETED"
    db_assessment.worker_signature = assessment.worker_signature
    db_assessment.sst_management_data = assessment.sst_management_data
    
    if assessment.photos:
        db_assessment.photos_data = json.dumps(assessment.photos)

    db.commit()
    db.refresh(db_assessment)

    # Cargar la relación worker
    db.refresh(db_assessment, ['worker'])
    return db_assessment

@router.post("/homework/bulk-assign")
def bulk_assign_homework_assessments(
    data: BulkAssessmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
):
    """
    Asigna evaluaciones de trabajo en casa a múltiples trabajadores.
    Crea registros con estado PENDING.
    """
    successful = []
    failed = []
    skipped = []

    for worker_id in data.worker_ids:
        worker = db.query(Worker).filter(Worker.id == worker_id).first()
        if not worker:
            failed.append({"id": worker_id, "error": "Trabajador no encontrado"})
            continue

        # Verificar si ya existe una evaluación pendiente para este trabajador
        existing_pending = db.query(HomeworkAssessment).filter(
            HomeworkAssessment.worker_id == worker_id,
            HomeworkAssessment.status == "PENDING"
        ).first()

        if existing_pending:
            skipped.append({"id": worker_id, "reason": "Ya tiene una evaluación pendiente"})
            continue

        try:
            assessment = HomeworkAssessment(
                worker_id=worker_id,
                evaluation_date=data.evaluation_date,
                status="PENDING",
                created_by=current_user.id
            )
            db.add(assessment)
            successful.append(worker_id)
        except Exception as e:
            failed.append({"id": worker_id, "error": str(e)})

    db.commit()

    return {
        "message": "Asignación masiva procesada",
        "successful_count": len(successful),
        "failed_count": len(failed),
        "skipped_count": len(skipped),
        "failed_details": failed,
        "skipped_details": skipped
    }


def _deactivate_retired_workers(db: Session) -> None:
    """
    Inactiva automáticamente trabajadores con fecha de retiro vencida.
    Esto evita que sigan apareciendo en reportes gerenciales activos.
    """
    today = date.today()
    affected = db.query(Worker).filter(
        Worker.is_active == True,
        Worker.fecha_de_retiro != None,
        Worker.fecha_de_retiro <= today
    ).update({Worker.is_active: False}, synchronize_session=False)
    if affected:
        db.commit()


def _active_homework_query(db: Session):
    """Base query para autoevaluaciones de trabajadores activos."""
    return db.query(HomeworkAssessment).join(
        Worker, HomeworkAssessment.worker_id == Worker.id
    ).filter(Worker.is_active == True)


def _active_ergonomic_query(db: Session):
    """Base query para autoinspecciones ergonómicas de trabajadores activos."""
    return db.query(ErgonomicSelfInspection).join(
        Worker, ErgonomicSelfInspection.worker_id == Worker.id
    ).filter(Worker.is_active == True)

@router.get("/homework/stats")
def get_homework_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
):
    """
    Obtiene estadísticas agregadas de las autoevaluaciones de trabajo en casa
    para análisis de cumplimiento y áreas de mejora.
    """
    _deactivate_retired_workers(db)
    active_q = _active_homework_query(db)

    total_count = active_q.count()
    completed_count = active_q.filter(HomeworkAssessment.status == "COMPLETED").count()
    pending_count = total_count - completed_count

    if completed_count == 0:
        return {
            "total": total_count,
            "completed": completed_count,
            "pending": pending_count,
            "compliance_by_category": [],
            "top_issues": []
        }

    # Categorías a evaluar
    categories = [
        ("lighting_check", "Iluminación"),
        ("ventilation_check", "Ventilación"),
        ("desk_check", "Mesa de Trabajo"),
        ("chair_check", "Silla Ergonómica"),
        ("screen_check", "Posición Pantalla"),
        ("mouse_keyboard_check", "Teclado y Ratón"),
        ("space_check", "Espacio Disponible"),
        ("floor_check", "Estado del Piso"),
        ("noise_check", "Ruido Ambiental"),
        ("connectivity_check", "Conectividad"),
        ("equipment_check", "Seguridad Equipos"),
        ("confidentiality_check", "Confidencialidad"),
        ("active_breaks_check", "Pausas Activas"),
        ("psychosocial_check", "Riesgo Psicosocial")
    ]

    compliance_data = []
    
    # Obtener sumas de cumplimiento (checks que son True)
    for field, label in categories:
        # Contar cuántos son True para este campo en evaluaciones COMPLETADAS
        count_true = db.query(func.count(HomeworkAssessment.id)).join(
            Worker, HomeworkAssessment.worker_id == Worker.id
        ).filter(
            Worker.is_active == True,
            HomeworkAssessment.status == "COMPLETED",
            getattr(HomeworkAssessment, field) == True
        ).scalar()
        
        percentage = (count_true / completed_count) * 100
        compliance_data.append({
            "category": label,
            "compliant_count": count_true,
            "non_compliant_count": completed_count - count_true,
            "percentage": round(percentage, 2)
        })

    # Top issues (categorías con menor cumplimiento)
    top_issues = sorted(compliance_data, key=lambda x: x["percentage"])[:5]

    # Resumen de estados de planes de acción (Seguimiento SST)
    all_management = db.query(HomeworkAssessment.sst_management_data).join(
        Worker, HomeworkAssessment.worker_id == Worker.id
    ).filter(
        Worker.is_active == True,
        HomeworkAssessment.sst_management_data != None
    ).all()
    
    action_stats = {"OPEN": 0, "IN_PROGRESS": 0, "CLOSED": 0}
    for (m_data_str,) in all_management:
        try:
            m_data = json.loads(m_data_str)
            for item in m_data.values():
                status = item.get("status", "OPEN")
                if status in action_stats:
                    action_stats[status] += 1
        except:
            continue

    return {
        "total": total_count,
        "completed": completed_count,
        "pending": pending_count,
        "compliance_by_category": compliance_data,
        "top_issues": top_issues,
        "action_stats": action_stats
    }

@router.get("/homework", response_model=List[AssessmentSchema])
def list_homework_assessments(
    worker_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(HomeworkAssessment).options(joinedload(HomeworkAssessment.worker))

    # Si no es supervisor/admin, solo puede ver sus propias evaluaciones (o las de su worker asociado)
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPERVISOR]:
        # Buscar el worker asociado al usuario
        worker = db.query(Worker).filter(Worker.user_id == current_user.id).first()
        if not worker:
            # Si no tiene worker asociado, no ve nada
            return []
        # Forzar filtro por worker_id
        query = query.filter(HomeworkAssessment.worker_id == worker.id)
    elif worker_id:
        # Si es admin/supervisor y especifica worker_id, filtrar
        query = query.filter(HomeworkAssessment.worker_id == worker_id)

    return query.order_by(HomeworkAssessment.evaluation_date.desc()).all()

@router.get("/homework/stats/pdf")
async def generate_dashboard_pdf(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
):
    """Genera un informe gerencial en PDF con el análisis consolidado de autoevaluaciones."""
    from datetime import date as date_cls

    # ── Reutilizar la misma lógica del endpoint /stats ──────────────────────
    _deactivate_retired_workers(db)
    active_q = _active_homework_query(db)

    total_count = active_q.count()
    completed_count = active_q.filter(HomeworkAssessment.status == "COMPLETED").count()
    pending_count = total_count - completed_count

    categories = [
        ("lighting_check", "Iluminación"),
        ("ventilation_check", "Ventilación"),
        ("desk_check", "Mesa de Trabajo"),
        ("chair_check", "Silla Ergonómica"),
        ("screen_check", "Posición Pantalla"),
        ("mouse_keyboard_check", "Teclado y Ratón"),
        ("space_check", "Espacio Disponible"),
        ("floor_check", "Estado del Piso"),
        ("noise_check", "Ruido Ambiental"),
        ("connectivity_check", "Conectividad"),
        ("equipment_check", "Seguridad Equipos"),
        ("confidentiality_check", "Confidencialidad"),
        ("active_breaks_check", "Pausas Activas"),
        ("psychosocial_check", "Riesgo Psicosocial"),
    ]

    compliance_data = []
    if completed_count > 0:
        for field, label in categories:
            count_true = db.query(func.count(HomeworkAssessment.id)).join(
                Worker, HomeworkAssessment.worker_id == Worker.id
            ).filter(
                Worker.is_active == True,
                HomeworkAssessment.status == "COMPLETED",
                getattr(HomeworkAssessment, field) == True
            ).scalar()
            pct = round((count_true / completed_count) * 100, 2)
            compliance_data.append({
                "category": label,
                "compliant_count": count_true,
                "non_compliant_count": completed_count - count_true,
                "percentage": pct,
            })

    top_issues = sorted(compliance_data, key=lambda x: x["percentage"])[:5]

    action_stats = {"OPEN": 0, "IN_PROGRESS": 0, "CLOSED": 0}
    for (m_data_str,) in db.query(HomeworkAssessment.sst_management_data).join(
        Worker, HomeworkAssessment.worker_id == Worker.id
    ).filter(
        Worker.is_active == True,
        HomeworkAssessment.sst_management_data != None
    ).all():
        try:
            for item in json.loads(m_data_str).values():
                s = item.get("status", "OPEN")
                if s in action_stats:
                    action_stats[s] += 1
        except Exception:
            pass

    stats = {
        "total": total_count,
        "completed": completed_count,
        "pending": pending_count,
        "compliance_by_category": compliance_data,
        "top_issues": top_issues,
        "action_stats": action_stats,
    }

    response_rate = round((completed_count / total_count * 100), 1) if total_count > 0 else 0

    recommendations = {
        "Iluminación": "Asegurar luz natural o lámpara de escritorio adecuada (≥500 lux). Eliminar reflejos.",
        "Ventilación": "Garantizar flujo de aire constante o ventilación mecánica. Temperatura entre 18-24 °C.",
        "Mesa de Trabajo": "Verificar altura adecuada (70-80 cm) y superficie estable. Espacio libre ≥60 cm de fondo.",
        "Silla Ergonómica": "Proveer o gestionar silla con apoyalumbar ajustable y altura regulable. Evaluar dotación.",
        "Posición Pantalla": "Elevar pantalla para que el borde superior quede a nivel de los ojos. Soporte portátil + teclado externo.",
        "Teclado y Ratón": "Usar teclado y mouse externos con apoyamuñecas. Antebrazos apoyados en escritorio.",
        "Espacio Disponible": "Reorganizar mobiliario para espacio libre para pies ≥50 cm de profundidad.",
        "Estado del Piso": "Retirar cables del piso. Instalar canaletas o cinta. Alfombra antideslizante si aplica.",
        "Ruido Ambiental": "Auriculares con cancelación activa de ruido. Acordar horarios de silencio con convivientes.",
        "Conectividad": "Revisar velocidad mínima requerida (≥10 Mbps). Reubicar router o instalar repetidor.",
        "Seguridad Equipos": "Inspeccionar cables eléctricos, regletas y cargadores. Usar supresores de pico.",
        "Confidencialidad": "Capacitación en bloqueo de pantalla y manejo de datos. Solicitar espacio privado.",
        "Pausas Activas": "Implementar alarmas o app de pausas activas. Guía de ejercicios cervicales y lumbares.",
        "Riesgo Psicosocial": "Programar seguimiento con bienestar o psicología. Establecer límites claros de horario.",
    }

    today = date_cls.today()
    converter = HTMLToPDFConverter()
    logo_b64 = converter._load_logo_base64()

    context = {
        "logo_base64": logo_b64,
        "stats": stats,
        "response_rate": response_rate,
        "recommendations": recommendations,
        "generated_date": today.strftime("%d/%m/%Y"),
        "period_label": f"Corte al {today.strftime('%d de %B de %Y')}",
    }

    pdf_bytes = await converter.generate_pdf_from_template("homework_dashboard_report.html", context)
    filename = f"Informe_Gerencial_TrabajoCasa_{today.strftime('%Y%m%d')}.pdf"

    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/homework/{assessment_id}/pdf")
async def generate_assessment_pdf(
    assessment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
):
    assessment = db.query(HomeworkAssessment).filter(HomeworkAssessment.id == assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Evaluación no encontrada")

    worker = assessment.worker

    converter = HTMLToPDFConverter()

    # Cargar logo en base64
    logo_base64 = converter._load_logo_base64()

    # Procesar fotos: convertir URLs a base64 si existen
    photos_base64 = {}
    if assessment.photos_data:
        try:
            photos_urls = json.loads(assessment.photos_data)
            for key, url in photos_urls.items():
                try:
                    # Descargar la imagen desde el storage
                    photo_bytes = await storage_manager.download_file(url)
                    if photo_bytes:
                        # Convertir a base64
                        photo_base64 = base64.b64encode(photo_bytes).decode('utf-8')
                        # Determinar el tipo de imagen
                        if url.lower().endswith('.png'):
                            photos_base64[key] = f"data:image/png;base64,{photo_base64}"
                        elif url.lower().endswith('.gif'):
                            photos_base64[key] = f"data:image/gif;base64,{photo_base64}"
                        else:
                            photos_base64[key] = f"data:image/jpeg;base64,{photo_base64}"
                except Exception as e:
                    print(f"Error cargando foto {key}: {e}")
                    continue
        except Exception as e:
            print(f"Error procesando fotos: {e}")

    # Preparar datos para la plantilla
    data = {
        "logo_base64": logo_base64,
        "worker": {
            "full_name": worker.full_name,
            "document_number": worker.document_number,
            "position": worker.position,
            "address": worker.direccion,
            "phone": worker.phone,
            "email": worker.email
        },
        "assessment": assessment,
        "evaluation_date": assessment.evaluation_date.strftime("%d/%m/%Y"),
        "photos": photos_base64
    }

    pdf_content = await converter.generate_pdf_from_template("homework_assessment.html", data)
    
    filename = f"Evaluacion_TrabajoCasa_{worker.document_number}_{assessment.evaluation_date}.pdf"
    
    return StreamingResponse(
        BytesIO(pdf_content),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.post("/homework/{assessment_id}/remind")
def send_assessment_reminder(
    assessment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
):
    """
    Envía un correo de recordatorio al trabajador para completar la evaluación.
    """
    assessment = db.query(HomeworkAssessment).filter(HomeworkAssessment.id == assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Evaluación no encontrada")
    
    worker = assessment.worker
    if not worker or not worker.email:
        raise HTTPException(status_code=400, detail="El trabajador no tiene correo electrónico registrado")
    
    # Enviar correo
    success = EmailService.send_homework_reminder(
        to_email=worker.email,
        user_name=f"{worker.first_name} {worker.last_name}",
        due_date=assessment.evaluation_date.strftime("%d/%m/%Y")
    )
    
    if not success:
        raise HTTPException(status_code=500, detail="Error al enviar el correo")
        
    return {"message": "Recordatorio enviado exitosamente"}


@router.delete("/homework/{assessment_id}")
async def delete_homework_assessment(
    assessment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
):
    """
    Elimina una evaluación de trabajo en casa y todos sus archivos asociados en Contabo.
    Solo accesible para supervisores y administradores.
    """
    assessment = db.query(HomeworkAssessment).filter(HomeworkAssessment.id == assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Evaluación no encontrada")

    try:
        # Lista para trackear archivos eliminados y errores
        deleted_files = []
        deletion_errors = []

        # 1. Eliminar fotos del storage
        if assessment.photos_data:
            try:
                photos_urls = json.loads(assessment.photos_data)
                for key, url in photos_urls.items():
                    try:
                        await storage_manager.delete_file(url)
                        deleted_files.append(f"photo_{key}")
                    except Exception as e:
                        deletion_errors.append(f"Error eliminando foto {key}: {str(e)}")
                        print(f"Error eliminando foto {key}: {e}")
            except Exception as e:
                deletion_errors.append(f"Error procesando fotos: {str(e)}")
                print(f"Error procesando fotos para eliminar: {e}")

        # 2. Eliminar firma del trabajador
        if assessment.worker_signature:
            try:
                await storage_manager.delete_file(assessment.worker_signature)
                deleted_files.append("worker_signature")
            except Exception as e:
                deletion_errors.append(f"Error eliminando firma trabajador: {str(e)}")
                print(f"Error eliminando firma trabajador: {e}")

        # 3. Eliminar firma SST si existe
        if assessment.sst_signature:
            try:
                await storage_manager.delete_file(assessment.sst_signature)
                deleted_files.append("sst_signature")
            except Exception as e:
                deletion_errors.append(f"Error eliminando firma SST: {str(e)}")
                print(f"Error eliminando firma SST: {e}")

        # 4. Eliminar registro de la base de datos
        db.delete(assessment)
        db.commit()

        # Preparar respuesta con detalles
        response = {
            "message": "Evaluación eliminada exitosamente",
            "id": assessment_id,
            "deleted_files_count": len(deleted_files),
            "deleted_files": deleted_files
        }

        # Incluir errores si los hubo (pero la evaluación se eliminó de todas formas)
        if deletion_errors:
            response["storage_warnings"] = deletion_errors

        return response

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al eliminar la evaluación: {str(e)}")


@router.get("/homework/proxy-image")
async def get_assessment_image(
    url: str = Query(..., description="URL de la imagen"),
    token: Optional[str] = Query(None, description="Token JWT para autenticación vía query param"),
    db: Session = Depends(get_db),
    # Quitamos la dependencia estricta de get_current_user aquí para manejar manualmente el token opcional
):
    """
    Proxy para descargar imágenes desde el almacenamiento (Contabo) y servirlas.
    Esto evita problemas de CORS y acceso a buckets privados.
    Permite autenticación por Header (Bearer) o Query Param (token).
    """
    # Autenticación manual
    user = None
    if token:
        try:
            user = auth_service.get_current_user(db, token)
        except Exception:
            pass # Token inválido en query param

    # Si no hay usuario por token, intentar header (aunque FastAPI no lo inyecta automáticamente si no usamos Depends)
    # Para simplificar y dado que el frontend manda token por query param para imagenes:
    if not user:
        raise HTTPException(status_code=401, detail="Autenticación requerida")

    # Validar acceso básico (cualquier usuario autenticado puede ver imágenes por ahora,
    # idealmente validar si la imagen le pertenece, pero es complejo solo con la URL)

    try:
        # Descargar archivo como bytes
        file_content = await storage_manager.download_file(url)

        if not file_content:
            raise HTTPException(status_code=404, detail="Imagen no encontrada")

        # Determinar content type
        content_type = "image/jpeg"
        if url.lower().endswith(".png"):
            content_type = "image/png"
        elif url.lower().endswith(".gif"):
            content_type = "image/gif"

        return StreamingResponse(BytesIO(file_content), media_type=content_type)

    except Exception as e:
        print(f"Error proxying image: {e}")
        raise HTTPException(status_code=500, detail="Error al recuperar la imagen")


async def _download_image_as_data_uri(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    try:
        image_bytes = await storage_manager.download_file(url)
        if not image_bytes:
            return None
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")
        if url.lower().endswith(".png"):
            return f"data:image/png;base64,{image_base64}"
        if url.lower().endswith(".gif"):
            return f"data:image/gif;base64,{image_base64}"
        return f"data:image/jpeg;base64,{image_base64}"
    except Exception:
        return None


@router.post("/ergonomic", response_model=ErgonomicSelfInspectionSchema)
async def create_ergonomic_self_inspection(
    inspection: ErgonomicSelfInspectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin),
):
    worker = db.query(Worker).filter(Worker.id == inspection.worker_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail="Trabajador no encontrado")

    if inspection.worker_signature and inspection.worker_signature.startswith("data:image"):
        try:
            _, encoded = inspection.worker_signature.split(",", 1)
            data = base64.b64decode(encoded)
            worker_name = sanitize_filename(f"{worker.first_name}_{worker.last_name}")
            folder = f"Autoinspeccion_Puesto_Ergonomico/{worker_name}"
            result = await storage_manager.upload_bytes(
                data,
                filename="firma_trabajador.png",
                folder=folder,
                content_type="image/png",
            )
            inspection.worker_signature = result["url"]
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error al subir la firma: {str(e)}")

    month_year = inspection.evaluation_date.strftime("%m/%Y")
    evaluator_name = (
        current_user.full_name
        if current_user.role in [UserRole.ADMIN, UserRole.SUPERVISOR]
        else None
    )

    db_inspection = ErgonomicSelfInspection(
        worker_id=inspection.worker_id,
        evaluation_date=inspection.evaluation_date,
        month_year=month_year,
        modality=inspection.modality,
        evaluator_name=evaluator_name,
        chair_height_check=inspection.chair_height_check,
        chair_height_obs=inspection.chair_height_obs,
        chair_lumbar_check=inspection.chair_lumbar_check,
        chair_lumbar_obs=inspection.chair_lumbar_obs,
        chair_armrests_check=inspection.chair_armrests_check,
        chair_armrests_obs=inspection.chair_armrests_obs,
        chair_condition_check=inspection.chair_condition_check,
        chair_condition_obs=inspection.chair_condition_obs,
        desk_elbows_90_check=inspection.desk_elbows_90_check,
        desk_elbows_90_obs=inspection.desk_elbows_90_obs,
        desk_leg_space_check=inspection.desk_leg_space_check,
        desk_leg_space_obs=inspection.desk_leg_space_obs,
        desk_edges_check=inspection.desk_edges_check,
        desk_edges_obs=inspection.desk_edges_obs,
        monitor_eye_level_check=inspection.monitor_eye_level_check,
        monitor_eye_level_obs=inspection.monitor_eye_level_obs,
        monitor_distance_check=inspection.monitor_distance_check,
        monitor_distance_obs=inspection.monitor_distance_obs,
        monitor_glare_check=inspection.monitor_glare_check,
        monitor_glare_obs=inspection.monitor_glare_obs,
        laptop_setup_check=inspection.laptop_setup_check,
        laptop_setup_obs=inspection.laptop_setup_obs,
        keyboard_mouse_level_check=inspection.keyboard_mouse_level_check,
        keyboard_mouse_level_obs=inspection.keyboard_mouse_level_obs,
        wrist_rest_check=inspection.wrist_rest_check,
        wrist_rest_obs=inspection.wrist_rest_obs,
        wrists_neutral_check=inspection.wrists_neutral_check,
        wrists_neutral_obs=inspection.wrists_neutral_obs,
        lighting_reflection_check=inspection.lighting_reflection_check,
        lighting_reflection_obs=inspection.lighting_reflection_obs,
        feet_on_floor_check=inspection.feet_on_floor_check,
        feet_on_floor_obs=inspection.feet_on_floor_obs,
        active_breaks_check=inspection.active_breaks_check,
        active_breaks_obs=inspection.active_breaks_obs,
        no_pain_check=inspection.no_pain_check,
        no_pain_obs=inspection.no_pain_obs,
        pain_discomfort=inspection.pain_discomfort,
        pain_region=inspection.pain_region,
        pain_intensity=inspection.pain_intensity,
        report_description=inspection.report_description,
        needs_medical_attention=inspection.needs_medical_attention,
        worker_signature=inspection.worker_signature,
        sst_signature=inspection.sst_signature,
        status="COMPLETED",
        sst_management_data=inspection.sst_management_data,
        created_by=current_user.id,
    )
    db.add(db_inspection)
    db.commit()
    db.refresh(db_inspection)
    db.refresh(db_inspection, ["worker"])
    return db_inspection


@router.put("/ergonomic/{inspection_id}", response_model=ErgonomicSelfInspectionSchema)
async def update_ergonomic_self_inspection(
    inspection_id: int,
    inspection: ErgonomicSelfInspectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_inspection = (
        db.query(ErgonomicSelfInspection)
        .options(joinedload(ErgonomicSelfInspection.worker))
        .filter(ErgonomicSelfInspection.id == inspection_id)
        .first()
    )
    if not db_inspection:
        raise HTTPException(status_code=404, detail="Autoinspección no encontrada")

    if current_user.role not in [UserRole.ADMIN, UserRole.SUPERVISOR]:
        worker = db.query(Worker).filter(Worker.user_id == current_user.id).first()
        if not worker or db_inspection.worker_id != worker.id:
            raise HTTPException(status_code=403, detail="No tiene permiso para actualizar esta autoinspección")
        if db_inspection.status != "PENDING":
            raise HTTPException(status_code=400, detail="Esta autoinspección ya fue respondida")

    if inspection.worker_signature and inspection.worker_signature.startswith("data:image"):
        try:
            worker = db_inspection.worker
            _, encoded = inspection.worker_signature.split(",", 1)
            data = base64.b64decode(encoded)
            worker_name = sanitize_filename(f"{worker.first_name}_{worker.last_name}")
            folder = f"Autoinspeccion_Puesto_Ergonomico/{worker_name}"
            result = await storage_manager.upload_bytes(
                data,
                filename="firma_trabajador.png",
                folder=folder,
                content_type="image/png",
            )
            inspection.worker_signature = result["url"]
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error al subir la firma: {str(e)}")

    db_inspection.evaluation_date = inspection.evaluation_date
    db_inspection.month_year = inspection.evaluation_date.strftime("%m/%Y")
    db_inspection.modality = inspection.modality
    if current_user.role in [UserRole.ADMIN, UserRole.SUPERVISOR] and not db_inspection.evaluator_name:
        db_inspection.evaluator_name = current_user.full_name

    db_inspection.chair_height_check = inspection.chair_height_check
    db_inspection.chair_height_obs = inspection.chair_height_obs
    db_inspection.chair_lumbar_check = inspection.chair_lumbar_check
    db_inspection.chair_lumbar_obs = inspection.chair_lumbar_obs
    db_inspection.chair_armrests_check = inspection.chair_armrests_check
    db_inspection.chair_armrests_obs = inspection.chair_armrests_obs
    db_inspection.chair_condition_check = inspection.chair_condition_check
    db_inspection.chair_condition_obs = inspection.chair_condition_obs

    db_inspection.desk_elbows_90_check = inspection.desk_elbows_90_check
    db_inspection.desk_elbows_90_obs = inspection.desk_elbows_90_obs
    db_inspection.desk_leg_space_check = inspection.desk_leg_space_check
    db_inspection.desk_leg_space_obs = inspection.desk_leg_space_obs
    db_inspection.desk_edges_check = inspection.desk_edges_check
    db_inspection.desk_edges_obs = inspection.desk_edges_obs

    db_inspection.monitor_eye_level_check = inspection.monitor_eye_level_check
    db_inspection.monitor_eye_level_obs = inspection.monitor_eye_level_obs
    db_inspection.monitor_distance_check = inspection.monitor_distance_check
    db_inspection.monitor_distance_obs = inspection.monitor_distance_obs
    db_inspection.monitor_glare_check = inspection.monitor_glare_check
    db_inspection.monitor_glare_obs = inspection.monitor_glare_obs
    db_inspection.laptop_setup_check = inspection.laptop_setup_check
    db_inspection.laptop_setup_obs = inspection.laptop_setup_obs

    db_inspection.keyboard_mouse_level_check = inspection.keyboard_mouse_level_check
    db_inspection.keyboard_mouse_level_obs = inspection.keyboard_mouse_level_obs
    db_inspection.wrist_rest_check = inspection.wrist_rest_check
    db_inspection.wrist_rest_obs = inspection.wrist_rest_obs
    db_inspection.wrists_neutral_check = inspection.wrists_neutral_check
    db_inspection.wrists_neutral_obs = inspection.wrists_neutral_obs

    db_inspection.lighting_reflection_check = inspection.lighting_reflection_check
    db_inspection.lighting_reflection_obs = inspection.lighting_reflection_obs
    db_inspection.feet_on_floor_check = inspection.feet_on_floor_check
    db_inspection.feet_on_floor_obs = inspection.feet_on_floor_obs
    db_inspection.active_breaks_check = inspection.active_breaks_check
    db_inspection.active_breaks_obs = inspection.active_breaks_obs
    db_inspection.no_pain_check = inspection.no_pain_check
    db_inspection.no_pain_obs = inspection.no_pain_obs

    db_inspection.pain_discomfort = inspection.pain_discomfort
    db_inspection.pain_region = inspection.pain_region
    db_inspection.pain_intensity = inspection.pain_intensity
    db_inspection.report_description = inspection.report_description
    db_inspection.needs_medical_attention = inspection.needs_medical_attention

    db_inspection.worker_signature = inspection.worker_signature
    db_inspection.sst_signature = inspection.sst_signature
    db_inspection.sst_management_data = inspection.sst_management_data
    db_inspection.status = "COMPLETED"

    db.commit()
    db.refresh(db_inspection)
    db.refresh(db_inspection, ["worker"])
    return db_inspection


@router.post("/ergonomic/bulk-assign")
async def bulk_assign_ergonomic_self_inspections(
    assignment: BulkAssessmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin),
):
    created = 0
    for worker_id in assignment.worker_ids:
        existing = (
            db.query(ErgonomicSelfInspection)
            .filter(
                ErgonomicSelfInspection.worker_id == worker_id,
                ErgonomicSelfInspection.status == "PENDING",
            )
            .first()
        )
        if existing:
            continue

        db_inspection = ErgonomicSelfInspection(
            worker_id=worker_id,
            evaluation_date=assignment.evaluation_date,
            month_year=assignment.evaluation_date.strftime("%m/%Y"),
            evaluator_name=current_user.full_name,
            status="PENDING",
            created_by=current_user.id,
        )
        db.add(db_inspection)
        created += 1

    db.commit()
    return {"message": "Asignación masiva completada", "created": created}


@router.get("/ergonomic", response_model=List[ErgonomicSelfInspectionSchema])
def list_ergonomic_self_inspections(
    worker_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(ErgonomicSelfInspection).options(joinedload(ErgonomicSelfInspection.worker))

    if current_user.role not in [UserRole.ADMIN, UserRole.SUPERVISOR]:
        associated_worker = db.query(Worker).filter(Worker.user_id == current_user.id).first()
        if not associated_worker:
            raise HTTPException(status_code=403, detail="No tiene trabajador asociado")
        query = query.filter(ErgonomicSelfInspection.worker_id == associated_worker.id)
    else:
        if worker_id:
            query = query.filter(ErgonomicSelfInspection.worker_id == worker_id)

    return query.order_by(ErgonomicSelfInspection.evaluation_date.desc()).all()


@router.get("/ergonomic/stats")
def get_ergonomic_self_inspection_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin),
):
    _deactivate_retired_workers(db)
    active_q = _active_ergonomic_query(db)

    total_count = active_q.count()
    completed_count = active_q.filter(ErgonomicSelfInspection.status == "COMPLETED").count()
    pending_count = total_count - completed_count

    if completed_count == 0:
        return {
            "total": total_count,
            "completed": completed_count,
            "pending": pending_count,
            "compliance_by_category": [],
            "top_issues": [],
            "action_stats": {"OPEN": 0, "IN_PROGRESS": 0, "CLOSED": 0},
        }

    groups = [
        (
            "Mi silla",
            [
                "chair_height_check",
                "chair_lumbar_check",
                "chair_armrests_check",
                "chair_condition_check",
            ],
        ),
        (
            "Mi escritorio / mesa",
            ["desk_elbows_90_check", "desk_leg_space_check", "desk_edges_check"],
        ),
        (
            "Mi monitor / pantalla",
            [
                "monitor_eye_level_check",
                "monitor_distance_check",
                "monitor_glare_check",
                "laptop_setup_check",
            ],
        ),
        (
            "Mi teclado y mouse",
            [
                "keyboard_mouse_level_check",
                "wrist_rest_check",
                "wrists_neutral_check",
            ],
        ),
        (
            "Mi postura e iluminación",
            [
                "lighting_reflection_check",
                "feet_on_floor_check",
                "active_breaks_check",
                "no_pain_check",
            ],
        ),
    ]

    compliance_data = []
    for label, fields in groups:
        compliant_sum = 0
        for field in fields:
            count_true = db.query(func.count(ErgonomicSelfInspection.id)).join(
                Worker, ErgonomicSelfInspection.worker_id == Worker.id
            ).filter(
                Worker.is_active == True,
                ErgonomicSelfInspection.status == "COMPLETED",
                getattr(ErgonomicSelfInspection, field) == True,
            ).scalar()
            compliant_sum += int(count_true or 0)

        total_items = completed_count * len(fields)
        non_compliant = total_items - compliant_sum
        pct = round((compliant_sum / total_items) * 100, 2) if total_items > 0 else 0
        compliance_data.append(
            {
                "category": label,
                "compliant_count": compliant_sum,
                "non_compliant_count": non_compliant,
                "percentage": pct,
            }
        )

    top_issues = sorted(compliance_data, key=lambda x: x["percentage"])[:5]

    action_stats = {"OPEN": 0, "IN_PROGRESS": 0, "CLOSED": 0}
    for (m_data_str,) in db.query(ErgonomicSelfInspection.sst_management_data).join(
        Worker, ErgonomicSelfInspection.worker_id == Worker.id
    ).filter(
        Worker.is_active == True,
        ErgonomicSelfInspection.sst_management_data != None
    ).all():
        try:
            for item in json.loads(m_data_str).values():
                s = item.get("status", "OPEN")
                if s in action_stats:
                    action_stats[s] += 1
        except Exception:
            pass

    return {
        "total": total_count,
        "completed": completed_count,
        "pending": pending_count,
        "compliance_by_category": compliance_data,
        "top_issues": top_issues,
        "action_stats": action_stats,
    }


@router.get("/ergonomic/stats/pdf")
async def generate_ergonomic_dashboard_pdf(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin),
):
    from datetime import date as date_cls

    stats = get_ergonomic_self_inspection_stats(db=db, current_user=current_user)
    total_count = stats["total"]
    completed_count = stats["completed"]

    response_rate = round((completed_count / total_count * 100), 1) if total_count > 0 else 0

    recommendations = {
        "Mi silla": "Ajustar altura y soporte lumbar. Verificar estado de la silla. Gestionar reposapiés o reposabrazos si aplica.",
        "Mi escritorio / mesa": "Ajustar altura para codos a 90°. Garantizar espacio para piernas y evitar bordes que presionen antebrazos.",
        "Mi monitor / pantalla": "Ubicar borde superior a nivel de ojos. Mantener distancia 50–70 cm. Evitar reflejos. Para laptop: soporte + teclado/mouse externos.",
        "Mi teclado y mouse": "Mantener teclado y mouse cerca y al mismo nivel. Usar reposamuñecas. Mantener muñecas neutras.",
        "Mi postura e iluminación": "Mejorar iluminación sin reflejos. Evitar cruzar piernas. Realizar pausas activas. Reportar y gestionar molestias persistentes.",
    }

    today = date_cls.today()
    converter = HTMLToPDFConverter()
    logo_b64 = converter._load_logo_base64()

    context = {
        "logo_base64": logo_b64,
        "stats": stats,
        "response_rate": response_rate,
        "recommendations": recommendations,
        "generated_date": today.strftime("%d/%m/%Y"),
        "period_label": f"Corte al {today.strftime('%d de %B de %Y')}",
    }

    pdf_bytes = await converter.generate_pdf_from_template("ergonomic_dashboard_report.html", context)
    filename = f"Informe_Gerencial_Autoinspeccion_Ergonomica_{today.strftime('%Y%m%d')}.pdf"

    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/ergonomic/{inspection_id}/pdf")
async def generate_ergonomic_self_inspection_pdf(
    inspection_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin),
):
    inspection = (
        db.query(ErgonomicSelfInspection)
        .options(joinedload(ErgonomicSelfInspection.worker))
        .filter(ErgonomicSelfInspection.id == inspection_id)
        .first()
    )
    if not inspection:
        raise HTTPException(status_code=404, detail="Autoinspección no encontrada")

    worker = inspection.worker
    converter = HTMLToPDFConverter()

    checks = [
        inspection.chair_height_check,
        inspection.chair_lumbar_check,
        inspection.chair_armrests_check,
        inspection.chair_condition_check,
        inspection.desk_elbows_90_check,
        inspection.desk_leg_space_check,
        inspection.desk_edges_check,
        inspection.monitor_eye_level_check,
        inspection.monitor_distance_check,
        inspection.monitor_glare_check,
        inspection.laptop_setup_check,
        inspection.keyboard_mouse_level_check,
        inspection.wrist_rest_check,
        inspection.wrists_neutral_check,
        inspection.lighting_reflection_check,
        inspection.feet_on_floor_check,
        inspection.active_breaks_check,
        inspection.no_pain_check,
    ]
    non_compliant_items = [str(i + 1) for i, v in enumerate(checks) if not v]
    non_compliant_items_text = ", ".join(non_compliant_items) if non_compliant_items else "Ninguno"

    worker_signature_b64 = await _download_image_as_data_uri(inspection.worker_signature)
    sst_signature_b64 = await _download_image_as_data_uri(inspection.sst_signature)

    data = {
        "worker": {
            "full_name": worker.full_name,
            "document_number": worker.document_number,
            "position": worker.position,
        },
        "inspection": inspection,
        "evaluation_date": inspection.evaluation_date.strftime("%d/%m/%Y"),
        "month_year": inspection.evaluation_date.strftime("%m/%Y"),
        "total_compliant": sum(1 for v in checks if v),
        "non_compliant_items_text": non_compliant_items_text,
        "worker_signature_b64": worker_signature_b64,
        "sst_signature_b64": sst_signature_b64,
    }

    pdf_content = await converter.generate_pdf_from_template("ergonomic_self_inspection.html", data)
    filename = f"Autoinspeccion_Ergonomica_{worker.document_number}_{inspection.evaluation_date}.pdf"

    return StreamingResponse(
        BytesIO(pdf_content),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/ergonomic/{inspection_id}/remind")
def send_ergonomic_self_inspection_reminder(
    inspection_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin),
):
    inspection = (
        db.query(ErgonomicSelfInspection)
        .options(joinedload(ErgonomicSelfInspection.worker))
        .filter(ErgonomicSelfInspection.id == inspection_id)
        .first()
    )
    if not inspection:
        raise HTTPException(status_code=404, detail="Autoinspección no encontrada")

    worker = inspection.worker
    if not worker or not worker.email:
        raise HTTPException(status_code=400, detail="El trabajador no tiene correo electrónico registrado")

    success = EmailService.send_ergonomic_self_inspection_reminder(
        to_email=worker.email,
        user_name=f"{worker.first_name} {worker.last_name}",
        due_date=inspection.evaluation_date.strftime("%d/%m/%Y"),
    )

    if not success:
        raise HTTPException(status_code=500, detail="Error al enviar el correo")

    return {"message": "Recordatorio enviado exitosamente"}


@router.delete("/ergonomic/{inspection_id}")
async def delete_ergonomic_self_inspection(
    inspection_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin),
):
    inspection = db.query(ErgonomicSelfInspection).filter(ErgonomicSelfInspection.id == inspection_id).first()
    if not inspection:
        raise HTTPException(status_code=404, detail="Autoinspección no encontrada")

    deleted_files = []
    deletion_errors = []

    if inspection.worker_signature:
        try:
            await storage_manager.delete_file(inspection.worker_signature)
            deleted_files.append("worker_signature")
        except Exception as e:
            deletion_errors.append(f"Error eliminando firma trabajador: {str(e)}")

    if inspection.sst_signature:
        try:
            await storage_manager.delete_file(inspection.sst_signature)
            deleted_files.append("sst_signature")
        except Exception as e:
            deletion_errors.append(f"Error eliminando firma SST: {str(e)}")

    db.delete(inspection)
    db.commit()

    response = {
        "message": "Autoinspección eliminada exitosamente",
        "id": inspection_id,
        "deleted_files_count": len(deleted_files),
        "deleted_files": deleted_files,
    }
    if deletion_errors:
        response["storage_warnings"] = deletion_errors
    return response
