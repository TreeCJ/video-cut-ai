"""Database connection and session management."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from video_cut.db.models import Base

# Database URL from environment or default to SQLite for development
DATABASE_URL = os.getenv(
    "VIDEO_CUT_DATABASE_URL",
    "sqlite:///./video_cut.db"  # Default to SQLite for easy testing
)

# For MySQL: mysql+pymysql://user:password@localhost/video_cut
# For PostgreSQL: postgresql://user:password@localhost/video_cut

# Engine configuration
engine = create_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=40,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=False,  # Set to True for SQL debugging
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency for FastAPI routes to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """Context manager for database sessions (non-FastAPI usage)."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db() -> None:
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)
