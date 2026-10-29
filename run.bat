@echo off
rem Start the Todo app. On first run, create the venv and install packages.
cd /d "%~dp0"
if not exist .env (
    echo .env file is missing. Copy .env.example to .env and fill in the values.
    pause
    exit /b 1
)
if not exist .venv (
    python -m venv .venv
)
.venv\Scripts\python -m pip install -q -r requirements.txt
start "" http://127.0.0.1:5000
.venv\Scripts\python app.py
