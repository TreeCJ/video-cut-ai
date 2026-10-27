#!/usr/bin/env python
"""Sync existing filesystem videos to database."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import json
import os
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from video_cut.db.models import Video, GenerationVersion, Highlight, ClipVersion
from video_cut.web.session import load_session

def sync_video_to_db(output_dir: Path):
    """Sync all videos from filesystem to database."""
    
    # Load environment
    load_dotenv('.env')
    db_url = os.getenv('VIDEO_CUT_DATABASE_URL')
    
    if not db_url:
        print("Error: DATABASE_URL not set in .env")
        return
    
    engine = create_engine(db_url)
    
    with Session(engine) as db:
        # Ensure default project exists
        from video_cut.db.models import Project, User
        
        default_project = db.query(Project).filter(Project.name == "Default Project").first()
        if not default_project:
            # Create default user first
            default_user = db.query(User).filter(User.username == "admin").first()
            if not default_user:
                from video_cut.auth.auth import hash_password
                default_user = User(
                    username="admin",
                    email="admin@example.com",
                    hashed_password=hash_password("admin123"),
                    role="admin",
                    is_active=True,
                )
                db.add(default_user)
                db.flush()
            
            default_project = Project(
                name="Default Project",
                description="Auto-created for existing videos",
                owner_id=default_user.id,
            )
            db.add(default_project)
            db.flush()
        
        synced_count = 0
        
        for child in sorted(output_dir.iterdir()):
            if not child.is_dir():
                continue
            
            session = load_session(child)
            if not session:
                continue
            
            # Check if video already exists
            source_filename = session.source_path.split('\\')[-1].split('/')[-1]
            existing_video = db.query(Video).filter(
                Video.original_filename == source_filename
            ).first()
            
            if existing_video:
                print(f"⊘ Skip: {source_filename} (already in DB)")
                continue
            
            # Check if highlights.json exists
            highlights_path = child / "highlights.json"
            if not highlights_path.exists():
                print(f"⊘ Skip: {child.name} (no highlights.json)")
                continue
            
            try:
                # Load highlights
                with open(highlights_path, 'r', encoding='utf-8') as f:
                    highlights_data = json.load(f)
                
                print(f"\n{'='*60}")
                print(f"Syncing: {source_filename}")
                print(f"  Highlights: {len(highlights_data)}")
                
                # Get video file info
                video_file_path = Path(session.source_path)
                actual_duration = getattr(session, 'duration', None)
                actual_file_size = None
                
                if video_file_path.exists():
                    actual_file_size = video_file_path.stat().st_size
                    # Try to get duration from audio file if not in session
                    if not actual_duration:
                        try:
                            import subprocess
                            result = subprocess.run(
                                ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                                 '-of', 'json', str(video_file_path)],
                                capture_output=True, text=True, encoding='utf-8'
                            )
                            if result.returncode == 0:
                                import json
                                probe_data = json.loads(result.stdout)
                                actual_duration = float(probe_data.get('format', {}).get('duration', 0))
                        except Exception as e:
                            print(f"    Warning: Could not probe duration: {e}")
                
                # Create video record with actual data
                video = Video(
                    project_id=default_project.id,
                    original_filename=source_filename,
                    storage_path=session.source_path,
                    duration=actual_duration,
                    file_size=actual_file_size,
                    status="ready",
                    total_versions=1,  # We're creating version 1
                )
                db.add(video)
                db.flush()
                
                # Create generation version
                version = GenerationVersion(
                    video_id=video.id,
                    version_number=1,
                    status="completed",
                    highlight_count=len(highlights_data),
                    is_active=True,
                )
                db.add(version)
                db.flush()
                
                # Create highlights and clip versions
                for idx, h in enumerate(highlights_data):
                    highlight = Highlight(
                        video_id=video.id,
                        title=h.get("title", ""),
                        start_time=h.get("start", h.get("start_time", 0)),  # Handle both field names
                        end_time=h.get("end", h.get("end_time", 0)),
                        reason=h.get("reason", ""),
                        quote=h.get("quote", ""),
                        order_index=idx,
                    )
                    db.add(highlight)
                    db.flush()
                    
                    # Create clip version
                    clip = ClipVersion(
                        generation_version_id=version.id,
                        highlight_id=highlight.id,
                        order_index=idx,
                    )
                    db.add(clip)
                
                # Update merged video path if exists
                merged_path = child / "merged.mp4"
                if merged_path.exists():
                    version.merged_video_path = str(merged_path)
                    version.file_size = merged_path.stat().st_size
                
                # Update clip paths if clips directory exists
                clips_dir = child / "clips"
                if clips_dir.exists():
                    clip_files = sorted(clips_dir.glob("*.mp4"))
                    for clip_file, highlight in zip(clip_files, db.query(Highlight).filter(
                        Highlight.video_id == video.id
                    ).order_by(Highlight.order_index).all()):
                        clip_version = db.query(ClipVersion).filter(
                            ClipVersion.highlight_id == highlight.id,
                            ClipVersion.generation_version_id == version.id,
                        ).first()
                        
                        if clip_version:
                            clip_version.clip_path = str(clip_file)
                            
                            # Check for subtitled version
                            subtitled_file = clips_dir / "subtitled" / clip_file.name
                            if subtitled_file.exists():
                                clip_version.subtitled_clip_path = str(subtitled_file)
                
                db.commit()
                print(f"✓ Synced: {source_filename}")
                synced_count += 1
                
            except Exception as e:
                print(f"✗ Error syncing {child.name}: {e}")
                import traceback
                traceback.print_exc()
        
        print(f"\n{'='*60}")
        print(f"Total synced: {synced_count} videos")


if __name__ == "__main__":
    output_dir = Path("output")
    if not output_dir.exists():
        print("Output directory not found!")
        sys.exit(1)
    
    sync_video_to_db(output_dir)
