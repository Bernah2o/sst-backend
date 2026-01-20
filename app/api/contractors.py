from typing import Any, List, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form
from fastapi.responses import StreamingResponse, Response
from sqlalchemy.orm import Session
from sqlalchemy import or_
from io import BytesIO
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill
from datetime import datetime, date, timedelta
import os
import uuid

from app.database import get_db
from app.dependencies import get_current_user, get_current_active_user, require_admin, require_supervisor_or_admin
from app.models.user import User, UserRole
from app.models.contractor import Contractor, ContractorContract, ContractorDocument
from app.services.contractor_service import contractor_service
from app.utils.storage import storage_manager
from app.config import settings
from app.schemas.contractor import (
    ContractorCreate,
    ContractorUpdate,
    ContractorResponse,
    ContractorList,
    ContractorDocumentResponse,
    ContractorDocumentUpdate,
    ContractorContractCreate,
    ContractorContractUpdate,
    ContractorContractResponse
)
from app.schemas.common import MessageResponse
import logging
import uuid

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=ContractorList)
@router.get("", response_model=ContractorList)
async def get_contractors(
    page: int = Query(1, ge=1, description="Número de página"),
    size: int = Query(10, ge=1, le=100, description="Tamaño de página"),
    search: str = Query(None, description="Buscar por nombre, documento o email"),
    is_active: bool = Query(None, description="Filtrar por estado activo"),
    area_id: int = Query(None, description="Filtrar por área"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """
    Obtener lista de contratistas con filtros opcionales y paginación
    """
    query = db.query(Contractor)
    
    # Filtro de búsqueda
    if search:
        search_filter = or_(
            Contractor.first_name.ilike(f"%{search}%"),
            Contractor.last_name.ilike(f"%{search}%"),
            Contractor.document_number.ilike(f"%{search}%"),
            Contractor.email.ilike(f"%{search}%")
        )
        query = query.filter(search_filter)
    
    # Filtro por estado activo
    if is_active is not None:
        query = query.filter(Contractor.is_active == is_active)
    
    # Filtro por área
    if area_id is not None:
        query = query.filter(Contractor.area_id == area_id)
    
    # Contar total de registros
    total = query.count()
    
    # Calcular offset y obtener registros paginados
    skip = (page - 1) * size
    contractors = query.offset(skip).limit(size).all()
    
    # Calcular número total de páginas
    pages = (total + size - 1) // size
    
    return ContractorList(
        contractors=contractors,
        total=total,
        page=page,
        size=size,
        pages=pages
    )


@router.get("/documents", response_model=Dict[str, Any])
async def get_all_contractor_documents(
    page: int = Query(1, ge=1, description="Número de página"),
    size: int = Query(10, ge=1, le=100, description="Tamaño de página"),
    contractor_id: int = Query(None, description="Filtrar por ID de contratista"),
    document_type: str = Query(None, description="Filtrar por tipo de documento"),
    search: str = Query(None, description="Buscar por nombre de documento"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """
    Obtener todos los documentos de contratistas con filtros opcionales y paginación
    """
    # Seleccionar solo las columnas básicas que sabemos que existen
    query = db.query(
        ContractorDocument.id,
        ContractorDocument.contractor_id,
        ContractorDocument.document_type,
        ContractorDocument.document_name,
        ContractorDocument.created_at
    )
    
    # Filtro por contratista
    if contractor_id:
        query = query.filter(ContractorDocument.contractor_id == contractor_id)
    
    # Filtro por tipo de documento
    if document_type:
        query = query.filter(ContractorDocument.document_type == document_type)
    
    # Filtro de búsqueda por nombre
    if search:
        query = query.filter(ContractorDocument.document_name.ilike(f"%{search}%"))
    
    # Crear una copia de la consulta para contar
    count_query = db.query(ContractorDocument.id)
    
    # Aplicar los mismos filtros para el conteo
    if contractor_id:
        count_query = count_query.filter(ContractorDocument.contractor_id == contractor_id)
    if document_type:
        count_query = count_query.filter(ContractorDocument.document_type == document_type)
    if search:
        count_query = count_query.filter(ContractorDocument.document_name.ilike(f"%{search}%"))
    
    # Contar total de registros
    total = count_query.count()
    
    # Calcular offset y obtener registros paginados
    skip = (page - 1) * size
    documents = query.offset(skip).limit(size).all()
    
    # Mapear los campos del modelo a lo que espera el frontend
    mapped_documents = []
    for doc in documents:
        # doc es una tupla con (id, contractor_id, document_type, document_name, created_at)
        mapped_doc = {
            "id": doc[0],  # id
            "contractor_id": doc[1],  # contractor_id
            "tipo_documento": doc[2],  # document_type
            "nombre": doc[3],  # document_name
            "archivo": doc[3],  # document_name como archivo
            "descripcion": "",  # Campo no existe en el modelo actual
            "fecha_subida": doc[4].isoformat() if doc[4] else "",  # created_at
            "tamano_archivo": 0,  # No disponible en la consulta simplificada
            "tipo_contenido": "",  # No disponible en la consulta simplificada
            "url_descarga": ""  # No disponible en la consulta simplificada
        }
        mapped_documents.append(mapped_doc)
    
    # Calcular número total de páginas
    pages = (total + size - 1) // size
    
    return {
        "documents": mapped_documents,
        "total": total,
        "page": page,
        "size": size,
        "pages": pages
    }


@router.get("/{contractor_id}", response_model=ContractorResponse)
async def get_contractor(
    contractor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """
    Obtener un contratista por ID
    """
    contractor = db.query(Contractor).filter(Contractor.id == contractor_id).first()
    if not contractor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contratista no encontrado"
        )
    return contractor


@router.post("/", response_model=ContractorResponse)
@router.post("", response_model=ContractorResponse)
async def create_contractor(
    contractor_data: ContractorCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """
    Crear un nuevo contratista
    """
    # Verificar que no exista un contratista con el mismo documento
    existing_contractor = db.query(Contractor).filter(
        Contractor.document_number == contractor_data.document_number
    ).first()
    
    if existing_contractor:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un contratista con este número de documento"
        )
    
    # Verificar que no exista un contratista con el mismo email
    if contractor_data.email:
        existing_email = db.query(Contractor).filter(
            Contractor.email == contractor_data.email
        ).first()
        
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe un contratista con este email"
            )
    
    # Mapear campos del esquema a nombres de columnas del modelo
    data = contractor_data.dict()
    
    
    
    # address (schema) -> direccion (modelo)
    if "address" in data:
        data["direccion"] = data.pop("address")
    # Seguridad social: eps_name/arl_name/afp_name (schema) -> eps/arl/afp (modelo)
    if "eps_name" in data:
        data["eps"] = data.pop("eps_name")
    if "arl_name" in data:
        data["arl"] = data.pop("arl_name")
    if "afp_name" in data:
        data["afp"] = data.pop("afp_name")
    
    
    
    # Filtrar solo claves válidas del modelo para evitar TypeError por kwargs desconocidos
    model_fields = {c.name for c in Contractor.__table__.columns}
    
    
    filtered_data = {k: v for k, v in data.items() if k in model_fields}
    
    
    data = filtered_data

    contractor = Contractor(**data)
    db.add(contractor)
    db.commit()
    db.refresh(contractor)

    return contractor


@router.put("/{contractor_id}", response_model=ContractorResponse)
async def update_contractor(
    contractor_id: int,
    contractor_data: ContractorUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """
    Actualizar un contratista
    """
    contractor = db.query(Contractor).filter(Contractor.id == contractor_id).first()
    if not contractor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contratista no encontrado"
        )
    
    # Verificar documento único si se está actualizando
    if contractor_data.document_number and contractor_data.document_number != contractor.document_number:
        existing_contractor = db.query(Contractor).filter(
            Contractor.document_number == contractor_data.document_number,
            Contractor.id != contractor_id
        ).first()
        
        if existing_contractor:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe un contratista con este número de documento"
            )
    
    # Verificar email único si se está actualizando
    if contractor_data.email and contractor_data.email != contractor.email:
        existing_email = db.query(Contractor).filter(
            Contractor.email == contractor_data.email,
            Contractor.id != contractor_id
        ).first()
        
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe un contratista con este email"
            )
    
    # Actualizar campos
    update_data = contractor_data.dict(exclude_unset=True)
    # Mapear campos del esquema a nombres de columnas del modelo
    if "address" in update_data:
        update_data["direccion"] = update_data.pop("address")
    if "eps_name" in update_data:
        update_data["eps"] = update_data.pop("eps_name")
    if "arl_name" in update_data:
        update_data["arl"] = update_data.pop("arl_name")
    if "afp_name" in update_data:
        update_data["afp"] = update_data.pop("afp_name")
    # Filtrar solo claves válidas del modelo
    model_fields = {c.name for c in Contractor.__table__.columns}
    update_data = {k: v for k, v in update_data.items() if k in model_fields}
    for field, value in update_data.items():
        setattr(contractor, field, value)
    
    contractor.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(contractor)
    
    return contractor


@router.delete("/{contractor_id}", response_model=MessageResponse)
async def delete_contractor(
    contractor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
) -> Any:
    """
    Eliminar un contratista (solo administradores)
    """
    contractor = db.query(Contractor).filter(Contractor.id == contractor_id).first()
    if not contractor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contratista no encontrado"
        )
    
    # Verificar si tiene inscripciones activas
    from app.models.enrollment import Enrollment
    active_enrollments = db.query(Enrollment).filter(
        Enrollment.contractor_id == contractor_id,
        Enrollment.status.in_(["enrolled", "in_progress"])
    ).count()
    
    if active_enrollments > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede eliminar el contratista porque tiene inscripciones activas"
        )
    
    db.delete(contractor)
    db.commit()
    
    return MessageResponse(message="Contratista eliminado exitosamente")


