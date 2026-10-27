"""Initialize database tables and create default admin user."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import create_engine
from video_cut.db.models import Base, User
from video_cut.auth.auth import hash_password


def init_database():
    """Create all tables and initialize default data."""
    # Get database URL from environment or use SQLite default
    database_url = os.getenv("VIDEO_CUT_DATABASE_URL")

    if not database_url:
        # Fallback to SQLite
        db_path = Path("data") / "videocut.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        database_url = f"sqlite:///{db_path}"
    elif database_url.startswith("mysql"):
        # For MySQL, we need to ensure the database exists
        import re
        # Extract connection info from URL like mysql+pymysql://user:pass@host:port/dbname
        match = re.match(r'mysql\+pymysql://([^:]+):([^@]+)@([^:/]+)(?::(\d+))?/(.+)', database_url)
        if match:
            user, password, host, port, dbname = match.groups()
            port = port or "3306"

            # Connect without database to create it
            base_url = f"mysql+pymysql://{user}:{password}@{host}:{port}"
            temp_engine = create_engine(base_url)

            try:
                with temp_engine.connect() as conn:
                    from sqlalchemy import text
                    conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{dbname}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
                    conn.commit()
                print(f"MySQL database '{dbname}' created/verified.")
            except Exception as e:
                print(f"Warning: Could not create database: {e}")

    engine = create_engine(database_url)

    # Create all tables
    print("Creating database tables...")
    Base.metadata.create_all(engine)
    print("Tables created successfully.")

    # Create default admin user if not exists
    from sqlalchemy.orm import sessionmaker
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    try:
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            print("Creating default admin user...")
            admin_user = User(
                username="admin",
                email="admin@localhost",
                password_hash=hash_password("admin123"),  # Change this!
                role="admin",
                is_active=True,
            )
            db.add(admin_user)
            db.commit()
            print("Default admin user created:")
            print("  Username: admin")
            print("  Password: admin123")
            print("  ⚠️  IMPORTANT: Change the password after first login!")
        else:
            print("Admin user already exists.")
    finally:
        db.close()


if __name__ == "__main__":
    init_database()
