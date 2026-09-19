@echo off
rem ==============================================================================
rem EdgeErgo — Central Server Launcher (PRD §11, §12.1, §107 Phase 16)
rem Runs FastAPI central server + serves compiled dashboard/dist + SQLite database.
rem ==============================================================================

setlocal enabledelayedexpansion
cd /d "%~dp0\.."

echo ==============================================================================
echo  EdgeErgo Central Server Launcher
echo ==============================================================================

rem Check if dashboard/dist exists
if not exist "dashboard\dist\index.html" (
    echo [WARNING] dashboard/dist/index.html not found!
    echo Attempting to build dashboard frontend...
    cd dashboard
    call npm run build
    cd ..
)

rem Find Python executable
if exist "venv\Scripts\python.exe" (
    set "PYTHON_EXE=venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

echo Starting EdgeErgo Central Server on http://0.0.0.0:8000 ...
echo Central Dashboard available at: http://localhost:8000
echo Edge API Docs available at:      http://localhost:8000/docs
echo Press Ctrl+C to stop the server.
echo.

"%PYTHON_EXE%" -m uvicorn central_server.main:app --host 0.0.0.0 --port 8000

pause
