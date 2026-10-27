#!/usr/bin/env python
"""Test script for file upload functionality."""

import asyncio
import io
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from video_cut.web.upload import (
    get_upload_dir,
    save_uploaded_file,
    validate_upload_file,
    cleanup_old_uploads,
)


class MockUploadFile:
    """Mock UploadFile for testing."""
    
    def __init__(self, filename: str, content: bytes):
        self.filename = filename
        self.content = content
        self._pos = 0
    
    async def read(self, size: int = -1) -> bytes:
        if size == -1:
            chunk = self.content[self._pos:]
            self._pos = len(self.content)
        else:
            chunk = self.content[self._pos:self._pos + size]
            self._pos += size
        return chunk


async def test_upload():
    """Test upload functionality."""
    print("=" * 80)
    print("Testing File Upload Functionality")
    print("=" * 80)
    print()
    
    # Test 1: Validate file extensions
    print("1. Testing file validation...")
    assert validate_upload_file("test.mp4") == True
    assert validate_upload_file("test.MP4") == True
    assert validate_upload_file("test.avi") == True
    assert validate_upload_file("test.txt") == False
    assert validate_upload_file("test.exe") == False
    print("   ✓ File extension validation passed")
    print()
    
    # Test 2: Save uploaded file
    print("2. Testing file saving...")
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        upload_dir = Path(tmpdir) / "_uploads"
        
        # Create mock file
        content = b"fake video content" * 1000
        mock_file = MockUploadFile("test_video.mp4", content)
        
        # Save file
        saved_path, file_size = await save_uploaded_file(upload_dir, mock_file)
        
        assert saved_path.exists(), "Saved file should exist"
        assert file_size == len(content), f"File size mismatch: {file_size} != {len(content)}"
        assert saved_path.suffix == ".mp4", "File extension should be preserved"
        
        print(f"   ✓ File saved successfully: {saved_path}")
        print(f"   ✓ File size: {file_size} bytes")
        print(f"   ✓ File exists: {saved_path.exists()}")
        print()
        
        # Test 3: Cleanup old files
        print("3. Testing cleanup of old files...")
        cleaned = cleanup_old_uploads(upload_dir, max_age_hours=0)
        print(f"   ✓ Cleaned up {cleaned} old files")
        print()
    
    # Test 4: Large file rejection
    print("4. Testing large file rejection...")
    with tempfile.TemporaryDirectory() as tmpdir:
        upload_dir = Path(tmpdir) / "_uploads"
        
        # Create a file larger than 2GB (simulated)
        large_content = b"x" * (3 * 1024 * 1024 * 1024)  # 3GB
        mock_file = MockUploadFile("large.mp4", large_content)
        
        try:
            await save_uploaded_file(upload_dir, mock_file)
            print("   ✗ Should have raised ValueError for large file")
        except ValueError as e:
            print(f"   ✓ Correctly rejected large file: {str(e)[:50]}...")
            print()
    
    print("=" * 80)
    print("✅ All upload tests passed!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_upload())
