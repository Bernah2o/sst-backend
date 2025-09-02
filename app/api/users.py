import os
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.dependencies import get_current_active_user
from app.models.user import User
from app.schemas.user import UserResponse, UserRegister, UserUpdate, UserProfile, PasswordChange, UserCreate, UserCreateByAdmin
from app.schemas.common import MessageResponse, PaginatedResponse
from app.services.auth import AuthService
from app.config import settings

security = HTTPBearer()

router = APIRouter()


@router.get("/me{trailing_slash:path}", response_model=UserResponse)
async def get_current_user_profile(
    trailing_slash: str = "",
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    Get current user profile
    """
    return current_user


@router.put("/profile", response_model=UserResponse)
async def update_current_user_profile(
    profile_update: UserProfile,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Update current user profile
    """
    # Update user fields
    update_data = profile_update.dict(exclude_unset=True)
    
    # Handle profile picture deletion
    if "profile_picture" in update_data and update_data["profile_picture"] is None:
        # Delete old profile picture file if exists
        if current_user.profile_picture:
            try:
                from app.utils.storage import storage_manager
                import asyncio
                asyncio.create_task(storage_manager.delete_file(current_user.profile_picture))
            except Exception as e:
                # Log error but don't fail the request
                print(f"Error deleting profile picture file: {e}")
    
    for field, value in update_data.items():
        setattr(current_user, field, value)
    
    db.commit()
    db.refresh(current_user)
    
    return current_user


@router.put("/change-password", response_model=MessageResponse)
async def change_password(
    password_change: PasswordChange,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Change current user password
    """
    auth_service = AuthService()
    
    # Verify current password
    if not auth_service.verify_password(password_change.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Update password
    current_user.hashed_password = auth_service.get_password_hash(password_change.new_password)
    db.commit()
    
    return MessageResponse(message="Password changed successfully")


@router.get("/", response_model=PaginatedResponse[UserResponse])
async def get_users(
    skip: int = 0,
    limit: int = 100,
    search: str = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get all users (admin only)
    """
    if current_user.role.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    query = db.query(User).options(joinedload(User.custom_role))
    
    # Apply search filter if provided
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            or_(
                User.first_name.ilike(search_filter),
                User.last_name.ilike(search_filter),
                User.email.ilike(search_filter),
                User.document_number.ilike(search_filter)
            )
        )
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    users = query.offset(skip).limit(limit).all()
    
    # Calculate pagination info
    page = (skip // limit) + 1 if limit > 0 else 1
    pages = (total + limit - 1) // limit if limit > 0 else 1
    has_next = skip + limit < total
    has_prev = skip > 0
    
    return PaginatedResponse(
        items=users,
        total=total,
        page=page,
        size=limit,
        pages=pages,
        has_next=has_next,
        has_prev=has_prev
    )


@router.post("/", response_model=UserResponse)
async def create_user(
    user_data: UserCreateByAdmin,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Create a new user (admin only)
    """
    if current_user.role.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # Check if worker exists and is already registered
    from app.models.worker import Worker
    worker = db.query(Worker).filter(
        Worker.email == user_data.email,
        Worker.document_number == user_data.document_number,
        Worker.is_active == True
    ).first()
    
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se encontró un trabajador activo con este correo y número de documento"
        )
    
    if worker.is_registered:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este trabajador ya tiene una cuenta de usuario registrada"
        )
    
    # Check if user already exists by email (additional safety check)
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un usuario con este correo electrónico"
        )
    
    # Create new user
    from app.services.auth import auth_service
    
    # Hash password only if provided
    if user_data.password:
        hashed_password = auth_service.get_password_hash(user_data.password)
        is_verified = True
    else:
        # Set a temporary password that will be changed during registration
        hashed_password = auth_service.get_password_hash('temp_password_123!')
        is_verified = False
    
    user = User(
        email=user_data.email,
        hashed_password=hashed_password,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        document_type=user_data.document_type,
        document_number=user_data.document_number,
        phone=user_data.phone,
        department=user_data.department,
        position=user_data.position,
        role=user_data.role,
        emergency_contact_name=user_data.emergency_contact_name,
        emergency_contact_phone=user_data.emergency_contact_phone,
        notes=user_data.notes,
        hire_date=user_data.hire_date,
        is_active=True,
        is_verified=is_verified
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Mark worker as registered and link to user
    worker.is_registered = True
    worker.user_id = user.id
    db.commit()
    
    return user


@router.get("/list{trailing_slash:path}", response_model=List[UserResponse])
async def get_users_list(
    trailing_slash: str = "",
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get basic list of users for selection (authenticated users only)
    """
    users = db.query(User).options(joinedload(User.custom_role)).filter(
        User.is_active == True
    ).all()
    
    return users


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get user by ID
    """
    if current_user.role.value != "admin" and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    user = db.query(User).options(joinedload(User.custom_role)).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user


@router.delete("/{user_id}", response_model=MessageResponse)
async def delete_user(
    user_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> Any:
    """
    Delete user (admin only)
    """
    from sqlalchemy import text
    from jose import jwt, JWTError
    from app.config import settings
    
    try:
        # Decode token directly without using auth service to avoid User object loading
        token = credentials.credentials
        try:
            payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
            current_user_id_str = payload.get("sub")
            current_user_role = payload.get("role")
            
            if not current_user_id_str or not current_user_role:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token"
                )
            
            current_user_id = int(current_user_id_str)
            
        except (JWTError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials"
            )
        
        # Check if current user is admin
        if current_user_role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
        
        # Check if target user exists using raw SQL
        result = db.execute(text("SELECT id FROM users WHERE id = :user_id"), {"user_id": user_id})
        user_exists = result.fetchone()
        
        if not user_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Prevent deleting the current admin user
        if user_id == current_user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete your own account"
            )
        print(f"Starting deletion process for user_id: {user_id}")
        
        # Delete related records first using raw SQL to avoid ORM relationship issues
        print(f"Deleting related records for user {user_id}")
        
        # Delete user_answers (they depend on user_evaluations)
        result = db.execute(text("""
            DELETE FROM user_answers 
            WHERE user_evaluation_id IN (
                SELECT id FROM user_evaluations WHERE user_id = :user_id
            )
        """), {"user_id": user_id})
        print(f"Deleted {result.rowcount} user answers")
        
        # Delete user_evaluations
        result = db.execute(text("DELETE FROM user_evaluations WHERE user_id = :user_id"), {"user_id": user_id})
        print(f"Deleted {result.rowcount} user evaluations")
        
        # Delete user_survey_answers (they depend on user_surveys)
        result = db.execute(text("""
            DELETE FROM user_survey_answers 
            WHERE user_survey_id IN (
                SELECT id FROM user_surveys WHERE user_id = :user_id
            )
        """), {"user_id": user_id})
        print(f"Deleted {result.rowcount} user survey answers")
        
        # Delete user_surveys
        result = db.execute(text("DELETE FROM user_surveys WHERE user_id = :user_id"), {"user_id": user_id})
        print(f"Deleted {result.rowcount} user surveys")
        
        # Delete user_material_progress (depends on enrollments)
        result = db.execute(text("""
            DELETE FROM user_material_progress 
            WHERE enrollment_id IN (
                SELECT id FROM enrollments WHERE user_id = :user_id
            )
        """), {"user_id": user_id})
        print(f"Deleted {result.rowcount} user material progress records")
        
        # Delete user_module_progress (depends on enrollments)
        result = db.execute(text("""
            DELETE FROM user_module_progress 
            WHERE enrollment_id IN (
                SELECT id FROM enrollments WHERE user_id = :user_id
            )
        """), {"user_id": user_id})
        print(f"Deleted {result.rowcount} user module progress records")
        
        # Delete enrollments
        result = db.execute(text("DELETE FROM enrollments WHERE user_id = :user_id"), {"user_id": user_id})
        print(f"Deleted {result.rowcount} enrollments")
        
        # Delete certificates
        result = db.execute(text("DELETE FROM certificates WHERE user_id = :user_id"), {"user_id": user_id})
        print(f"Deleted {result.rowcount} certificates")
        
        # Delete attendances
        result = db.execute(text("DELETE FROM attendances WHERE user_id = :user_id"), {"user_id": user_id})
        print(f"Deleted {result.rowcount} attendances")
        
        # Delete notifications
        result = db.execute(text("DELETE FROM notifications WHERE user_id = :user_id"), {"user_id": user_id})
        print(f"Deleted {result.rowcount} notifications")
        
        # Delete audit_logs
        result = db.execute(text("DELETE FROM audit_logs WHERE user_id = :user_id"), {"user_id": user_id})
        print(f"Deleted {result.rowcount} audit logs")
        
        # Finally delete the user using raw SQL to avoid ORM relationship issues
        print(f"Deleting user {user_id}")
        result = db.execute(text("DELETE FROM users WHERE id = :user_id"), {"user_id": user_id})
        print(f"Deleted {result.rowcount} users")
        
        db.commit()
        print("User deletion completed successfully")
        
        return MessageResponse(message="User deleted successfully")
        
    except Exception as e:
        print(f"Error during user deletion: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        error_traceback = traceback.format_exc()
        print(f"Traceback: {error_traceback}")
        db.rollback()
        
        # Return detailed error information for debugging
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_message": str(e),
                "error_type": type(e).__name__,
                "operation": "delete_user"
            }
        )


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Update user (admin only)
    """
    if current_user.role.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update user fields
    update_data = user_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)
    
    db.commit()
    db.refresh(user)
    
    return user