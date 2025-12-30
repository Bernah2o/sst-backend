from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload, contains_eager
from sqlalchemy import desc, and_, or_

from app.dependencies import get_current_active_user, require_supervisor_or_admin
from app.database import get_db
from app.models.user import User
from app.models.audit import AuditLog, AuditAction
from app.schemas.audit import AuditLogResponse, AuditLogListResponse
from app.schemas.common import MessageResponse

router = APIRouter()


def format_audit_log(log: AuditLog) -> AuditLogResponse:
    """Helper to format audit log with user info"""
    log_dict = {
        "id": log.id,
        "user_id": log.user_id,
        "action": log.action,
        "resource_type": log.resource_type,
        "resource_id": log.resource_id,
        "resource_name": log.resource_name,
        "old_values": log.old_values,
        "new_values": log.new_values,
        "ip_address": log.ip_address,
        "user_agent": log.user_agent,
        "session_id": log.session_id,
        "request_id": log.request_id,
        "details": log.details,
        "success": log.success,
        "error_message": log.error_message,
        "duration_ms": log.duration_ms,
        "created_at": log.created_at,
        "user_name": None,
        "user_email": None
    }
    
    # Add user information if available
    if log.user:
        log_dict["user_name"] = f"{log.user.first_name} {log.user.last_name}".strip()
        log_dict["user_email"] = log.user.email
    
    return AuditLogResponse(**log_dict)


@router.get("/", response_model=AuditLogListResponse)
async def get_audit_logs(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    action: Optional[AuditAction] = Query(None, description="Filter by action type"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    search: Optional[str] = Query(None, description="Search in resource name, details, IP or user info"),
    current_user: User = Depends(require_supervisor_or_admin),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get audit logs with pagination and filtering.
    Only accessible by supervisors and admins.
    """
    # Build query with user information
    # Use outerjoin + contains_eager to allow filtering by user fields while keeping logs without users
    query = db.query(AuditLog).outerjoin(AuditLog.user).options(
        contains_eager(AuditLog.user)
    )
    
    # Apply filters
    if action:
        query = query.filter(AuditLog.action == action)
    
    if resource_type:
        query = query.filter(AuditLog.resource_type == resource_type)
    
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    
    if start_date:
        from datetime import datetime
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(AuditLog.created_at >= start_dt)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Formato de fecha de inicio inválido. Use YYYY-MM-DD"
            )
    
    if end_date:
        from datetime import datetime, timedelta
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            query = query.filter(AuditLog.created_at < end_dt)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Formato de fecha de fin inválido. Use YYYY-MM-DD"
            )
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                AuditLog.resource_name.ilike(search_term),
                AuditLog.details.ilike(search_term),
                AuditLog.resource_type.ilike(search_term),
                AuditLog.ip_address.ilike(search_term),
                User.first_name.ilike(search_term),
                User.last_name.ilike(search_term),
                User.email.ilike(search_term)
            )
        )
    
    # Order by created_at descending (newest first)
    query = query.order_by(desc(AuditLog.created_at))
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    offset = (page - 1) * limit
    audit_logs = query.offset(offset).limit(limit).all()
    
    # Calculate total pages
    total_pages = (total + limit - 1) // limit
    
    # Format response with user information
    items = [format_audit_log(log) for log in audit_logs]
    
    return AuditLogListResponse(
        items=items,
        total=total,
        page=page,
        limit=limit,
        total_pages=total_pages
    )


@router.get("/{audit_id}", response_model=AuditLogResponse)
async def get_audit_log(
    audit_id: int,
    current_user: User = Depends(require_supervisor_or_admin),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get a specific audit log by ID.
    Only accessible by supervisors and admins.
    """
    audit_log = db.query(AuditLog).options(
        joinedload(AuditLog.user)
    ).filter(AuditLog.id == audit_id).first()
    
    if not audit_log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Registro de auditoría no encontrado"
        )
    
    return format_audit_log(audit_log)


@router.get("/actions/list")
async def get_audit_actions(
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """
    Get list of available audit actions for filtering.
    Only accessible by supervisors and admins.
    """
    actions = [action.value for action in AuditAction]
    return {"actions": actions}


@router.get("/resources/list")
async def get_audit_resource_types(
    current_user: User = Depends(require_supervisor_or_admin),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get list of available resource types for filtering.
    Only accessible by supervisors and admins.
    """
    # Get distinct resource types from audit logs
    resource_types = db.query(AuditLog.resource_type).distinct().all()
    resource_types = [rt[0] for rt in resource_types if rt[0]]
    
    return {"resource_types": sorted(resource_types)}
