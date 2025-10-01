import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.models.user import User
from app.schemas.user import TokenData


class AuthService:
    def __init__(self):
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        self.secret_key = settings.secret_key
        self.algorithm = settings.algorithm
        self.access_token_expire_minutes = settings.access_token_expire_minutes
        self.refresh_token_expire_days = settings.refresh_token_expire_days

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return self.pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password: str) -> str:
        """Hash a password"""
        return self.pwd_context.hash(password)

    def authenticate_user(self, db: Session, email: str, password: str) -> Optional[User]:
        """Authenticate a user by email and password with failed login attempt tracking"""
        # Find user by email only
        user = db.query(User).filter(User.email == email).first()
        
        if not user:
            return None
        
        # Check if account is locked
        if user.is_account_locked():
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Su cuenta ha sido bloqueada por múltiples intentos de inicio de sesión fallidos. Para desbloquear su cuenta, debe restablecer su contraseña utilizando el enlace 'Olvidé mi contraseña'."
            )
        
        if not self.verify_password(password, user.hashed_password):
            # Increment failed login attempts
            user.increment_failed_login_attempts()
            db.commit()
            
            # Check if account is now locked after this attempt
            if user.is_account_locked():
                raise HTTPException(
                    status_code=status.HTTP_423_LOCKED,
                    detail="Su cuenta ha sido bloqueada por múltiples intentos de inicio de sesión fallidos. Para desbloquear su cuenta, debe restablecer su contraseña utilizando el enlace 'Olvidé mi contraseña'."
                )
            
            return None
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inactive user"
            )
        
        # Reset failed login attempts on successful login
        user.reset_failed_login_attempts()
        
        # Update last login
        user.last_login = datetime.utcnow()
        db.commit()
        
        return user

    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create a JWT access token"""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        
        to_encode.update({"exp": expire, "type": "access"})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt

    def create_refresh_token(self, data: dict) -> str:
        """Create a JWT refresh token"""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)
        to_encode.update({"exp": expire, "type": "refresh"})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt

    def verify_token(self, token: str, token_type: str = "access") -> TokenData:
        """Verify and decode a JWT token"""
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            user_id_str: str = payload.get("sub")
            email: str = payload.get("email")
            role: str = payload.get("role")
            token_type_payload: str = payload.get("type")
            
            if user_id_str is None or token_type_payload != token_type:
                raise credentials_exception
            
            # Convert string user_id back to int
            try:
                user_id = int(user_id_str)
            except (ValueError, TypeError):
                raise credentials_exception
            
            token_data = TokenData(
                user_id=user_id,
                email=email,
                role=role
            )
            return token_data
        except JWTError:
            raise credentials_exception

    def get_current_user(self, db: Session, token: str) -> User:
        """Get current user from JWT token"""
        from sqlalchemy.orm import joinedload
        token_data = self.verify_token(token)
        user = db.query(User).options(joinedload(User.custom_role)).filter(User.id == token_data.user_id).first()
        
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inactive user"
            )
        
        return user

    def refresh_access_token(self, refresh_token: str) -> str:
        """Create new access token from refresh token"""
        token_data = self.verify_token(refresh_token, "refresh")
        
        new_token_data = {
            "sub": str(token_data.user_id),  # JWT standard requires sub to be a string
            "email": token_data.email,
            "role": token_data.role
        }
        
        return self.create_access_token(new_token_data)

    def generate_password_reset_token(self) -> str:
        """Generate a secure password reset token"""
        return secrets.token_urlsafe(32)

    def generate_email_verification_token(self) -> str:
        """Generate a secure email verification token"""
        return secrets.token_urlsafe(32)

    def create_user_tokens(self, user: User) -> dict:
        """Create both access and refresh tokens for a user"""
        token_data = {
            "sub": str(user.id),  # JWT standard requires sub to be a string
            "email": user.email,
            "role": user.role.value
        }
        
        access_token = self.create_access_token(token_data)
        refresh_token = self.create_refresh_token(token_data)
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": self.access_token_expire_minutes * 60
        }

    def validate_password_strength(self, password: str) -> bool:
        """Validate password strength"""
        if len(password) < 8:
            return False
        
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password)
        
        return has_upper and has_lower and has_digit and has_special


# Global instance
auth_service = AuthService()