from typing import Any, List
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func
import os
import tempfile
import requests
from contextlib import contextmanager

from app.dependencies import get_current_active_user
from app.database import get_db
from app.models.user import User
from app.models.certificate import Certificate, CertificateStatus
from app.models.course import Course
from app.schemas.certificate import (
    CertificateCreate, CertificateUpdate, CertificateResponse,
    CertificateListResponse, CertificateVerification,
    CertificateVerificationResponse, CertificateGeneration,
    CertificatePDFGeneration
)
from app.schemas.common import MessageResponse, PaginatedResponse
from app.services.certificate_generator import CertificateGenerator
from app.utils.storage import StorageManager

router = APIRouter()


class TempFileResponse(FileResponse):
    """FileResponse que limpia automáticamente archivos temporales después del envío"""
    
    def __init__(self, path: str, cleanup_temp: bool = False, **kwargs):
        super().__init__(path, **kwargs)
        self.cleanup_temp = cleanup_temp
        self.temp_path = path if cleanup_temp else None
    
    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            if self.cleanup_temp and self.temp_path and os.path.exists(self.temp_path):
                try:
                    os.unlink(self.temp_path)
                except OSError:
                    pass  # Ignore cleanup errors


@router.get("/", response_model=PaginatedResponse[CertificateListResponse])
async def get_certificates(
    skip: int = 0,
    limit: int = 100,
    user_id: int = None,
    course_id: int = None,
    status: str = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get certificates with optional filtering
    """
    query = db.query(Certificate).options(
        joinedload(Certificate.user),
        joinedload(Certificate.course)
    )
    
    # Apply filters
    if user_id:
        # Users can only see their own certificates unless they are admin
        if current_user.role.value != "admin" and current_user.id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permisos insuficientes"
            )
        query = query.filter(Certificate.user_id == user_id)
    elif current_user.role.value != "admin":
        # Non-admin users can only see their own certificates
        query = query.filter(Certificate.user_id == current_user.id)
    
    if course_id:
        query = query.filter(Certificate.course_id == course_id)
    
    if status:
        # Convert string status to enum
        try:
            status_enum = CertificateStatus(status)
            query = query.filter(Certificate.status == status_enum)
        except ValueError:
            # If invalid status, ignore filter
            pass
    else:
        # Only show issued certificates for non-admin users
        if current_user.role.value not in ["admin", "capacitador"]:
            query = query.filter(Certificate.status == CertificateStatus.ISSUED)
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    certificates = query.offset(skip).limit(limit).all()
    
    # Calculate pagination info
    page = (skip // limit) + 1
    pages = (total + limit - 1) // limit  # Ceiling division
    has_next = skip + limit < total
    has_prev = skip > 0
    
    return PaginatedResponse(
        items=certificates,
        total=total,
        page=page,
        size=limit,
        pages=pages,
        has_next=has_next,
        has_prev=has_prev
    )


@router.post("/", response_model=CertificateResponse)
async def create_certificate(
    certificate_data: CertificateCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Create new certificate (admin and capacitador roles only)
    """
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permisos insuficientes"
        )
    
    # Check if course exists
    course = db.query(Course).filter(Course.id == certificate_data.course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Curso no encontrado"
        )
    
    # Check if user exists
    user = db.query(User).filter(User.id == certificate_data.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )
    
    # Check if certificate already exists for this user and course
    existing_certificate = db.query(Certificate).filter(
        and_(
            Certificate.user_id == certificate_data.user_id,
            Certificate.course_id == certificate_data.course_id
        )
    ).first()
    
    if existing_certificate:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un certificado para este usuario y curso"
        )
    
    # Generate certificate number
    import uuid
    certificate_number = f"CERT-{datetime.now().year}-{str(uuid.uuid4())[:8].upper()}"
    
    # Generate verification code
    verification_code = str(uuid.uuid4())
    
    # Create new certificate
    certificate = Certificate(
        **certificate_data.dict(),
        certificate_number=certificate_number,
        verification_code=verification_code,
        issued_by=current_user.id,
        issue_date=datetime.utcnow()
    )
    
    db.add(certificate)
    db.commit()
    db.refresh(certificate)
    
    return certificate


