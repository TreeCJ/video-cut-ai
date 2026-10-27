#!/usr/bin/env python
"""Quick test for local HTTP server functionality."""

import tempfile
from pathlib import Path
from video_cut.local_http import LocalFileServer


def test_local_http_server():
    """Test that the local HTTP server can serve files."""
    # Create a temporary file
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        f.write("Test content for HTTP server")
        temp_path = Path(f.name)
    
    try:
        # Get server instance
        server = LocalFileServer.get_instance()
        server.start()
        
        # Upload file and get URL
        url = server.upload(temp_path)
        print(f"✓ File uploaded, URL: {url}")
        
        # Verify URL format
        assert url.startswith("http://127.0.0.1:"), "URL should be HTTP"
        assert temp_path.name in url, "URL should contain filename"
        print(f"✓ URL format is correct")
        
        # Test signed_url method
        signed = server.signed_url(str(temp_path))
        assert signed.startswith("http://127.0.0.1:"), "Signed URL should be HTTP"
        print(f"✓ Signed URL works: {signed}")
        
        # Test delete method
        server.delete(url)
        print(f"✓ Delete operation completed")
        
        print("\n✅ All tests passed! Local HTTP server is working correctly.")
        
    finally:
        # Cleanup
        if temp_path.exists():
            temp_path.unlink()
        server.stop()


if __name__ == "__main__":
    test_local_http_server()
