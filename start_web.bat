@echo off
REM Start web service with local HTTP storage (no OSS required)
REM Usage: start_web.bat [port]

setlocal

REM Set the fake storage directory to bypass OSS config check
set VIDEO_CUT_OSS_FAKE_DIR=%cd%\staging

REM Optional: set a custom port (default 8462)
if "%1"=="" (
    set PORT=8462
) else (
    set PORT=%1
)

echo Starting video-cut web service...
echo Local storage directory: %VIDEO_CUT_OSS_FAKE_DIR%
echo Port: %PORT%
echo.
echo Open http://127.0.0.1:%PORT% in your browser
echo Press Ctrl+C to stop the server
echo.

uv run video-cut serve --port %PORT%
