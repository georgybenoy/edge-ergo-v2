@echo off
title EdgeErgo — Presentation Launcher
color 0A
cd /d "%~dp0"

echo ===============================================================================
echo                EDGEERGO INTELLIGENCE PLATFORM — PRESENTATION SUITE
echo       Privacy-Preserving Distributed Edge AI Ergonomics & Well-Being
echo ===============================================================================
echo.
echo Current Live URLs:
echo   - Executive Dashboard: http://localhost:5173
echo   - Central Server REST: http://localhost:8000
echo   - Interactive API Docs: http://localhost:8000/docs
echo.
echo Select an action to run:
echo   [1] Open Executive Dashboard in default web browser
echo   [2] Launch Live Edge Agent (Webcam + PySide6 Desktop HUD Overlay)
echo   [3] Launch Synthetic Edge Agent (Headless / No Webcam needed)
echo   [4] Re-seed Enterprise Presentation Fleet Data
echo   [5] Restart Central Server (Port 8000)
echo   [6] Restart React Dashboard (Port 5173)
echo   [Q] Quit
echo.
set /p choice="Enter choice [1-6, Q]: "

if /i "%choice%"=="1" (
    start http://localhost:5173
    goto menu_end
)
if /i "%choice%"=="2" (
    echo Launching Edge Agent with Webcam and Desktop Awareness HUD...
    .\venv\Scripts\python.exe -m edge_agent.main --server-url http://localhost:8000
    goto menu_end
)
if /i "%choice%"=="3" (
    echo Launching Headless Synthetic Edge Agent...
    .\venv\Scripts\python.exe -m edge_agent.main --headless --no-camera --server-url http://localhost:8000
    goto menu_end
)
if /i "%choice%"=="4" (
    echo Seeding realistic multi-workstation enterprise dataset...
    .\venv\Scripts\python.exe scripts/seed_presentation_data.py
    echo Done! Refresh your dashboard at http://localhost:5173
    pause
    goto menu_end
)
if /i "%choice%"=="5" (
    echo Starting Central FastAPI Server on port 8000...
    .\venv\Scripts\python.exe -m uvicorn central_server.main:app --host 0.0.0.0 --port 8000
    goto menu_end
)
if /i "%choice%"=="6" (
    echo Starting React Dashboard Dev Server on port 5173...
    cd dashboard && npm run dev
    goto menu_end
)
if /i "%choice%"=="Q" (
    exit /b 0
)

:menu_end
pause
