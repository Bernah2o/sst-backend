from typing import Any, List, Dict
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_
from io import BytesIO
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill
from datetime import datetime

from app.database import get_db
from app.dependencies import get_current_user, require_admin, require_supervisor_or_admin
from app.models.user import User
from app.models.worker import Worker, WorkerContract
from app.models.occupational_exam import OccupationalExam
from app.models.seguimiento import Seguimiento, EstadoSeguimiento
from app.schemas.worker import (
    Worker as WorkerSchema,
    WorkerCreate,
    WorkerUpdate,
    WorkerList,
    WorkerContract as WorkerContractSchema,
    WorkerContractCreate,
    WorkerContractUpdate
)
from app.schemas.occupational_exam import (
    OccupationalExamCreate,
    OccupationalExamUpdate,
    OccupationalExamResponse,
    OccupationalExamListResponse
)
from app.schemas.common import MessageResponse

router = APIRouter()


@router.get("/", response_model=List[WorkerList])
async def get_workers(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: str = Query(None, description="Buscar por nombre, documento o email"),
    is_active: bool = Query(None, description="Filtrar por estado activo"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """
    Obtener lista de trabajadores con filtros opcionales
    """
    query = db.query(Worker)
    
    # Filtro de búsqueda
    if search:
        search_filter = or_(
            Worker.first_name.ilike(f"%{search}%"),
            Worker.last_name.ilike(f"%{search}%"),
            Worker.document_number.ilike(f"%{search}%"),
            Worker.email.ilike(f"%{search}%")
        )
        query = query.filter(search_filter)
    
    # Filtro por estado activo
    if is_active is not None:
        query = query.filter(Worker.is_active == is_active)
    
    workers = query.offset(skip).limit(limit).all()
    return workers


@router.post("/", response_model=WorkerSchema)
async def create_worker(
    worker_data: WorkerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """
    Crear un nuevo trabajador
    """
    # Verificar si ya existe un trabajador con el mismo documento o email
    existing_worker = db.query(Worker).filter(
        or_(
            Worker.document_number == worker_data.document_number,
            Worker.email == worker_data.email
        )
    ).first()
    
    if existing_worker:
        if existing_worker.document_number == worker_data.document_number:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe un trabajador con este número de documento"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe un trabajador con este email"
            )
    
    # Crear el trabajador
    worker = Worker(**worker_data.dict())
    db.add(worker)
    db.commit()
    db.refresh(worker)
    
    return worker


@router.get("/{worker_id}", response_model=WorkerSchema)
async def get_worker(
    worker_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """
    Obtener un trabajador por ID
    """
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trabajador no encontrado"
        )
    return worker


@router.put("/{worker_id}", response_model=WorkerSchema)
async def update_worker(
    worker_id: int,
    worker_data: WorkerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """
    Actualizar un trabajador
    """
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trabajador no encontrado"
        )
    
    # Verificar duplicados si se actualiza documento o email
    update_data = worker_data.dict(exclude_unset=True)
    
    if "document_number" in update_data or "email" in update_data:
        existing_worker = db.query(Worker).filter(
            Worker.id != worker_id,
            or_(
                Worker.document_number == update_data.get("document_number", worker.document_number),
                Worker.email == update_data.get("email", worker.email)
            )
        ).first()
        
        if existing_worker:
            if existing_worker.document_number == update_data.get("document_number"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Ya existe otro trabajador con este número de documento"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Ya existe otro trabajador con este email"
                )
    
    # Actualizar campos
    for field, value in update_data.items():
        setattr(worker, field, value)
    
    db.commit()
    db.refresh(worker)
    
    return worker


@router.delete("/{worker_id}", response_model=MessageResponse)
async def delete_worker(
    worker_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
) -> Any:
    """
    Eliminar un trabajador (solo administradores)
    """
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trabajador no encontrado"
        )
    
    db.delete(worker)
    db.commit()
    
    return MessageResponse(message="Trabajador eliminado exitosamente")


# Endpoints para contratos
@router.post("/{worker_id}/contracts", response_model=WorkerContractSchema)
async def create_worker_contract(
    worker_id: int,
    contract_data: WorkerContractCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """
    Crear un nuevo contrato para un trabajador
    """
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trabajador no encontrado"
        )
    
    contract = WorkerContract(
        worker_id=worker_id,
        **contract_data.dict()
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)
    
    return contract


@router.get("/{worker_id}/contracts", response_model=List[WorkerContractSchema])
async def get_worker_contracts(
    worker_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """
    Obtener todos los contratos de un trabajador
    """
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trabajador no encontrado"
        )
    
    return worker.contracts


@router.put("/contracts/{contract_id}", response_model=WorkerContractSchema)
async def update_worker_contract(
    contract_id: int,
    contract_data: WorkerContractUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """
    Actualizar un contrato de trabajador
    """
    contract = db.query(WorkerContract).filter(WorkerContract.id == contract_id).first()
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contrato no encontrado"
        )
    
    update_data = contract_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(contract, field, value)
    
    db.commit()
    db.refresh(contract)
    
    return contract


@router.delete("/contracts/{contract_id}", response_model=MessageResponse)
async def delete_worker_contract(
    contract_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
) -> Any:
    """
    Eliminar un contrato de trabajador (solo administradores)
    """
    contract = db.query(WorkerContract).filter(WorkerContract.id == contract_id).first()
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contrato no encontrado"
        )
    
    db.delete(contract)
    db.commit()
    
    return MessageResponse(message="Contrato eliminado exitosamente")


