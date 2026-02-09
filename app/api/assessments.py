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
from datetime import datetime
import json

from app.database import get_db
from app.dependencies import get_current_user, require_supervisor_or_admin
from app.models.user import User, UserRole
from app.models.assessment import HomeworkAssessment
from app.models.worker import Worker
from app.schemas.assessment import HomeworkAssessment as AssessmentSchema, HomeworkAssessmentCreate, BulkAssessmentCreate
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

@router.get("/homework/stats")
def get_homework_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
):
    """
    Obtiene estadísticas agregadas de las autoevaluaciones de trabajo en casa
    para análisis de cumplimiento y áreas de mejora.
    """
    total_count = db.query(HomeworkAssessment).count()
    completed_count = db.query(HomeworkAssessment).filter(HomeworkAssessment.status == "COMPLETED").count()
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
        count_true = db.query(func.count(HomeworkAssessment.id)).filter(
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
    all_management = db.query(HomeworkAssessment.sst_management_data).filter(
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
