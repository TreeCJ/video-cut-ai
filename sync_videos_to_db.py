#!/usr/bin/env python
"""Sync existing video directories to database."""

import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, 'src')

from video_cut.db.database import SessionLocal
from video_cut.db.models import Video, GenerationVersion, Highlight
from video_cut.audio import probe_duration


def sync_video_directory(output_dir: Path):
    """Scan output directory and sync video tasks to database."""
    db = SessionLocal()
    
    try:
        synced_count = 0
        
        # Scan all directories in output folder
        for video_dir in sorted(output_dir.iterdir()):
            if not video_dir.is_dir():
                continue
            
            # Skip special directories
            if video_dir.name.startswith('_') or video_dir.name == 'clips':
                continue
            
            print(f"\nChecking: {video_dir.name}")
            
            # Check if already in database
            existing = db.query(Video).filter(
                Video.original_filename.like(f"%{video_dir.name}%")
            ).first()
            
            if existing:
                print(f"  ✓ Already exists in database (ID: {existing.id})")
                continue
            
            # Check for web-session.json
            session_file = video_dir / "web-session.json"
            if not session_file.exists():
                print(f"  ⊘ No web-session.json found")
                continue
            
            import json
            with open(session_file, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
            
            source_path = session_data.get('source_path', '')
            
            # Check for highlights.json
            highlights_file = video_dir / "highlights.json"
            has_highlights = highlights_file.exists()
            
            # Check for merged.mp4
            merged_file = video_dir / "merged.mp4"
            has_merged = merged_file.exists()
            
            # Get video duration if possible
            duration = None
            file_size = None
            
            # Try to get from original video
            if source_path and Path(source_path).exists():
                try:
                    duration = probe_duration(Path(source_path))
                    file_size = Path(source_path).stat().st_size
                except Exception as e:
                    print(f"  ⚠ Could not probe duration: {e}")
            
            # Create video record
            print(f"  → Creating video record...")
            video = Video(
                project_id=1,  # Default project
                original_filename=video_dir.name,
                storage_path=source_path,
                duration=duration,
                file_size=file_size,
                status="completed" if has_merged else "ready",
                total_versions=1 if has_highlights else 0,
            )
            
            db.add(video)
            db.flush()
            
            # Create generation version if highlights exist
            if has_highlights:
                print(f"  → Creating generation version...")
                
                # Load highlights
                with open(highlights_file, 'r', encoding='utf-8') as f:
                    highlights_data = json.load(f)
                
                version = GenerationVersion(
                    video_id=video.id,
                    version_number=1,
                    status="completed" if has_merged else "processing",
                    highlight_count=len(highlights_data),
                    is_active=True,
                    merged_video_path=str(merged_file) if has_merged else None,
                )
                
                db.add(version)
                db.flush()
                
                # Update video's current version
                video.current_version_id = version.id
                
                # Create highlight records
                print(f"  → Creating {len(highlights_data)} highlight records...")
                for idx, h in enumerate(highlights_data):
                    highlight = Highlight(
                        video_id=video.id,
                        title=h.get('title', f'Highlight {idx+1}'),
                        start_time=h.get('start_time', h.get('start', 0)),
                        end_time=h.get('end_time', h.get('end', 0)),
                        reason=h.get('reason', ''),
                        quote=h.get('quote', ''),
                        order_index=idx,
                    )
                    db.add(highlight)
                
                synced_count += 1
                print(f"  ✓ Synced video with {len(highlights_data)} highlights")
            else:
                print(f"  ✓ Created basic video record")
        
        db.commit()
        
        print(f"\n{'='*60}")
        print(f"Sync completed:")
        print(f"  Videos synced: {synced_count}")
        print(f"{'='*60}")
        
    finally:
        db.close()


if __name__ == "__main__":
    output_dir = Path("output")
    
    if not output_dir.exists():
        print(f"Error: Output directory '{output_dir}' does not exist")
        sys.exit(1)
    
    print(f"Scanning output directory: {output_dir}")
    sync_video_directory(output_dir)
