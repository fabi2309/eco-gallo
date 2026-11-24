@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Falta el entorno .venv. Ejecuta primero run_dev.bat para preparar el proyecto.
  exit /b 1
)
.venv\Scripts\python.exe tools\run_mobile_local.py %*
pause