@router.get("/my-certificates", response_model=PaginatedResponse[CertificateListResponse])
async def get_my_certificates(
    skip: int = 0,
    limit: int = 100,
    status: str = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get current user's certificates
    """
    query = db.query(Certificate).options(
        joinedload(Certificate.user),
        joinedload(Certificate.course)
    ).filter(Certificate.user_id == current_user.id)
    
    if status:
        # Convert string status to enum
        try:
            status_enum = CertificateStatus(status)
            query = query.filter(Certificate.status == status_enum)
        except ValueError:
            # If invalid status, ignore filter
            pass
    else:
        # Only show issued certificates by default
        query = query.filter(Certificate.status == CertificateStatus.ISSUED)
    
    # Order by issue date descending (newest first)
    query = query.order_by(Certificate.issue_date.desc())
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    certificates = query.offset(skip).limit(limit).all()
    
    # Calculate pagination info
    page = (skip // limit) + 1
    pages = (total + limit - 1) // limit  # Ceiling division
    has_next = skip + limit < total
    has_prev = skip > 0
    
    return PaginatedResponse(
        items=certificates,
        total=total,
        page=page,
        size=limit,
        pages=pages,
        has_next=has_next,
        has_prev=has_prev
    )


@router.get("/{certificate_id}", response_model=CertificateResponse)
async def get_certificate(
    certificate_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get certificate by ID
    """
    certificate = db.query(Certificate).options(
        joinedload(Certificate.user),
        joinedload(Certificate.course)
    ).filter(Certificate.id == certificate_id).first()
    
    if not certificate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificado no encontrado"
        )
    
    # Users can only see their own certificates unless they are admin
    if current_user.role.value != "admin" and certificate.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permisos insuficientes"
        )
    
    return certificate


@router.put("/{certificate_id}", response_model=CertificateResponse)
async def update_certificate(
    certificate_id: int,
    certificate_data: CertificateUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Update certificate (admin only)
    """
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permisos insuficientes"
        )
    
    certificate = db.query(Certificate).filter(Certificate.id == certificate_id).first()
    
    if not certificate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificado no encontrado"
        )
    
    # Update certificate fields
    update_data = certificate_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(certificate, field, value)
    
    db.commit()
    db.refresh(certificate)
    
    return certificate


@router.delete("/{certificate_id}", response_model=MessageResponse)
async def delete_certificate(
    certificate_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Delete certificate (admin only)
    """
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permisos insuficientes"
        )
    
    certificate = db.query(Certificate).filter(Certificate.id == certificate_id).first()
    
    if not certificate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificado no encontrado"
        )
    
    # Eliminar archivos asociados antes de eliminar el registro de la base de datos
    try:
        storage_manager = StorageManager()
        
        # Si el certificado tiene una ruta de archivo
        if certificate.file_path:
            # Detectar si es Firebase Storage o almacenamiento local
            if certificate.file_path.startswith('https://storage.googleapis.com/'):
                # Firebase Storage - extraer la ruta del archivo
                firebase_path = certificate.file_path.split('/')[-1]  # Obtener solo el nombre del archivo
                await storage_manager.delete_file(f"certificates/{firebase_path}")
            else:
                # Almacenamiento local
                if os.path.exists(certificate.file_path):
                    os.remove(certificate.file_path)
        
        # También intentar eliminar usando el generador de certificados
        generator = CertificateGenerator(db)
        generator.delete_certificate_file(certificate_id)
        
    except Exception as e:
        # Continuar con la eliminación del registro aunque falle la eliminación de archivos
        pass
    
    db.delete(certificate)
    db.commit()
    
    return MessageResponse(message="Certificado eliminado exitosamente")


