"""Mestre do Pregão: o robô da sala. Responde comandos que começam com barra.

    /ajuda                   lista os comandos
    /cotacao TAEE11          preço e variação do dia
    /grafico TAEE11 6m       mostra o gráfico na sua mesa e no telão (1m, 6m, 1a, 5a)
    /proventos TAEE11        últimos proventos e a próxima data com anunciada
    /quem                    quem está na sala agora

O robô só mostra dados públicos e nunca recomenda compra ou venda.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from chronotrade.calculos import brl
from chronotrade.mercado import normalizar_ticker, ticker_curto
from chronotrade.pregao import PERIODOS

AJUDA = ("Comandos do Pregão: /cotacao TAEE11, /grafico TAEE11 6m (mostra o gráfico na sua mesa e no telão), "
         "/proventos TAEE11, /quem. Dados públicos, não é recomendação de investimento.")


@dataclass
class Resposta:
    acao: str                 # "bot" (o robô responde na sala) ou "grafico" (compartilhar gráfico)
    texto: str = ""
    dados: dict = field(default_factory=dict)


def _ticker(partes: list[str]) -> str | None:
    if len(partes) < 2:
        return None
    t = partes[1].strip().upper().lstrip("$")
    if t in ("IBOV", "IBOVESPA"):
        return "^BVSP"
    return t if t.replace("^", "").isalnum() and 4 <= len(t) <= 8 else None


def responder(texto: str, obter: Callable[[str], object], online: list[str] | None = None) -> Resposta | None:
    """None quando não é comando (mensagem normal)."""
    texto = (texto or "").strip()
    if not texto.startswith("/"):
        return None
    partes = texto.split()
    comando = partes[0].lower().lstrip("/")
    comando = {"cotação": "cotacao", "gráfico": "grafico", "help": "ajuda", "?": "ajuda"}.get(comando, comando)
    if comando == "ajuda":
        return Resposta("bot", AJUDA)
    if comando == "quem":
        nomes = online or []
        return Resposta("bot", f"{len(nomes)} na sala: " + ", ".join(nomes[:15]) + ("…" if len(nomes) > 15 else "")
                        if nomes else "Só você por aqui agora.")
    ticker = _ticker(partes)
    if comando in ("cotacao", "grafico", "proventos") and not ticker:
        return Resposta("bot", f"Use assim: /{comando} TAEE11")
    if comando == "grafico":
        periodo = partes[2].lower() if len(partes) > 2 and partes[2].lower() in PERIODOS else "6m"
        nota = " ".join(partes[3:] if len(partes) > 2 and partes[2].lower() in PERIODOS else partes[2:])
        return Resposta("grafico", dados={"ticker": ticker, "periodo": periodo, "nota": nota})
    if comando == "cotacao":
        d = obter(ticker if ticker.startswith("^") else normalizar_ticker(ticker))
        if not getattr(d, "preco", None):
            return Resposta("bot", f"Não achei cotação para {ticker} agora.")
        nome = "Ibovespa" if ticker == "^BVSP" else ticker_curto(ticker)
        valor = f"{d.preco:,.0f} pontos".replace(",", ".") if ticker == "^BVSP" else brl(d.preco)
        var = d.variacao_dia
        extra = f", {var * 100:+.2f}% no dia".replace(".", ",") if var is not None else ""
        return Resposta("bot", f"${nome}: {valor}{extra}.", {"ticker": ticker})
    if comando == "proventos":
        d = obter(normalizar_ticker(ticker))
        div = getattr(d, "dividendos", None)
        partes_txt = []
        if div is not None and len(div):
            ultimos = div.tail(3)
            partes_txt.append("últimos: " + "; ".join(f"{data:%d/%m/%Y} {brl(v)}" for data, v in ultimos.items()))
        prox = getattr(d, "proximo_provento", None)
        if prox:
            partes_txt.append(f"próxima data com anunciada: {prox[0]:%d/%m/%Y}, {brl(prox[1])} por cota")
        if not partes_txt:
            return Resposta("bot", f"Sem histórico de proventos para {ticker_curto(ticker)}.")
        return Resposta("bot", f"${ticker_curto(ticker)}, " + "; ".join(partes_txt) + ". Dados públicos, podem mudar.")
    return Resposta("bot", "Não conheço esse comando. " + AJUDA)
