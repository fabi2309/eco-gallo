@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe python -m venv .venv
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -m pip install -q -r backend\requirements.txt
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe tools\run_mobile_demo.py
pause
