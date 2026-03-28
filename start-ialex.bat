@echo off
title IAlex - Agente Vendedor WhatsApp
echo.
echo ============================================
echo   IAlex - Agente Vendedor IAprendo
echo ============================================
echo.

:: Verificar Docker
docker info >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Docker nao esta rodando!
    echo Abra o Docker Desktop e tente novamente.
    pause
    exit /b 1
)

:: Iniciar Evolution API se nao estiver rodando
docker ps --filter "name=evolution_api" --format "{{.Status}}" | findstr "Up" >nul 2>&1
if errorlevel 1 (
    echo Iniciando Evolution API...
    docker compose up -d
    echo Aguardando Evolution API iniciar...
    timeout /t 15 /nobreak >nul
)

echo Evolution API rodando!
echo.

:: Instalar Flask se necessario
venv\Scripts\python.exe -c "import flask" 2>nul
if errorlevel 1 (
    echo Instalando Flask...
    venv\Scripts\python.exe -m pip install flask schedule -q
)

:: Iniciar IAlex
echo Iniciando IAlex...
echo.
venv\Scripts\python.exe agent\start_ialex.py