# Endpoints para documentos
@router.post("/{contractor_id}/documents", response_model=ContractorDocumentResponse)
async def upload_contractor_document(
    contractor_id: int,
    file: UploadFile = File(...),
    tipo_documento: str = Form(...),
    nombre: str = Form(None),
    descripcion: str = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """
    Subir documento general de contratista
    """
    # Verificar que el contratista existe
    contractor = db.query(Contractor).filter(Contractor.id == contractor_id).first()
    if not contractor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contratista no encontrado"
        )
    
    # Validar tipo de archivo
    allowed_types = ['application/pdf', 'image/jpeg', 'image/png', 'image/jpg']
    allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png']
    
    file_extension = '.' + file.filename.split('.')[-1].lower() if '.' in file.filename else ''
    
    if file.content_type not in allowed_types and file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tipo de archivo no permitido. Solo se permiten PDF, JPG, JPEG y PNG"
        )
    
    # Validar tamaño de archivo (máximo 10MB)
    max_size = 10 * 1024 * 1024  # 10MB
    file_content = await file.read()
    if len(file_content) > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo es demasiado grande. Máximo 10MB"
        )
    
    try:
        # Generar nombre único para el archivo
        file_extension = file.filename.split('.')[-1] if '.' in file.filename else 'pdf'
        unique_filename = f"contractor_{contractor_id}_{tipo_documento}_{uuid.uuid4().hex}.{file_extension}"
        storage_path = f"contractors/{contractor_id}/documents/{unique_filename}"
        
        # Subir archivo usando storage_manager
        result = await storage_manager.upload_bytes(
            file_content=file_content,
            filename=unique_filename,
            folder=f"contractors/{contractor_id}/documents",
            content_type=file.content_type
        )
        file_url = result["url"]
        
        # Crear registro en la base de datos (usando columnas que existen en la tabla)
        document = ContractorDocument(
            contractor_id=contractor_id,
            document_type=tipo_documento,
            document_name=nombre or file.filename,
            file_path=file_url,  # Usar file_path en lugar de file_url
            file_size=len(file_content),
            content_type=file.content_type or "application/octet-stream",
            created_at=datetime.utcnow()
        )
        
        db.add(document)
        db.commit()
        db.refresh(document)
        
        # Mapear respuesta
        return {
            "id": document.id,
            "contractor_id": document.contractor_id,
            "tipo_documento": document.document_type,
            "nombre": document.document_name,
            "archivo": document.document_name,
            "descripcion": descripcion or "",
            "fecha_subida": document.created_at.isoformat(),
            "tamano_archivo": document.file_size,
            "tipo_contenido": document.content_type,
            "url_descarga": document.file_path
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al subir documento: {str(e)}"
        )