@router.get("/check-document/{document_number}", response_model=Dict[str, Any])
async def check_worker_document(
    document_number: str,
    db: Session = Depends(get_db)
) -> Any:
    """
    Verificar si un número de documento corresponde a un trabajador registrado
    y si ya está registrado como usuario
    """
    worker = db.query(Worker).filter(
        Worker.document_number == document_number,
        Worker.is_active == True
    ).first()
    
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró un trabajador activo con ese número de documento"
        )
    
    return {
        "exists": True,
        "is_registered": worker.is_registered,
        "assigned_role": worker.assigned_role
    }


@router.post("/validate-employee", response_model=Dict[str, Any])
async def validate_employee_credentials(
    credentials: Dict[str, str],
    db: Session = Depends(get_db)
) -> Any:
    """
    Validar que tanto el número de documento como el correo electrónico
    correspondan a un trabajador registrado por el administrador
    """
    document_number = credentials.get("document_number")
    email = credentials.get("email")
    
    if not document_number or not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Se requiere número de documento y correo electrónico"
        )
    
    worker = db.query(Worker).filter(
        Worker.document_number == document_number,
        Worker.email == email,
        Worker.is_active == True
    ).first()
    
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró un trabajador activo con ese número de documento y correo electrónico. Solo los empleados registrados por el administrador pueden crear una cuenta."
        )
    
    if worker.is_registered:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este trabajador ya tiene una cuenta registrada en el sistema."
        )
    
    return {
        "valid": True,
        "worker_id": worker.id,
        "assigned_role": worker.assigned_role,
        "full_name": worker.full_name
    }