@router.post("/generate", response_model=CertificateResponse)
async def generate_certificate(
    generation_data: CertificateGeneration,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Generate certificate for course completion (admin and capacitador roles only)
    """
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permisos insuficientes"
        )
    
    # Check if course exists
    course = db.query(Course).filter(Course.id == generation_data.course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Curso no encontrado"
        )
    
    # Check if user exists
    user = db.query(User).filter(User.id == generation_data.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )
    
    # Check if certificate already exists
    existing_certificate = db.query(Certificate).filter(
        and_(
            Certificate.user_id == generation_data.user_id,
            Certificate.course_id == generation_data.course_id
        )
    ).first()
    
    if existing_certificate:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un certificado para este usuario y curso"
        )
    
    # Generate certificate details
    import uuid
    certificate_number = f"CERT-{datetime.now().year}-{str(uuid.uuid4())[:8].upper()}"
    verification_code = str(uuid.uuid4())
    
    # Create certificate
    certificate = Certificate(
        user_id=generation_data.user_id,
        course_id=generation_data.course_id,
        certificate_number=certificate_number,
        title=f"Certificate of Completion - {course.title}",
        description=f"This certifies that {user.full_name} has successfully completed the course {course.title}",
        score_achieved=generation_data.score_achieved,
        completion_date=generation_data.completion_date or datetime.now(),
        issue_date=datetime.now(),
        expiry_date=generation_data.expiry_date,
        status=CertificateStatus.VALID,
        verification_code=verification_code,
        template_used=generation_data.template_used or "default",
        issued_by=current_user.id
    )
    
    db.add(certificate)
    db.commit()
    db.refresh(certificate)
    
    return certificate


@router.post("/verify", response_model=CertificateVerificationResponse)
async def verify_certificate(
    verification_data: CertificateVerification,
    db: Session = Depends(get_db)
) -> Any:
    """
    Verify certificate by certificate number or verification code
    """
    query = db.query(Certificate)
    
    if verification_data.certificate_number:
        query = query.filter(Certificate.certificate_number == verification_data.certificate_number)
    elif verification_data.verification_code:
        query = query.filter(Certificate.verification_code == verification_data.verification_code)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Se debe proporcionar certificate_number o verification_code"
        )
    
    certificate = query.first()
    
    if not certificate:
        return CertificateVerificationResponse(
            is_valid=False,
            message="Certificado no encontrado"
        )
    
    # Check if certificate is valid
    if certificate.status != CertificateStatus.VALID:
        return CertificateVerificationResponse(
            is_valid=False,
            message=f"Certificate is {certificate.status.value}",
            certificate=certificate
        )
    
    # Check if certificate is expired
    if certificate.expiry_date and certificate.expiry_date < datetime.now():
        return CertificateVerificationResponse(
            is_valid=False,
            message="El certificado ha expirado",
            certificate=certificate
        )
    
    return CertificateVerificationResponse(
        is_valid=True,
        message="El certificado es válido",
        certificate=certificate
    )


@router.put("/{certificate_id}/revoke", response_model=MessageResponse)
async def revoke_certificate(
    certificate_id: int,
    reason: str = "Revocado por administrador",
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Revoke certificate (admin only)
    """
    if current_user.role.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permisos insuficientes"
        )
    
    certificate = db.query(Certificate).filter(Certificate.id == certificate_id).first()
    
    if not certificate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificado no encontrado"
        )
    
    if certificate.status == CertificateStatus.REVOKED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El certificado ya está revocado"
        )
    
    # Revoke certificate
    certificate.status = CertificateStatus.REVOKED
    certificate.revoked_by = current_user.id
    certificate.revoked_at = datetime.utcnow()
    certificate.revocation_reason = reason
    
    db.commit()
    
    return MessageResponse(message="Certificado revocado exitosamente")


