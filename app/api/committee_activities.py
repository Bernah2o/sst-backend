"""
API endpoints for Committee Activities and Documents Management
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, desc, asc
from datetime import date

from app.database import get_db
from app.dependencies import get_current_user
from app.models.committee import (
    Committee, CommitteeActivity, CommitteeDocument, CommitteeMember
)
from app.models.user import User
from app.schemas.committee import (
    CommitteeActivity as CommitteeActivitySchema,
    CommitteeActivityCreate,
    CommitteeActivityUpdate,
    CommitteeDocument as CommitteeDocumentSchema,
    CommitteeDocumentCreate,
    CommitteeDocumentUpdate,
    ActivityStatusEnum,
    ActivityPriorityEnum,
    DocumentTypeEnum
)

router = APIRouter()

# Committee Activity endpoints
@router.get("/", response_model=List[CommitteeActivitySchema])
@router.get("", response_model=List[CommitteeActivitySchema])  # Add route without trailing slash to avoid 307 redirect
async def get_committee_activities(
    committee_id: Optional[int] = Query(None),
    status: Optional[ActivityStatusEnum] = Query(None),
    priority: Optional[ActivityPriorityEnum] = Query(None),
    assigned_to: Optional[int] = Query(None),
    due_date_from: Optional[date] = Query(None),
    due_date_to: Optional[date] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtener actividades de comités con filtros"""
    query = db.query(CommitteeActivity).options(
        joinedload(CommitteeActivity.committee)
    )
    
    # Filtros
    if committee_id:
        query = query.filter(CommitteeActivity.committee_id == committee_id)
    
    if status:
        query = query.filter(CommitteeActivity.status == status)
    
    if priority:
        query = query.filter(CommitteeActivity.priority == priority)
    
    if assigned_to:
        query = query.filter(CommitteeActivity.assigned_to == assigned_to)
    
    if due_date_from:
        query = query.filter(CommitteeActivity.due_date >= due_date_from)
    
    if due_date_to:
        query = query.filter(CommitteeActivity.due_date <= due_date_to)
    
    # Ordenar por prioridad y fecha de vencimiento
    query = query.order_by(
        CommitteeActivity.priority.desc(),
        CommitteeActivity.due_date.asc()
    )
    
    activities = query.offset(skip).limit(limit).all()
    
    return activities

@router.post("/", response_model=CommitteeActivitySchema, status_code=status.HTTP_201_CREATED)
async def create_committee_activity(
    activity: CommitteeActivityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Crear una nueva actividad de comité"""
    # Verificar que el comité existe
    committee = db.query(Committee).filter(Committee.id == activity.committee_id).first()
    if not committee:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Comité no encontrado"
        )
    
    # Verificar que el usuario asignado es miembro del comité (si se especifica)
    if activity.assigned_to:
        member = db.query(CommitteeMember).filter(
            and_(
                CommitteeMember.committee_id == activity.committee_id,
                CommitteeMember.user_id == activity.assigned_to,
                CommitteeMember.is_active == True
            )
        ).first()
        
        if not member:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El usuario asignado no es miembro activo del comité"
            )
    
    activity_data = activity.model_dump()
    activity_data["created_by"] = current_user.id
    
    db_activity = CommitteeActivity(**activity_data)
    db.add(db_activity)
    db.commit()
    db.refresh(db_activity)
    
    return db_activity

@router.get("/{activity_id}", response_model=CommitteeActivitySchema)
async def get_committee_activity(
    activity_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtener una actividad de comité por ID"""
    activity = db.query(CommitteeActivity).options(
        joinedload(CommitteeActivity.committee)
    ).filter(CommitteeActivity.id == activity_id).first()
    
    if not activity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Actividad no encontrada"
        )
    
    return activity

@router.put("/{activity_id}", response_model=CommitteeActivitySchema)
async def update_committee_activity(
    activity_id: int,
    activity_update: CommitteeActivityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Actualizar una actividad de comité"""
    activity = db.query(CommitteeActivity).filter(CommitteeActivity.id == activity_id).first()
    
    if not activity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Actividad no encontrada"
        )
    
    # Verificar que el usuario asignado es miembro del comité (si se especifica)
    if activity_update.assigned_to:
        member = db.query(CommitteeMember).filter(
            and_(
                CommitteeMember.committee_id == activity.committee_id,
                CommitteeMember.user_id == activity_update.assigned_to,
                CommitteeMember.is_active == True
            )
        ).first()
        
        if not member:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El usuario asignado no es miembro activo del comité"
            )
    
    update_data = activity_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(activity, field, value)
    
    db.commit()
    db.refresh(activity)
    
    return activity

@router.delete("/{activity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_committee_activity(
    activity_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Eliminar una actividad de comité"""
    activity = db.query(CommitteeActivity).filter(CommitteeActivity.id == activity_id).first()
    
    if not activity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Actividad no encontrada"
        )
    
    db.delete(activity)
    db.commit()

