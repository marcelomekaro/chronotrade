#!/bin/sh
# Início do Chrono Trade no Render: o agente Sentinela e o app no mesmo serviço (os dois usam o disco /data).
set -e
mkdir -p "${CHRONOTRADE_HOME:-/data}"
echo "Chrono Trade: dados em ${CHRONOTRADE_HOME:-/data}, porta ${PORT:-10000}"

# Agente Sentinela sempre ligado (dicas, alertas, datas com, DARF, pagamentos PIX), mesmo sem ninguém no app.
# Se ele cair, volta sozinho depois de 30 segundos.
( while true; do chronotrade-agente loop || true; echo "Sentinela parou; religando em 30 s"; sleep 30; done ) &

# O app web (o agente já roda acima, então o app não liga outro).
export CHRONOTRADE_AGENTE_AUTOMATICO=0
exec chronotrade --server.port "${PORT:-10000}" --server.address 0.0.0.0 --server.headless true
