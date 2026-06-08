@echo off
set BASE=%~dp0
echo [Backend] Activating venv...
call "%BASE%venv\Scripts\activate.bat"
echo [Backend] Starting uvicorn on port 8000...
cd /d "%BASE%"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
pause
