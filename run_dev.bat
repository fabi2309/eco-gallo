@echo off
REM ECO-GALLO UAA - Arranca en modo desarrollo 100% Python (sin necesidad de Java)
cd /d "%~dp0"
REM Los valores salen de .env (si existe) y, si faltan, de run_dev.py.
if "%PORT%"=="" set PORT=8080
if not exist .venv\Scripts\python.exe python -m venv .venv
if errorlevel 1 exit /b 1
echo Instalando dependencias en el entorno local .venv...
.venv\Scripts\python.exe -m pip install -q -r backend\requirements.txt
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe run_dev.py
pause
