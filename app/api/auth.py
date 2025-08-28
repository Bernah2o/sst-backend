from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_current_active_user
from app.models.user import User
from app.models.worker import Worker
from app.schemas.user import (
    Token,
    UserLogin,
    UserRegister,
    PasswordReset,
    PasswordResetConfirm,
    PasswordChange,
)
from app.schemas.common import MessageResponse
from app.services.auth import auth_service
from app.services.email_service import EmailService
from app.api.auth_worker_update import update_worker_after_registration

router = APIRouter()


@router.get("/login")
async def login_info():
    """
    GET endpoint for login information.
    The actual login should be done via POST to this same endpoint.
    """
    return {
        "message": "Para iniciar sesión, envía una petición POST a este endpoint con email y password",
        "method": "POST",
        "endpoint": "/api/v1/auth/login",
        "required_fields": {
            "email": "string",
            "password": "string"
        },
        "example": {
            "email": "usuario@ejemplo.com",
            "password": "tu_contraseña"
        }
    }


@router.post("/login")
async def login(
    user_credentials: UserLogin,
    db: Session = Depends(get_db)
) -> Any:
    """
    User login with email and password, get an access token for future requests
    """
    user = auth_service.authenticate_user(db, user_credentials.email, user_credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    tokens = auth_service.create_user_tokens(user)
    
    # Add user information to the response
    response = {
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "token_type": tokens["token_type"],
        "expires_in": tokens["expires_in"],
        "user": {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role.value,
            "full_name": user.full_name,
            "is_active": user.is_active,
            "is_verified": user.is_verified,
            "custom_role_id": user.custom_role_id
        }
    }
    
    return response


@router.post("/register", response_model=MessageResponse)
async def register(
    user_data: UserRegister,
    db: Session = Depends(get_db)
) -> Any:
    """
    Register a new user (simplified version)
    """
    # First, validate that the worker exists and is authorized to register
    worker = db.query(Worker).filter(
        Worker.document_number == user_data.document_number,
        Worker.email == user_data.email,
        Worker.is_active == True
    ).first()
    
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró un trabajador activo con ese número de documento y correo electrónico. Solo los empleados registrados por el administrador pueden crear una cuenta."
        )
    
    # Check if worker is already registered and has a verified account
    if worker.is_registered and worker.user_id:
        # Check if the existing user is already verified
        existing_linked_user = db.query(User).filter(User.id == worker.user_id).first()
        if existing_linked_user and existing_linked_user.is_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Este empleado ya tiene una cuenta registrada en el sistema. Puede iniciar sesión directamente."
            )
    
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    
    if existing_user:
        # If user exists but is not verified (created by admin without password)
        if not existing_user.is_verified:
            # Update the existing user with registration data and password
            hashed_password = auth_service.get_password_hash(user_data.password)
            existing_user.hashed_password = hashed_password
            existing_user.first_name = user_data.first_name
            existing_user.last_name = user_data.last_name
            existing_user.document_type = user_data.document_type
            existing_user.document_number = user_data.document_number
            existing_user.phone = user_data.phone
            existing_user.department = user_data.department
            existing_user.position = user_data.position
            existing_user.is_verified = True
            user = existing_user
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe un usuario con este correo electrónico"
            )
    else:
        # Create new user
        hashed_password = auth_service.get_password_hash(user_data.password)
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
            is_active=True,
            is_verified=True  # Auto-verify for now
        )
        db.add(user)
    
    db.commit()
    db.refresh(user)
    
    # Update worker record to mark as registered and link to this user
    # This validates that the user is an authorized employee
    try:
        update_worker_after_registration(db, user)
        db.commit()
    except HTTPException as e:
        # If worker validation fails, rollback user creation and re-raise the error
        db.rollback()
        raise e
    except Exception as e:
        # For unexpected errors, rollback and provide a generic error message
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor durante el registro"
        )
    
    return MessageResponse(message="User registered successfully")


# Endpoint worker-register eliminado


@router.post("/refresh", response_model=Token)
async def refresh_token(
    refresh_token: str,
    db: Session = Depends(get_db)
) -> Any:
    """
    Refresh access token using refresh token
    """
    try:
        token_data = auth_service.verify_token(refresh_token, "refresh")
        user = db.query(User).filter(User.id == token_data.user_id).first()
        
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
        
        tokens = auth_service.create_user_tokens(user)
        return tokens
        
    except HTTPException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Logout user (client should discard tokens)
    """
    # In a more sophisticated implementation, you might want to:
    # 1. Blacklist the token
    # 2. Store logout event in audit log
    # 3. Clear any server-side sessions
    
    return MessageResponse(message="Successfully logged out")


@router.post("/forgot-password", response_model=MessageResponse)
async def request_password_reset(
    password_reset: PasswordReset,
    db: Session = Depends(get_db)
) -> Any:
    """
    Request password reset email
    """
    # Find user by email
    user = db.query(User).filter(User.email == password_reset.email).first()
    
    if not user:
        # Don't reveal if email exists or not for security
        return MessageResponse(
            message="Si el correo existe en nuestro sistema, recibirás un enlace de recuperación"
        )
    
    # Generate reset token
    reset_token = auth_service.generate_password_reset_token()
    user.password_reset_token = reset_token
    user.password_reset_expires = datetime.utcnow() + timedelta(hours=1)  # Token expires in 1 hour
    
    db.commit()
    
    # Send password reset email
    try:
        EmailService.send_password_reset_email(
            to_email=user.email,
            reset_token=reset_token,
            user_name=user.full_name
        )
    except Exception as e:
        # Log error but don't reveal to user for security
        print(f"Error sending password reset email: {e}")
    
    return MessageResponse(
        message="Si el correo existe en nuestro sistema, recibirás un enlace de recuperación"
    )


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    password_reset_confirm: PasswordResetConfirm,
    db: Session = Depends(get_db)
) -> Any:
    """
    Reset password using token
    """
    # Find user by reset token
    user = db.query(User).filter(
        User.password_reset_token == password_reset_confirm.token
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token de recuperación inválido"
        )
    
    # Check if token has expired
    if not user.password_reset_expires or user.password_reset_expires < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token de recuperación expirado"
        )
    
    # Update password
    user.hashed_password = auth_service.get_password_hash(password_reset_confirm.new_password)
    user.password_reset_token = None
    user.password_reset_expires = None
    
    db.commit()
    
    return MessageResponse(
        message="Contraseña actualizada exitosamente"
    )


@router.put("/change-password", response_model=MessageResponse)
async def change_password(
    password_change: PasswordChange,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Change password for authenticated user
    """
    # Verify current password
    if not auth_service.verify_password(password_change.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Contraseña actual incorrecta"
        )
    
    # Update password
    current_user.hashed_password = auth_service.get_password_hash(password_change.new_password)
    
    db.commit()
    
    return MessageResponse(
        message="Contraseña cambiada exitosamente"
    )


@router.get("/validate-token", response_model=MessageResponse)
async def validate_token(
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Validate if current token is valid
    """
    return MessageResponse(message="Token is valid")


# Additional endpoints can be added here as needed