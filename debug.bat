@echo off
setlocal
pushd "%~dp0"

set LOG=%~dp0debug.log
echo. > "%LOG%"
echo [START] %DATE% %TIME% >> "%LOG%"

echo Step 1: pushd OK >> "%LOG%"
echo Step 1: pushd OK

set PORT=8000
set PYTHON=backend\venv\Scripts\python.exe
set PIP=backend\venv\Scripts\pip.exe
set UVICORN=backend\venv\Scripts\uvicorn.exe

echo Step 2: checking files >> "%LOG%"
echo Step 2: checking files
if exist "%PYTHON%"  (echo   PYTHON : OK >> "%LOG%") else (echo   PYTHON : MISSING >> "%LOG%")
if exist "%PIP%"     (echo   PIP    : OK >> "%LOG%") else (echo   PIP    : MISSING >> "%LOG%")
if exist "%UVICORN%" (echo   UVICORN: OK >> "%LOG%") else (echo   UVICORN: MISSING >> "%LOG%")
if exist "backend\.env" (echo   ENV    : OK >> "%LOG%") else (echo   ENV    : MISSING >> "%LOG%")
if exist "frontend\node_modules" (echo   MODULES: OK >> "%LOG%") else (echo   MODULES: MISSING >> "%LOG%")

echo Step 3: pip install >> "%LOG%"
echo Step 3: pip install
%PIP% install -r backend\requirements.txt -q --no-warn-script-location >> "%LOG%" 2>&1
echo   pip exit: %ERRORLEVEL% >> "%LOG%"
echo   pip exit: %ERRORLEVEL%
if errorlevel 1 goto :fail

echo Step 4: frontend build >> "%LOG%"
echo Step 4: frontend build
pushd frontend
npm run build >> "%LOG%" 2>&1
set BUILD_EXIT=%ERRORLEVEL%
popd
echo   build exit: %BUILD_EXIT% >> "%LOG%"
echo   build exit: %BUILD_EXIT%
if exist "frontend\dist\index.html" (
    echo   dist exists, continuing >> "%LOG%"
) else (
    if %BUILD_EXIT% neq 0 goto :fail
)

echo Step 5: kill port %PORT% >> "%LOG%"
echo Step 5: kill port %PORT%
for /f "tokens=5 delims= " %%a in ('netstat -ano 2^>nul ^| findstr " :%PORT% " ^| findstr "LISTENING"') do (
    if not "%%a"=="" taskkill /F /T /PID %%a > nul 2>&1
)

echo Step 6: start uvicorn >> "%LOG%"
echo Step 6: start uvicorn
pushd backend
echo   cwd: %CD% >> "%LOG%"
echo   cwd: %CD%
..\%UVICORN% app.main:app --host 0.0.0.0 --port %PORT% --reload >> "%LOG%" 2>&1
echo   uvicorn exit: %ERRORLEVEL% >> "%LOG%"
echo   uvicorn exit: %ERRORLEVEL%
popd

echo [END] %DATE% %TIME% >> "%LOG%"
echo.
echo === Log saved: %LOG% ===
popd
pause
endlocal
goto :eof

:fail
echo [FAIL] at step above >> "%LOG%"
echo [FAIL] at step above
echo.
echo === Log saved: %LOG% ===
popd
pause
endlocal
exit /b 1