@router.post("/{activity_id}/complete", response_model=CommitteeActivitySchema)
async def complete_activity(
    activity_id: int,
    completion_notes: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Marcar una actividad como completada"""
    activity = db.query(CommitteeActivity).filter(CommitteeActivity.id == activity_id).first()
    
    if not activity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Actividad no encontrada"
        )
    
    if activity.status == ActivityStatusEnum.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La actividad ya está completada"
        )
    
    activity.status = ActivityStatusEnum.COMPLETED
    activity.completed_date = date.today()
    
    if completion_notes:
        activity.notes = (activity.notes or "") + f"\n\nCompletada: {completion_notes}"
    
    db.commit()
    db.refresh(activity)
    
    return activity

@router.get("/activities/committee/{committee_id}", response_model=List[CommitteeActivitySchema])
async def get_activities_by_committee(
    committee_id: int,
    status: Optional[ActivityStatusEnum] = Query(None),
    priority: Optional[ActivityPriorityEnum] = Query(None),
    overdue_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtener todas las actividades de un comité específico"""
    # Verificar que el comité existe
    committee = db.query(Committee).filter(Committee.id == committee_id).first()
    if not committee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comité no encontrado"
        )
    
    query = db.query(CommitteeActivity).filter(
        CommitteeActivity.committee_id == committee_id
    )
    
    if status:
        query = query.filter(CommitteeActivity.status == status)
    
    if priority:
        query = query.filter(CommitteeActivity.priority == priority)
    
    if overdue_only:
        today = date.today()
        query = query.filter(
            and_(
                CommitteeActivity.due_date < today,
                CommitteeActivity.status != ActivityStatusEnum.COMPLETED
            )
        )
    
    query = query.order_by(
        CommitteeActivity.priority.desc(),
        CommitteeActivity.due_date.asc()
    )
    
    activities = query.all()
    
    return activities

# Committee Document endpoints
@router.get("/documents/committee/{committee_id}", response_model=List[CommitteeDocumentSchema])
async def get_committee_documents(
    committee_id: int,
    document_type: Optional[DocumentTypeEnum] = Query(None),
    search: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtener documentos de un comité específico con filtros"""
    # Verificar que el comité existe
    committee = db.query(Committee).filter(Committee.id == committee_id).first()
    if not committee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comité no encontrado"
        )
    
    query = db.query(CommitteeDocument).options(
        joinedload(CommitteeDocument.committee)
    ).filter(CommitteeDocument.committee_id == committee_id)
    
    # Filtros
    if document_type:
        query = query.filter(CommitteeDocument.document_type == document_type)
    
    if search:
        query = query.filter(
            or_(
                CommitteeDocument.title.ilike(f"%{search}%"),
                CommitteeDocument.description.ilike(f"%{search}%")
            )
        )
    
    # Ordenar por fecha de creación descendente
    query = query.order_by(desc(CommitteeDocument.created_at))
    
    documents = query.offset(skip).limit(limit).all()
    
    return documents

@router.get("/documents/recent", response_model=List[CommitteeDocumentSchema])
async def get_recent_documents(
    committee_id: int = Query(..., description="ID del comité"),
    limit: int = Query(10, ge=1, le=50, description="Número máximo de documentos a retornar"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtener los documentos más recientes de un comité específico"""
    # Verificar que el comité existe
    committee = db.query(Committee).filter(Committee.id == committee_id).first()
    if not committee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comité no encontrado"
        )
    
    # Obtener documentos más recientes ordenados por fecha de creación
    documents = db.query(CommitteeDocument).options(
        joinedload(CommitteeDocument.committee)
    ).filter(
        CommitteeDocument.committee_id == committee_id
    ).order_by(
        desc(CommitteeDocument.created_at)
    ).limit(limit).all()
    
    return documents