@router.post("/{contractor_id}/documents/arl", response_model=ContractorDocumentResponse)
async def upload_arl_certificate(
    contractor_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """
    Subir certificación ARL
    """
    contractor = db.query(Contractor).filter(Contractor.id == contractor_id).first()
    if not contractor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contratista no encontrado"
        )
    
    try:
        document = await contractor_service.upload_arl_certificate(
            contractor_id=contractor_id,
            file=file,
            db=db
        )
        return document
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al subir certificación ARL: {str(e)}"
        )


@router.post("/{contractor_id}/documents/eps", response_model=ContractorDocumentResponse)
async def upload_eps_certificate(
    contractor_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """
    Subir certificación EPS
    """
    contractor = db.query(Contractor).filter(Contractor.id == contractor_id).first()
    if not contractor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contratista no encontrado"
        )
    
    try:
        document = await contractor_service.upload_eps_certificate(
            contractor_id=contractor_id,
            file=file,
            db=db
        )
        return document
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al subir certificación EPS: {str(e)}"
        )


@router.post("/{contractor_id}/documents/afp", response_model=ContractorDocumentResponse)
async def upload_afp_certificate(
    contractor_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """
    Subir certificación AFP
    """
    contractor = db.query(Contractor).filter(Contractor.id == contractor_id).first()
    if not contractor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contratista no encontrado"
        )
    
    try:
        document = await contractor_service.upload_afp_certificate(
            contractor_id=contractor_id,
            file=file,
            db=db
        )
        return document
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al subir certificación AFP: {str(e)}"
        )


