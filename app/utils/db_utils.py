
from sqlalchemy import TypeDecorator, String
import logging

logger = logging.getLogger(__name__)

class CaseInsensitiveEnumType(TypeDecorator):
    """
    A TypeDecorator that handles Case-Insensitive Enum values.
    It stores the value as a string (lowercase) in the database,
    and converts incoming values (from DB) to the Enum member,
    handling case mismatches (e.g. 'ADMIN' -> UserRole.ADMIN).
    
    This is useful when the database contains values in different cases
    than what the Python Enum expects (e.g. legacy data or manual inserts).
    """
    impl = String
    cache_ok = True

    def __init__(self, enum_class, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.enum_class = enum_class

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if hasattr(value, 'value'):
            return value.value
        return str(value).lower()

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        
        # 1. Try exact match
        try:
            return self.enum_class(value)
        except ValueError:
            pass
            
        # 2. Try lowercase match (e.g. DB has 'ADMIN', Enum wants 'admin')
        try:
            return self.enum_class(value.lower())
        except ValueError:
            pass

        # 3. Try finding by name (case-insensitive)
        # e.g. if DB has 'Admin' and Enum.ADMIN = 'admin'
        for member in self.enum_class:
            if member.name.lower() == value.lower() or member.value.lower() == value.lower():
                return member
                
        # 4. If all fails, log warning and return raw string or raise error
        # Returning raw string might break pydantic validation later, but better than crashing DB load?
        # Actually, if we return raw string, Pydantic might fail validation.
        # But let's let it raise the error if we really can't map it.
        logger.error(f"Could not map database value '{value}' to enum {self.enum_class.__name__}")
        raise ValueError(f"'{value}' is not a valid {self.enum_class.__name__}")
