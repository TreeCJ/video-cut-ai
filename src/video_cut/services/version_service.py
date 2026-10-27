"""Version management service for enterprise video-cut platform."""

from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from video_cut.db.models import (
    ClipVersion,
    GenerationVersion,
    Highlight,
    UserDeletedVersion,
    User,
    Video,
)


class VersionService:
    """Manages generation versions with full history and soft-delete."""

    @staticmethod
    def create_new_version(
        db: Session,
        video_id: int,
        prompt: str = "",
        max_duration: float = 300.0,
        with_subtitles: bool = False,
        user_id: Optional[int] = None,
    ) -> GenerationVersion:
        """Create a new generation version record."""

        # Get last version number
        last_version = (
            db.query(GenerationVersion)
            .filter_by(video_id=video_id)
            .order_by(GenerationVersion.version_number.desc())
            .first()
        )

        new_version_number = (last_version.version_number + 1) if last_version else 1

        # Create new version record
        new_version = GenerationVersion(
            video_id=video_id,
            version_number=new_version_number,
            status="generating",
            prompt=prompt,
            max_duration=max_duration,
            with_subtitles=with_subtitles,
            created_by=user_id,
            created_at=datetime.utcnow(),
            is_active=False,
        )

        db.add(new_version)
        db.flush()  # Get the ID without committing

        return new_version

    @staticmethod
    def complete_version(
        db: Session,
        version_id: int,
        highlights_json_path: str,
        merged_video_path: str,
        file_size: int,
        highlight_count: Optional[int] = None,
    ):
        """Mark version as completed and set as active."""
        version = db.query(GenerationVersion).get(version_id)
        if not version:
            raise ValueError(f"Version {version_id} not found")

        version.status = "completed"
        version.highlights_json_path = highlights_json_path
        version.merged_video_path = merged_video_path
        version.file_size = file_size
        if highlight_count:
            version.highlight_count = highlight_count
        version.is_active = True  # Set as active version

        # Update video's current version
        video = db.query(Video).get(version.video_id)
        video.current_version_id = version_id
        video.total_versions += 1

        db.flush()

    @staticmethod
    def fail_version(db: Session, version_id: int, error_message: str):
        """Mark version as failed."""
        version = db.query(GenerationVersion).get(version_id)
        if version:
            version.status = "failed"
            db.flush()

    @staticmethod
    def soft_delete_version(
        db: Session, version_id: int, user_id: int, reason: str = ""
    ):
        """Soft delete a version (can be restored later)."""
        version = db.query(GenerationVersion).get(version_id)
        if not version:
            raise ValueError(f"Version {version_id} not found")

        # Mark as deleted
        version.deleted_at = datetime.utcnow()
        version.delete_reason = reason

        # Record who deleted it
        deletion_record = UserDeletedVersion(
            version_id=version_id,
            user_id=user_id,
            deleted_at=datetime.utcnow(),
            reason=reason,
        )
        db.add(deletion_record)

        # If deleting active version, switch to latest available
        if version.is_active:
            latest_version = (
                db.query(GenerationVersion)
                .filter_by(video_id=version.video_id)
                .filter(GenerationVersion.deleted_at.is_(None))
                .filter(GenerationVersion.status == "completed")
                .order_by(GenerationVersion.version_number.desc())
                .first()
            )

            if latest_version:
                latest_version.is_active = True
                video = db.query(Video).get(version.video_id)
                video.current_version_id = latest_version.id
            else:
                # No versions left, deactivate
                version.is_active = False
                video = db.query(Video).get(version.video_id)
                video.current_version_id = None

        db.flush()

    @staticmethod
    def restore_version(db: Session, version_id: int):
        """Restore a previously deleted version."""
        version = db.query(GenerationVersion).get(version_id)
        if not version or not version.deleted_at:
            raise ValueError(f"Version {version_id} is not deleted or doesn't exist")

        version.deleted_at = None
        version.delete_reason = None

        # Remove deletion record
        deletion_record = (
            db.query(UserDeletedVersion)
            .filter_by(version_id=version_id)
            .order_by(UserDeletedVersion.deleted_at.desc())
            .first()
        )
        if deletion_record:
            db.delete(deletion_record)

        db.flush()

    @staticmethod
    def get_video_versions(
        db: Session, video_id: int, include_deleted: bool = False
    ) -> list[GenerationVersion]:
        """Get all versions for a video."""
        query = (
            db.query(GenerationVersion)
            .filter_by(video_id=video_id)
            .order_by(GenerationVersion.version_number.desc())
        )

        if not include_deleted:
            query = query.filter(GenerationVersion.deleted_at.is_(None))

        return query.all()

    @staticmethod
    def switch_active_version(db: Session, version_id: int):
        """Switch to a different version as the active one."""
        version = db.query(GenerationVersion).get(version_id)
        if not version:
            raise ValueError(f"Version {version_id} not found")

        if version.status != "completed":
            raise ValueError("Can only switch to completed versions")

        # Deactivate all other versions for this video
        db.query(GenerationVersion).filter_by(video_id=version.video_id).update(
            {"is_active": False}
        )

        # Activate this version
        version.is_active = True

        # Update video reference
        video = db.query(Video).get(version.video_id)
        video.current_version_id = version_id

        db.flush()

    @staticmethod
    def hard_delete_old_versions(
        db: Session, days_keep: int = 30, dry_run: bool = False
    ) -> int:
        """Permanently delete versions older than specified days."""
        from datetime import timedelta

        cutoff_date = datetime.utcnow() - timedelta(days=days_keep)

        # Find deleted versions beyond retention period
        old_versions = (
            db.query(GenerationVersion)
            .filter(
                GenerationVersion.deleted_at.isnot(None),
                GenerationVersion.deleted_at < cutoff_date,
            )
            .all()
        )

        if dry_run:
            print(f"Would delete {len(old_versions)} versions")
            return len(old_versions)

        for version in old_versions:
            # Delete files from filesystem
            if version.highlights_json_path and os.path.exists(
                version.highlights_json_path
            ):
                try:
                    os.remove(version.highlights_json_path)
                except OSError:
                    pass

            if version.merged_video_path and os.path.exists(version.merged_video_path):
                try:
                    os.remove(version.merged_video_path)
                except OSError:
                    pass

            # Delete clip files
            clips_dir = Path(version.merged_video_path).parent if version.merged_video_path else None
            if clips_dir and clips_dir.exists():
                try:
                    shutil.rmtree(clips_dir)
                except OSError:
                    pass

            # Delete database record
            db.delete(version)

        db.flush()
        return len(old_versions)
