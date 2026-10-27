#!/usr/bin/env python
"""Initialize database tables for the enterprise video-cut platform."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from video_cut.db.database import init_db, engine
from video_cut.db.models import Base


def main():
    """Initialize database."""
    print("Initializing database...")
    print(f"Database URL: {engine.url}")

    try:
        init_db()
        print("✓ Database tables created successfully!")
    except Exception as e:
        print(f"✗ Error initializing database: {e}")
        raise


if __name__ == "__main__":
    main()
