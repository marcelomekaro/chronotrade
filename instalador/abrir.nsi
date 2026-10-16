; "Chrono Trade.exe": o atalho que abre o app (chama o Python embutido, sem janela preta).
Unicode true
Name "Chrono Trade"
OutFile "${SAIDA}"
Icon "${ICONE}"
RequestExecutionLevel user
SilentInstall silent
Caption "Chrono Trade"
VIProductVersion "${VERSAO}.0"
VIAddVersionKey "ProductName" "Chrono Trade"
VIAddVersionKey "CompanyName" "Marcelo Mekaro"
VIAddVersionKey "FileDescription" "Chrono Trade: buy and hold diário"
VIAddVersionKey "FileVersion" "${VERSAO}"
VIAddVersionKey "LegalCopyright" "Marcelo Mekaro"
Section
  Exec '"$EXEDIR\python\pythonw.exe" "$EXEDIR\ChronoTrade.pyw"'
SectionEnd
