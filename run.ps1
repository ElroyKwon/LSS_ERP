# LSS ERP - Production launcher
$BASE     = $PSScriptRoot
$BACKEND  = Join-Path $BASE "backend"
$FRONTEND = Join-Path $BASE "frontend"
$VENV     = Join-Path $BACKEND "venv"
$PYTHON   = Join-Path $VENV "Scripts\python.exe"
$PIP      = Join-Path $VENV "Scripts\pip.exe"
$UVICORN  = Join-Path $VENV "Scripts\uvicorn.exe"
$PORT     = 8000

function Write-Step { param($msg) Write-Host "[....] $msg" -ForegroundColor Cyan }
function Write-OK   { param($msg) Write-Host "[ OK ] $msg" -ForegroundColor Green }
function Write-Fail { param($msg) Write-Host "[FAIL] $msg" -ForegroundColor Red }

function Kill-Port {
    param($port)
    $raw = cmd /c "netstat -ano 2>nul" 2>$null
    $pids = $raw | Where-Object { $_ -match ":$port\s" -and $_ -match "LISTENING" } |
        ForEach-Object { ($_ -split '\s+')[-1] } |
        Where-Object { $_ -match '^\d+$' } | Select-Object -Unique
    foreach ($p in $pids) {
        cmd /c "taskkill /F /T /PID $p" 2>$null | Out-Null
    }
    Start-Sleep -Milliseconds 500
}

function Run-Build {
    $tmp = Join-Path $FRONTEND "dist_build_tmp"
    Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
    $script = "const{build}=require('vite');build({root:process.cwd(),build:{outDir:'dist_build_tmp'}}).catch(()=>{})"
    $p = Start-Process cmd `
        -ArgumentList "/c `"cd /d `"$FRONTEND`" && node -e `"$script`"`"" `
        -Wait -PassThru -NoNewWindow
    if (Test-Path (Join-Path $tmp "index.html")) {
        Remove-Item -Recurse -Force (Join-Path $FRONTEND "dist") -ErrorAction SilentlyContinue
        Copy-Item -Recurse $tmp (Join-Path $FRONTEND "dist")
        Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
        return 0
    }
    return $p.ExitCode
}

Write-Host ""
Write-Host "============================================" -ForegroundColor DarkCyan
Write-Host "  LSS ERP - Production Mode" -ForegroundColor White
Write-Host "============================================" -ForegroundColor DarkCyan
Write-Host ""

if (-not (Test-Path (Join-Path $BACKEND ".env"))) {
    Write-Fail ".env not found. Copy .env.example to .env and set DB settings."
    Read-Host "Enter"; exit 1
}

if (-not (Test-Path $PYTHON)) {
    Write-Step "Creating Python venv..."
    & python -m venv $VENV
    if ($LASTEXITCODE -ne 0) { Write-Fail "venv failed"; Read-Host "Enter"; exit 1 }
}
Write-OK "venv OK"

Write-Step "Checking packages..."
$pipLog = Join-Path $BASE ".pip-install.log"
& $PYTHON -m pip install -r (Join-Path $BACKEND "requirements.txt") -q --no-warn-script-location *> $pipLog
if ($LASTEXITCODE -ne 0) {
    Write-Fail "pip failed"
    if (Test-Path $pipLog) { Get-Content $pipLog -Tail 20 | ForEach-Object { Write-Host $_ -ForegroundColor DarkGray } }
    Read-Host "Enter"; exit 1
}
Remove-Item $pipLog -Force -ErrorAction SilentlyContinue
Write-OK "packages OK"

if (-not (Test-Path (Join-Path $FRONTEND "node_modules"))) {
    Write-Step "npm install..."
    Push-Location $FRONTEND; npm install; Pop-Location
}

Write-Step "Building frontend..."
$buildExit = Run-Build
$distOk = Test-Path (Join-Path $FRONTEND "dist\index.html")
if ($buildExit -ne 0) {
    if ($distOk) {
        Write-Host "[WARN] Build exit $buildExit - using existing dist" -ForegroundColor Yellow
    } else {
        Write-Fail "Build failed (exit: $buildExit) and no dist found"
        Read-Host "Enter"; exit 1
    }
} else {
    Write-OK "Frontend built"
}

Kill-Port $PORT

Write-Host ""
Write-Host "============================================" -ForegroundColor DarkCyan
Write-Host "  URL    : http://localhost:$PORT" -ForegroundColor Yellow
Write-Host "  Docs   : http://localhost:$PORT/api/docs" -ForegroundColor Gray
Write-Host "  Login  : admin / admin" -ForegroundColor White
Write-Host "  Stop   : Ctrl+C" -ForegroundColor Gray
Write-Host "============================================" -ForegroundColor DarkCyan
Write-Host ""

try {
    Push-Location $BACKEND
    & $PYTHON -m uvicorn app.main:app --host 0.0.0.0 --port $PORT
} finally {
    Pop-Location -ErrorAction SilentlyContinue
    Kill-Port $PORT
    Write-OK "Port $PORT released"
}

Read-Host "Press Enter to close"
