@echo off
rem ==============================================================================
rem EdgeErgo — Standalone Edge Agent Launcher (PRD §12.1, §42, §43, §107)
rem Runs EdgeErgoAgent.exe without requiring Python, OpenCV, or MediaPipe.
rem ==============================================================================

setlocal enabledelayedexpansion

rem Detect executable location (supports standalone folder or repo checkout)
if exist "%~dp0EdgeErgoAgent.exe" (
    set "EXE_PATH=%~dp0EdgeErgoAgent.exe"
    cd /d "%~dp0"
) else if exist "%~dp0dist\EdgeErgoAgent.exe" (
    set "EXE_PATH=%~dp0dist\EdgeErgoAgent.exe"
    cd /d "%~dp0"
) else if exist "%~dp0..\installer\dist\EdgeErgoAgent.exe" (
    set "EXE_PATH=%~dp0..\installer\dist\EdgeErgoAgent.exe"
    cd /d "%~dp0.."
) else (
    cd /d "%~dp0\.."
    set "EXE_PATH=installer\dist\EdgeErgoAgent.exe"
)

if not exist "%EXE_PATH%" (
    echo [ERROR] %EXE_PATH% not found!
    echo Please build the agent executable first by running:
    echo   python installer\build_agent.py
    echo.
    pause
    exit /b 1
)

echo ==============================================================================
echo  EdgeErgo Edge Agent Launcher
echo ==============================================================================

rem Check if edge_config.json already exists
if not exist "edge_config.json" (
    echo First-time launch detected!
    set /p "SERVER_URL=Enter Central Server URL [default: http://localhost:8000]: "
    if "!SERVER_URL!"=="" set "SERVER_URL=http://localhost:8000"
    
    set /p "DEVICE_NAME=Enter Workstation / Desk Name [default: Workstation-01]: "
    if "!DEVICE_NAME!"=="" set "DEVICE_NAME=Workstation-01"

    echo.
    echo Launching EdgeErgoAgent connected to !SERVER_URL! ...
    "%EXE_PATH%" --server "!SERVER_URL!" --device-name "!DEVICE_NAME!" %*
) else (
    echo Starting EdgeErgoAgent with existing configuration...
    "%EXE_PATH%" %*
)

if %ERRORLEVEL% neq 0 (
    echo.
    echo [Edge Agent exited with code %ERRORLEVEL%]
    pause
)
