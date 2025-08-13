from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.database import get_db
from app.models.admin_config import AdminConfig, Programas
from app.schemas.admin_config import (
    AdminConfigCreate,
    AdminConfigUpdate,
    AdminConfig as AdminConfigSchema,
    AdminConfigList,
    ProgramasCreate,
    ProgramasUpdate,
    Programas as ProgramasSchema
)
from app.dependencies import require_admin
from app.models.user import User

router = APIRouter()


@router.get("/categories", response_model=List[str])
async def get_categories(
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
@router.get("/programas", response_model=List[ProgramasSchema])
async def get_all_programas(
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


@router.post("/programas", response_model=ProgramasSchema, status_code=status.HTTP_201_CREATED)
async def create_programa(
    programa: ProgramasCreate,
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


@router.put("/programas/{programa_id}", response_model=ProgramasSchema)
async def update_programa(
    programa_id: int,
    programa_update: ProgramasUpdate,
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


@router.delete("/programas/{programa_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_programa(
    programa_id: int,
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