# Endpoints para exámenes ocupacionales
@router.post("/{worker_id}/occupational-exams", response_model=OccupationalExamResponse)
async def create_occupational_exam(
    worker_id: int,
    exam_data: OccupationalExamCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """
    Crear un nuevo examen ocupacional para un trabajador
    """
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trabajador no encontrado"
        )
    
    exam = OccupationalExam(
        worker_id=worker_id,
        **exam_data.dict(exclude={"worker_id"})
    )
    db.add(exam)
    db.commit()
    db.refresh(exam)
    
    # Crear seguimiento automáticamente si se asigna un programa
    if exam.programa and exam.programa.strip():
        # Verificar si ya existe un seguimiento activo para este programa
        existing_seguimiento = db.query(Seguimiento).filter(
            Seguimiento.worker_id == worker_id,
            Seguimiento.programa == exam.programa,
            Seguimiento.estado == EstadoSeguimiento.INICIADO
        ).first()
        
        if not existing_seguimiento:
            # Crear nuevo seguimiento automáticamente
            seguimiento = Seguimiento(
                worker_id=worker_id,
                programa=exam.programa,
                nombre_trabajador=worker.full_name,
                cedula=worker.document_number,
                cargo=worker.position,
                fecha_ingreso=worker.fecha_de_ingreso,
                estado=EstadoSeguimiento.INICIADO,
                # Copiar datos del examen ocupacional
                conclusiones_ocupacionales=exam.occupational_conclusions,
                conductas_ocupacionales_prevenir=exam.preventive_occupational_behaviors,
                recomendaciones_generales=exam.general_recommendations,
                observaciones_examen=exam.observations
            )
            db.add(seguimiento)
            db.commit()
    
    return exam


@router.get("/{worker_id}/occupational-exams", response_model=List[OccupationalExamResponse])
async def get_worker_occupational_exams(
    worker_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """
    Obtener todos los exámenes ocupacionales de un trabajador ordenados por fecha descendente
    """
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trabajador no encontrado"
        )
    
    # Ordenar exámenes por fecha descendente (más reciente primero)
    exams = db.query(OccupationalExam).filter(
        OccupationalExam.worker_id == worker_id
    ).order_by(OccupationalExam.exam_date.desc()).all()
    
    return exams


@router.get("/occupational-exams/{exam_id}", response_model=OccupationalExamResponse)
async def get_occupational_exam(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """
    Obtener un examen ocupacional por ID
    """
    exam = db.query(OccupationalExam).filter(OccupationalExam.id == exam_id).first()
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Examen ocupacional no encontrado"
        )
    return exam


@router.put("/occupational-exams/{exam_id}", response_model=OccupationalExamResponse)
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
    
    # Guardar el programa anterior para comparar
    old_programa = exam.programa
    
    update_data = exam_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(exam, field, value)
    
    db.commit()
    db.refresh(exam)
    
    # Crear seguimiento automáticamente si se asigna un programa nuevo
    if exam.programa and exam.programa.strip() and exam.programa != old_programa:
        worker = db.query(Worker).filter(Worker.id == exam.worker_id).first()
        if worker:
            # Verificar si ya existe un seguimiento activo para este programa
            existing_seguimiento = db.query(Seguimiento).filter(
                Seguimiento.worker_id == exam.worker_id,
                Seguimiento.programa == exam.programa,
                Seguimiento.estado == EstadoSeguimiento.INICIADO
            ).first()
            
            if not existing_seguimiento:
                # Crear nuevo seguimiento automáticamente
                seguimiento = Seguimiento(
                    worker_id=exam.worker_id,
                    programa=exam.programa,
                    nombre_trabajador=worker.full_name,
                    cedula=worker.document_number,
                    cargo=worker.position,
                    fecha_ingreso=worker.fecha_de_ingreso,
                    estado=EstadoSeguimiento.INICIADO,
                    # Copiar datos del examen ocupacional
                    conclusiones_ocupacionales=exam.occupational_conclusions,
                    conductas_ocupacionales_prevenir=exam.preventive_occupational_behaviors,
                    recomendaciones_generales=exam.general_recommendations,
                    observaciones_examen=exam.observations
                )
                db.add(seguimiento)
                db.commit()
    
    return exam


@router.delete("/occupational-exams/{exam_id}", response_model=MessageResponse)
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


