@echo off
REM ============================================================================
REM Quick Deployment Script for video-cut (Windows)
REM ============================================================================

echo ==========================================
echo   video-cut Docker Deployment Script
echo ==========================================
echo.

REM Check prerequisites
echo [INFO] Checking prerequisites...

where docker >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Docker is not installed. Please install Docker Desktop first.
    exit /b 1
)

where docker-compose >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Docker Compose is not installed.
    exit /b 1
)

if not exist .env (
    echo [WARNING] .env file not found. Copying from template...
    copy .env.production .env
    echo [WARNING] Please edit .env file and update the configuration!
    echo [INFO] Then run this script again.
    pause
    exit /b 1
)

echo [SUCCESS] Prerequisites check passed
echo.

REM Generate JWT secret if using default
findstr /C:"your-super-secret-jwt-key" .env >nul
if %ERRORLEVEL% EQU 0 (
    echo [INFO] Generating JWT secret key...
    REM Note: Windows doesn't have openssl by default, user should generate manually
    echo [WARNING] Please generate a JWT_SECRET_KEY manually using: openssl rand -hex 32
    echo [WARNING] Or use an online generator and paste it in .env file
    echo.
)

REM Build and start
echo [INFO] Building Docker images (this may take a few minutes)...
docker-compose build --no-cache

echo [INFO] Starting services...
docker-compose up -d

echo [INFO] Waiting for services to be ready...
timeout /t 15 /nobreak >nul

REM Check services
echo [INFO] Checking service status...
docker-compose ps | findstr "Up" >nul
if %ERRORLEVEL% EQU 0 (
    echo [SUCCESS] Services are running!
) else (
    echo [ERROR] Some services failed to start. Check logs:
    docker-compose logs
    pause
    exit /b 1
)

echo.
echo [SUCCESS] Deployment complete!
echo.
echo Access the application at: http://localhost:8462
echo Default login: admin / admin123
echo IMPORTANT: Change the default admin password immediately!
echo.
echo Useful commands:
echo   View logs:       docker-compose logs -f
echo   Stop services:   docker-compose down
echo   Restart:         docker-compose restart
echo.

pause
