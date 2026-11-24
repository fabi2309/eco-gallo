@echo off
setlocal
cd /d "%~dp0mobile"
call flutter pub get
if errorlevel 1 exit /b 1
call flutter build apk --profile --dart-define=LOCAL_NETWORK_BUILD=true
if errorlevel 1 exit /b 1
if not exist "..\artifacts\mobile" mkdir "..\artifacts\mobile"
copy /y "build\app\outputs\flutter-apk\app-profile.apk" "..\artifacts\mobile\ECO-GALLO-local.apk" >nul
if errorlevel 1 exit /b 1
certutil.exe -hashfile "..\artifacts\mobile\ECO-GALLO-local.apk" SHA256
if errorlevel 1 exit /b 1
echo APK local listo en artifacts\mobile\ECO-GALLO-local.apk
echo Perfil optimizado para tesina, firmado con la clave de pruebas de este equipo. No es una publicacion de tienda.
