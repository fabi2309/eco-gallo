@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\connect_mobile_usb.ps1" %*
exit /b %errorlevel%
