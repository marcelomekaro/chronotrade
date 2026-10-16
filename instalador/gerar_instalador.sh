#!/bin/sh
# Gera o instalador do Windows a partir do Linux ou do Mac (precisa de: python3 com pip e Pillow, makensis, curl).
#   sh instalador/gerar_instalador.sh                 -> instalador sem chave (para distribuir)
#   CHAVE_GEMINI=sua-chave sh instalador/gerar_instalador.sh  -> já vem com a chave preenchida (só para os SEUS PCs)
set -e
AQUI=$(cd "$(dirname "$0")" && pwd); RAIZ=$(dirname "$AQUI")
PY=${PYTHON:-python3}
VERSAO=$($PY -c "import re;print(re.search(r'__version__\s*=\s*\"([^\"]+)\"', open('$RAIZ/tradingagents/__init__.py').read()).group(1))" 2>/dev/null || echo 1.0.0)
VERSAO=$(echo "$VERSAO" | awk -F. '{printf "%d.%d.%d", $1, $2, $3}')
PY_URL=${PY_URL:-https://github.com/astral-sh/python-build-standalone/releases/download/20241016/cpython-3.12.7+20241016-x86_64-pc-windows-msvc-install_only.tar.gz}
B="$AQUI/build"; APP="$B/app"; DIST="$AQUI/dist"
rm -rf "$B" && mkdir -p "$APP" "$DIST" "$B/whl"

echo "1/5 Python 3.12 para Windows (portátil)"
curl -fsSL -o "$B/python.tar.gz" "$PY_URL"; tar xzf "$B/python.tar.gz" -C "$APP"

echo "2/5 Chrono Trade e dependências (versões para Windows)"
$PY -m pip wheel -q --no-deps -w "$B/whl" "$RAIZ"
$PY -m pip install -q --target "$APP/python/Lib/site-packages" --platform win_amd64 --python-version 3.12 \
    --implementation cp --abi cp312 --only-binary=:all: --no-compile "$B"/whl/*.whl
rm -rf "$APP/python/Lib/site-packages/bin"; find "$APP/python" -name "*.pdb" -delete

echo "3/5 Ícone, termos e atalhos"
$PY "$AQUI/preparar.py" "$APP"
makensis -V2 -DSAIDA="$APP/Chrono Trade.exe" -DICONE="$APP/icone.ico" -DVERSAO="$VERSAO" "$AQUI/abrir.nsi"

echo "4/5 Instalador"
EXTRA=""
if [ -n "$CHAVE_GEMINI" ]; then
  echo "   ATENÇÃO: a chave do Gemini vai DENTRO do instalador. Use só nos seus computadores; não distribua."
  EXTRA="-DCHAVE_GEMINI=$CHAVE_GEMINI"; SUFIXO="-PESSOAL"
fi
makensis -V2 -DSAIDA="$DIST/ChronoTrade-Setup-$VERSAO${SUFIXO}.exe" -DAPP="$APP" -DICONE="$APP/icone.ico" \
  -DVERSAO="$VERSAO" -DTERMOS="$B/termos.txt" $EXTRA "$AQUI/chronotrade.nsi"

echo "5/5 Pronto: $DIST/ChronoTrade-Setup-$VERSAO${SUFIXO}.exe"
ls -la "$DIST"
