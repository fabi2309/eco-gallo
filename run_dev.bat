@echo off
REM ECO-GALLO UAA - Arranca en modo desarrollo 100% Python (sin necesidad de Java)
cd /d "%~dp0"
if "%ECOGALLO_SEED%"=="" set ECOGALLO_SEED=1
if "%ECOGALLO_DEV%"=="" set ECOGALLO_DEV=1
if "%ECOGALLO_ADMINS%"=="" set ECOGALLO_ADMINS=admin@edu.uaa.mx
if "%PORT%"=="" set PORT=8080
echo Instalando dependencias de Python si hacen falta...
python -m pip install -q -r backend\requirements.txt
python run_dev.py
pause
