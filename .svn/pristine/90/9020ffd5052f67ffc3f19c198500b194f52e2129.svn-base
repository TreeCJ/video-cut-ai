#!/usr/bin/env python
"""Simple test for local HTTP server."""

import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from video_cut.local_http import LocalFileServer


def main():
    print("Testing Local HTTP Server...")
    
    # Create a test file
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        f.write("Hello from local HTTP server!")
        temp_path = Path(f.name)
    
    print(f"Created test file: {temp_path}")
    
    try:
        # Get and start server
        server = LocalFileServer.get_instance()
        server.start()
        print(f"✓ Server started on http://{server.host}:{server.port}")
        
        # Test upload
        url = server.upload(temp_path)
        print(f"✓ File uploaded: {url}")
        
        # Verify URL format
        if url.startswith("http://127.0.0.1:"):
            print("✓ URL format is correct")
        else:
            print(f"✗ Unexpected URL format: {url}")
            return False
        
        # Test signed_url
        signed = server.signed_url(str(temp_path))
        print(f"✓ Signed URL: {signed}")
        
        # Cleanup
        server.delete(url)
        print("✓ Cleanup completed")
        
        print("\n✅ Local HTTP server is working correctly!")
        return True
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        if temp_path.exists():
            temp_path.unlink()
        server.stop()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
