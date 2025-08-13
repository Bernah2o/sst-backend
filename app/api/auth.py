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
    UserRegister,
    PasswordReset,
)
from app.schemas.common import MessageResponse
from app.services.auth import auth_service
from app.api.auth_worker_update import update_worker_after_registration

router = APIRouter()


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests
    """
    user = auth_service.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    tokens = auth_service.create_user_tokens(user)
    return tokens


@router.post("/register", response_model=MessageResponse)
async def register(
    user_data: UserRegister,
    db: Session = Depends(get_db)
) -> Any:
    """
    Register a new user (simplified version)
    """
    # Check if user already exists
    existing_user = db.query(User).filter(
        (User.email == user_data.email) | 
        (User.username == user_data.username)
    ).first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already exists"
        )
    
    # Create new user
    hashed_password = auth_service.get_password_hash(user_data.password)
    user = User(
        username=user_data.username,
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


@router.post("/password-reset", response_model=MessageResponse)
async def request_password_reset(
    password_reset: PasswordReset,
    db: Session = Depends(get_db)
) -> Any:
    """
    Request password reset email (simplified - not implemented)
    """
    return MessageResponse(
        message="Password reset feature not implemented yet"
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