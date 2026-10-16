; Instalador do Chrono Trade para Windows (NSIS 3). Gerado por gerar_instalador.ps1 / gerar_instalador.sh.
; Instala só para o usuário (não pede administrador), cria atalhos e, se a pessoa quiser, grava a chave da IA.
Unicode true
!include "MUI2.nsh"
!include "nsDialogs.nsh"
!include "LogicLib.nsh"

!ifndef CHAVE_GEMINI
  !define CHAVE_GEMINI ""
!endif

Name "Chrono Trade"
OutFile "${SAIDA}"
InstallDir "$LOCALAPPDATA\Programs\Chrono Trade"
InstallDirRegKey HKCU "Software\ChronoTrade" "Pasta"
RequestExecutionLevel user
SetCompressor /SOLID lzma
SetCompressorDictSize 64
BrandingText "Chrono Trade, desenvolvido por Marcelo Mekaro"
VIProductVersion "${VERSAO}.0"
VIAddVersionKey "ProductName" "Chrono Trade"
VIAddVersionKey "CompanyName" "Marcelo Mekaro"
VIAddVersionKey "FileDescription" "Instalador do Chrono Trade"
VIAddVersionKey "FileVersion" "${VERSAO}"
VIAddVersionKey "LegalCopyright" "Marcelo Mekaro"

!define MUI_ICON "${ICONE}"
!define MUI_UNICON "${ICONE}"
!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TITLE "Chrono Trade ${VERSAO}"
!define MUI_WELCOMEPAGE_TEXT "Buy and hold diário. Prosperidade no longo prazo.$\r$\n$\r$\nEste assistente instala o Chrono Trade neste computador. Não precisa de administrador e não mexe em outros programas.$\r$\n$\r$\nDesenvolvido por Marcelo Mekaro$\r$\nmarcelomekaro@gmail.com · WhatsApp (19) 99965-0436"
!define MUI_FINISHPAGE_RUN "$INSTDIR\Chrono Trade.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Abrir o Chrono Trade agora"
!define MUI_FINISHPAGE_LINK "Falar com o desenvolvedor no WhatsApp"
!define MUI_FINISHPAGE_LINK_LOCATION "https://wa.me/5519999650436"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "${TERMOS}"
!insertmacro MUI_PAGE_DIRECTORY
Page custom PaginaChaves PaginaChavesSair
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "PortugueseBR"

Var Dialogo
Var CampoChave
Var Chave

Function PaginaChaves
  !insertmacro MUI_HEADER_TEXT "Inteligência artificial (opcional)" "O Oráculo e as dicas escritas por IA usam o Gemini, do Google."
  nsDialogs::Create 1018
  Pop $Dialogo
  ${If} $Dialogo == error
    Abort
  ${EndIf}
  ${NSD_CreateLabel} 0 0 100% 40u "Cole a sua chave do Gemini (GOOGLE_API_KEY). Ela fica só neste computador, no arquivo .env da sua pasta de dados. Pode deixar em branco: o app funciona sem IA e dá para colocar depois em %USERPROFILE%\.chronotrade\.env."
  Pop $0
  ${NSD_CreateText} 0 46u 100% 13u "${CHAVE_GEMINI}"
  Pop $CampoChave
  ${NSD_CreateLabel} 0 66u 100% 30u "Crie a chave grátis em aistudio.google.com/apikey. Não compartilhe a sua chave: quem tiver acesso a ela usa a sua cota."
  Pop $0
  nsDialogs::Show
FunctionEnd

Function PaginaChavesSair
  ${NSD_GetText} $CampoChave $Chave
FunctionEnd

!macro FecharApp
  ; fecha o Chrono Trade que estiver aberto a partir desta pasta (sem mexer em outros programas Python)
  nsExec::Exec `powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-Process python,pythonw -ErrorAction SilentlyContinue | Where-Object { $$_.Path -like '$INSTDIR\*' } | Stop-Process -Force"`
  Pop $0
  Sleep 800
