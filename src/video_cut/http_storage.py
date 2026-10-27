"""Local HTTP server for serving audio files to DashScope ASR.

Provides HTTPS URLs for local audio files, compatible with paraformer-v2.
Uses ngrok or similar service to expose local server to the internet.
"""

from __future__ import annotations

import uuid
import threading
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler


class LocalHttpAudioServer:
    """Serves local audio files over HTTP/HTTPS for DashScope ASR."""
    
    _instance = None
    _lock = threading.Lock()
    
    def __init__(self, host: str = "127.0.0.1", port: int = 8080):
        self.host = host
        self.port = port
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._temp_dir = Path.home() / ".video-cut" / "http-staging"
        self._temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Public URL (will be set by ngrok or similar)
        self.public_url: str | None = None
    
    @classmethod
    def get_instance(cls, host: str = "127.0.0.1", port: int = 8080) -> "LocalHttpAudioServer":
        """Get or create singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(host, port)
        return cls._instance
    
    def start(self):
        """Start the HTTP server in background thread."""
        with self._lock:
            if self._server:
                return
            
            server_instance = self
            
            class AudioHandler(SimpleHTTPRequestHandler):
                def __init__(self, *args, **kwargs):
                    super().__init__(
                        *args, 
                        directory=str(server_instance._temp_dir), 
                        **kwargs
                    )
                
                def log_message(self, format, *args):
                    pass  # Suppress logs
            
            try:
                self._server = HTTPServer((self.host, self.port), AudioHandler)
                self._thread = threading.Thread(
                    target=self._server.serve_forever, 
                    daemon=True
                )
                self._thread.start()
                print(f"✓ Audio server started on http://{self.host}:{self.port}")
            except OSError as e:
                if "Address already in use" in str(e):
                    print(f"⚠ Port {self.port} in use, trying {self.port + 1}")
                    self._server = HTTPServer(
                        (self.host, self.port + 1), 
                        AudioHandler
                    )
                    self.port = self.port + 1
                    self._thread = threading.Thread(
                        target=self._server.serve_forever, 
                        daemon=True
                    )
                    self._thread.start()
                    print(f"✓ Audio server started on http://{self.host}:{self.port}")
                else:
                    raise
    
    def upload(self, local_path: Path) -> str:
        """Upload audio file and return public HTTPS URL.
        
        Args:
            local_path: Path to local audio file
            
        Returns:
            Public HTTPS URL for the audio file
        """
        self.start()
        
        # Copy file to staging with unique name
        filename = f"{uuid.uuid4().hex}-{local_path.name}"
        dest = self._temp_dir / filename
        dest.write_bytes(local_path.read_bytes())
        
        # Return public URL
        if self.public_url:
            return f"{self.public_url}/{filename}"
        else:
            # Fallback to local URL (for testing)
            return f"http://{self.host}:{self.port}/{filename}"
    
    def delete(self, url: str) -> None:
        """Delete staged audio file."""
        filename = Path(url).name
        path = self._temp_dir / filename
        if path.exists():
            path.unlink()
    
    def stop(self):
        """Stop the HTTP server."""
        if self._server:
            self._server.shutdown()
            if self._thread:
                self._thread.join(timeout=5)
            self._server = None
            self._thread = None


def setup_ngrok_tunnel(auth_token: str | None = None) -> str:
    """Setup ngrok tunnel for public HTTPS access.
    
    Args:
        auth_token: Optional ngrok auth token
        
    Returns:
        Public HTTPS URL
    """
    try:
        import pyngrok.ngrok as ngrok
        from pyngrok.conf import PyngrokConfig
        
        # Set auth token if provided
        if auth_token:
            ngrok.set_auth_token(auth_token)
        
        # Open tunnel
        public_url = ngrok.connect(LocalHttpAudioServer.get_instance().port)
        print(f"✓ Ngrok tunnel created: {public_url}")
        
        return public_url
    except ImportError:
        print("⚠ pyngrok not installed. Install with: pip install pyngrok")
        print("⚠ Using local HTTP URL (may not work with DashScope)")
        return None
    except Exception as e:
        print(f"⚠ Failed to setup ngrok: {e}")
        print("⚠ Using local HTTP URL")
        return None
