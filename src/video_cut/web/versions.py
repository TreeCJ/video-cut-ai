"""Version management API routes for enterprise platform."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from video_cut.db.database import get_db
from video_cut.db.models import GenerationVersion, User
from video_cut.services.version_service import VersionService
from video_cut.web.session import load_session

router = APIRouter()


# Request/Response models
class CreateVersionRequest(BaseModel):
    prompt: str = ""
    max_duration: float = 300.0
    with_subtitles: bool = False


class DeleteVersionRequest(BaseModel):
    reason: str = ""


class VersionResponse(BaseModel):
    id: int
    version_number: int
    status: str
    created_at: str
    created_by: Optional[int] = None
    prompt: Optional[str] = None
    max_duration: Optional[float] = None
    with_subtitles: bool = False
    is_active: bool = False
    file_size: int = 0
    deleted_at: Optional[str] = None
    clip_count: int = 0


@router.get("/api/videos/{video_id}/versions")
def list_versions(
    video_id: int,
    include_deleted: bool = False,
    db: Session = Depends(get_db),
) -> dict:
    """List all versions for a video."""
    from video_cut.db.models import Video, ClipVersion

    version_service = VersionService()
    versions = version_service.get_video_versions(db, video_id, include_deleted)

    video = db.query(Video).get(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    return {
        "video_id": video_id,
        "current_version_id": video.current_version_id,
        "total_versions": len(versions),
        "versions": [
            VersionResponse(
                id=v.id,
                version_number=v.version_number,
                status=v.status,
                created_at=v.created_at.isoformat(),
                created_by=v.created_by,
                prompt=v.prompt,
                max_duration=v.max_duration,
                with_subtitles=v.with_subtitles,
                is_active=v.is_active,
                file_size=v.file_size,
                deleted_at=v.deleted_at.isoformat() if v.deleted_at else None,
                clip_count=db.query(ClipVersion)
                .filter_by(generation_version_id=v.id)
                .count(),
            )
            for v in versions
        ],
    }


@router.post("/api/videos/{video_id}/versions")
def create_new_version(
    video_id: int,
    request: CreateVersionRequest,
    db: Session = Depends(get_db),
) -> dict:
    """Create a new generation version."""
    from video_cut.db.models import Video
    from video_cut.web.tasks import TaskRunner

    # Get current user (for now, use a default user_id=1)
    # In production, this would come from authentication middleware
    current_user_id = 1  # TODO: Implement proper auth

    version_service = VersionService()

    # Check if video exists
    video = db.query(Video).get(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Create version record
    new_version = version_service.create_new_version(
        db=db,
        video_id=video_id,
        prompt=request.prompt,
        max_duration=request.max_duration,
        with_subtitles=request.with_subtitles,
        user_id=current_user_id,
    )

    # Trigger async task (integrate with existing task system)
    # For now, just return the version info
    # In production, you'd call: generate_highlights_version_task.delay(...)

    return {
        "version_id": new_version.id,
        "version_number": new_version.version_number,
        "status": "generating",
        "message": "新版本生成任务已启动",
    }


@router.delete("/api/videos/{video_id}/versions/{version_id}")
def delete_version(
    video_id: int,
    version_id: int,
    request: DeleteVersionRequest,
    db: Session = Depends(get_db),
) -> dict:
    """Soft delete a version."""
    # Current user ID
    current_user_id = 1  # TODO: Implement proper auth

    version_service = VersionService()

    try:
        version_service.soft_delete_version(
            db=db,
            version_id=version_id,
            user_id=current_user_id,
            reason=request.reason,
        )
        return {"message": f"版本 {version_id} 已删除"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/api/videos/{video_id}/versions/{version_id}/restore")
def restore_version(
    video_id: int,
    version_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """Restore a deleted version."""
    version_service = VersionService()

    try:
        version_service.restore_version(db, version_id)
        return {"message": f"版本 {version_id} 已恢复"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/api/videos/{video_id}/versions/{version_id}/switch")
def switch_active_version(
    video_id: int,
    version_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """Switch to a different version as active."""
    version_service = VersionService()

    try:
        version_service.switch_active_version(db, version_id)
        version = db.query(GenerationVersion).get(version_id)
        return {
            "message": f"已切换到版本 {version.version_number}",
            "current_version_id": version_id,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/api/videos/{video_id}/versions/{version_id}/clips")
def get_version_clips(
    video_id: int,
    version_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """Get clips for a specific version."""
    from video_cut.db.models import ClipVersion

    version = db.query(GenerationVersion).get(version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")

    clips = (
        db.query(ClipVersion)
        .filter_by(generation_version_id=version_id)
        .order_by(ClipVersion.order_index)
        .all()
    )

    return {
        "version_id": version_id,
        "clips": [
            {
                "id": c.id,
                "order_index": c.order_index,
                "clip_path": c.clip_path,
                "subtitled_clip_path": c.subtitled_clip_path,
            }
            for c in clips
        ],
    }