@router.post("/documents", response_model=CommitteeDocumentSchema, status_code=status.HTTP_201_CREATED)
async def create_committee_document(
    committee_id: int,
    document: CommitteeDocumentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Crear un nuevo documento de comité"""
    # Verificar que el comité existe
    committee = db.query(Committee).filter(Committee.id == committee_id).first()
    if not committee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comité no encontrado"
        )
    
    document_data = document.model_dump()
    document_data["committee_id"] = committee_id
    document_data["uploaded_by"] = current_user.id
    
    db_document = CommitteeDocument(**document_data)
    db.add(db_document)
    db.commit()
    db.refresh(db_document)
    
    return db_document

@router.get("/documents/{document_id}", response_model=CommitteeDocumentSchema)
async def get_committee_document(
    committee_id: int,
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtener un documento de comité por ID"""
    document = db.query(CommitteeDocument).options(
        joinedload(CommitteeDocument.committee)
    ).filter(
        and_(
            CommitteeDocument.id == document_id,
            CommitteeDocument.committee_id == committee_id
        )
    ).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento no encontrado"
        )
    
    return document

@router.put("/documents/{document_id}", response_model=CommitteeDocumentSchema)
async def update_committee_document(
    committee_id: int,
    document_id: int,
    document_update: CommitteeDocumentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Actualizar un documento de comité"""
    document = db.query(CommitteeDocument).filter(
        and_(
            CommitteeDocument.id == document_id,
            CommitteeDocument.committee_id == committee_id
        )
    ).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento no encontrado"
        )
    
    update_data = document_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(document, field, value)
    
    db.commit()
    db.refresh(document)
    
    return document

@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_committee_document(
    committee_id: int,
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Eliminar un documento de comité"""
    document = db.query(CommitteeDocument).filter(
        and_(
            CommitteeDocument.id == document_id,
            CommitteeDocument.committee_id == committee_id
        )
    ).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento no encontrado"
        )
    
    # TODO: Eliminar archivo físico del sistema de archivos si existe
    # if document.file_path and os.path.exists(document.file_path):
    #     os.remove(document.file_path)
    
    db.delete(document)
    db.commit()

@router.post("/documents/upload")
async def upload_document_file(
    committee_id: int,
    title: str,
    document_type: DocumentTypeEnum,
    file: UploadFile = File(...),
    description: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Subir un archivo de documento para un comité"""
    # Verificar que el comité existe
    committee = db.query(Committee).filter(Committee.id == committee_id).first()
    if not committee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comité no encontrado"
        )
    
    # Validar tipo de archivo
    allowed_extensions = {'.pdf', '.doc', '.docx', '.txt', '.xlsx', '.xls', '.ppt', '.pptx'}
    file_extension = '.' + file.filename.split('.')[-1].lower() if '.' in file.filename else ''
    
    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tipo de archivo no permitido. Tipos permitidos: PDF, DOC, DOCX, TXT, XLS, XLSX, PPT, PPTX"
        )
    
    # TODO: Implementar lógica de guardado de archivo
    # Por ahora, solo creamos el registro en la base de datos
    file_path = f"/uploads/committees/{committee_id}/{file.filename}"
    
    document_data = {
        "committee_id": committee_id,
        "title": title,
        "description": description,
        "document_type": document_type,
        "file_name": file.filename,
        "file_path": file_path,
        "file_size": file.size if hasattr(file, 'size') else 0,
        "uploaded_by": current_user.id
    }
    
    db_document = CommitteeDocument(**document_data)
    db.add(db_document)
    db.commit()
    db.refresh(db_document)
    
    return {
        "message": "Documento subido exitosamente",
        "document": db_document
    }

@router.get("/activities/user/{user_id}", response_model=List[CommitteeActivitySchema])
async def get_activities_by_user(
    user_id: int,
    status: Optional[ActivityStatusEnum] = Query(None),
    committee_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtener todas las actividades asignadas a un usuario específico"""
    query = db.query(CommitteeActivity).options(
        joinedload(CommitteeActivity.committee)
    ).filter(CommitteeActivity.assigned_to == user_id)
    
    if status:
        query = query.filter(CommitteeActivity.status == status)
    
    if committee_id:
        query = query.filter(CommitteeActivity.committee_id == committee_id)
    
    query = query.order_by(
        CommitteeActivity.priority.desc(),
        CommitteeActivity.due_date.asc()
    )
    
    activities = query.all()
    
    return activities

@router.get("/activities/overdue", response_model=List[CommitteeActivitySchema])
async def get_overdue_activities(
    committee_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtener todas las actividades vencidas"""
    today = date.today()
    
    query = db.query(CommitteeActivity).options(
        joinedload(CommitteeActivity.committee)
    ).filter(
        and_(
            CommitteeActivity.due_date < today,
            CommitteeActivity.status != ActivityStatusEnum.COMPLETED
        )
    )
    
    if committee_id:
        query = query.filter(CommitteeActivity.committee_id == committee_id)
    
    query = query.order_by(CommitteeActivity.due_date.asc())
    
    activities = query.all()
    
    return activities