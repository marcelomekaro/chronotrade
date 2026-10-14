"""Profit (Nelogica) pela ProfitDLL.

A ProfitDLL é o produto da Nelogica para programas conversarem com o Profit:
cotações e, no modo roteamento, ordens na corretora. Requisitos:
- licença da ProfitDLL contratada com a Nelogica (ela fornece a chave de ativação);
- Windows (a DLL é só para Windows) e o arquivo ProfitDLL64.dll;
- o pacote comunitário ``profitdll-wrapper`` (pip install profitdll-wrapper),
  que não é da Nelogica.

O wrapper ainda é novo: este adaptador chama os métodos documentados por nome e
avisa com clareza quando algum não existe na versão instalada. Valide primeiro
no simulador da Nelogica. Ordens reais seguem a mesma trava do MetaTrader 5
(CHRONOTRADE_PERMITIR_ORDENS_REAIS=1 e confirmação na tela).
"""

from __future__ import annotations

import os

from chronotrade.corretoras.base import (
    Corretora,
    ErroCorretora,
    Ordem,
    PosicaoCorretora,
    ResultadoOrdem,
)
from chronotrade.corretoras.mt5 import ordens_reais_permitidas
from chronotrade.mercado import ticker_curto


class CorretoraProfit(Corretora):
    nome = "Profit (Nelogica)"
    dinheiro_real = True

    def __init__(self, chave_ativacao: str | None = None, usuario: str | None = None, senha: str | None = None,
                 dll: str | None = None, corretora_id: int | None = None, tickers: list[str] | None = None,
                 modo: str = "routing"):
        try:
            from profitdll_wrapper import ProfitClient
        except ImportError as erro:
            raise ErroCorretora("Instale o conector da ProfitDLL: pip install profitdll-wrapper "
                                "(só funciona no Windows).") from erro
        if dll:
            os.environ["PROFITDLL_PATH"] = dll
        if not (chave_ativacao and usuario and senha):
            raise ErroCorretora("Informe a chave de ativação da ProfitDLL, o usuário e a senha da Nelogica.")
        argumentos = {"activation_key": chave_ativacao, "user": usuario, "password": senha, "mode": modo}
        if corretora_id:
            argumentos["broker_id"] = int(corretora_id)
        try:
            self.cliente = ProfitClient(**argumentos)
            entrar = getattr(self.cliente, "__enter__", None)
            if entrar:
                entrar()
        except Exception as erro:
            raise ErroCorretora(f"A ProfitDLL não conectou: {erro}. Confira a chave de ativação, "
                                "usuário, senha e se o arquivo ProfitDLL64.dll está no caminho informado.") from erro
        self.tickers = [ticker_curto(t) for t in (tickers or [])]

    def _metodo(self, nome: str):
        metodo = getattr(self.cliente, nome, None)
        if metodo is None:
            raise ErroCorretora(f"A versão instalada do profitdll-wrapper não tem '{nome}'. Atualize o pacote.")
        return metodo

    def posicoes(self) -> list[PosicaoCorretora]:
        resultado = []
        for ticker in self.tickers:
            try:
                pos = self._metodo("get_position")(ticker, exchange="B")
            except ErroCorretora:
                raise
            except Exception:
                continue
            quantidade = float(getattr(pos, "quantity", 0) or getattr(pos, "open_quantity", 0) or 0)
            preco = float(getattr(pos, "average_price", 0) or getattr(pos, "avg_price", 0) or 0)
            if quantidade:
                resultado.append(PosicaoCorretora(ticker, quantidade, preco))
        return resultado

    def saldo(self) -> float:
        for nome in ("get_balance", "get_account_balance"):
            metodo = getattr(self.cliente, nome, None)
            if metodo:
                try:
                    return float(metodo())
                except Exception:
                    break
        return 0.0

    def enviar(self, ordem: Ordem) -> ResultadoOrdem:
        ordem.validar()
        if not ordens_reais_permitidas():
            raise ErroCorretora("Ordens reais estão desligadas. Defina CHRONOTRADE_PERMITIR_ORDENS_REAIS=1 no .env "
                                "do seu computador para ligar.")
        ticker = ticker_curto(ordem.ticker)
        compra = ordem.lado == "compra"
        try:
            if ordem.tipo == "limitada":
                metodo = self._metodo("send_buy_order" if compra else "send_sell_order")
                resposta = metodo(ticker, exchange="B", price=float(ordem.preco_limite), quantity=int(ordem.quantidade))
            else:
                metodo = self._metodo("send_market_buy" if compra else "send_market_sell")
                resposta = metodo(ticker, exchange="B", quantity=int(ordem.quantidade))
        except ErroCorretora:
            raise
        except Exception as erro:
            return ResultadoOrdem("", "recusada", None, f"A Profit recusou: {erro}", ordem)
        return ResultadoOrdem(str(getattr(resposta, "id", resposta) or ""), "pendente", None,
                              "Ordem enviada à corretora pela Profit. Acompanhe no Profit.", ordem)

    def ordens(self) -> list[ResultadoOrdem]:
        return []
