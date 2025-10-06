"""
Password utilities using bcrypt directly.
This replaces the passlib dependency for better compatibility.
"""
import bcrypt


class PasswordManager:
    """Password manager using bcrypt directly for hashing and verification."""
    
    def __init__(self, rounds: int = 12):
        """
        Initialize password manager.
        
        Args:
            rounds: Number of rounds for bcrypt hashing (default: 12)
        """
        self.rounds = rounds
    
    def hash_password(self, password: str) -> str:
        """
        Hash a password using bcrypt.
        
        Args:
            password: Plain text password to hash
            
        Returns:
            Hashed password as string
        """
        # Convert password to bytes
        password_bytes = password.encode('utf-8')
        
        # Generate salt and hash
        salt = bcrypt.gensalt(rounds=self.rounds)
        hashed = bcrypt.hashpw(password_bytes, salt)
        
        # Return as string
        return hashed.decode('utf-8')
    
    def verify_password(self, password: str, hashed_password: str) -> bool:
        """
        Verify a password against its hash.
        
        Args:
            password: Plain text password to verify
            hashed_password: Hashed password to verify against
            
        Returns:
            True if password matches, False otherwise
        """
        try:
            # Convert to bytes
            password_bytes = password.encode('utf-8')
            hashed_bytes = hashed_password.encode('utf-8')
            
            # Verify password
            return bcrypt.checkpw(password_bytes, hashed_bytes)
        except (ValueError, TypeError):
            # Handle any encoding or bcrypt errors
            return False


# Global instance with default settings
password_manager = PasswordManager()