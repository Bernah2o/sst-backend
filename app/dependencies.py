from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.services.auth import auth_service


security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Get current authenticated user"""
    token = credentials.credentials
    return auth_service.get_current_user(db, token)


def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Get current active user"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user


def get_current_verified_user(current_user: User = Depends(get_current_active_user)) -> User:
    """Get current verified user"""
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email not verified"
        )
    return current_user


def _user_has_custom_role(user: User) -> bool:
    """Check if user has an active custom role assigned"""
    return bool(user.custom_role_id)


def has_role_or_custom(user: User, allowed_roles: list) -> bool:
    """Check if user has one of the allowed roles OR has a custom role assigned.
    Use this in internal endpoint checks instead of: user.role.value not in [...]
    """
    return user.role.value in allowed_roles or _user_has_custom_role(user)


def require_role(required_role: UserRole):
    """Dependency factory to require specific user role"""
    def role_checker(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.role != required_role and not _user_has_custom_role(current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        return current_user
    return role_checker


def require_roles(*required_roles: UserRole):
    """Dependency factory to require any of the specified roles"""
    def role_checker(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.role not in required_roles and not _user_has_custom_role(current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        return current_user
    return role_checker


def require_admin(current_user: User = Depends(get_current_active_user)) -> User:
    """Require admin role"""
    if not current_user.is_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


def require_trainer_or_admin(current_user: User = Depends(get_current_active_user)) -> User:
    """Require trainer or admin role, or user with custom role"""
    if not (current_user.is_trainer() or current_user.is_admin() or _user_has_custom_role(current_user)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Trainer or admin access required"
        )
    return current_user


def require_supervisor_or_admin(current_user: User = Depends(get_current_active_user)) -> User:
    """Require supervisor or admin role, or user with custom role"""
    if not (current_user.is_supervisor() or current_user.is_admin() or _user_has_custom_role(current_user)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Supervisor or admin access required"
        )
    return current_user


def require_manager_access(current_user: User = Depends(get_current_active_user)) -> User:
    """Require manager level access (admin, supervisor, trainer, or custom role)"""
    if not (current_user.can_view_reports() or _user_has_custom_role(current_user)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manager access required"
        )
    return current_user


def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Get current user if authenticated, otherwise None"""
    if not credentials:
        return None
    
    try:
        token = credentials.credentials
        return auth_service.get_current_user(db, token)
    except HTTPException:
        return None


class PermissionChecker:
    """Class-based permission checker for more complex authorization logic"""
    
    def __init__(self, resource_type: str, action: str):
        self.resource_type = resource_type
        self.action = action
    
    def __call__(self, current_user: User = Depends(get_current_active_user)) -> User:
        if not self._has_permission(current_user, self.resource_type, self.action):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"No permission to {self.action} {self.resource_type}"
            )
        return current_user
    
    def _has_permission(self, user: User, resource_type: str, action: str) -> bool:
        """Check if user has permission for specific resource and action.
        Custom roles EXTEND base role permissions (don't replace them).
        """
        # Admin has all permissions
        if user.is_admin():
            return True

        # Check hardcoded role permissions first (base permissions)
        if self._check_hardcoded_role_permission(user, resource_type, action):
            return True

        # Then check custom role permissions (additional permissions)
        if user.custom_role_id:
            return self._check_custom_role_permission(user, resource_type, action)

        return False
    
    def _check_custom_role_permission(self, user: User, resource_type: str, action: str) -> bool:
        """Check permission based on custom role"""
        from sqlalchemy.orm import Session
        from app.database import get_db
        from app.models.custom_role import role_permissions
        from app.api.permissions import PERMISSIONS_DATA
        
        # Get database session
        db = next(get_db())
        
        try:
            # Get permission IDs for this custom role
            permission_ids_result = db.execute(
                role_permissions.select().where(role_permissions.c.role_id == user.custom_role_id)
            ).fetchall()
            
            permission_ids = [row.permission_id for row in permission_ids_result]
            
            # Check if the required permission exists
            required_permission = next(
                (p for p in PERMISSIONS_DATA 
                 if p["resource_type"] == resource_type and p["action"] == action),
                None
            )
            
            if required_permission and required_permission["id"] in permission_ids:
                return True
                
            return False
        except Exception:
            # If there's any error with custom role checking, fallback to hardcoded roles
            return self._check_hardcoded_role_permission(user, resource_type, action)
        finally:
            db.close()
    
    def _check_hardcoded_role_permission(self, user: User, resource_type: str, action: str) -> bool:
        """Check permission based on hardcoded role matrix"""
        # Matriz de permisos para roles hardcodeados (basada en páginas/módulos)
        permissions = {
            UserRole.TRAINER: {
                "dashboard": ["view"],
                "courses": ["view", "create", "read", "update", "delete", "enroll"],
                "evaluations": ["view", "create", "read", "update", "delete"],
                "surveys": ["view", "create", "read", "update", "delete"],
                "certificates": ["view", "create", "read", "download"],
                "attendance": ["view", "create", "read", "update"],
                "reports": ["view", "read"],
                "users": ["view", "read"],
                "notifications": ["view", "read"]
            },
            UserRole.SUPERVISOR: {
                "dashboard": ["view"],
                "courses": ["view", "read", "enroll"],
                "evaluations": ["view", "read", "submit"],
                "surveys": ["view", "read", "submit"],
                "certificates": ["view", "read", "download"],
                "attendance": ["view", "read"],
                "reports": ["view", "read"],
                "users": ["view", "read", "update"],
                "notifications": ["view", "read"],
                "suppliers": ["view", "read"],
                "workers": ["view", "read", "create", "update", "delete"]
            },
            UserRole.EMPLOYEE: {
                "dashboard": ["view"],
                "courses": ["view", "read", "enroll"],
                "modules": ["view", "read"],
                "materials": ["view", "read"],
                "evaluations": ["view", "read", "submit"],
                "surveys": ["view", "read", "submit"],
                "certificates": ["view", "read", "download"],
                "notifications": ["view", "read"],
                "workers": ["view", "read"]
            },
        }
        
        user_permissions = permissions.get(user.role, {})
        resource_permissions = user_permissions.get(resource_type, [])
        
        return action in resource_permissions


# Common permission dependencies
can_manage_users = PermissionChecker("user", "update")
can_create_courses = PermissionChecker("course", "create")
can_manage_evaluations = PermissionChecker("evaluation", "create")
can_view_reports = PermissionChecker("report", "read")


def has_permission(user: User, resource_type: str, action: str) -> bool:
    """
    Check if user has permission for specific resource and action.
    This is a standalone function that can be used without dependency injection.
    """
    checker = PermissionChecker(resource_type, action)
    return checker._has_permission(user, resource_type, action)