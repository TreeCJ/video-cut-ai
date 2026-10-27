"""Clip management API routes."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy import func, desc, asc
from sqlalchemy.orm import Session

from video_cut.db.models import ClipVersion, GenerationVersion, Highlight, Video
from video_cut.auth.auth import get_current_user, require_role
from video_cut.db.database import get_db
from video_cut.db.models import User


router = APIRouter()


# ============================================================================
# Video Task Management (First Level - Show all uploaded videos)
# ============================================================================

class VideoTaskInfo(BaseModel):
    """Video task information."""
    id: int
    original_filename: str
    duration: Optional[float] = None
    file_size: Optional[int] = None
    status: str
    total_versions: int
    current_version_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class VideoTaskListResponse(BaseModel):
    """Response for video task list."""
    videos: List[VideoTaskInfo]
    total: int


class TaskStats(BaseModel):
    """Statistics for video tasks."""
    total_videos: int
    total_versions: int
    total_clips: int
    total_duration: float


@router.get("/api/video-tasks/stats", response_model=TaskStats)
async def get_task_stats(
    current_user: User = Depends(require_role("editor")),
    db: Session = Depends(get_db),
):
    """Get statistics for video tasks."""
    # Total videos
    total_videos = db.query(Video).count()
    
    # Total versions
    total_versions = db.query(GenerationVersion).filter(
        GenerationVersion.status == "completed"
    ).count()
    
    # Total clips
    total_clips = db.query(ClipVersion).count()
    
    # Total duration (from highlights via ClipVersion)
    clips_with_duration = db.query(
        ClipVersion,
        Highlight.start_time,
        Highlight.end_time
    ).join(Highlight, ClipVersion.highlight_id == Highlight.id).all()
    
    total_duration = sum(
        end_time - start_time
        for clip, start_time, end_time in clips_with_duration
    )
    
    return TaskStats(
        total_videos=total_videos,
        total_versions=total_versions,
        total_clips=total_clips,
        total_duration=round(total_duration, 2),
    )


@router.get("/api/video-tasks", response_model=VideoTaskListResponse)
async def list_video_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    current_user: User = Depends(require_role("editor")),
    db: Session = Depends(get_db),
):
    """List all video tasks (uploaded videos)."""
    query = db.query(Video)
    
    # Apply search filter
    if search:
        query = query.filter(
            Video.original_filename.ilike(f"%{search}%")
        )
    
    # Get total count
    total = query.count()
    
    # Apply pagination and sorting
    offset = (page - 1) * page_size
    videos = query.order_by(desc(Video.created_at)).offset(offset).limit(page_size).all()
    
    return VideoTaskListResponse(
        videos=[
            VideoTaskInfo(
                id=v.id,
                original_filename=v.original_filename,
                duration=v.duration,
                file_size=v.file_size,
                status=v.status,
                total_versions=v.total_versions,
                current_version_id=v.current_version_id,
                created_at=v.created_at,
                updated_at=v.updated_at,
            )
            for v in videos
        ],
        total=total,
    )


@router.get("/api/video-tasks/{video_id}")
async def get_video_task_details(
    video_id: int,
    current_user: User = Depends(require_role("editor")),
    db: Session = Depends(get_db),
):
    """Get detailed information about a video task including all versions."""
    video = db.query(Video).filter(Video.id == video_id).first()
    
    if not video:
        raise HTTPException(status_code=404, detail="Video task not found")
    
    # Get all versions for this video
    versions = db.query(GenerationVersion).filter(
        GenerationVersion.video_id == video_id
    ).order_by(desc(GenerationVersion.version_number)).all()
    
    version_details = []
    for version in versions:
        # Get clips for this version
        clips = db.query(ClipVersion).filter(
            ClipVersion.generation_version_id == version.id
        ).order_by(ClipVersion.order_index).all()
        
        highlights = db.query(Highlight).join(
            ClipVersion, ClipVersion.highlight_id == Highlight.id
        ).filter(
            ClipVersion.generation_version_id == version.id
        ).order_by(Highlight.order_index).all()
        
        clip_data = []
        for clip, highlight in zip(clips, highlights):
            duration = highlight.end_time - highlight.start_time
            clip_data.append({
                "id": clip.id,
                "title": highlight.title,
                "start_time": highlight.start_time,
                "end_time": highlight.end_time,
                "duration": round(duration, 2),
                "reason": highlight.reason,
                "quote": highlight.quote,
                "clip_path": clip.clip_path,
                "subtitled_clip_path": clip.subtitled_clip_path,
                "order_index": clip.order_index,
            })
        
        version_details.append({
            "id": version.id,
            "version_number": version.version_number,
            "status": version.status,
            "is_active": version.is_active,
            "highlight_count": len(highlights),
            "merged_video_path": version.merged_video_path,
            "created_at": version.created_at.isoformat(),
            "clips": clip_data,
        })
    
    return {
        "id": video.id,
        "original_filename": video.original_filename,
        "storage_path": video.storage_path,
        "duration": video.duration,
        "file_size": video.file_size,
        "status": video.status,
        "created_at": video.created_at.isoformat(),
        "versions": version_details,
    }


@router.delete("/api/video-tasks/{video_id}")
async def delete_video_task(
    video_id: int,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Delete a video task and all its associated data."""
    video = db.query(Video).filter(Video.id == video_id).first()
    
    if not video:
        raise HTTPException(status_code=404, detail="Video task not found")
    
    # Delete all versions and their clips
    versions = db.query(GenerationVersion).filter(
        GenerationVersion.video_id == video_id
    ).all()
    
    for version in versions:
        # Delete clip files
        clips = db.query(ClipVersion).filter(
            ClipVersion.generation_version_id == version.id
        ).all()
        
        for clip in clips:
            # Delete physical files
            if clip.clip_path and Path(clip.clip_path).exists():
                try:
                    Path(clip.clip_path).unlink()
                except Exception as e:
                    print(f"Warning: Failed to delete clip file: {e}")
            
            if clip.subtitled_clip_path and Path(clip.subtitled_clip_path).exists():
                try:
                    Path(clip.subtitled_clip_path).unlink()
                except Exception as e:
                    print(f"Warning: Failed to delete subtitled clip file: {e}")
            
            db.delete(clip)
        
        # Delete merged video file
        if version.merged_video_path and Path(version.merged_video_path).exists():
            try:
                Path(version.merged_video_path).unlink()
            except Exception as e:
                print(f"Warning: Failed to delete merged video: {e}")
        
        db.delete(version)
    
    # Delete highlights
    highlights = db.query(Highlight).filter(
        Highlight.video_id == video_id
    ).all()
    for highlight in highlights:
        db.delete(highlight)
    
    # Finally delete the video record
    db.delete(video)
    db.commit()
    
    return {"message": f"Video task '{video.original_filename}' deleted successfully"}


