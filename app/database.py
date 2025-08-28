from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

from app.config import settings

# Determine if we should echo SQL queries
# Only echo in development mode and when explicitly enabled
echo_sql = settings.debug and os.getenv("SQL_ECHO", "false").lower() == "true"

# Create database engine with production-optimized settings
engine_kwargs = {
    "echo": echo_sql,
    "pool_pre_ping": True,  # Verify connections before use
    "pool_recycle": 3600,   # Recycle connections every hour
}

# Add PostgreSQL-specific optimizations if using PostgreSQL
if "postgresql" in settings.database_url:
    engine_kwargs.update({
        "pool_size": 10,
        "max_overflow": 20,
        "pool_timeout": 30,
    })

engine = create_engine(settings.database_url, **engine_kwargs)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class
Base = declarative_base()


def get_db():
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Create all tables in the database"""
    Base.metadata.create_all(bind=engine)


def drop_tables():
    """Drop all tables in the database"""
    Base.metadata.drop_all(bind=engine)