@router.get("/export/excel")
async def export_workers_to_excel(
    search: str = Query(None, description="Buscar por nombre, documento o email"),
    is_active: bool = Query(None, description="Filtrar por estado activo"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> StreamingResponse:
    """
    Exportar trabajadores a Excel
    """
    # Obtener trabajadores con los mismos filtros que el endpoint principal
    query = db.query(Worker)
    
    # Filtro de búsqueda
    if search:
        search_filter = or_(
            Worker.first_name.ilike(f"%{search}%"),
            Worker.last_name.ilike(f"%{search}%"),
            Worker.document_number.ilike(f"%{search}%"),
            Worker.email.ilike(f"%{search}%")
        )
        query = query.filter(search_filter)
    
    # Filtro por estado activo
    if is_active is not None:
        query = query.filter(Worker.is_active == is_active)
    
    workers = query.all()
    
    # Crear el archivo Excel
    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.title = "Trabajadores"
    
    # Definir estilos
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
    header_alignment = Alignment(horizontal="center", vertical="center")
    
    # Encabezados
    headers = [
        "ID", "Nombre", "Apellido", "Tipo Documento", "Número Documento", 
        "Email", "Teléfono", "Fecha Nacimiento", "Género", "Ciudad", 
        "Departamento", "País", "Cargo", "Fecha Ingreso", "Tipo Contrato", 
        "Modalidad Trabajo", "Profesión", "Nivel Riesgo", "Ocupación", 
        "Salario IBC", "EPS", "AFP", "ARL", "Tipo Sangre", "Observaciones", 
        "Estado", "Rol Asignado", "Fecha Creación"
    ]
    
    # Escribir encabezados
    for col, header in enumerate(headers, 1):
        cell = worksheet.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
    
    # Escribir datos de trabajadores
    for row, worker in enumerate(workers, 2):
        worksheet.cell(row=row, column=1, value=worker.id)
        worksheet.cell(row=row, column=2, value=worker.first_name)
        worksheet.cell(row=row, column=3, value=worker.last_name)
        worksheet.cell(row=row, column=4, value=worker.document_type)
        worksheet.cell(row=row, column=5, value=worker.document_number)
        worksheet.cell(row=row, column=6, value=worker.email)
        worksheet.cell(row=row, column=7, value=worker.phone)
        worksheet.cell(row=row, column=8, value=worker.birth_date.strftime("%Y-%m-%d") if worker.birth_date else "")
        worksheet.cell(row=row, column=9, value=worker.gender)
        worksheet.cell(row=row, column=10, value=worker.city)
        worksheet.cell(row=row, column=11, value=worker.department)
        worksheet.cell(row=row, column=12, value=worker.country)
        worksheet.cell(row=row, column=13, value=worker.position)
        worksheet.cell(row=row, column=14, value=worker.fecha_de_ingreso.strftime("%Y-%m-%d") if worker.fecha_de_ingreso else "")
        worksheet.cell(row=row, column=15, value=worker.contract_type)
        worksheet.cell(row=row, column=16, value=worker.work_modality)
        worksheet.cell(row=row, column=17, value=worker.profession)
        worksheet.cell(row=row, column=18, value=worker.risk_level)
        worksheet.cell(row=row, column=19, value=worker.occupation)
        worksheet.cell(row=row, column=20, value=float(worker.salary_ibc) if worker.salary_ibc else "")
        worksheet.cell(row=row, column=21, value=worker.eps)
        worksheet.cell(row=row, column=22, value=worker.afp)
        worksheet.cell(row=row, column=23, value=worker.arl)
        worksheet.cell(row=row, column=24, value=worker.blood_type)
        worksheet.cell(row=row, column=25, value=worker.observations)
        worksheet.cell(row=row, column=26, value="Activo" if worker.is_active else "Inactivo")
        worksheet.cell(row=row, column=27, value=worker.assigned_role)
        worksheet.cell(row=row, column=28, value=worker.created_at.strftime("%Y-%m-%d %H:%M:%S") if worker.created_at else "")
    
    # Ajustar ancho de columnas
    for column in worksheet.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 50)
        worksheet.column_dimensions[column_letter].width = adjusted_width
    
    # Guardar en memoria
    excel_buffer = BytesIO()
    workbook.save(excel_buffer)
    excel_buffer.seek(0)
    
    # Generar nombre de archivo con timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"trabajadores_{timestamp}.xlsx"
    
    # Retornar como respuesta de streaming
    return StreamingResponse(
        BytesIO(excel_buffer.read()),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )