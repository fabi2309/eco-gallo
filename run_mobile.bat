@echo off
setlocal
cd /d "%~dp0"
where flutter >nul 2>nul
if errorlevel 1 (
  echo Flutter no esta en PATH. Abre una terminal nueva despues de instalarlo.
  exit /b 1
)
powershell.exe -NoProfile -Command "try { $health = Invoke-RestMethod 'http://127.0.0.1:8080/api/health' -TimeoutSec 3; if ($health.ok -ne $true) { exit 1 } } catch { exit 1 }"
if errorlevel 1 (
  echo El servidor ECO-GALLO no responde en http://127.0.0.1:8080.
  echo Abre otra terminal en esta carpeta y ejecuta: .\run_mobile_demo.bat
  echo Deja esa terminal abierta y vuelve a ejecutar este script.
  exit /b 1
)
set "SDK=%ANDROID_HOME%"
if "%SDK%"=="" set "SDK=%ANDROID_SDK_ROOT%"
if "%SDK%"=="" set "SDK=%LOCALAPPDATA%\Android\Sdk"
set "DEVICE=%~1"
if "%DEVICE%"=="" set "DEVICE=emulator-5554"
"%SDK%\platform-tools\adb.exe" -s "%DEVICE%" reverse tcp:8080 tcp:8080
if errorlevel 1 (
  echo Enciende el emulador primero. Para otro dispositivo: run_mobile.bat SERIAL
  exit /b 1
)
cd mobile
call flutter pub get
if errorlevel 1 exit /b 1
call flutter run -d "%DEVICE%"
