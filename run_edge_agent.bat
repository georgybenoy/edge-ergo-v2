@echo off
title EdgeErgo — Live Edge Agent (Camera + HUD)
color 0B
cd /d "%~dp0"

echo ===============================================================================
echo                EDGEERGO EDGE AGENT — LIVE DESKTOP MONITORING
echo ===============================================================================
echo Connecting to Central Server at http://localhost:8000 ...
echo Initializing camera capture, MediaPipe vision pipeline, and PySide6 overlay...
echo.

.\venv\Scripts\python.exe -m edge_agent.main --server-url http://localhost:8000

pause
