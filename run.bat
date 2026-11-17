@echo off
REM ECO-GALLO UAA - arranca backend (Python/Flask) + gateway (Java)
cd /d "%~dp0"
if "%ECOGALLO_SEED%"=="" set ECOGALLO_SEED=1
if "%ECOGALLO_SMTP_HOST%"=="" if "%ECOGALLO_DEV%"=="" set ECOGALLO_DEV=1
if "%ECOGALLO_ADMINS%"=="" set ECOGALLO_ADMINS=admin@edu.uaa.mx
if "%PORT%"=="" set PORT=8080
if "%ECOGALLO_PROXY_TOKEN%"=="" for /f %%S in ('python -c "import secrets; print(secrets.token_hex(32))"') do set ECOGALLO_PROXY_TOKEN=%%S
if not exist .venv\Scripts\python.exe python -m venv .venv
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -m pip install -q -r backend\requirements.txt
if errorlevel 1 exit /b 1
if not exist gateway\out mkdir gateway\out
javac -d gateway\out gateway\Gateway.java
start "ECO-GALLO backend" /B .venv\Scripts\python.exe backend\app.py
timeout /t 2 >nul
echo   Abre http://localhost:%PORT%
java -cp gateway\out Gateway %PORT% 5000 frontend
