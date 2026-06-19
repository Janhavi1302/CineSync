# CineSync AI — Launch Script
# Starts both the Python AI server and the Electron app

Write-Host ""
Write-Host "  ========================================" -ForegroundColor Cyan
Write-Host "  🎬 CineSync AI — Starting Platform" -ForegroundColor Cyan
Write-Host "  ========================================" -ForegroundColor Cyan
Write-Host ""

$pythonPath = "C:\Users\HP\AppData\Local\Programs\Python\Python311\python.exe"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

# Start AI Server
Write-Host "[1/2] Starting AI Engine..." -ForegroundColor Yellow
$aiServer = Start-Process -FilePath $pythonPath -ArgumentList "main.py" -WorkingDirectory "$projectRoot\ai-engine" -PassThru -WindowStyle Normal
Write-Host "       AI Server PID: $($aiServer.Id)" -ForegroundColor DarkGray
Start-Sleep -Seconds 2

# Start Electron App
Write-Host "[2/2] Starting Electron App..." -ForegroundColor Yellow
$electronApp = Start-Process -FilePath "npm" -ArgumentList "run", "dev" -WorkingDirectory $projectRoot -PassThru -WindowStyle Normal
Write-Host "       Electron PID: $($electronApp.Id)" -ForegroundColor DarkGray

Write-Host ""
Write-Host "  ✅ CineSync AI is running!" -ForegroundColor Green
Write-Host "  • AI Server: http://localhost:8765/health" -ForegroundColor DarkGray
Write-Host "  • Electron:  http://localhost:5173/" -ForegroundColor DarkGray
Write-Host "  • Press Ctrl+C to stop" -ForegroundColor DarkGray
Write-Host ""

# Wait for either to exit
try {
    while ($true) {
        if ($aiServer.HasExited) {
            Write-Host "AI Server exited." -ForegroundColor Red
            break
        }
        if ($electronApp.HasExited) {
            Write-Host "Electron app exited." -ForegroundColor Red
            break
        }
        Start-Sleep -Seconds 1
    }
} finally {
    # Cleanup
    if (!$aiServer.HasExited) { $aiServer.Kill() }
    if (!$electronApp.HasExited) { $electronApp.Kill() }
    Write-Host "CineSync AI stopped." -ForegroundColor Yellow
}