# ============================================================================
# Clip Management (Second Level - Show clips for a specific video)
# ============================================================================

class ClipInfo(BaseModel):
    """Clip information model."""
    id: int
    highlight_id: int
    title: str
    start_time: float
    end_time: float
    duration: float
    reason: Optional[str] = None
    quote: Optional[str] = None
    clip_path: Optional[str] = None
    subtitled_clip_path: Optional[str] = None
    order_index: int
    version_number: int
    video_title: str
    created_at: datetime


class ClipListResponse(BaseModel):
    """Response for clip list endpoint."""
    clips: List[ClipInfo]
    total: int
    page: int
    page_size: int


class TaskStats(BaseModel):
    """Statistics for video tasks."""
    total_videos: int
    total_versions: int
    total_clips: int
    total_duration: float


@router.get("/api/clips", response_model=ClipListResponse)
async def list_clips(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    video_id: Optional[int] = Query(None),
    version_id: Optional[int] = Query(None),
    sort_by: str = Query("created_at", regex="^(created_at|duration|title)$"),
    order: str = Query("desc", regex="^(asc|desc)$"),
    current_user: User = Depends(require_role("editor")),
    db: Session = Depends(get_db),
):
    """List all clips with filtering and pagination from database."""
    query = db.query(
        ClipVersion,
        Highlight,
        GenerationVersion.version_number,
        Video.original_filename.label("video_title")
    ).join(
        Highlight, ClipVersion.highlight_id == Highlight.id
    ).join(
        GenerationVersion, ClipVersion.generation_version_id == GenerationVersion.id
    ).join(
        Video, Highlight.video_id == Video.id
    )

    # Apply filters
    if search:
        query = query.filter(
            Highlight.title.ilike(f"%{search}%") |
            Highlight.reason.ilike(f"%{search}%")
        )

    if video_id:
        query = query.filter(Highlight.video_id == video_id)

    if version_id:
        query = query.filter(ClipVersion.generation_version_id == version_id)

    # Apply sorting
    if sort_by == "duration":
        if order == "asc":
            query = query.order_by(asc(Highlight.end_time - Highlight.start_time))
        else:
            query = query.order_by(desc(Highlight.end_time - Highlight.start_time))
    elif sort_by == "title":
        if order == "asc":
            query = query.order_by(asc(Highlight.title))
        else:
            query = query.order_by(desc(Highlight.title))
    else:  # created_at
        if order == "asc":
            query = query.order_by(asc(ClipVersion.created_at))
        else:
            query = query.order_by(desc(ClipVersion.created_at))

    # Get total count
    total = query.count()

    # Apply pagination
    offset = (page - 1) * page_size
    items = query.offset(offset).limit(page_size).all()

    # Build response
    clips = []
    for clip, highlight, version_num, video_title in items:
        duration = highlight.end_time - highlight.start_time
        clips.append(ClipInfo(
            id=clip.id,
            highlight_id=highlight.id,
            title=highlight.title,
            start_time=highlight.start_time,
            end_time=highlight.end_time,
            duration=round(duration, 2),
            reason=highlight.reason,
            quote=highlight.quote,
            clip_path=clip.clip_path,
            subtitled_clip_path=clip.subtitled_clip_path,
            order_index=clip.order_index,
            version_number=version_num,
            video_title=video_title,
            created_at=clip.created_at,
        ))

    return ClipListResponse(
        clips=clips,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/api/clips/{clip_id}")
async def get_clip_details(
    clip_id: int,
    current_user: User = Depends(require_role("editor")),
    db: Session = Depends(get_db),
):
    """Get detailed information about a specific clip."""
    result = db.query(
        ClipVersion,
        Highlight,
        GenerationVersion.version_number,
        Video.original_filename.label("video_title"),
        Video.original_filename
    ).join(
        Highlight, ClipVersion.highlight_id == Highlight.id
    ).join(
        GenerationVersion, ClipVersion.generation_version_id == GenerationVersion.id
    ).join(
        Video, Highlight.video_id == Video.id
    ).filter(
        ClipVersion.id == clip_id
    ).first()

    if not result:
        raise HTTPException(status_code=404, detail="Clip not found")

    clip, highlight, version_num, video_title, original_filename = result
    duration = highlight.end_time - highlight.start_time

    return {
        "id": clip.id,
        "highlight_id": highlight.id,
        "title": highlight.title,
        "start_time": highlight.start_time,
        "end_time": highlight.end_time,
        "duration": round(duration, 2),
        "reason": highlight.reason,
        "quote": highlight.quote,
        "clip_path": clip.clip_path,
        "subtitled_clip_path": clip.subtitled_clip_path,
        "order_index": clip.order_index,
        "version_number": version_num,
        "video_title": video_title,
        "original_filename": original_filename,
        "created_at": clip.created_at.isoformat(),
    }


@router.delete("/api/clips/{clip_id}")
async def delete_clip(
    clip_id: int,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Delete a clip (soft delete by removing file references)."""
    clip = db.query(ClipVersion).filter(ClipVersion.id == clip_id).first()

    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    # Delete physical files if they exist
    if clip.clip_path and Path(clip.clip_path).exists():
        try:
            Path(clip.clip_path).unlink()
        except Exception as e:
            print(f"Warning: Failed to delete clip file {clip.clip_path}: {e}")

    if clip.subtitled_clip_path and Path(clip.subtitled_clip_path).exists():
        try:
            Path(clip.subtitled_clip_path).unlink()
        except Exception as e:
            print(f"Warning: Failed to delete subtitled clip file {clip.subtitled_clip_path}: {e}")

    # Remove from database
    db.delete(clip)
    db.commit()

    return {"message": "Clip deleted successfully"}


@router.post("/api/clips/bulk-delete")
async def bulk_delete_clips(
    clip_ids: List[int],
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Delete multiple clips at once."""
    clips = db.query(ClipVersion).filter(ClipVersion.id.in_(clip_ids)).all()

    deleted_count = 0
    for clip in clips:
        # Delete physical files
        if clip.clip_path and Path(clip.clip_path).exists():
            try:
                Path(clip.clip_path).unlink()
            except Exception as e:
                print(f"Warning: Failed to delete clip file {clip.clip_path}: {e}")

        if clip.subtitled_clip_path and Path(clip.subtitled_clip_path).exists():
            try:
                Path(clip.subtitled_clip_path).unlink()
            except Exception as e:
                print(f"Warning: Failed to delete subtitled clip file {clip.subtitled_clip_path}: {e}")

        db.delete(clip)
        deleted_count += 1

    db.commit()

    return {
        "message": f"Successfully deleted {deleted_count} clips",
        "deleted_count": deleted_count,
    }
