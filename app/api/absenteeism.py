from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, extract, text

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Absenteeism, Worker, User
from app.schemas.absenteeism import (
    AbsenteeismCreate,
    AbsenteeismUpdate,
    AbsenteeismResponse,
    AbsenteeismWithWorker,
    AbsenteeismList,
    AbsenteeismStats,
)
from app.models.absenteeism import EventMonth, EventType

router = APIRouter(tags=["absenteeism"])


@router.post("/", response_model=AbsenteeismResponse, status_code=status.HTTP_200_OK)
def create_absenteeism(
    absenteeism_data: AbsenteeismCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Crear un nuevo registro de ausentismo"""
    
    # Verificar que el trabajador existe
    worker = db.query(Worker).filter(Worker.id == absenteeism_data.worker_id).first()
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Trabajador no encontrado"
        )
    
    # Validar que no haya otro registro del mismo tipo con fechas superpuestas
    overlapping_record = db.query(Absenteeism).filter(
        Absenteeism.worker_id == absenteeism_data.worker_id,
        Absenteeism.event_type == absenteeism_data.event_type,
        Absenteeism.start_date <= absenteeism_data.end_date,
        Absenteeism.end_date >= absenteeism_data.start_date
    ).first()

    if overlapping_record:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Existe un registro del mismo tipo con fechas que se superponen"
        )

    # Crear el registro de ausentismo
    db_absenteeism = Absenteeism(**absenteeism_data.model_dump())
    db.add(db_absenteeism)
    db.commit()
    db.refresh(db_absenteeism)

    # Cargar la relación con el trabajador
    db_absenteeism = (
        db.query(Absenteeism)
        .options(joinedload(Absenteeism.worker))
        .filter(Absenteeism.id == db_absenteeism.id)
        .first()
    )

    return db_absenteeism


@router.get("/", response_model=AbsenteeismList)
def get_absenteeism_list(
    skip: int = Query(0, ge=0, description="Número de registros a omitir"),
    limit: int = Query(
        100, ge=1, le=1000, description="Número máximo de registros a devolver"
    ),
    worker_id: Optional[int] = Query(None, description="Filtrar por ID del trabajador"),
    event_type: Optional[EventType] = Query(
        None, description="Filtrar por tipo de evento"
    ),
    event_month: Optional[EventMonth] = Query(
        None, description="Filtrar por mes del evento"
    ),
    start_date_from: Optional[date] = Query(
        None, description="Filtrar por fecha inicial desde"
    ),
    start_date_to: Optional[date] = Query(
        None, description="Filtrar por fecha inicial hasta"
    ),
    search: Optional[str] = Query(
        None, description="Buscar por nombre del trabajador o cédula"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Obtener lista paginada de registros de ausentismo"""

    query = db.query(Absenteeism).options(joinedload(Absenteeism.worker))

    # Aplicar filtros
    if worker_id:
        query = query.filter(Absenteeism.worker_id == worker_id)

    if event_type:
        query = query.filter(Absenteeism.event_type == event_type)

    if event_month:
        query = query.filter(Absenteeism.event_month == event_month)

    if start_date_from:
        query = query.filter(Absenteeism.start_date >= start_date_from)

    if start_date_to:
        query = query.filter(Absenteeism.start_date <= start_date_to)

    if search:
        query = query.join(Worker).filter(
            or_(
                func.concat(Worker.first_name, " ", Worker.last_name).ilike(
                    f"%{search}%"
                ),
                Worker.document_number.ilike(f"%{search}%"),
                Worker.cedula.ilike(f"%{search}%"),
            )
        )

    # Contar total de registros y aplicar paginación con manejo robusto de enums
    try:
        total = query.count()
        items = query.offset(skip).limit(limit).all()
    except Exception as e:
        # Si hay un error de mapeo de enum, usar consulta SQL directa
        from sqlalchemy import text

        # Construir consulta SQL directa
        sql_query = """
        SELECT a.*, w.first_name, w.last_name, w.email, w.phone, 
               w.document_number as cedula,
               w.position as cargo,
               w.salary_ibc as base_salary
        FROM absenteeism a
        LEFT JOIN workers w ON a.worker_id = w.id
        """

        # Agregar filtros si existen
        where_conditions = []
        params = {}

        if event_type:
            where_conditions.append("a.event_type = :event_type")
            params["event_type"] = (
                event_type.value if hasattr(event_type, "value") else str(event_type)
            )

        if event_month:
            where_conditions.append("a.event_month = :event_month")
            params["event_month"] = (
                event_month.value if hasattr(event_month, "value") else str(event_month)
            )

        if start_date_from:
            where_conditions.append("a.start_date >= :start_date_from")
            params["start_date_from"] = start_date_from

        if start_date_to:
            where_conditions.append("a.start_date <= :start_date_to")
            params["start_date_to"] = start_date_to

        if search:
            where_conditions.append(
                "(CONCAT(w.first_name, ' ', w.last_name) ILIKE :search OR w.document_number ILIKE :search)"
            )
            params["search"] = f"%{search}%"

        if where_conditions:
            sql_query += " WHERE " + " AND ".join(where_conditions)

        # Calcular total primero
        count_query = """
        SELECT COUNT(*) as total
        FROM absenteeism a
        LEFT JOIN workers w ON a.worker_id = w.id
        """
        if where_conditions:
            count_query += " WHERE " + " AND ".join(where_conditions)

        count_result = db.execute(text(count_query), params)
        total = count_result.fetchone().total

        sql_query += f" ORDER BY a.id DESC LIMIT {limit} OFFSET {skip}"

        result = db.execute(text(sql_query), params)
        raw_items = result.fetchall()

        # Convertir resultados a objetos AbsenteeismWithWorker
        items_with_worker = []
        for row in raw_items:
            # Mapear manualmente los valores de enum
            event_type_value = str(row.event_type)
            event_month_value = str(row.event_month)

            item_dict = {
                "id": row.id,
                "event_month": event_month_value,
                "worker_id": row.worker_id,
                "event_type": event_type_value,
                "start_date": row.start_date,
                "end_date": row.end_date,
                "disability_days": row.disability_days,
                "extension": row.extension or 0,
                "charged_days": row.charged_days or 0,
                "disability_or_charged_days": row.disability_or_charged_days,
                "diagnostic_code": row.diagnostic_code,
                "health_condition_description": row.health_condition_description,
                "observations": row.observations,
                "insured_costs_at": float(row.insured_costs_at or 0),
                "insured_costs_ac_eg": float(row.insured_costs_ac_eg or 0),
                "assumed_costs_at": float(row.assumed_costs_at or 0),
                "assumed_costs_ac_eg": float(row.assumed_costs_ac_eg or 0),
                "worker_name": (
                    f"{row.first_name or ''} {row.last_name or ''}".strip()
                    if row.first_name or row.last_name
                    else None
                ),
                "worker_email": row.email,
                "worker_phone": row.phone,
                "cedula": row.cedula,
                "cargo": row.cargo,
                "base_salary": float(row.base_salary or 0),
            }
            items_with_worker.append(AbsenteeismWithWorker(**item_dict))

        return AbsenteeismList(
            items=items_with_worker,
            total=total,
            page=skip // limit + 1,
            size=limit,
            pages=(total + limit - 1) // limit,
        )

    # Convertir a esquema con información del trabajador (flujo normal)
    items_with_worker = []
    for item in items:
        item_dict = {
            **item.__dict__,
            "worker_name": item.worker.full_name if item.worker else None,
            "worker_email": item.worker.email if item.worker else None,
            "worker_phone": item.worker.phone if item.worker else None,
            "cedula": (
                item.worker.cedula or item.worker.document_number
                if item.worker
                else None
            ),
            "cargo": item.worker.cargo or item.worker.position if item.worker else None,
            "base_salary": (
                item.worker.salario or item.worker.salary_ibc if item.worker else None
            ),
        }
        items_with_worker.append(AbsenteeismWithWorker(**item_dict))

    return AbsenteeismList(
        items=items_with_worker,
        total=total,
        page=skip // limit + 1,
        size=limit,
        pages=(total + limit - 1) // limit,
    )


@router.get("/{absenteeism_id}", response_model=AbsenteeismWithWorker)
def get_absenteeism(
    absenteeism_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Obtener un registro de ausentismo por ID"""

    try:
        absenteeism = (
            db.query(Absenteeism)
            .options(joinedload(Absenteeism.worker))
            .filter(Absenteeism.id == absenteeism_id)
            .first()
        )

        if not absenteeism:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Registro de ausentismo no encontrado",
            )

        # Agregar información del trabajador
        absenteeism_dict = {
            **absenteeism.__dict__,
            "worker_name": absenteeism.worker.full_name if absenteeism.worker else None,
            "worker_email": absenteeism.worker.email if absenteeism.worker else None,
            "worker_phone": absenteeism.worker.phone if absenteeism.worker else None,
            "cedula": (
                absenteeism.worker.cedula or absenteeism.worker.document_number
                if absenteeism.worker
                else None
            ),
            "cargo": (
                absenteeism.worker.cargo or absenteeism.worker.position
                if absenteeism.worker
                else None
            ),
            "base_salary": (
                absenteeism.worker.salario or absenteeism.worker.salary_ibc
                if absenteeism.worker
                else None
            ),
        }

        return AbsenteeismWithWorker(**absenteeism_dict)

    except HTTPException:
        # Re-lanzar excepciones HTTP
        raise
    except Exception as e:
        # Si hay un error de mapeo de enum, usar consulta SQL directa
        from sqlalchemy import text

        sql_query = """
        SELECT a.*, w.first_name, w.last_name, w.email, w.phone,
               w.document_number as cedula,
               w.position as cargo,
               w.salary_ibc as base_salary
        FROM absenteeism a
        LEFT JOIN workers w ON a.worker_id = w.id
        WHERE a.id = :absenteeism_id
        """

        result = db.execute(text(sql_query), {"absenteeism_id": absenteeism_id})
        row = result.fetchone()

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Registro de ausentismo no encontrado",
            )

        # Convertir manualmente los valores de enum
        event_type_value = row.event_type
        event_month_value = row.event_month

        # Mapear valores de enum manualmente
        event_type_mapped = None
        for et in EventType:
            if et.value == event_type_value:
                event_type_mapped = et
                break

        event_month_mapped = None
        for em in EventMonth:
            if em.value == event_month_value:
                event_month_mapped = em
                break

        absenteeism_dict = {
            "id": row.id,
            "event_month": event_month_mapped or event_month_value,
            "worker_id": row.worker_id,
            "event_type": event_type_mapped or event_type_value,
            "start_date": row.start_date,
            "end_date": row.end_date,
            "disability_days": row.disability_days,
            "extension": row.extension,
            "charged_days": row.charged_days,
            "diagnostic_code": row.diagnostic_code,
            "health_condition_description": row.health_condition_description,
            "observations": row.observations,
            "insured_costs_at": row.insured_costs_at,
            "insured_costs_ac_eg": row.insured_costs_ac_eg,
            "assumed_costs_at": row.assumed_costs_at,
            "assumed_costs_ac_eg": row.assumed_costs_ac_eg,
            "created_at": getattr(row, "created_at", None),
            "updated_at": getattr(row, "updated_at", None),
            "worker_name": (
                f"{row.first_name} {row.last_name}"
                if row.first_name and row.last_name
                else None
            ),
            "worker_email": row.email,
            "worker_phone": row.phone,
            "cedula": row.cedula,
            "cargo": row.cargo,
            "base_salary": row.base_salary,
        }

        return AbsenteeismWithWorker(**absenteeism_dict)


@router.put("/{absenteeism_id}", response_model=AbsenteeismWithWorker)
def update_absenteeism(
    absenteeism_id: int,
    absenteeism_data: AbsenteeismUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Actualizar un registro de ausentismo"""

    try:
        absenteeism = (
            db.query(Absenteeism).filter(Absenteeism.id == absenteeism_id).first()
        )
        if not absenteeism:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Registro de ausentismo no encontrado",
            )

        # Verificar que el trabajador existe si se está actualizando
        if absenteeism_data.worker_id:
            worker = (
                db.query(Worker).filter(Worker.id == absenteeism_data.worker_id).first()
            )
            if not worker:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Trabajador no encontrado",
                )

        # Actualizar campos
        update_data = absenteeism_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(absenteeism, field, value)

        db.commit()
        db.refresh(absenteeism)

        # Cargar la relación con el trabajador
        absenteeism = (
            db.query(Absenteeism)
            .options(joinedload(Absenteeism.worker))
            .filter(Absenteeism.id == absenteeism_id)
            .first()
        )

        # Agregar información del trabajador
        absenteeism_dict = {
            **absenteeism.__dict__,
            "worker_name": absenteeism.worker.full_name if absenteeism.worker else None,
            "worker_email": absenteeism.worker.email if absenteeism.worker else None,
            "worker_phone": absenteeism.worker.phone if absenteeism.worker else None,
            "cedula": (
                absenteeism.worker.cedula or absenteeism.worker.document_number
                if absenteeism.worker
                else None
            ),
            "cargo": (
                absenteeism.worker.cargo or absenteeism.worker.position
                if absenteeism.worker
                else None
            ),
            "base_salary": (
                absenteeism.worker.salario or absenteeism.worker.salary_ibc
                if absenteeism.worker
                else None
            ),
        }

        return AbsenteeismWithWorker(**absenteeism_dict)

    except LookupError as e:
        # Fallback usando consulta SQL directa para manejar problemas de mapeo de enum
        sql_query = text(
            """
            SELECT a.*, CONCAT(w.first_name, ' ', w.last_name) as worker_name, w.email as worker_email, 
                   w.phone as worker_phone, 
                   w.document_number as cedula,
                   w.position as cargo,
                   w.salary_ibc as base_salary
            FROM absenteeism a
            LEFT JOIN workers w ON a.worker_id = w.id
            WHERE a.id = :absenteeism_id
        """
        )

        result = db.execute(sql_query, {"absenteeism_id": absenteeism_id}).fetchone()

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Registro de ausentismo no encontrado",
            )

        # Convertir el resultado a diccionario y manejar enums manualmente
        absenteeism_dict = dict(result._mapping)

        # Convertir event_type y event_month a sus valores de enum correspondientes
        if absenteeism_dict.get("event_type"):
            absenteeism_dict["event_type"] = absenteeism_dict["event_type"]
        if absenteeism_dict.get("event_month"):
            absenteeism_dict["event_month"] = absenteeism_dict["event_month"]

        return AbsenteeismWithWorker(**absenteeism_dict)