!macroend

Section "Chrono Trade" Principal
  !insertmacro FecharApp
  SetOutPath "$INSTDIR"
  ; atualização: tira a versão antiga do Python embutido antes de copiar a nova
  RMDir /r "$INSTDIR\python"
  File /r "${APP}\*.*"

  ; pasta de dados e .env da pessoa (não é apagada ao desinstalar)
  CreateDirectory "$PROFILE\.chronotrade"
  ${IfNot} ${FileExists} "$PROFILE\.chronotrade\.env"
    FileOpen $0 "$PROFILE\.chronotrade\.env" w
    FileWrite $0 "# Chrono Trade: configuracoes deste computador$\r$\nCHRONOTRADE_MODO=pessoal$\r$\nTRADINGAGENTS_LLM_PROVIDER=google$\r$\n"
    FileClose $0
  ${EndIf}
  ${If} $Chave != ""
    FileOpen $0 "$PROFILE\.chronotrade\.env" a
    FileSeek $0 0 END
    FileWrite $0 "$\r$\nGOOGLE_API_KEY=$Chave$\r$\n"
    FileClose $0
  ${EndIf}

  CreateShortcut "$DESKTOP\Chrono Trade.lnk" "$INSTDIR\Chrono Trade.exe" "" "$INSTDIR\icone.ico"
  CreateDirectory "$SMPROGRAMS\Chrono Trade"
  CreateShortcut "$SMPROGRAMS\Chrono Trade\Chrono Trade.lnk" "$INSTDIR\Chrono Trade.exe" "" "$INSTDIR\icone.ico"
  CreateShortcut "$SMPROGRAMS\Chrono Trade\Fechar o Chrono Trade.lnk" "$INSTDIR\python\pythonw.exe" '"$INSTDIR\Fechar.pyw"' "$INSTDIR\icone.ico"
  CreateShortcut "$SMPROGRAMS\Chrono Trade\Meus dados e chaves.lnk" "$PROFILE\.chronotrade"
  CreateShortcut "$SMPROGRAMS\Chrono Trade\Desinstalar.lnk" "$INSTDIR\Desinstalar.exe"

  WriteUninstaller "$INSTDIR\Desinstalar.exe"
  WriteRegStr HKCU "Software\ChronoTrade" "Pasta" "$INSTDIR"
  !define CHAVE_REG "Software\Microsoft\Windows\CurrentVersion\Uninstall\ChronoTrade"
  WriteRegStr HKCU "${CHAVE_REG}" "DisplayName" "Chrono Trade"
  WriteRegStr HKCU "${CHAVE_REG}" "DisplayVersion" "${VERSAO}"
  WriteRegStr HKCU "${CHAVE_REG}" "Publisher" "Marcelo Mekaro"
  WriteRegStr HKCU "${CHAVE_REG}" "DisplayIcon" "$INSTDIR\icone.ico"
  WriteRegStr HKCU "${CHAVE_REG}" "UninstallString" '"$INSTDIR\Desinstalar.exe"'
  WriteRegStr HKCU "${CHAVE_REG}" "URLInfoAbout" "https://wa.me/5519999650436"
  WriteRegDWORD HKCU "${CHAVE_REG}" "NoModify" 1
  WriteRegDWORD HKCU "${CHAVE_REG}" "NoRepair" 1
SectionEnd

Section "Uninstall"
  !insertmacro FecharApp
  Delete "$DESKTOP\Chrono Trade.lnk"
  RMDir /r "$SMPROGRAMS\Chrono Trade"
  RMDir /r "$INSTDIR"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ChronoTrade"
  DeleteRegKey HKCU "Software\ChronoTrade"
  MessageBox MB_OK "Chrono Trade removido. A sua carteira e as chaves continuam em $PROFILE\.chronotrade (apague a pasta se quiser)."
SectionEnd
