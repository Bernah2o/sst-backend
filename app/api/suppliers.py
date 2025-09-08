from typing import Any, List, Dict
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, func

from app.database import get_db
from app.dependencies import get_current_user, require_admin, require_supervisor_or_admin
from app.models.user import User
from app.models.supplier import Supplier, Doctor
from app.schemas.supplier import (
    Supplier as SupplierSchema,
    SupplierCreate,
    SupplierUpdate,
    SupplierList,
    SupplierWithDoctors,
    Doctor as DoctorSchema,
    DoctorCreate,
    DoctorUpdate,
    DoctorList
)
from app.schemas.common import MessageResponse

router = APIRouter()


# Endpoints para Suppliers
@router.get("/", response_model=List[SupplierList])
@router.get("", response_model=List[SupplierList])
async def get_suppliers(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: str = Query(None, description="Buscar por nombre, NIT o ciudad"),
    supplier_type: str = Query(None, description="Filtrar por tipo de proveedor"),
    status: str = Query(None, description="Filtrar por estado"),
    is_active: bool = Query(None, description="Filtrar por estado activo"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """Obtener lista de proveedores con filtros opcionales"""
    query = db.query(Supplier)
    
    # Aplicar filtros
    if search:
        query = query.filter(
            or_(
                Supplier.name.ilike(f"%{search}%"),
                Supplier.nit.ilike(f"%{search}%"),
                Supplier.city.ilike(f"%{search}%")
            )
        )
    
    if supplier_type:
        query = query.filter(Supplier.supplier_type == supplier_type)
    
    if status:
        query = query.filter(Supplier.status == status)
    
    if is_active is not None:
        query = query.filter(Supplier.is_active == is_active)
    
    # Agregar conteo de médicos
    suppliers = query.offset(skip).limit(limit).all()
    
    # Convertir a lista con conteo de médicos
    result = []
    for supplier in suppliers:
        supplier_dict = {
            "id": supplier.id,
            "name": supplier.name,
            "nit": supplier.nit,
            "supplier_type": supplier.supplier_type,
            "status": supplier.status,
            "email": supplier.email,
            "phone": supplier.phone,
            "city": supplier.city,
            "department": supplier.department,
            "is_active": supplier.is_active,
            "doctors_count": len(supplier.doctors)
        }
        result.append(supplier_dict)
    
    return result


@router.get("/types")
async def get_supplier_types(
    current_user: User = Depends(get_current_user)
) -> Any:
    """Obtener tipos de proveedores disponibles"""
    return {
        "types": [
            {"value": "medical_center", "label": "Centro Médico"},
            {"value": "laboratory", "label": "Laboratorio"},
            {"value": "clinic", "label": "Clínica"},
            {"value": "hospital", "label": "Hospital"},
            {"value": "pharmacy", "label": "Farmacia"}
        ],
        "statuses": [
            {"value": "active", "label": "Activo"},
            {"value": "inactive", "label": "Inactivo"}
        ]
    }


@router.get("/active", response_model=List[SupplierList])
async def get_active_suppliers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Obtener todos los proveedores activos.
    """
    suppliers = db.query(Supplier).filter(Supplier.is_active == True).all()
    
    # Convertir a lista con conteo de médicos
    result = []
    for supplier in suppliers:
        supplier_dict = {
            "id": supplier.id,
            "name": supplier.name,
            "nit": supplier.nit,
            "supplier_type": supplier.supplier_type,
            "status": supplier.status,
            "email": supplier.email,
            "phone": supplier.phone,
            "city": supplier.city,
            "department": supplier.department,
            "is_active": supplier.is_active,
            "doctors_count": len(supplier.doctors)
        }
        result.append(supplier_dict)
    
    return result


@router.get("/doctors", response_model=List[DoctorList])
@router.get("/doctors/", response_model=List[DoctorList])
async def get_all_doctors(
    is_active: bool = Query(None, description="Filtrar por estado activo"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """Obtener todos los médicos"""
    query = db.query(Doctor).options(joinedload(Doctor.supplier))
    
    if is_active is not None:
        query = query.filter(Doctor.is_active == is_active)
    
    doctors = query.all()
    return doctors


@router.post("/doctors", response_model=DoctorSchema)
@router.post("/doctors/", response_model=DoctorSchema)
async def create_doctor_general(
    doctor_data: DoctorCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """Crear un nuevo médico (requiere supplier_id en el body)"""
    # Verificar que se proporcione supplier_id
    if not hasattr(doctor_data, 'supplier_id') or not doctor_data.supplier_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="supplier_id es requerido"
        )
    
    # Verificar que el proveedor existe
    supplier = db.query(Supplier).filter(Supplier.id == doctor_data.supplier_id).first()
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proveedor no encontrado"
        )
    
    # Verificar que el documento no exista (solo si se proporciona)
    if doctor_data.document_number:
        existing_doctor = db.query(Doctor).filter(Doctor.document_number == doctor_data.document_number).first()
        if existing_doctor:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe un médico con este número de documento"
            )
    
    # Verificar que la licencia médica no exista
    existing_license = db.query(Doctor).filter(Doctor.medical_license == doctor_data.medical_license).first()
    if existing_license:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un médico con esta licencia médica"
        )
    
    # Crear el médico
    doctor_dict = doctor_data.dict()
    db_doctor = Doctor(**doctor_dict)
    db.add(db_doctor)
    db.commit()
    db.refresh(db_doctor)
    
    # Cargar la relación con el proveedor para la respuesta
    doctor_with_supplier = db.query(Doctor).options(joinedload(Doctor.supplier)).filter(Doctor.id == db_doctor.id).first()
    
    return doctor_with_supplier


@router.post("/", response_model=SupplierSchema)
@router.post("", response_model=SupplierSchema)
async def create_supplier(
    supplier_data: SupplierCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """Crear un nuevo proveedor"""
    # Verificar si ya existe un proveedor con el mismo NIT
    existing_supplier = db.query(Supplier).filter(Supplier.nit == supplier_data.nit).first()
    if existing_supplier:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un proveedor con este NIT"
        )
    
    # Crear el proveedor
    supplier = Supplier(**supplier_data.model_dump())
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    
    return supplier


@router.get("/{supplier_id}", response_model=SupplierWithDoctors)
async def get_supplier(
    supplier_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """Obtener un proveedor específico con sus médicos"""
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proveedor no encontrado"
        )
    
    return supplier


@router.put("/{supplier_id}", response_model=SupplierSchema)
async def update_supplier(
    supplier_id: int,
    supplier_data: SupplierUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """Actualizar un proveedor"""
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proveedor no encontrado"
        )
    
    # Verificar NIT único si se está actualizando
    if supplier_data.nit and supplier_data.nit != supplier.nit:
        existing_supplier = db.query(Supplier).filter(
            Supplier.nit == supplier_data.nit,
            Supplier.id != supplier_id
        ).first()
        if existing_supplier:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe un proveedor con este NIT"
            )
    
    # Actualizar campos
    update_data = supplier_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(supplier, field, value)
    
    db.commit()
    db.refresh(supplier)
    
    return supplier


@router.delete("/{supplier_id}", response_model=MessageResponse)
async def delete_supplier(
    supplier_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
) -> Any:
    """Eliminar un proveedor"""
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proveedor no encontrado"
        )
    
    db.delete(supplier)
    db.commit()
    
    return {"message": "Proveedor eliminado exitosamente"}


# Endpoints para Doctors
@router.post("/{supplier_id}/doctors", response_model=DoctorSchema)
async def create_doctor(
    supplier_id: int,
    doctor_data: DoctorCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """Crear un nuevo médico para un proveedor"""
    # Verificar que el proveedor existe
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proveedor no encontrado"
        )
    
    # Verificar que el documento no exista (solo si se proporciona)
    if doctor_data.document_number:
        existing_doctor = db.query(Doctor).filter(Doctor.document_number == doctor_data.document_number).first()
        if existing_doctor:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe un médico con este número de documento"
            )
    
    # Verificar que la licencia médica no exista
    existing_license = db.query(Doctor).filter(Doctor.medical_license == doctor_data.medical_license).first()
    if existing_license:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un médico con esta licencia médica"
        )
    
    # Crear el médico
    doctor_dict = doctor_data.dict()
    doctor_dict['supplier_id'] = supplier_id
    db_doctor = Doctor(**doctor_dict)
    db.add(db_doctor)
    db.commit()
    db.refresh(db_doctor)
    
    # Cargar la relación con el proveedor para la respuesta
    doctor_with_supplier = db.query(Doctor).options(joinedload(Doctor.supplier)).filter(Doctor.id == db_doctor.id).first()
    
    return doctor_with_supplier


@router.get("/{supplier_id}/doctors", response_model=List[DoctorList])
async def get_supplier_doctors(
    supplier_id: int,
    is_active: bool = Query(None, description="Filtrar por estado activo"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """Obtener médicos de un proveedor"""
    # Verificar que el proveedor existe
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proveedor no encontrado"
        )
    
    query = db.query(Doctor).options(joinedload(Doctor.supplier)).filter(Doctor.supplier_id == supplier_id)
    
    if is_active is not None:
        query = query.filter(Doctor.is_active == is_active)
    
    doctors = query.all()
    return doctors


# Endpoint para obtener todos los médicos activos (útil para selects)
@router.get("/doctors/active", response_model=List[DoctorList])
async def get_active_doctors(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Obtener todos los médicos activos de todos los proveedores"""
    doctors = db.query(Doctor).options(joinedload(Doctor.supplier)).filter(Doctor.is_active == True).all()
    return doctors


@router.get("/doctors/active/all", response_model=List[DoctorList])
async def get_all_active_doctors(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Obtener todos los médicos activos de todos los proveedores"""
    doctors = db.query(Doctor).options(joinedload(Doctor.supplier)).filter(Doctor.is_active == True).all()
    return doctors


@router.get("/doctors/{doctor_id}", response_model=DoctorSchema)
async def get_doctor(
    doctor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """Obtener un médico específico"""
    doctor = db.query(Doctor).options(joinedload(Doctor.supplier)).filter(Doctor.id == doctor_id).first()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Médico no encontrado"
        )
    
    return doctor


@router.put("/doctors/{doctor_id}", response_model=DoctorSchema)
async def update_doctor(
    doctor_id: int,
    doctor_data: DoctorUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """Actualizar un médico"""
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Médico no encontrado"
        )
    
    # Verificar documento único si se está actualizando
    if doctor_data.document_number and doctor_data.document_number != doctor.document_number:
        existing_doctor = db.query(Doctor).filter(
            Doctor.document_number == doctor_data.document_number,
            Doctor.id != doctor_id
        ).first()
        if existing_doctor:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe un médico con este número de documento"
            )
    
    # Verificar licencia médica única si se está actualizando
    if doctor_data.medical_license and doctor_data.medical_license != doctor.medical_license:
        existing_license = db.query(Doctor).filter(
            Doctor.medical_license == doctor_data.medical_license,
            Doctor.id != doctor_id
        ).first()
        if existing_license:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe un médico con esta licencia médica"
            )
    
    # Actualizar campos
    update_data = doctor_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(doctor, field, value)
    
    db.commit()
    db.refresh(doctor)
    
    # Cargar la relación con el proveedor para la respuesta
    doctor_with_supplier = db.query(Doctor).options(joinedload(Doctor.supplier)).filter(Doctor.id == doctor_id).first()
    
    return doctor_with_supplier


@router.delete("/doctors/{doctor_id}", response_model=MessageResponse)
async def delete_doctor(
    doctor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
) -> Any:
    """Eliminar un médico"""
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Médico no encontrado"
        )
    
    db.delete(doctor)
    db.commit()
    
    return {"message": "Médico eliminado exitosamente"}