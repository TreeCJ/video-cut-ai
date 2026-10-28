"""Video task service for database integration."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Optional
from datetime import datetime

from sqlalchemy.orm import Session

from video_cut.db.models import Video, GenerationVersion, Highlight, ClipVersion
from video_cut.audio import probe_duration


def create_video_from_upload(
    db: Session,
    original_filename: str,
    storage_path: str,
    file_size: int,
) -> Video:
    """Create a Video record from uploaded file.
    
    Args:
        db: Database session
        original_filename: Original filename
        storage_path: Path to the stored video file
        file_size: File size in bytes
    
    Returns:
        Created Video object
    """
    # Probe video duration
    duration = None
    try:
        duration = probe_duration(Path(storage_path))
    except Exception as e:
        print(f"Warning: Failed to probe duration for {storage_path}: {e}")
    
    # Create video record
    video = Video(
        original_filename=original_filename,
        storage_path=storage_path,
        duration=duration,
        file_size=file_size,
        status="uploaded",
        total_versions=0,
        current_version_id=None,
    )
    
    db.add(video)
    db.commit()
    db.refresh(video)
    
    return video


def create_generation_version(
    db: Session,
    video_id: int,
    version_number: int = 1,
) -> GenerationVersion:
    """Create a new generation version for a video.
    
    Args:
        db: Database session
        video_id: Video ID
        version_number: Version number (auto-increment if not provided)
    
    Returns:
        Created GenerationVersion object
    """
    # Auto-calculate version number if not provided
    if version_number is None:
        max_version = db.query(GenerationVersion).filter(
            GenerationVersion.video_id == video_id
        ).order_by(GenerationVersion.version_number.desc()).first()
        
        version_number = (max_version.version_number + 1) if max_version else 1
    
    # Create version record
    version = GenerationVersion(
        video_id=video_id,
        version_number=version_number,
        status="processing",
        highlight_count=0,
        with_subtitles=False,
        is_active=True,
    )
    
    db.add(version)
    db.commit()
    db.refresh(version)
    
    # Update video's current version and total versions
    video = db.query(Video).filter(Video.id == video_id).first()
    if video:
        video.current_version_id = version.id
        video.total_versions = db.query(GenerationVersion).filter(
            GenerationVersion.video_id == video_id
        ).count()
        db.commit()
    
    return version


def create_highlights_from_analysis(
    db: Session,
    video_id: int,
    version_id: int,
    highlights: list[dict],
) -> list[Highlight]:
    """Create highlight records from AI analysis results.
    
    Args:
        db: Database session
        video_id: Video ID
        version_id: Generation version ID
        highlights: List of highlight data from LLM analysis
    
    Returns:
        List of created Highlight objects
    """
    created_highlights = []
    
    for idx, h in enumerate(highlights):
        highlight = Highlight(
            video_id=video_id,
            title=h.get("title", f"Highlight {idx + 1}"),
            start_time=h.get("start", 0),
            end_time=h.get("end", 0),
            reason=h.get("reason", ""),
            quote=h.get("quote", ""),
            order_index=idx,
        )
        
        db.add(highlight)
        created_highlights.append(highlight)
    
    db.commit()
    
    # Refresh all highlights to get IDs
    for h in created_highlights:
        db.refresh(h)
    
    # Update version highlight count
    version = db.query(GenerationVersion).filter(GenerationVersion.id == version_id).first()
    if version:
        version.highlight_count = len(created_highlights)
        db.commit()
    
    return created_highlights


def create_clip_version(
    db: Session,
    highlight_id: int,
    generation_version_id: int,
    clip_path: Optional[str] = None,
    subtitled_clip_path: Optional[str] = None,
    order_index: int = 0,
) -> ClipVersion:
    """Create a clip version record.
    
    Args:
        db: Database session
        highlight_id: Associated highlight ID
        generation_version_id: Parent generation version ID
        clip_path: Path to clip file without subtitles
        subtitled_clip_path: Path to clip file with subtitles
        order_index: Order index in the version
    
    Returns:
        Created ClipVersion object
    """
    clip_version = ClipVersion(
        highlight_id=highlight_id,
        generation_version_id=generation_version_id,
        clip_path=clip_path,
        subtitled_clip_path=subtitled_clip_path,
        order_index=order_index,
    )
    
    db.add(clip_version)
    db.commit()
    db.refresh(clip_version)
    
    return clip_version


def update_version_status(
    db: Session,
    version_id: int,
    status: str,
    merged_video_path: Optional[str] = None,
) -> None:
    """Update generation version status.
    
    Args:
        db: Database session
        version_id: Version ID
        status: New status (completed, failed, etc.)
        merged_video_path: Path to merged video file
    """
    version = db.query(GenerationVersion).filter(GenerationVersion.id == version_id).first()
    if version:
        version.status = status
        if merged_video_path:
            version.merged_video_path = merged_video_path
        db.commit()


def update_video_status(
    db: Session,
    video_id: int,
    status: str,
) -> None:
    """Update video task status.
    
    Args:
        db: Database session
        video_id: Video ID
        status: New status
    """
    video = db.query(Video).filter(Video.id == video_id).first()
    if video:
        video.status = status
        db.commit()
