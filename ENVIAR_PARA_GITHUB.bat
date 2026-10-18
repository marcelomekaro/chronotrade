@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo ===============================================
echo   Enviando o Chrono Trade para o GitHub
echo   github.com/marcelomekaro/chronotrade
echo ===============================================
echo.
where git >nul 2>nul
if errorlevel 1 (
  echo O Git nao esta instalado. Baixe em https://git-scm.com/download/win e rode de novo.
  pause
  exit /b 1
)
git config --global --add safe.directory "%cd%" >nul 2>nul
git add -A
git -c user.name="Marcelo Mekaro" -c user.email="mmekaro@gmail.com" commit -m "Atualizacoes" >nul 2>nul
git push -u origin main
echo.
if errorlevel 1 (
  echo Algo deu errado. Confira se o repositorio "chronotrade" ja foi criado vazio no GitHub
  echo e se voce entrou com a conta marcelomekaro na janela de login.
) else (
  echo Pronto! Abra https://github.com/marcelomekaro/chronotrade
)
echo.
pause
