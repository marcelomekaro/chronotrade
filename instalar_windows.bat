@echo off
title Chrono Trade - instalacao
cd /d "%~dp0"
echo.
echo  === Chrono Trade: instalacao no Windows ===
echo.
where py >nul 2>nul
if errorlevel 1 (
  echo Python nao encontrado. Instale em https://www.python.org/downloads/
  echo e marque a caixa "Add python.exe to PATH". Depois rode este arquivo de novo.
  pause
  exit /b 1
)
if not exist .venv (
  echo Criando o ambiente do app...
  py -3 -m venv .venv || goto erro
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip uninstall -y tradingagents >nul 2>nul
echo Instalando as bibliotecas (leva alguns minutos)...
pip install -e . || goto erro
echo Instalando o conector do MetaTrader 5 (opcional)...
pip install MetaTrader5 >nul 2>nul
rem Profit: so quem tem a licenca da ProfitDLL precisa de  pip install profitdll-wrapper
if not exist .env copy .env.example .env >nul
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\Chrono Trade.lnk'); $s.TargetPath='%~dp0abrir_chronotrade.bat'; $s.WorkingDirectory='%~dp0'; $s.Save()"
echo.
echo Pronto! Abra pelo atalho "Chrono Trade" na area de trabalho.
pause
exit /b 0
:erro
echo.
echo A instalacao parou com erro. Copie as mensagens acima e peca ajuda.
pause
exit /b 1
