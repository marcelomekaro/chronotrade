@echo off
title Chrono Trade
cd /d "%~dp0"
if not exist .venv (
  echo Rode primeiro o arquivo instalar_windows.bat
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
echo Abrindo o Chrono Trade no navegador. Para fechar, feche esta janela.
chronotrade
