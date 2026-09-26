@echo off
setlocal
cd /d "%~dp0"
docker info >nul 2>&1
if errorlevel 1 (
  echo Start Docker Desktop with Linux containers, then try again.
  exit /b 1
)
docker compose up --build -d
if errorlevel 1 exit /b 1
if not defined PORT set PORT=8000
echo CodeArena: http://localhost:%PORT%
echo Published address (includes .env overrides):
docker compose port api 8000
echo LAN addresses:
powershell -NoProfile -Command "Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -ne '127.0.0.1' -and $_.IPAddress -notlike '169.254.*' } | Select-Object InterfaceAlias,IPAddress"
docker compose ps
