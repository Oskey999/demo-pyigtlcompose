# PowerShell script to build and run the ROS2 container safely

Write-Host "=== ROS2 Container Build Script ===" -ForegroundColor Cyan

# Clean up old container
Write-Host "`nStopping and removing old container..." -ForegroundColor Yellow
docker compose down 2>$null

# Optional: Clean old image to force rebuild
# Uncomment if you want to rebuild from scratch
# Write-Host "Removing old image..." -ForegroundColor Yellow
# docker rmi rossim 2>$null

# Build with increased resources
Write-Host "`nBuilding container (this may take 20-30 minutes)..." -ForegroundColor Yellow
Write-Host "Tip: Watch for 'Build completed successfully' message" -ForegroundColor Gray

$buildStart = Get-Date
docker compose build --progress=plain ROSsim 2>&1 | Tee-Object -FilePath "build.log"
$buildEnd = Get-Date
$buildTime = $buildEnd - $buildStart

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n✓ Build completed in $($buildTime.TotalMinutes.ToString('0.0')) minutes" -ForegroundColor Green
    
    # Start the container
    Write-Host "`nStarting container..." -ForegroundColor Yellow
    docker compose up -d ROSsim
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "`n✓ Container started successfully!" -ForegroundColor Green
        Write-Host "`nWaiting 10 seconds for services to initialize..." -ForegroundColor Gray
        Start-Sleep -Seconds 10
        
        # Check if it's actually running
        Write-Host "`nChecking container status..." -ForegroundColor Yellow
        $status = docker inspect rossim --format='{{.State.Status}}' 2>$null
        
        if ($status -eq "running") {
            Write-Host "✓ Container is running" -ForegroundColor Green
            
            # Check for the critical WebSocket service
            Write-Host "`nChecking for WebSocket service..." -ForegroundColor Yellow
            docker logs rossim 2>&1 | Select-String "Data WebSocket Server listening" | Select-Object -First 1
            
            Write-Host "`n" -NoNewline
            Write-Host "========================================" -ForegroundColor Cyan
            Write-Host "Access your ROS2 desktop at:" -ForegroundColor Green
            Write-Host "  http://localhost:3000" -ForegroundColor White
            Write-Host "========================================" -ForegroundColor Cyan
            Write-Host "`nTo run the MoveIt demo, open a terminal in the desktop and run:" -ForegroundColor Gray
            Write-Host "  start-demo.sh" -ForegroundColor White
            
            Write-Host "`nTo view live logs:" -ForegroundColor Gray
            Write-Host "  docker logs -f rossim" -ForegroundColor White
        } else {
            Write-Host "✗ Container is not running (Status: $status)" -ForegroundColor Red
            Write-Host "`nLast 50 lines of logs:" -ForegroundColor Yellow
            docker logs rossim --tail 50
        }
    } else {
        Write-Host "`n✗ Failed to start container" -ForegroundColor Red
    }
} else {
    Write-Host "`n✗ Build failed" -ForegroundColor Red
    Write-Host "Check build.log for details" -ForegroundColor Yellow
}

Write-Host "`nBuild log saved to: build.log" -ForegroundColor Gray
