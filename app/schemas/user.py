from datetime import datetime
from typing import Optional
import re

from pydantic import BaseModel, EmailStr, validator

from app.models.user import UserRole
from app.schemas.custom_role import CustomRoleResponse


class UserBase(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str
    document_type: str
    document_number: str
    phone: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    role: UserRole = UserRole.EMPLOYEE
    custom_role_id: Optional[int] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    notes: Optional[str] = None


class UserCreate(UserBase):
    password: str
    hire_date: Optional[datetime] = None
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('La contraseña debe tener al menos 8 caracteres')
        
        # Check for at least one letter
        if not re.search(r'[a-zA-Z]', v):
            raise ValueError('La contraseña debe contener al menos una letra')
        
        # Check for at least one number
        if not re.search(r'\d', v):
            raise ValueError('La contraseña debe contener al menos un número')
        
        # Check for at least one special character
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError('La contraseña debe contener al menos un carácter especial (!@#$%^&*(),.?":{}|<>)')
        
        return v
    
    @validator('document_number')
    def validate_document_number(cls, v):
        if not v.isdigit():
            raise ValueError('El número de documento debe contener solo números')
        return v


class UserCreateByAdmin(UserBase):
    password: Optional[str] = None
    hire_date: Optional[datetime] = None
    
    @validator('password', pre=True, always=True)
    def validate_password(cls, v):
        if v is None:
            return v
        if len(v) < 8:
            raise ValueError('La contraseña debe tener al menos 8 caracteres')
        
        # Check for at least one letter
        if not re.search(r'[a-zA-Z]', v):
            raise ValueError('La contraseña debe contener al menos una letra')
        
        # Check for at least one number
        if not re.search(r'\d', v):
            raise ValueError('La contraseña debe contener al menos un número')
        
        # Check for at least one special character
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError('La contraseña debe contener al menos un carácter especial (!@#$%^&*(),.?":{}|<>)')
        
        return v
    
    @validator('document_number')
    def validate_document_number(cls, v):
        if not v.isdigit():
            raise ValueError('Document number must contain only digits')
        return v


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    document_type: Optional[str] = None
    document_number: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    role: Optional[UserRole] = None
    custom_role_id: Optional[int] = None
    is_active: Optional[bool] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    notes: Optional[str] = None
    hire_date: Optional[datetime] = None


class UserResponse(UserBase):
    id: int
    is_active: bool
    is_verified: bool
    profile_picture: Optional[str] = None
    hire_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None
    full_name: str
    custom_role: Optional[CustomRoleResponse] = None
    
    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserRegister(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str
    document_type: str
    document_number: str
    phone: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('La contraseña debe tener al menos 8 caracteres')
        
        # Check for at least one letter
        if not re.search(r'[a-zA-Z]', v):
            raise ValueError('La contraseña debe contener al menos una letra')
        
        # Check for at least one number
        if not re.search(r'\d', v):
            raise ValueError('La contraseña debe contener al menos un número')
        
        # Check for at least one special character
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError('La contraseña debe contener al menos un carácter especial (!@#$%^&*(),.?":{}|<>)')
        
        return v
    
    @validator('document_number')
    def validate_document_number(cls, v):
        if not v.isdigit():
            raise ValueError('El número de documento debe contener solo dígitos')
        return v


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenData(BaseModel):
    user_id: Optional[int] = None
    email: Optional[str] = None
    role: Optional[UserRole] = None


class PasswordReset(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str
    
    @validator('new_password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('La contraseña debe tener al menos 8 caracteres')
        
        # Check for at least one letter
        if not re.search(r'[a-zA-Z]', v):
            raise ValueError('La contraseña debe contener al menos una letra')
        
        # Check for at least one number
        if not re.search(r'\d', v):
            raise ValueError('La contraseña debe contener al menos un número')
        
        # Check for at least one special character
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError('La contraseña debe contener al menos un carácter especial (!@#$%^&*(),.?":{}|<>)')
        
        return v


class PasswordChange(BaseModel):
    current_password: str
    new_password: str
    
    @validator('new_password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('La contraseña debe tener al menos 8 caracteres')
        
        # Check for at least one letter
        if not re.search(r'[a-zA-Z]', v):
            raise ValueError('La contraseña debe contener al menos una letra')
        
        # Check for at least one number
        if not re.search(r'\d', v):
            raise ValueError('La contraseña debe contener al menos un número')
        
        # Check for at least one special character
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError('La contraseña debe contener al menos un carácter especial (!@#$%^&*(),.?":{}|<>)')
        
        return v


class EmailVerification(BaseModel):
    token: str


class UserProfile(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    profile_picture: Optional[str] = None


class UserStats(BaseModel):
    total_courses_completed: int
    total_evaluations_passed: int
    total_certificates_earned: int
    average_score: float
    last_activity: Optional[datetime] = None
    
    class Config:
        from_attributes = True
