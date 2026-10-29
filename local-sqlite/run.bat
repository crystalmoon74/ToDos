@echo off
rem Start the local SQLite version (v1). Uses the project's .venv; data is saved to todo.db in this folder.
cd /d "%~dp0"
if not exist ..\.venv (
    python -m venv ..\.venv
)
..\.venv\Scripts\python -m pip install -q -r ..\requirements.txt
start "" http://127.0.0.1:5001
..\.venv\Scripts\python app.py
