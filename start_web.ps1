# Start web service with local HTTP storage (no OSS required)
# Usage: .\start_web.ps1 [port]

param(
    [int]$Port = 8462
)

# Set the fake storage directory to bypass OSS config check
$env:VIDEO_CUT_OSS_FAKE_DIR = Join-Path $PWD "staging"

Write-Host ""
Write-Host "Starting video-cut web service..." -ForegroundColor Green
Write-Host "Local storage directory: $env:VIDEO_CUT_OSS_FAKE_DIR" -ForegroundColor Cyan
Write-Host "Port: $Port" -ForegroundColor Cyan
Write-Host ""
Write-Host "Open http://127.0.0.1:$Port in your browser" -ForegroundColor Yellow
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

uv run video-cut serve --port $Port
