@echo off
title RIGOL DHO1204 Voice Control
echo ========================================
echo   RIGOL DHO1204 Voice Control Server
echo ========================================
echo.

cd /d "%~dp0"

echo [*] Cleaning up previous instances...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8765" ^| findstr "LISTENING"') do taskkill /f /pid %%a >nul 2>&1


set PYTHON=C:\Users\quanquan.shang\AppData\Local\Programs\Python\Python314\python.exe

if not exist "%PYTHON%" (
    echo [ERROR] Python not found at %PYTHON%
    echo Please update the PYTHON path in run.bat
    pause
    exit /b 1
)

echo [*] Server:  http://localhost:8765
echo [*] Scope:   192.168.152.177:5555
echo.
echo Features:
echo   - Voice control (Chrome/Edge required)
echo   - Click-to-connect / disconnect
echo   - Screenshot saved to screenshots\ folder
echo   - Live scope view (click "Live View")
echo.
echo Press Ctrl+C to stop
echo ========================================
echo.

"%PYTHON%" server.py

pause