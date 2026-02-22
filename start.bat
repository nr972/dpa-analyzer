@echo off
REM Privacy & DPA Analyzer — One-command startup (Windows)
REM Starts both the FastAPI backend and Streamlit frontend.

cd /d "%~dp0"

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed.
    echo Please install Python 3.11+ from https://python.org
    pause
    exit /b 1
)

REM Install dependencies
pip show dpa-analyzer >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    pip install -e ".[dev]"
)

REM Create data directories
if not exist "data\uploads" mkdir "data\uploads"
if not exist "data\reports" mkdir "data\reports"
if not exist "data\matrices" mkdir "data\matrices"

REM Start API server in background
echo Starting API server on port 8000...
start /b uvicorn app.main:app --host 0.0.0.0 --port 8000

REM Wait for API
echo Waiting for API to start...
timeout /t 5 /nobreak >nul

REM Start Streamlit frontend
echo Starting frontend on port 8501...
echo Open http://localhost:8501 in your browser.
streamlit run frontend/app.py --server.port 8501 --server.address 0.0.0.0 --server.headless true
