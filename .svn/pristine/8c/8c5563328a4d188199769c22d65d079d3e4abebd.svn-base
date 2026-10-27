"""Local HTTP server as OSS replacement for ASR staging.

Serves local audio files over HTTP so DashScope ASR can fetch them
without requiring Aliyun OSS credentials.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading


class LocalFileServer:
    """Serves local audio files over HTTP so ASR can fetch them."""
    
    _instance = None
    _lock = threading.Lock()
    
    def __init__(self, host: str = "127.0.0.1", port: int = 0):
        self.host = host
        self.port = port
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._temp_dir = Path.home() / ".video-cut" / "staging"
        self._temp_dir.mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def get_instance(cls) -> "LocalFileServer":
        """Get or create singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
    
    def start(self):
        """Start background HTTP server."""
        with self._lock:
            if self._server:
                return
            
            server_instance = self
            
            class Handler(SimpleHTTPRequestHandler):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, directory=str(server_instance._temp_dir), **kwargs)
                
                def log_message(self, format, *args):
                    pass  # Suppress logs to avoid console spam
            
            self._server = HTTPServer((self.host, self.port), Handler)
            self.port = self._server.server_address[1]  # Update if port=0 (ephemeral)
            
            self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
            self._thread.start()
    
    def upload(self, local_path: Path) -> str:
        """Copy file to staging and return HTTP URL."""
        self.start()
        filename = f"{uuid.uuid4().hex}-{local_path.name}"
        dest = self._temp_dir / filename
        dest.write_bytes(local_path.read_bytes())
        return f"http://{self.host}:{self.port}/{filename}"
    
    def signed_url(self, file_path: str) -> str:
        """Convert local file path to HTTP URL."""
        self.start()
        filename = Path(file_path).name
        return f"http://{self.host}:{self.port}/{filename}"
    
    def delete(self, key: str) -> None:
        """Delete the staged file."""
        # Handle both URL and filename formats
        if key.startswith("http"):
            filename = Path(key).name
        else:
            filename = Path(key).name
        
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
