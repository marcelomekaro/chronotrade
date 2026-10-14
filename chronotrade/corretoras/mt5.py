"""MetaTrader 5: posições e ordens numa corretora real.

Requisitos: Windows, o terminal MetaTrader 5 da sua corretora instalado, aberto e
logado, e o pacote ``MetaTrader5`` (pip install MetaTrader5). Nem toda corretora
oferece ações da B3 no MT5; confira com a sua.

Por segurança, mandar ordens reais fica DESLIGADO. Para ligar, o dono do
computador precisa pôr CHRONOTRADE_PERMITIR_ORDENS_REAIS=1 no .env, e cada ordem
ainda pede confirmação na tela.
"""

from __future__ import annotations

import os
from datetime import datetime

from chronotrade.corretoras.base import (
    Corretora,
    ErroCorretora,
    Ordem,
    PosicaoCorretora,
    ResultadoOrdem,
)
from chronotrade.mercado import ticker_curto


def ordens_reais_permitidas() -> bool:
    return os.environ.get("CHRONOTRADE_PERMITIR_ORDENS_REAIS", "").strip() in ("1", "sim", "true")


class CorretoraMT5(Corretora):
    nome = "MetaTrader 5"
    dinheiro_real = True

    def __init__(self, caminho_terminal: str | None = None, login: int | None = None,
                 senha: str | None = None, servidor: str | None = None):
        try:
            import MetaTrader5 as mt5
        except ImportError as erro:
            raise ErroCorretora("Instale o pacote MetaTrader5 (pip install MetaTrader5). Ele só funciona no Windows.") from erro
        self.mt5 = mt5
        argumentos = {}
        if caminho_terminal:
            argumentos["path"] = caminho_terminal
        if login:
            argumentos.update(login=int(login), password=senha or "", server=servidor or "")
        if not mt5.initialize(**argumentos):
            raise ErroCorretora(f"Não consegui abrir o MetaTrader 5: {mt5.last_error()}. "
                                "Abra o terminal da corretora e faça login.")

    def posicoes(self) -> list[PosicaoCorretora]:
        resultado = self.mt5.positions_get() or []
        return [PosicaoCorretora(p.symbol, float(p.volume), float(p.price_open)) for p in resultado]

    def saldo(self) -> float:
        conta = self.mt5.account_info()
        return float(conta.balance) if conta else 0.0

    def enviar(self, ordem: Ordem) -> ResultadoOrdem:
        ordem.validar()
        if not ordens_reais_permitidas():
            raise ErroCorretora("Ordens reais estão desligadas. Defina CHRONOTRADE_PERMITIR_ORDENS_REAIS=1 no .env "
                                "do seu computador para ligar.")
        mt5 = self.mt5
        simbolo = ticker_curto(ordem.ticker)
        if not mt5.symbol_select(simbolo, True):
            raise ErroCorretora(f"A corretora não oferece {simbolo} no MetaTrader 5.")
        tick = mt5.symbol_info_tick(simbolo)
        compra = ordem.lado == "compra"
        pedido = {
            "symbol": simbolo, "volume": float(ordem.quantidade),
            "type": mt5.ORDER_TYPE_BUY if compra else mt5.ORDER_TYPE_SELL,
            "comment": "Chrono Trade", "type_time": mt5.ORDER_TIME_DAY,
        }
        if ordem.tipo == "limitada":
            pedido.update(action=mt5.TRADE_ACTION_PENDING, price=float(ordem.preco_limite),
                          type=mt5.ORDER_TYPE_BUY_LIMIT if compra else mt5.ORDER_TYPE_SELL_LIMIT)
        else:
            pedido.update(action=mt5.TRADE_ACTION_DEAL, price=float(tick.ask if compra else tick.bid))
        resultado = mt5.order_send(pedido)
        ok = resultado is not None and resultado.retcode in (mt5.TRADE_RETCODE_DONE, mt5.TRADE_RETCODE_PLACED)
        return ResultadoOrdem(str(getattr(resultado, "order", "")), "executada" if ok else "recusada",
                              float(getattr(resultado, "price", 0) or 0) or None,
                              getattr(resultado, "comment", "") or str(mt5.last_error()), ordem)

    def ordens(self) -> list[ResultadoOrdem]:
        inicio = datetime.now().replace(hour=0, minute=0, second=0)
        historico = self.mt5.history_orders_get(inicio, datetime.now()) or []
        return [ResultadoOrdem(str(o.ticket), "executada", float(o.price_current or 0) or None, o.comment,
                               Ordem(o.symbol, "compra" if o.type in (0, 2) else "venda", int(o.volume_initial)))
                for o in historico]
