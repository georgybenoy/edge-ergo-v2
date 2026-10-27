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

rem Launch EdgeErgoAgent with native interactive setup and health verification
"%EXE_PATH%" %*

if %ERRORLEVEL% neq 0 (
    echo.
    echo [Edge Agent exited with code %ERRORLEVEL%]
    pause
)
