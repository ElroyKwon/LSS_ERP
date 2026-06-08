# LSS ERP - Dev launcher
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
        Write-Host "  Killed PID $p (port $port)"
    }
    Start-Sleep -Milliseconds 500
}

function Run-Build {
    # Rollup 네이티브 모듈이 Windows/Node24 에서 크래시하므로
    # 임시 폴더로 빌드 후 성공하면 dist 교체
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
Write-Host "  LSS ERP - Starting" -ForegroundColor White
Write-Host "============================================" -ForegroundColor DarkCyan
Write-Host ""

# .env
if (-not (Test-Path (Join-Path $BACKEND ".env"))) {
    Copy-Item (Join-Path $BACKEND ".env.example") (Join-Path $BACKEND ".env")
    Write-OK ".env created"
}

# venv
if (-not (Test-Path $PYTHON)) {
    Write-Step "Creating Python venv..."
    & python -m venv $VENV
    if ($LASTEXITCODE -ne 0) { Write-Fail "venv failed"; Read-Host "Enter"; exit 1 }
}
Write-OK "venv OK"

# pip
Write-Step "Checking packages..."
& $PIP install -r (Join-Path $BACKEND "requirements.txt") -q --no-warn-script-location 2>$null
if ($LASTEXITCODE -ne 0) { Write-Fail "pip install failed"; Read-Host "Enter"; exit 1 }
Write-OK "packages OK"

# npm install
if (-not (Test-Path (Join-Path $FRONTEND "node_modules"))) {
    Write-Step "npm install..."
    Push-Location $FRONTEND
    npm install
    Pop-Location
    if ($LASTEXITCODE -ne 0) { Write-Fail "npm install failed"; Read-Host "Enter"; exit 1 }
    Write-OK "node_modules OK"
}

# frontend build (격리 프로세스)
Write-Step "Building frontend..."
$buildExit = Run-Build
$distOk = Test-Path (Join-Path $FRONTEND "dist\index.html")
if ($buildExit -ne 0) {
    if ($distOk) {
        Write-Host "[WARN] Build exit $buildExit - using existing dist" -ForegroundColor Yellow
    } else {
        Write-Fail "Frontend build failed (exit: $buildExit) and no dist found"
        Read-Host "Enter"; exit 1
    }
} else {
    Write-OK "Frontend built"
}

# kill port
Kill-Port $PORT

Write-Host ""
Write-Host "============================================" -ForegroundColor DarkCyan
Write-Host "  URL   : http://localhost:$PORT" -ForegroundColor Yellow
Write-Host "  Login : admin / admin" -ForegroundColor White
Write-Host "  Stop  : Ctrl+C" -ForegroundColor Gray
Write-Host "============================================" -ForegroundColor DarkCyan
Write-Host ""

# uvicorn
try {
    Push-Location $BACKEND
    & $UVICORN app.main:app --host 0.0.0.0 --port $PORT --reload
} finally {
    Pop-Location -ErrorAction SilentlyContinue
    Write-Host ""
    Write-Step "Releasing port $PORT..."
    Kill-Port $PORT
    Write-OK "Port $PORT released"
}

Read-Host "Press Enter to close"
