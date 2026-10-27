#!/usr/bin/env python
"""Reset admin password in database."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from sqlalchemy import create_engine, MetaData, Table
from video_cut.auth.auth import hash_password
import os

# Get database URL from .env
database_url = os.getenv("VIDEO_CUT_DATABASE_URL")
if not database_url:
    print("ERROR: VIDEO_CUT_DATABASE_URL not set in .env")
    sys.exit(1)

print(f"Connecting to database: {database_url.split('@')[1] if '@' in database_url else database_url}")

engine = create_engine(database_url)

# Check if users table exists and has data
metadata = MetaData()
metadata.reflect(engine)

if 'users' not in metadata.tables:
    print("ERROR: users table does not exist")
    sys.exit(1)

users_table = metadata.tables['users']

# Query admin user
with engine.connect() as conn:
    from sqlalchemy import text
    result = conn.execute(text("SELECT id, username, email, role, password_hash FROM users WHERE username='admin'"))
    admin = result.fetchone()

    if not admin:
        print("ERROR: admin user not found in database")
        sys.exit(1)

    print(f"\nCurrent admin user:")
    print(f"  ID: {admin.id}")
    print(f"  Username: {admin.username}")
    print(f"  Email: {admin.email}")
    print(f"  Role: {admin.role}")
    print(f"  Password Hash: {admin.password_hash[:50]}...")

    # Reset password
    new_password = "admin123"
    new_hash = hash_password(new_password)

    print(f"\nResetting password to: {new_password}")

    conn.execute(
        text("UPDATE users SET password_hash = :hash WHERE username = 'admin'"),
        {"hash": new_hash}
    )
    conn.commit()

    print("✓ Password reset successful!")
    print("\nYou can now login with:")
    print("  Username: admin")
    print("  Password: admin123")
