@echo off
REM ECO-GALLO UAA - arranca backend (Python/Flask) + gateway (Java)
cd /d "%~dp0"
if "%ECOGALLO_SEED%"=="" set ECOGALLO_SEED=1
if "%ECOGALLO_SMTP_HOST%"=="" if "%ECOGALLO_DEV%"=="" set ECOGALLO_DEV=1
if "%PORT%"=="" set PORT=8080
python -m pip install -q -r backend\requirements.txt
if not exist gateway\out mkdir gateway\out
javac -d gateway\out gateway\Gateway.java
start "ECO-GALLO backend" /B python backend\app.py
timeout /t 2 >nul
echo   Abre http://localhost:%PORT%
java -cp gateway\out Gateway %PORT% 5000 frontend
