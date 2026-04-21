@echo off
title IAprendo Dashboard - Streamlit
echo.
echo ============================================
echo   IAprendo Dashboard (Streamlit)
echo ============================================
echo.
echo Iniciando na porta 8502...
echo URL: http://localhost:8502
echo.
echo Pressione Ctrl+C para encerrar.
echo.

cd /d "%~dp0"
venv\Scripts\python.exe -m streamlit run dashboard\app.py --server.port 8502
pause
