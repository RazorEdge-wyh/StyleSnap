@echo off
REM StyleSnap 一键启动 / One-command start (Windows)
cd /d %~dp0

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.10+.
    pause
    exit /b 1
)

if not exist .venv (
    echo Creating virtual environment...
    python -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install -r requirements.txt
echo.
echo StyleSnap is starting...  open http://localhost:8000
python run.py
