from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_supervisor_or_admin
from app.models.master_document import MasterDocument
from app.models.user import User
from app.schemas.master_document import (
    MasterDocumentCreate,
    MasterDocumentResponse,
    MasterDocumentUpdate,
)


router = APIRouter()


def _get_master_document_or_404(db: Session, document_id: int) -> MasterDocument:
    document = db.query(MasterDocument).filter(MasterDocument.id == document_id).first()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento no encontrado")
    return document


@router.get("/", response_model=List[MasterDocumentResponse])
def listar_master_documents(
    empresa_id: Optional[int] = Query(None),
    tipo_documento: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    include_inactive: bool = Query(False),
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(MasterDocument)
    if empresa_id is not None:
        query = query.filter(MasterDocument.empresa_id == empresa_id)
    if tipo_documento:
        query = query.filter(MasterDocument.tipo_documento == tipo_documento)
    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(
                MasterDocument.codigo.ilike(like),
                MasterDocument.nombre_documento.ilike(like),
            )
        )
    if not include_inactive:
        query = query.filter(MasterDocument.is_active.is_(True))

    return (
        query.order_by(MasterDocument.tipo_documento.asc(), MasterDocument.codigo.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.post("/", response_model=MasterDocumentResponse, status_code=status.HTTP_201_CREATED)
def crear_master_document(
    data: MasterDocumentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin),
):
    # Validar unicidad del código (case-insensitive)
    codigo_normalizado = data.codigo.strip()
    
    existente = (
        db.query(MasterDocument)
        .filter(MasterDocument.empresa_id == data.empresa_id)
        .filter(func.lower(MasterDocument.codigo) == func.lower(codigo_normalizado))
        .first()
    )
    if existente:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe un documento con el código '{codigo_normalizado}' para esta empresa",
        )

    # Actualizar código normalizado en los datos
    document_data = data.model_dump()
    document_data["codigo"] = codigo_normalizado

    document = MasterDocument(**document_data, created_by=current_user.id)
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


@router.get("/{document_id}", response_model=MasterDocumentResponse)
def obtener_master_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _get_master_document_or_404(db, document_id)


@router.put("/{document_id}", response_model=MasterDocumentResponse)
def actualizar_master_document(
    document_id: int,
    data: MasterDocumentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin),
):
    document = _get_master_document_or_404(db, document_id)

    update_data = data.model_dump(exclude_unset=True)

    if "codigo" in update_data or "empresa_id" in update_data:
        new_codigo = update_data.get("codigo", document.codigo).strip()
        new_empresa_id = update_data.get("empresa_id", document.empresa_id)
        
        existente = (
            db.query(MasterDocument)
            .filter(MasterDocument.id != document.id)
            .filter(MasterDocument.empresa_id == new_empresa_id)
            .filter(func.lower(MasterDocument.codigo) == func.lower(new_codigo))
            .first()
        )
        if existente:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ya existe un documento con el código '{new_codigo}' para esta empresa",
            )
        
        # Actualizar el código si fue proporcionado
        if "codigo" in update_data:
            update_data["codigo"] = new_codigo

    for field, value in update_data.items():
        setattr(document, field, value)
    document.updated_by = current_user.id
    db.commit()
    db.refresh(document)
    return document


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def desactivar_master_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin),
):
    document = _get_master_document_or_404(db, document_id)
    document.is_active = False
    document.updated_by = current_user.id
    db.commit()
    return None

