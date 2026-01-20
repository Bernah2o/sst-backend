from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.database import get_db
from app.models.admin_config import AdminConfig, Programas
from app.models.cargo import Cargo
from app.models.seguridad_social import SeguridadSocial
from app.schemas.admin_config import (
    AdminConfigCreate,
    AdminConfigUpdate,
    AdminConfig as AdminConfigSchema,
    AdminConfigList,
    ProgramasCreate,
    ProgramasUpdate,
    Programas as ProgramasSchema
)
from app.schemas.cargo import CargoCreate, CargoUpdate, Cargo as CargoSchema
from app.schemas.seguridad_social import SeguridadSocialCreate, SeguridadSocialUpdate, SeguridadSocial as SeguridadSocialSchema
from app.dependencies import require_admin, get_current_active_user
from app.models.user import User
from app.models.worker_document import WorkerDocument
from app.models.contractor import ContractorDocument
from app.models.occupational_exam import OccupationalExam
from app.models.course import CourseMaterial, CourseModule
from app.models.certificate import Certificate
from app.models.committee import CommitteeDocument, Committee, CommitteeMember, CommitteeMeeting, CommitteeActivity
from app.utils.storage import storage_manager
from app.services.s3_storage import s3_service, contabo_service
import httpx
from app.config import settings
import logging
from datetime import datetime

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/categories{trailing_slash:path}", response_model=List[str])
async def get_categories(
    trailing_slash: str = "",
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get all available configuration categories"""
    categories = db.query(AdminConfig.category).distinct().all()
    return [cat[0] for cat in categories]


@router.get("/category/{category}", response_model=AdminConfigList)
async def get_configs_by_category(
    category: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get all configurations for a specific category"""
    if category == "position":
        # Redirigir a cargos para mantener compatibilidad
        cargos = db.query(Cargo).all()
        # Convertir cargos a formato AdminConfig para compatibilidad
        configs = [
            AdminConfigSchema(
                id=cargo.id,
                category="position",
                display_name=cargo.nombre_cargo,
                emo_periodicity=cargo.periodicidad_emo,
                is_active=cargo.activo,
                created_at=cargo.created_at,
                updated_at=cargo.updated_at
            )
            for cargo in cargos
        ]
        return AdminConfigList(
            category=category,
            configs=configs
        )
    
    configs = db.query(AdminConfig).filter(
        AdminConfig.category == category
    ).order_by(AdminConfig.display_name).all()
    
    return AdminConfigList(
        category=category,
        configs=configs
    )


@router.get("/category/{category}/active", response_model=List[AdminConfigSchema])
async def get_active_configs_by_category(
    category: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get all active configurations for a specific category (admin endpoint)"""
    configs = db.query(AdminConfig).filter(
        and_(
            AdminConfig.category == category,
            AdminConfig.is_active == True
        )
    ).order_by(AdminConfig.display_name).all()
    
    return configs


@router.get("/active/{category}", response_model=List[AdminConfigSchema])
async def get_public_active_configs(
    category: str,
    db: Session = Depends(get_db)
):
    """Public endpoint to get all active configurations for a specific category"""
    configs = db.query(AdminConfig).filter(
        and_(
            AdminConfig.category == category,
            AdminConfig.is_active == True
        )
    ).order_by(AdminConfig.display_name).all()
    
    return configs





@router.post("/", response_model=AdminConfigSchema, status_code=status.HTTP_201_CREATED)
async def create_config(
    config: AdminConfigCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Create a new configuration"""
    # Check if configuration with same category and display_name already exists
    existing = db.query(AdminConfig).filter(
        and_(
            AdminConfig.category == config.category,
            AdminConfig.display_name == config.display_name
        )
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Configuration with category '{config.category}' and display name '{config.display_name}' already exists"
        )
    
    db_config = AdminConfig(**config.dict())
    db.add(db_config)
    db.commit()
    db.refresh(db_config)
    
    return db_config


@router.put("/{config_id}", response_model=AdminConfigSchema)
async def update_config(
    config_id: int,
    config_update: AdminConfigUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Update an existing configuration"""
    db_config = db.query(AdminConfig).filter(AdminConfig.id == config_id).first()
    
    if not db_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Configuration not found"
        )
    
    # Check for duplicate display_name in same category if display_name is being updated
    if config_update.display_name and config_update.display_name != db_config.display_name:
        existing = db.query(AdminConfig).filter(
            and_(
                AdminConfig.category == db_config.category,
                AdminConfig.display_name == config_update.display_name,
                AdminConfig.id != config_id
            )
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Configuration with category '{db_config.category}' and display name '{config_update.display_name}' already exists"
            )
    
    # Update fields
    update_data = config_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_config, field, value)
    
    db.commit()
    db.refresh(db_config)
    
    return db_config


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_config(
    config_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Delete a configuration"""
    db_config = db.query(AdminConfig).filter(AdminConfig.id == config_id).first()
    
    if not db_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Configuration not found"
        )
    
    db.delete(db_config)
    db.commit()
    
    return None


# Endpoints para Seguridad Social
@router.get("/seguridad-social{trailing_slash:path}", response_model=List[SeguridadSocialSchema])
def get_seguridad_social(
    trailing_slash: str = "",
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    is_active: Optional[bool] = Query(None, description="Filtrar por estado activo"),
    tipo: Optional[str] = Query(None, description="Filtrar por tipo (eps, afp, arl)"),
    search: Optional[str] = Query(None, description="Buscar por nombre"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Obtener lista de entidades de seguridad social"""
    query = db.query(SeguridadSocial)
    
    if is_active is not None:
        query = query.filter(SeguridadSocial.is_active == is_active)
    
    if tipo:
        query = query.filter(SeguridadSocial.tipo == tipo)
    
    if search:
        query = query.filter(SeguridadSocial.nombre.ilike(f"%{search}%"))
    
    return query.offset(skip).limit(limit).all()


@router.get("/seguridad-social/active{trailing_slash:path}", response_model=List[SeguridadSocialSchema])
def get_active_seguridad_social(
    trailing_slash: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Obtener entidades de seguridad social activas"""
    return db.query(SeguridadSocial).filter(SeguridadSocial.is_active == True).all()


@router.get("/seguridad-social/tipo/{tipo}{trailing_slash:path}", response_model=List[SeguridadSocialSchema])
def get_seguridad_social_by_tipo(
    tipo: str,
    trailing_slash: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Obtener entidades de seguridad social activas por tipo (eps, afp, arl)"""
    return db.query(SeguridadSocial).filter(
        and_(
            SeguridadSocial.tipo == tipo,
            SeguridadSocial.is_active == True
        )
    ).all()


@router.get("/seguridad-social/{seguridad_social_id}{trailing_slash:path}", response_model=SeguridadSocialSchema)
def get_seguridad_social_by_id(
    seguridad_social_id: int,
    trailing_slash: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Obtener una entidad de seguridad social por ID"""
    seguridad_social = db.query(SeguridadSocial).filter(SeguridadSocial.id == seguridad_social_id).first()
    if not seguridad_social:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entidad de seguridad social no encontrada"
        )
    return seguridad_social


@router.post("/seguridad-social{trailing_slash:path}", response_model=SeguridadSocialSchema, status_code=status.HTTP_201_CREATED)
def create_seguridad_social(
    seguridad_social_data: SeguridadSocialCreate,
    trailing_slash: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Crear nueva entidad de seguridad social"""
    # Verificar si ya existe una entidad con el mismo nombre y tipo
    existing = db.query(SeguridadSocial).filter(
        and_(
            SeguridadSocial.nombre == seguridad_social_data.nombre,
            SeguridadSocial.tipo == seguridad_social_data.tipo
        )
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe una entidad {seguridad_social_data.tipo.upper()} con el nombre '{seguridad_social_data.nombre}'"
        )
    
    seguridad_social = SeguridadSocial(**seguridad_social_data.dict())
    db.add(seguridad_social)
    db.commit()
    db.refresh(seguridad_social)
    return seguridad_social


@router.put("/seguridad-social/{seguridad_social_id}{trailing_slash:path}", response_model=SeguridadSocialSchema)
def update_seguridad_social(
    seguridad_social_id: int,
    seguridad_social_data: SeguridadSocialUpdate,
    trailing_slash: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Actualizar entidad de seguridad social"""
    seguridad_social = db.query(SeguridadSocial).filter(SeguridadSocial.id == seguridad_social_id).first()
    if not seguridad_social:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entidad de seguridad social no encontrada"
        )
    
    # Verificar duplicados si se está actualizando el nombre
    if seguridad_social_data.nombre and seguridad_social_data.nombre != seguridad_social.nombre:
        existing = db.query(SeguridadSocial).filter(
            and_(
                SeguridadSocial.nombre == seguridad_social_data.nombre,
                SeguridadSocial.tipo == seguridad_social.tipo,
                SeguridadSocial.id != seguridad_social_id
            )
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ya existe una entidad {seguridad_social.tipo.upper()} con el nombre '{seguridad_social_data.nombre}'"
            )
    
    # Actualizar campos
    update_data = seguridad_social_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(seguridad_social, field, value)
    
    db.commit()
    db.refresh(seguridad_social)
    return seguridad_social


@router.delete("/seguridad-social/{seguridad_social_id}{trailing_slash:path}", status_code=status.HTTP_204_NO_CONTENT)
def delete_seguridad_social(
    seguridad_social_id: int,
    trailing_slash: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Eliminar entidad de seguridad social"""
    seguridad_social = db.query(SeguridadSocial).filter(SeguridadSocial.id == seguridad_social_id).first()
    if not seguridad_social:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entidad de seguridad social no encontrada"
        )
    
    db.delete(seguridad_social)
    db.commit()
    return None


# Endpoints específicos para cargos bajo /admin/config/cargos
@router.get("/cargos{trailing_slash:path}", response_model=List[CargoSchema])
def get_cargos(
    trailing_slash: str = "",
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    activo: Optional[bool] = Query(None, description="Filtrar por estado activo"),
    search: Optional[str] = Query(None, description="Buscar por nombre de cargo"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Obtener lista de cargos"""
    query = db.query(Cargo)
    
    # Filtros
    if activo is not None:
        query = query.filter(Cargo.activo == activo)
    
    if search:
        query = query.filter(Cargo.nombre_cargo.ilike(f"%{search}%"))
    
    # Ordenar por nombre
    query = query.order_by(Cargo.nombre_cargo)
    
    # Paginación
    cargos = query.offset(skip).limit(limit).all()
    
    return cargos


@router.get("/cargos/active", response_model=List[CargoSchema])
def get_active_cargos(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Obtener solo cargos activos"""
    cargos = db.query(Cargo).filter(Cargo.activo == True).order_by(Cargo.nombre_cargo).all()
    return cargos


@router.get("/cargos/{cargo_id}", response_model=CargoSchema)
def get_cargo(
    cargo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Obtener un cargo específico"""
    cargo = db.query(Cargo).filter(Cargo.id == cargo_id).first()
    if not cargo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cargo no encontrado"
        )
    return cargo


@router.post("/cargos{trailing_slash:path}", response_model=CargoSchema, status_code=status.HTTP_201_CREATED)
def create_cargo(
    cargo_data: CargoCreate,
    trailing_slash: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Crear un nuevo cargo"""
    # Verificar que no exista un cargo con el mismo nombre
    existing_cargo = db.query(Cargo).filter(Cargo.nombre_cargo == cargo_data.nombre_cargo).first()
    if existing_cargo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un cargo con este nombre"
        )
    
    # Crear el cargo
    cargo = Cargo(**cargo_data.model_dump())
    db.add(cargo)
    db.commit()
    db.refresh(cargo)
    
    return cargo


@router.put("/cargos/{cargo_id}{trailing_slash:path}", response_model=CargoSchema)
def update_cargo(
    cargo_id: int,
    cargo_data: CargoUpdate,
    trailing_slash: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Actualizar un cargo existente"""
    cargo = db.query(Cargo).filter(Cargo.id == cargo_id).first()
    if not cargo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cargo no encontrado"
        )
    
    # Verificar nombre único si se está actualizando
    if cargo_data.nombre_cargo and cargo_data.nombre_cargo != cargo.nombre_cargo:
        existing_cargo = db.query(Cargo).filter(
            and_(
                Cargo.nombre_cargo == cargo_data.nombre_cargo,
                Cargo.id != cargo_id
            )
        ).first()
        if existing_cargo:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe un cargo con este nombre"
            )
    
    # Actualizar campos
    update_data = cargo_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(cargo, field, value)
    
    db.commit()
    db.refresh(cargo)
    
    return cargo


@router.delete("/cargos/{cargo_id}{trailing_slash:path}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cargo(
    cargo_id: int,
    trailing_slash: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Eliminar un cargo"""
    cargo = db.query(Cargo).filter(Cargo.id == cargo_id).first()
    if not cargo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cargo no encontrado"
        )
    
    # TODO: Verificar si el cargo está siendo usado por trabajadores
    # antes de permitir la eliminación
    
    db.delete(cargo)
    db.commit()
    
    return None


@router.post("/seed", status_code=status.HTTP_201_CREATED)
async def seed_initial_data(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Seed initial configuration data"""
    
    # Initial EPS data
    eps_data = [
        {"category": "eps", "display_name": "EPS SURA"},
        {"category": "eps", "display_name": "EPS Sanitas"},
        {"category": "eps", "display_name": "Nueva EPS"},
        {"category": "eps", "display_name": "Compensar EPS"},
        {"category": "eps", "display_name": "Famisanar EPS"},
        {"category": "eps", "display_name": "Salud Total EPS"},
        {"category": "eps", "display_name": "Coomeva EPS"},
        {"category": "eps", "display_name": "Medimás EPS"},
    ]
    
    # Initial AFP data
    afp_data = [
        {"category": "afp", "display_name": "Porvenir"},
        {"category": "afp", "display_name": "Protección"},
        {"category": "afp", "display_name": "Old Mutual"},
        {"category": "afp", "display_name": "Colfondos"},
        {"category": "afp", "display_name": "Colpensiones"},
    ]
    
    # Initial ARL data
    arl_data = [
        {"category": "arl", "display_name": "ARL SURA"},
        {"category": "arl", "display_name": "Positiva Compañía de Seguros"},
        {"category": "arl", "display_name": "Colmena Seguros"},
        {"category": "arl", "display_name": "Liberty Seguros"},
        {"category": "arl", "display_name": "Mapfre Seguros"},
        {"category": "arl", "display_name": "Seguros Bolívar"},
        {"category": "arl", "display_name": "La Equidad Seguros"},
    ]
    
    all_data = eps_data + afp_data + arl_data
    created_count = 0
    
    for item in all_data:
        # Check if already exists
        existing = db.query(AdminConfig).filter(
            and_(
                AdminConfig.category == item["category"],
                AdminConfig.display_name == item["display_name"]
            )
        ).first()
        
        if not existing:
            db_config = AdminConfig(**item)
            db.add(db_config)
            created_count += 1
    
    db.commit()
    
    return {"message": f"Seeded {created_count} configuration items"}


# Programas endpoints
@router.get("/programas{trailing_slash:path}", response_model=List[ProgramasSchema])
async def get_all_programas(
    trailing_slash: str = "",
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get all programs"""
    programas = db.query(Programas).order_by(Programas.nombre_programa).all()
    return programas


@router.get("/programas/active", response_model=List[ProgramasSchema])
async def get_active_programas(
    db: Session = Depends(get_db)
):
    """Get all active programs (public endpoint)"""
    programas = db.query(Programas).filter(
        Programas.activo == True
    ).order_by(Programas.nombre_programa).all()
    return programas


@router.get("/programas/{programa_id}", response_model=ProgramasSchema)
async def get_programa(
    programa_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get a specific program by ID"""
    programa = db.query(Programas).filter(Programas.id == programa_id).first()
    if not programa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Programa no encontrado"
        )
    return programa


@router.post("/programas{trailing_slash:path}", response_model=ProgramasSchema, status_code=status.HTTP_201_CREATED)
async def create_programa(
    programa: ProgramasCreate,
    trailing_slash: str = "",
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Create a new program"""
    # Check if program name already exists
    existing = db.query(Programas).filter(
        Programas.nombre_programa == programa.nombre_programa
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un programa con este nombre"
        )
    
    db_programa = Programas(**programa.dict())
    db.add(db_programa)
    db.commit()
    db.refresh(db_programa)
    
    return db_programa


@router.put("/programas/{programa_id}{trailing_slash:path}", response_model=ProgramasSchema)
async def update_programa(
    programa_id: int,
    programa_update: ProgramasUpdate,
    trailing_slash: str = "",
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Update a program"""
    db_programa = db.query(Programas).filter(Programas.id == programa_id).first()
    
    if not db_programa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Programa no encontrado"
        )
    
    # Check if new name already exists (if name is being updated)
    if programa_update.nombre_programa and programa_update.nombre_programa != db_programa.nombre_programa:
        existing = db.query(Programas).filter(
            and_(
                Programas.nombre_programa == programa_update.nombre_programa,
                Programas.id != programa_id
            )
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe un programa con este nombre"
            )
    
    # Update fields
    update_data = programa_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_programa, field, value)
    
    db.commit()
    db.refresh(db_programa)
    
    return db_programa


@router.delete("/programas/{programa_id}{trailing_slash:path}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_programa(
    programa_id: int,
    trailing_slash: str = "",
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Delete a program"""
    db_programa = db.query(Programas).filter(Programas.id == programa_id).first()
    
    if not db_programa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Programa no encontrado"
        )
    
    db.delete(db_programa)
    db.commit()
    
    return None
