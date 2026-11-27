@echo off
REM Runs Ball Cutter straight from the source code (needs Python 3.10+ from python.org).
cd /d "%~dp0"
if not exist .venv (
  python -m venv .venv
  call .venv\Scripts\activate.bat
  pip install -r requirements.txt
) else (
  call .venv\Scripts\activate.bat
)
start "" pythonw app.py
