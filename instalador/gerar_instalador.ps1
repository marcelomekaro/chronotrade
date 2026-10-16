<#
  Gera o instalador do Chrono Trade para Windows (ChronoTrade-Setup-X.Y.Z.exe).

  Como usar (PowerShell aberto na pasta do projeto, por exemplo o terminal do VS Code):
      powershell -ExecutionPolicy Bypass -File instalador\gerar_instalador.ps1
  Com a SUA chave do Gemini já preenchida (só para instalar nos seus computadores, não distribua):
      powershell -ExecutionPolicy Bypass -File instalador\gerar_instalador.ps1 -UsarMinhaChave

  Precisa de: Windows 10/11, internet e o NSIS (instale uma vez com:  winget install NSIS.NSIS).
  Não precisa ter Python: o script baixa um Python portátil que vai dentro do instalador.
#>
param(
  [switch]$UsarMinhaChave,
  [string]$ChaveGemini = "",
  [string]$PyUrl = "https://github.com/astral-sh/python-build-standalone/releases/download/20241016/cpython-3.12.7+20241016-x86_64-pc-windows-msvc-install_only.tar.gz"
)
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$Aqui = Split-Path -Parent $MyInvocation.MyCommand.Path
$Raiz = Split-Path -Parent $Aqui
$B = Join-Path $Aqui "build"
$App = Join-Path $B "app"
$Dist = Join-Path $Aqui "dist"

# NSIS
$makensis = $null
$cmd = Get-Command makensis -ErrorAction SilentlyContinue
if ($cmd) { $makensis = $cmd.Source }
foreach ($c in @("${env:ProgramFiles(x86)}\NSIS\makensis.exe", "$env:ProgramFiles\NSIS\makensis.exe")) {
  if (-not $makensis -and (Test-Path $c)) { $makensis = $c }
}
if (-not $makensis) {
  Write-Host "Falta o NSIS. Instale com:  winget install NSIS.NSIS   e rode este script de novo." -ForegroundColor Yellow
  exit 1
}

# Versão do app
$init = Get-Content (Join-Path $Raiz "tradingagents\__init__.py") -Raw
$Versao = "1.0.0"
if ($init -match '__version__\s*=\s*"(\d+)\.(\d+)\.(\d+)') { $Versao = "$($Matches[1]).$($Matches[2]).$($Matches[3])" }

if (Test-Path $B) { Remove-Item $B -Recurse -Force }
New-Item -ItemType Directory -Force -Path $App, $Dist | Out-Null

Write-Host "1/5 Baixando o Python portátil..." -ForegroundColor Cyan
Invoke-WebRequest -Uri $PyUrl -OutFile (Join-Path $B "python.tar.gz")
tar -xzf (Join-Path $B "python.tar.gz") -C $App
$Py = Join-Path $App "python\python.exe"

Write-Host "2/5 Instalando o Chrono Trade e as dependências (alguns minutos)..." -ForegroundColor Cyan
& $Py -m pip install --disable-pip-version-check --no-warn-script-location --quiet `
    --target (Join-Path $App "python\Lib\site-packages") $Raiz
if ($LASTEXITCODE -ne 0) { throw "pip falhou" }
Get-ChildItem (Join-Path $App "python") -Recurse -Filter *.pdb | Remove-Item -Force

Write-Host "3/5 Ícone, termos e o atalho 'Chrono Trade.exe'..." -ForegroundColor Cyan
& $Py (Join-Path $Aqui "preparar.py") $App
& $makensis /V2 "/DSAIDA=$App\Chrono Trade.exe" "/DICONE=$App\icone.ico" "/DVERSAO=$Versao" (Join-Path $Aqui "abrir.nsi")
if ($LASTEXITCODE -ne 0) { throw "makensis (atalho) falhou" }

Write-Host "4/5 Montando o instalador..." -ForegroundColor Cyan
$Sufixo = ""
$Extra = @()
if ($UsarMinhaChave -and -not $ChaveGemini) {
  $envArq = Join-Path $Raiz ".env"
  if (Test-Path $envArq) {
    $linha = Select-String -Path $envArq -Pattern '^\s*GOOGLE_API_KEY\s*=\s*(.+)$' | Select-Object -First 1
    if ($linha) { $ChaveGemini = $linha.Matches[0].Groups[1].Value.Trim().Trim('"').Trim("'") }
  }
  if (-not $ChaveGemini) { Write-Host "Não achei GOOGLE_API_KEY no .env do projeto." -ForegroundColor Yellow }
}
if ($ChaveGemini) {
  Write-Host "   ATENÇÃO: a chave vai DENTRO do instalador. Use só nos seus computadores; não envie para clientes." -ForegroundColor Yellow
  $Extra = @("/DCHAVE_GEMINI=$ChaveGemini")
  $Sufixo = "-PESSOAL"
}
$Saida = Join-Path $Dist "ChronoTrade-Setup-$Versao$Sufixo.exe"
& $makensis /V2 "/DSAIDA=$Saida" "/DAPP=$App" "/DICONE=$App\icone.ico" "/DVERSAO=$Versao" `
    "/DTERMOS=$B\termos.txt" @Extra (Join-Path $Aqui "chronotrade.nsi")
if ($LASTEXITCODE -ne 0) { throw "makensis (instalador) falhou" }

Write-Host "5/5 Pronto: $Saida" -ForegroundColor Green
Get-Item $Saida | Select-Object Name, @{n = "MB"; e = { [math]::Round($_.Length / 1MB) } }