@router.post("/{contractor_id}/documents/other", response_model=ContractorDocumentResponse)
async def upload_other_document(
    contractor_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """
    Subir otros documentos
    """
    contractor = db.query(Contractor).filter(Contractor.id == contractor_id).first()
    if not contractor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contratista no encontrado"
        )
    
    try:
        document = await contractor_service.upload_other_document(
            contractor_id=contractor_id,
            file=file,
            db=db
        )
        return document
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al subir documento: {str(e)}"
        )


@router.get("/{contractor_id}/documents", response_model=Dict[str, Any])
def get_contractor_documents(
    contractor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """
    Obtener todos los documentos de un contratista
    """
    contractor = db.query(Contractor).filter(Contractor.id == contractor_id).first()
    if not contractor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contratista no encontrado"
        )
    
    try:
        documents = contractor_service.get_contractor_documents(db, contractor_id)
        return documents
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener documentos: {str(e)}"
        )



@router.delete("/{contractor_id}/documents/{document_id}", response_model=MessageResponse)
async def delete_contractor_document(
    contractor_id: int,
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """
    Eliminar un documento de contratista
    """
    contractor = db.query(Contractor).filter(Contractor.id == contractor_id).first()
    if not contractor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contratista no encontrado"
        )
    
    try:
        await contractor_service.delete_document(document_id, db)
        return MessageResponse(message="Documento eliminado exitosamente")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al eliminar documento: {str(e)}"
        )


