@echo off
setlocal
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Install Python 3.10 or newer and enable Add Python to PATH.
  pause
  exit /b 1
)
if not exist .venv\Scripts\python.exe python -m venv .venv
if not exist .venv\Scripts\python.exe exit /b 1
.venv\Scripts\python.exe -m pip install -r requirements-core.txt
if errorlevel 1 (
  pause
  exit /b 1
)
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 echo Vnstock install failed. Synthetic practice is available. Real-data modes require vnstock.
.venv\Scripts\python.exe run.py --open
pause