@router.post("/{certificate_id}/regenerate", response_model=MessageResponse)
async def regenerate_certificate(
    certificate_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Regenerate certificate PDF (admin only)
    """
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permisos insuficientes"
        )
    
    certificate = db.query(Certificate).filter(Certificate.id == certificate_id).first()
    
    if not certificate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificado no encontrado"
        )
    
    if certificate.status not in [CertificateStatus.ISSUED, CertificateStatus.REVOKED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se pueden regenerar certificados emitidos o revocados"
        )
    
    try:
        # Generate new certificate PDF
        generator = CertificateGenerator(db)
        file_path = await generator.generate_certificate_pdf(certificate_id)
        
        # Update certificate status to issued if it was revoked
        if certificate.status == CertificateStatus.REVOKED:
            certificate.status = CertificateStatus.ISSUED
            db.commit()
        
        # Update certificate with new file path
        db.refresh(certificate)
        
        return MessageResponse(message="Certificado regenerado exitosamente")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error regenerando certificado: {str(e)}"
        )


@router.get("/user/{user_id}/summary")
async def get_user_certificates_summary(
    user_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get certificate summary for a user
    """
    # Users can only see their own summary unless they are admin
    if current_user.role.value != "admin" and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    query = db.query(Certificate).filter(Certificate.user_id == user_id)
    
    # Get certificate statistics
    total_certificates = query.count()
    valid_certificates = query.filter(Certificate.status == CertificateStatus.VALID).count()
    revoked_certificates = query.filter(Certificate.status == CertificateStatus.REVOKED).count()
    expired_certificates = query.filter(
        and_(
            Certificate.expiry_date < datetime.now(),
            Certificate.status == CertificateStatus.VALID
        )
    ).count()
    
    return {
        "user_id": user_id,
        "total_certificates": total_certificates,
        "valid_certificates": valid_certificates,
        "revoked_certificates": revoked_certificates,
        "expired_certificates": expired_certificates
    }


@router.post("/{certificate_id}/generate-pdf", response_model=MessageResponse)
async def generate_certificate_pdf(
    certificate_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Generate PDF for an existing certificate (admin and capacitador roles only)
    """
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # Check if certificate exists
    certificate = db.query(Certificate).filter(Certificate.id == certificate_id).first()
    if not certificate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificate not found"
        )
    
    # Generate PDF
    try:
        generator = CertificateGenerator(db)
        file_path = generator.generate_certificate_pdf(certificate_id)
        
        # Update certificate status to issued if it was pending
        if certificate.status == CertificateStatus.PENDING:
            certificate.status = CertificateStatus.ISSUED
            db.commit()
        
        return MessageResponse(message=f"PDF del certificado generado exitosamente: {file_path}")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generando PDF del certificado: {str(e)}"
        )


# Endpoint eliminado: download_certificate se ha fusionado con get_certificate_pdf


@router.get("/{certificate_id}/pdf", response_class=FileResponse)
async def get_certificate_pdf(
    certificate_id: int,
    download: bool = Query(False, description="Set to true to download the file with a custom filename"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    View or download certificate PDF file
    """
    # Get certificate
    certificate = db.query(Certificate).filter(Certificate.id == certificate_id).first()
    if not certificate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificate not found"
        )
    
    # Check permissions
    if current_user.role.value not in ["admin", "capacitador"] and certificate.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # Check if certificate is issued
    if certificate.status != CertificateStatus.ISSUED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Certificate is not issued yet"
        )
    
    # Get file path from certificate or generate if needed
    file_path = certificate.file_path
    
    # Check if we need to generate the certificate
    if not file_path:
        try:
            # Importante: usar await ya que generate_certificate_pdf es una función asíncrona
            generator = CertificateGenerator(db)
            file_path = await generator.generate_certificate_pdf(certificate_id)
            # Actualizar el certificado para obtener la ruta actualizada
            db.refresh(certificate)
            file_path = certificate.file_path
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error generando PDF del certificado: {str(e)}"
            )
    
    # Handle Firebase Storage URLs vs local files
    is_temp_file = False
    if file_path.startswith('https://storage.googleapis.com/'):
        # Firebase Storage URL - need to download temporarily for FileResponse
        try:
            # Download file from Firebase Storage
            response = requests.get(file_path, timeout=30)
            response.raise_for_status()
            
            # Create temporary file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
            temp_file.write(response.content)
            temp_file.close()
            
            local_file_path = temp_file.name
            is_temp_file = True
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Error descargando archivo del certificado: {str(e)}"
            )
    else:
        # Local file path
        local_file_path = file_path
        if not os.path.exists(local_file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Archivo del certificado no encontrado"
            )
    
    # Prepare response parameters
    response_params = {
        "path": local_file_path,
        "media_type": "application/pdf"
    }
    
    # If download is requested, add a custom filename
    if download:
        # Get course information for filename
        course = db.query(Course).filter(Course.id == certificate.course_id).first()
        course_name = course.title if course else "Curso"
        
        # Clean course name for filename (remove special characters)
        import re
        clean_course_name = re.sub(r'[^\w\s-]', '', course_name).strip()
        clean_course_name = re.sub(r'[-\s]+', '_', clean_course_name)
        
        # Add filename to response parameters
        response_params["filename"] = f"Certificado_{clean_course_name}_{certificate.certificate_number}.pdf"
    
    # Return file response with appropriate parameters
    if is_temp_file:
        return TempFileResponse(cleanup_temp=True, **response_params)
    else:
        return FileResponse(**response_params)


@router.post("/generate-from-course", response_model=CertificateResponse)
async def generate_certificate_from_course(
    certificate_data: CertificatePDFGeneration,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Generate certificate for a user who completed a course (admin and capacitador roles only)
    """
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # Check if course exists
    course = db.query(Course).filter(Course.id == certificate_data.course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Curso no encontrado"
        )
    
    # Check if user exists
    user = db.query(User).filter(User.id == certificate_data.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )
    
    # Check if certificate already exists
    existing_certificate = db.query(Certificate).filter(
        and_(
            Certificate.user_id == certificate_data.user_id,
            Certificate.course_id == certificate_data.course_id
        )
    ).first()
    
    if existing_certificate:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un certificado para este usuario y curso"
        )
    
    # TODO: Verificar que el usuario realmente completó el curso
    # Aquí deberías agregar lógica para verificar el progreso del curso
    
    # Generate certificate details
    import uuid
    certificate_number = f"CERT-{datetime.now().year}-{str(uuid.uuid4())[:8].upper()}"
    verification_code = str(uuid.uuid4())
    
    # Create certificate
    certificate = Certificate(
        user_id=certificate_data.user_id,
        course_id=certificate_data.course_id,
        certificate_number=certificate_number,
        title=f"Certificado de Finalización - {course.title}",
        description=f"Certifica que {user.full_name} Ha completado satisfactoriamente el curso {course.title}",
        completion_date=datetime.now(),
        issue_date=datetime.now(),
        status=CertificateStatus.ISSUED,
        verification_code=verification_code,
        template_used="default",
        issued_by=current_user.id
    )
    
    db.add(certificate)
    db.commit()
    db.refresh(certificate)
    
    # Generate PDF
    try:
        generator = CertificateGenerator(db)
        generator.generate_certificate_pdf(certificate.id)
    except Exception as e:
        # Si falla la generación del PDF, no fallar la creación del certificado
        print(f"Warning: Failed to generate PDF for certificate {certificate.id}: {str(e)}")
    
    return certificate