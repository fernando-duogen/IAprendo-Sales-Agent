@echo off
title IAprendo Sales Agent - Modo Mobile
echo.
echo ============================================
echo   IAprendo Sales Agent - Acesso Mobile
echo ============================================
echo.
echo Iniciando Streamlit + Ngrok...
echo.

:: Iniciar Streamlit em background
start /B "" venv\Scripts\python.exe -m streamlit run dashboard\app.py --server.port 8501 --server.headless true

:: Esperar Streamlit iniciar
echo Aguardando Streamlit iniciar...
timeout /t 5 /nobreak >nul

:: Iniciar Ngrok
echo.
echo ============================================
echo   Acesse pelo celular a URL abaixo:
echo ============================================
echo.
ngrok http 8501
