@echo off
REM Quick fix script for Docker networking issue - Windows version

echo ==========================================
echo Docker Network Cleanup and Restart Script
echo ==========================================
echo.

echo Step 1: Stopping all containers...
docker-compose down

echo.
echo Step 2: Force removing containers if they exist...
docker rm -f optimized tmsserver rossim 2>nul

echo.
echo Step 3: Removing orphaned networks...
docker network rm demo-pyigtlcompose_tms-network 2>nul
docker network prune -f

echo.
echo Step 4: Starting services...
docker-compose up -d tmsserver
timeout /t 2 /nobreak >nul
docker-compose up -d SlicerApp

echo.
echo Step 5: Checking status...
docker-compose ps

echo.
echo Step 6: Verifying TMS environment variables...
docker exec optimized env | findstr TMS

echo.
echo ==========================================
echo Cleanup complete!
echo ==========================================
echo.
echo To view logs, run:
echo   docker-compose logs -f SlicerApp
echo.
echo To check for 'Connecting' messages, run:
echo   docker-compose logs SlicerApp | findstr /I "connecting"