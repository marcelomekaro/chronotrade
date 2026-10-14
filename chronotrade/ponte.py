"""Conector do PC: lê as posições do MetaTrader 5 ou do Profit e envia ao Chrono Trade online.

Roda no Windows de quem investe, ao lado do terminal da corretora:

    chronotrade-ponte --servidor https://seu-dominio --token ct_xxx --plataforma mt5
    chronotrade-ponte ... --plataforma profit --tickers PETR4,TAEE11 --minutos 15

O jeito mais fácil é baixar o arquivo .bat pronto na tela Conexões (já vem com o
token). As senhas da Profit ficam só no seu PC (variáveis PROFIT_CHAVE,
PROFIT_USUARIO, PROFIT_SENHA, PROFIT_DLL ou digitadas na hora).
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import time
import urllib.error
import urllib.request

from chronotrade.corretoras import abrir
from chronotrade.corretoras.base import ErroCorretora, PosicaoCorretora


def ler_posicoes(plataforma: str, tickers: list[str], fabrica=abrir) -> list[PosicaoCorretora]:
    if plataforma == "mt5":
        login = os.environ.get("MT5_LOGIN")
        corretora = fabrica("mt5", None, caminho_terminal=os.environ.get("MT5_CAMINHO") or None,
                            login=int(login) if login and login.isdigit() else None,
                            senha=os.environ.get("MT5_SENHA") or None, servidor=os.environ.get("MT5_SERVIDOR") or None)
    elif plataforma == "profit":
        corretora = fabrica("profit", None,
                            chave_ativacao=os.environ.get("PROFIT_CHAVE") or getpass.getpass("Chave de ativação ProfitDLL: "),
                            usuario=os.environ.get("PROFIT_USUARIO") or input("Usuário Nelogica: "),
                            senha=os.environ.get("PROFIT_SENHA") or getpass.getpass("Senha Nelogica: "),
                            dll=os.environ.get("PROFIT_DLL") or None, tickers=tickers)
    else:
        raise ErroCorretora("Plataforma deve ser mt5 ou profit.")
    return corretora.posicoes()


def enviar(servidor: str, token: str, plataforma: str, posicoes: list[PosicaoCorretora], enviar_http=None) -> dict:
    corpo = json.dumps({"plataforma": plataforma, "posicoes": [
        {"ticker": p.ticker, "quantidade": p.quantidade, "preco_medio": p.preco_medio} for p in posicoes]}).encode()
    pedido = urllib.request.Request(servidor.rstrip("/") + "/api/ponte/posicoes", data=corpo, method="POST",
                                    headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"})
    if enviar_http:
        return enviar_http(pedido)
    try:
        with urllib.request.urlopen(pedido, timeout=30) as resposta:
            return json.loads(resposta.read())
    except urllib.error.HTTPError as erro:
        detalhe = erro.read().decode(errors="ignore")
        raise ErroCorretora(f"O servidor recusou ({erro.code}): {detalhe}") from erro


def uma_vez(args) -> None:
    tickers = [t.strip().upper() for t in (args.tickers or "").split(",") if t.strip()]
    posicoes = ler_posicoes(args.plataforma, tickers)
    status = enviar(args.servidor, args.token, args.plataforma, posicoes)
    print(f"[{time.strftime('%H:%M')}] Enviei {status.get('posicoes', len(posicoes))} posições; "
          f"{status.get('mudancas', 0)} mudaram na sua carteira.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Conector do PC do Chrono Trade (MetaTrader 5 / Profit).")
    parser.add_argument("--servidor", required=True, help="Endereço do Chrono Trade, ex.: https://chronotrade.com.br")
    parser.add_argument("--token", default=os.environ.get("CHRONOTRADE_TOKEN"), help="Token gerado na tela Conexões")
    parser.add_argument("--plataforma", choices=["mt5", "profit"], default="mt5")
    parser.add_argument("--tickers", default="", help="Profit: ativos a consultar, separados por vírgula")
    parser.add_argument("--minutos", type=int, default=0, help="Repetir a cada N minutos (0 = uma vez só)")
    args = parser.parse_args()
    if not args.token:
        parser.error("Informe --token (gere na tela Conexões > Conector do PC).")
    print("Conector do PC do Chrono Trade. Ele só LÊ posições; não envia ordens.")
    while True:
        try:
            uma_vez(args)
        except ErroCorretora as erro:
            print(f"Atenção: {erro}")
        except (urllib.error.URLError, OSError) as erro:
            print(f"Sem conexão com o servidor: {erro}")
        if args.minutos <= 0:
            break
        time.sleep(args.minutos * 60)


if __name__ == "__main__":
    main()
