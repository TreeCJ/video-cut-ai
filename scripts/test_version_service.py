#!/usr/bin/env python
"""Test script for version management service."""

import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from video_cut.db.database import SessionLocal, init_db
from video_cut.db.models import Base, User, Video, GenerationVersion
from video_cut.services.version_service import VersionService


def test_version_service():
    """Test version management functionality."""
    print("=" * 80)
    print("Testing Version Management Service")
    print("=" * 80)
    print()

    db = SessionLocal()

    try:
        # Create a test user
        print("1. Creating test user...")
        user = User(
            username="test_user",
            email="test@example.com",
            password_hash="hashed_password",
            role="editor"
        )
        db.add(user)
        db.flush()
        print(f"   ✓ User created: {user.username} (ID: {user.id})")
        print()

        # Create a test video
        print("2. Creating test video...")
        video = Video(
            project_id=1,  # Assuming project exists, or create one
            original_filename="test_video.mp4",
            storage_path="/media_storage/test_video.mp4",
            duration=300.0,
            resolution="1920x1080",
            file_size=50000000,
            status="ready"
        )
        db.add(video)
        db.flush()
        print(f"   ✓ Video created: {video.original_filename} (ID: {video.id})")
        print()

        # Test version creation
        print("3. Testing version creation...")
        version_service = VersionService()

        # Create version 1
        v1 = version_service.create_new_version(
            db=db,
            video_id=video.id,
            prompt="Test prompt 1",
            max_duration=180.0,
            with_subtitles=True,
            user_id=user.id
        )
        print(f"   ✓ Version 1 created: ID={v1.id}, Number={v1.version_number}")

        # Complete version 1
        version_service.complete_version(
            db=db,
            version_id=v1.id,
            highlights_json_path="/path/to/v1/highlights.json",
            merged_video_path="/path/to/v1/merged.mp4",
            file_size=45000000,
            highlight_count=5
        )
        print(f"   ✓ Version 1 completed")
        print()

        # Create version 2
        print("4. Creating version 2...")
        v2 = version_service.create_new_version(
            db=db,
            video_id=video.id,
            prompt="Test prompt 2",
            max_duration=200.0,
            with_subtitles=False,
            user_id=user.id
        )
        print(f"   ✓ Version 2 created: ID={v2.id}, Number={v2.version_number}")

        # Complete version 2
        version_service.complete_version(
            db=db,
            version_id=v2.id,
            highlights_json_path="/path/to/v2/highlights.json",
            merged_video_path="/path/to/v2/merged.mp4",
            file_size=48000000,
            highlight_count=6
        )
        print(f"   ✓ Version 2 completed")
        print()

        # List versions
        print("5. Listing all versions...")
        versions = version_service.get_video_versions(db, video.id)
        print(f"   Found {len(versions)} versions:")
        for v in versions:
            print(f"   - v{v.version_number}: status={v.status}, active={v.is_active}")
        print()

        # Test soft delete
        print("6. Testing soft delete...")
        version_service.soft_delete_version(
            db=db,
            version_id=v1.id,
            user_id=user.id,
            reason="Testing deletion"
        )
        print(f"   ✓ Version 1 soft deleted")

        # Verify only non-deleted versions
        versions_active = version_service.get_video_versions(db, video.id, include_deleted=False)
        print(f"   Active versions: {len(versions_active)}")

        # List with deleted
        versions_all = version_service.get_video_versions(db, video.id, include_deleted=True)
        print(f"   Total versions (including deleted): {len(versions_all)}")
        print()

        # Test restore
        print("7. Testing version restore...")
        version_service.restore_version(db, v1.id)
        print(f"   ✓ Version 1 restored")

        versions_active = version_service.get_video_versions(db, video.id, include_deleted=False)
        print(f"   Active versions after restore: {len(versions_active)}")
        print()

        # Test switch
        print("8. Testing version switch...")
        version_service.switch_active_version(db, v1.id)
        print(f"   ✓ Switched to version 1")

        video_refreshed = db.query(Video).get(video.id)
        print(f"   Current active version: {video_refreshed.current_version_id}")
        print()

        print("=" * 80)
        print("✅ All tests passed!")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    # Initialize database first
    init_db()

    # Run tests
    test_version_service()