@router.delete("/{absenteeism_id}", status_code=status.HTTP_200_OK)
def delete_absenteeism(
    absenteeism_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Eliminar un registro de ausentismo"""

    try:
        absenteeism = (
            db.query(Absenteeism).filter(Absenteeism.id == absenteeism_id).first()
        )
        if not absenteeism:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Registro de ausentismo no encontrado",
            )

        db.delete(absenteeism)
        db.commit()

    except LookupError as e:
        # Fallback usando consulta SQL directa para manejar problemas de mapeo de enum
        sql_query = text("SELECT id FROM absenteeism WHERE id = :absenteeism_id")
        result = db.execute(sql_query, {"absenteeism_id": absenteeism_id}).fetchone()

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Registro de ausentismo no encontrado",
            )

        # Eliminar usando SQL directo
        delete_query = text("DELETE FROM absenteeism WHERE id = :absenteeism_id")
        db.execute(delete_query, {"absenteeism_id": absenteeism_id})
        db.commit()


@router.get("/stats/summary", response_model=AbsenteeismStats)
def get_absenteeism_stats(
    year: Optional[int] = Query(None, description="Filtrar por año"),
    worker_id: Optional[int] = Query(None, description="Filtrar por trabajador"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Obtener estadísticas de ausentismo"""

    try:
        # Crear filtros base
        base_filters = []
        params = {}

        if year:
            base_filters.append("EXTRACT(year FROM start_date) = :year")
            params["year"] = year

        if worker_id:
            base_filters.append("worker_id = :worker_id")
            params["worker_id"] = worker_id

        where_clause = " WHERE " + " AND ".join(base_filters) if base_filters else ""

        # Estadísticas básicas con SQL directo para evitar problemas de transacción
        stats_query = f"""
        SELECT 
            COUNT(*) as total_records,
            COALESCE(SUM(disability_days), 0) as total_disability_days,
            COALESCE(SUM(insured_costs_at + assumed_costs_at), 0) as total_costs_at,
            COALESCE(SUM(insured_costs_ac_eg + assumed_costs_ac_eg), 0) as total_costs_ac_eg
        FROM absenteeism{where_clause}
        """

        result = db.execute(text(stats_query), params)
        stats_row = result.fetchone()

        # Estadísticas por tipo de evento
        by_event_type = {}
        for event_type in EventType:
            event_query = f"""
            SELECT COUNT(*) as count
            FROM absenteeism
            WHERE event_type = :event_type{' AND ' + ' AND '.join(base_filters) if base_filters else ''}
            """
            event_params = {**params, "event_type": event_type.value}
            event_result = db.execute(text(event_query), event_params)
            by_event_type[event_type.value] = event_result.fetchone().count

        # Estadísticas por mes
        by_month = {}
        for month in EventMonth:
            month_query = f"""
            SELECT COUNT(*) as count
            FROM absenteeism
            WHERE event_month = :event_month{' AND ' + ' AND '.join(base_filters) if base_filters else ''}
            """
            month_params = {**params, "event_month": month.value}
            month_result = db.execute(text(month_query), month_params)
            by_month[month.value] = month_result.fetchone().count

        return AbsenteeismStats(
            total_records=stats_row.total_records,
            total_disability_days=stats_row.total_disability_days,
            total_costs_at=stats_row.total_costs_at,
            total_costs_ac_eg=stats_row.total_costs_ac_eg,
            by_event_type=by_event_type,
            by_month=by_month,
        )

    except Exception as e:
        # Log del error para debugging
        print(f"Error en estadísticas de ausentismo: {str(e)}")

        # Retornar estadísticas vacías en caso de error
        return AbsenteeismStats(
            total_records=0,
            total_disability_days=0,
            total_costs_at=0,
            total_costs_ac_eg=0,
            by_event_type={},
            by_month={},
        )


@router.get("/workers/search", response_model=List[dict])
def search_workers(
    q: str = Query(..., min_length=2, description="Término de búsqueda"),
    limit: int = Query(10, ge=1, le=50, description="Número máximo de resultados"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Buscar trabajadores para selección en formularios"""

    workers = (
        db.query(Worker)
        .filter(
            and_(
                Worker.is_active == True,
                or_(
                    func.concat(Worker.first_name, " ", Worker.last_name).ilike(
                        f"%{q}%"
                    ),
                    Worker.document_number.ilike(f"%{q}%"),
                    Worker.cedula.ilike(f"%{q}%"),
                    Worker.email.ilike(f"%{q}%"),
                ),
            )
        )
        .limit(limit)
        .all()
    )

    return [
        {
            "id": worker.id,
            "name": worker.full_name,
            "cedula": worker.cedula or worker.document_number,
            "cargo": worker.cargo or worker.position,
            "email": worker.email,
            "salario": float(worker.salario or worker.salary_ibc or 0),
        }
        for worker in workers
    ]