@router.get("/{contractor_id}/documents/{document_id}/download")
async def download_contractor_document(
    contractor_id: int,
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """
    Descargar un documento de contratista
    """
    contractor = db.query(Contractor).filter(Contractor.id == contractor_id).first()
    if not contractor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contratista no encontrado"
        )
    
    # Buscar el documento
    document = db.query(ContractorDocument).filter(
        ContractorDocument.id == document_id,
        ContractorDocument.contractor_id == contractor_id
    ).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento no encontrado"
        )
    
    try:
        # Descargar el archivo usando storage_manager
        file_content = await storage_manager.download_file(document.file_path)
        
        # Crear un stream de bytes para la respuesta
        from fastapi.responses import StreamingResponse
        import io
        
        return StreamingResponse(
            io.BytesIO(file_content),
            media_type=document.content_type or 'application/octet-stream',
            headers={"Content-Disposition": f"attachment; filename={document.document_name}"}
        )
        
    except Exception as e:
        logger.error(f"Error al descargar documento {document_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al descargar documento: {str(e)}"
        )


# Endpoints para contratos
@router.get("/{contractor_id}/contracts", response_model=List[ContractorContractResponse])
async def get_contractor_contracts(
    contractor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """
    Obtener contratos de un contratista
    """
    contractor = db.query(Contractor).filter(Contractor.id == contractor_id).first()
    if not contractor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contratista no encontrado"
        )
    
    contracts = db.query(ContractorContract).filter(
        ContractorContract.contractor_id == contractor_id
    ).all()
    
    return contracts


@router.post("/{contractor_id}/contracts", response_model=ContractorContractResponse)
async def create_contractor_contract(
    contractor_id: int,
    contract_data: ContractorContractCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """
    Crear un nuevo contrato para un contratista
    """
    contractor = db.query(Contractor).filter(Contractor.id == contractor_id).first()
    if not contractor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contratista no encontrado"
        )
    
    # Verificar que no exista un contrato con el mismo número
    existing_contract = db.query(ContractorContract).filter(
        ContractorContract.contract_number == contract_data.contract_number
    ).first()
    
    if existing_contract:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un contrato con este número"
        )
    
    contract_data.contractor_id = contractor_id
    contract = ContractorContract(**contract_data.dict())
    db.add(contract)
    db.commit()
    db.refresh(contract)
    
    return contract


@router.put("/{contractor_id}/contracts/{contract_id}", response_model=ContractorContractResponse)
async def update_contractor_contract(
    contractor_id: int,
    contract_id: int,
    contract_data: ContractorContractUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """
    Actualizar un contrato de contratista
    """
    contract = db.query(ContractorContract).filter(
        ContractorContract.id == contract_id,
        ContractorContract.contractor_id == contractor_id
    ).first()
    
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contrato no encontrado"
        )
    
    # Verificar número de contrato único si se está actualizando
    if contract_data.contract_number and contract_data.contract_number != contract.contract_number:
        existing_contract = db.query(ContractorContract).filter(
            ContractorContract.contract_number == contract_data.contract_number,
            ContractorContract.id != contract_id
        ).first()
        
        if existing_contract:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe un contrato con este número"
            )
    
    # Actualizar campos
    update_data = contract_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(contract, field, value)
    
    contract.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(contract)
    
    return contract


@router.delete("/{contractor_id}/contracts/{contract_id}", response_model=MessageResponse)
async def delete_contractor_contract(
    contractor_id: int,
    contract_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
) -> Any:
    """
    Eliminar un contrato de contratista (solo administradores)
    """
    contract = db.query(ContractorContract).filter(
        ContractorContract.id == contract_id,
        ContractorContract.contractor_id == contractor_id
    ).first()
    
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contrato no encontrado"
        )
    
    db.delete(contract)
    db.commit()
    
    return MessageResponse(message="Contrato eliminado exitosamente")
