#!/usr/bin/env python
"""Start the video-cut development server with proper path configuration."""

import sys
import logging
from pathlib import Path

# Configure logging to show important messages but filter noisy asyncio errors
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Filter out ConnectionResetError warnings from asyncio
class AsyncioConnectionFilter(logging.Filter):
    def filter(self, record):
        # Allow all records except specific connection reset errors
        if 'ConnectionResetError' in str(record.getMessage()):
            return False
        if 'remote host强迫关闭' in str(record.getMessage()):
            return False
        return True

# Filter out noisy Chrome DevTools and static file 404s
class NoiseFilter(logging.Filter):
    def filter(self, record):
        msg = str(record.getMessage())
        # Filter Chrome DevTools requests and common 404s
        if 'chrome.devtools.json' in msg:
            return False
        if '.well-known' in msg and '404' in msg:
            return False
        return True

# Apply filters to asyncio logger
asyncio_logger = logging.getLogger("asyncio")
asyncio_logger.addFilter(AsyncioConnectionFilter())

# Apply noise filter to uvicorn access logs
uvicorn_access = logging.getLogger("uvicorn.access")
uvicorn_access.addFilter(NoiseFilter())

# Add src directory to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# Load environment variables from .env file
from dotenv import load_dotenv
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(str(env_path))
    print(f"Loaded environment variables from {env_path}")
else:
    print("Warning: .env file not found")

import uvicorn

if __name__ == "__main__":
    print("Starting video-cut development server...")
    print("Access the application at: http://127.0.0.1:8465")
    print("Login with: admin / admin123\n")

    uvicorn.run(
        "video_cut.web.app:create_app_dev",
        factory=True,
        host="127.0.0.1",
        port=8466,
        reload=False,
        log_level="info",  # Show info level logs
    )
