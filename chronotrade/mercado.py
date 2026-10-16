"""Dados de mercado do Chrono Trade.

Cotações, histórico, proventos e indicadores vêm do Yahoo Finance (gratuito, via
yfinance). O modo demonstração gera séries fictícias determinísticas, para ver a
interface sem internet; tudo que sai dele é marcado como fictício.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

_SEM_SUFIXO = re.compile(r"^[A-Z]{4}\d{1,2}[A-Z]?$")


def normalizar_ticker(ticker: str) -> str:
    """'petr4' → 'PETR4.SA'. Tickers com sufixo (AAPL, BTC-USD, ^BVSP) ficam como estão."""
    t = (ticker or "").strip().upper()
    if not t:
        return t
    if _SEM_SUFIXO.match(t):
        return f"{t}.SA"
    return t


def ticker_curto(ticker: str) -> str:
    """'PETR4.SA' → 'PETR4', para exibir."""
    return ticker[:-3] if ticker.upper().endswith(".SA") else ticker


def parece_fii(ticker: str) -> bool:
    """Fundos imobiliários e units costumam terminar em 11; serve só como palpite inicial."""
    return ticker_curto(ticker).endswith("11")


@dataclass
class DadosAtivo:
    ticker: str
    nome: str = ""
    setor: str = ""
    preco: float | None = None
    fechamento_anterior: float | None = None
    lpa: float | None = None          # lucro por ação
    vpa: float | None = None          # valor patrimonial por ação
    historico: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))
    dividendos: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))
    proximo_provento: tuple | None = None  # (data com, valor) quando já anunciado
    fonte: str = "yahoo"              # "yahoo", "demo" ou "indisponivel"
    erro: str = ""

    @property
    def variacao_dia(self) -> float | None:
        if self.preco and self.fechamento_anterior:
            return self.preco / self.fechamento_anterior - 1
        return None

    @property
    def ok(self) -> bool:
        return self.preco is not None


def _numero(valor) -> float | None:
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return None
    return v if np.isfinite(v) else None


def carregar_ativo(ticker: str, demo: bool = False) -> DadosAtivo:
    ticker = normalizar_ticker(ticker)
    if demo:
        return _ativo_demo(ticker)
    try:
        import yfinance as yf

        ativo = yf.Ticker(ticker)
        hist = ativo.history(period="5y", auto_adjust=False)
        fechamento = hist["Close"].dropna() if not hist.empty else pd.Series(dtype=float)
        dividendos = ativo.dividends if ativo.dividends is not None else pd.Series(dtype=float)
        try:
            info = ativo.info or {}
        except Exception:  # o Yahoo às vezes falha só nesta parte
            info = {}
        if fechamento.empty:
            return DadosAtivo(ticker=ticker, fonte="indisponivel",
                              erro="O Yahoo Finance não devolveu cotações para este ticker.")
        return DadosAtivo(
            ticker=ticker,
            nome=info.get("longName") or info.get("shortName") or ticker_curto(ticker),
            setor=info.get("sector") or "",
            preco=float(fechamento.iloc[-1]),
            fechamento_anterior=float(fechamento.iloc[-2]) if len(fechamento) > 1 else None,
            lpa=_numero(info.get("trailingEps")),
            vpa=_numero(info.get("bookValue")),
            historico=fechamento,
            dividendos=dividendos,
            proximo_provento=_proximo(info),
            fonte="yahoo",
        )
    except Exception as exc:
        return DadosAtivo(ticker=ticker, fonte="indisponivel",
                          erro=f"Não foi possível buscar os dados ({type(exc).__name__}).")


def _proximo(info: dict):
    from chronotrade.agenda import proxima_data_anunciada

    return proxima_data_anunciada(info)


def carregar_indice(ticker: str = "^BVSP", demo: bool = False) -> pd.Series:
    """Histórico de fechamento de um índice, para comparar com a carteira."""
    return carregar_ativo(ticker, demo=demo).historico


# ---------------------------------------------------------------------------
# Modo demonstração (dados fictícios)
# ---------------------------------------------------------------------------

_PRECO_BASE = {
    "PETR4": 37.0, "VALE3": 60.0, "ITUB4": 35.0, "BBAS3": 27.0, "TAEE11": 36.0,
    "EGIE3": 42.0, "WEGE3": 50.0, "BBSE3": 34.0, "HGLG11": 160.0, "MXRF11": 10.0,
    "KNRI11": 140.0, "XPML11": 105.0, "BOVA11": 130.0, "IVVB11": 340.0, "^BVSP": 130000.0,
}


def _semente(ticker: str) -> int:
    return int(hashlib.md5(ticker.encode()).hexdigest()[:8], 16)


def _ativo_demo(ticker: str) -> DadosAtivo:
    curto = ticker_curto(ticker)
    rng = np.random.default_rng(_semente(ticker))
    base = _PRECO_BASE.get(curto, float(rng.uniform(15, 90)))
    fim = pd.Timestamp.today().normalize()
    dias = pd.bdate_range(end=fim, periods=5 * 252)
    deriva = 0.08 / 252 if not curto.startswith("^") else 0.06 / 252
    passos = rng.normal(deriva, 0.017, len(dias))
    serie = np.exp(np.cumsum(passos))
    historico = pd.Series(base * serie / serie[-1], index=dias)

    fii = parece_fii(ticker) and curto not in ("TAEE11", "BOVA11", "IVVB11")
    if curto.startswith("^") or curto in ("BOVA11", "IVVB11"):
        dividendos = pd.Series(dtype=float)
    elif fii:
        datas = pd.date_range(end=fim, periods=60, freq="MS") + pd.Timedelta(days=14)
        datas = datas[datas <= fim]
        valor = base * rng.uniform(0.0075, 0.0095)
        dividendos = pd.Series(valor * rng.uniform(0.9, 1.1, len(datas)), index=datas)
    else:
        datas = pd.date_range(end=fim, periods=20, freq="QS") + pd.Timedelta(days=20)
        datas = datas[datas <= fim]
        dy = rng.uniform(0.04, 0.11)
        dividendos = pd.Series(base * dy / 4 * rng.uniform(0.6, 1.4, len(datas)), index=datas)

    return DadosAtivo(
        ticker=ticker,
        nome=f"{curto} (dados fictícios)",
        setor="Fundo imobiliário" if fii else "Demonstração",
        preco=float(historico.iloc[-1]),
        fechamento_anterior=float(historico.iloc[-2]),
        lpa=None if fii else round(base * rng.uniform(0.06, 0.16), 2),
        vpa=None if fii else round(base * rng.uniform(0.5, 1.2), 2),
        historico=historico,
        dividendos=dividendos,
        fonte="demo",
    )


# ---------------------------------------------------------------------------
# Cotação ao vivo (carteiras virtuais): preço de agora, com cache curto
# ---------------------------------------------------------------------------

_AO_VIVO: dict[str, tuple[float, float, float | None]] = {}   # ticker -> (quando, preço, variação do dia)
AO_VIVO_CACHE = 20.0
_BASE_DEMO: dict[tuple[str, str], DadosAtivo] = {}


def preco_ao_vivo(ticker: str, demo: bool = False, agora: float | None = None) -> tuple[float | None, float | None]:
    """(preço, variação do dia). No Yahoo vem com o atraso da B3 (uns 15 minutos); no modo demonstração o preço
    oscila de leve a cada poucos segundos, para a tela parecer um pregão de verdade."""
    import math
    import time

    ticker = normalizar_ticker(ticker)
    agora = agora if agora is not None else time.time()
    if demo:
        chave = (ticker, time.strftime("%Y-%m-%d"))
        if chave not in _BASE_DEMO:
            _BASE_DEMO[chave] = _ativo_demo(ticker)
        base = _BASE_DEMO[chave]
        s = _semente(ticker)
        onda = 0.006 * math.sin(agora / 47 + s % 97) + 0.003 * math.sin(agora / 9 + s % 13)
        preco = round(base.preco * (1 + onda), 2)
        anterior = base.fechamento_anterior or base.preco
        return preco, preco / anterior - 1
    guardado = _AO_VIVO.get(ticker)
    if guardado and agora - guardado[0] < AO_VIVO_CACHE:
        return guardado[1], guardado[2]
    try:
        import yfinance as yf

        info = yf.Ticker(ticker).fast_info
        preco = _numero(info.get("last_price") or info.get("lastPrice"))
        anterior = _numero(info.get("previous_close") or info.get("previousClose"))
    except Exception:
        preco = anterior = None
    if not preco:
        d = carregar_ativo(ticker)
        preco, anterior = d.preco, d.fechamento_anterior
    if not preco:
        return None, None
    variacao = preco / anterior - 1 if anterior else None
    _AO_VIVO[ticker] = (agora, float(preco), variacao)
    return float(preco), variacao
