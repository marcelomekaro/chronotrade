"""Agenda dos próximos proventos.

O Yahoo Finance guarda as datas "com" (data de corte) de cada provento pago. As
empresas costumam repetir os meses de pagamento ano após ano, então projetamos os
próximos 12 meses a partir do padrão dos últimos dois anos. Quando o Yahoo já
traz a próxima data anunciada, ela entra como "Confirmado".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

CONFIRMADO = "Confirmado"
PREVISTO = "Previsto"


@dataclass
class Evento:
    ticker: str
    data: date            # data com (quem tem a ação neste dia recebe)
    valor_por_cota: float
    quantidade: float
    situacao: str

    @property
    def total(self) -> float:
        return self.valor_por_cota * self.quantidade


def _serie(dividendos: pd.Series) -> pd.Series:
    if dividendos is None or len(dividendos) == 0:
        return pd.Series(dtype=float)
    s = dividendos.copy()
    indice = pd.DatetimeIndex(s.index)
    s.index = indice.tz_localize(None) if indice.tz is not None else indice
    return s.sort_index()


def prever(ticker: str, dividendos: pd.Series, quantidade: float, hoje: date | None = None,
           meses: int = 12, confirmado: tuple[date, float] | None = None) -> list[Evento]:
    """Os pagamentos esperados nos próximos ``meses`` meses."""
    hoje = hoje or date.today()
    s = _serie(dividendos)
    fim = pd.Timestamp(hoje) + pd.DateOffset(months=meses)
    eventos: list[Evento] = []
    if confirmado and confirmado[0] >= hoje:
        eventos.append(Evento(ticker, confirmado[0], confirmado[1], quantidade, CONFIRMADO))
    if s.empty:
        return eventos

    inicio = pd.Timestamp(hoje) - pd.DateOffset(years=2)
    recentes = s[s.index > inicio]
    if recentes.empty:
        return eventos
    # Para cada mês do ano, quantos dos últimos 2 anos pagaram nele e o valor médio.
    por_mes = recentes.groupby(recentes.index.month)
    for mes, grupo in por_mes:
        anos_com_pagamento = grupo.index.year.nunique()
        if anos_com_pagamento < 1:
            continue
        dia = int(round(grupo.index.day.to_series().median()))
        valor = float(grupo.groupby(grupo.index.year).sum().mean())
        for ano in (hoje.year, hoje.year + 1):
            try:
                quando = date(ano, int(mes), min(dia, 28))
            except ValueError:
                continue
            if hoje < quando <= fim.date():
                ja_confirmado = any(e.situacao == CONFIRMADO and e.data.year == quando.year
                                    and e.data.month == quando.month for e in eventos)
                if not ja_confirmado:
                    eventos.append(Evento(ticker, quando, valor, quantidade, PREVISTO))
    return sorted(eventos, key=lambda e: e.data)


def proxima_data_anunciada(info: dict) -> tuple[date, float] | None:
    """Lê a próxima data com e o valor, quando o Yahoo já os publicou."""
    bruto = (info or {}).get("exDividendDate")
    if not bruto:
        return None
    try:
        quando = pd.Timestamp(bruto, unit="s").date() if isinstance(bruto, (int, float)) else pd.Timestamp(bruto).date()
    except (ValueError, TypeError):
        return None
    valor = (info or {}).get("lastDividendValue") or (info or {}).get("dividendRate") or 0.0
    return quando, float(valor or 0.0)


def por_mes(eventos: list[Evento]) -> pd.DataFrame:
    """Total esperado por mês e por ativo, para o gráfico da agenda."""
    if not eventos:
        return pd.DataFrame(columns=["mes", "ticker", "total"])
    df = pd.DataFrame([{"mes": pd.Timestamp(e.data).to_period("M"), "ticker": e.ticker, "total": e.total}
                       for e in eventos])
    return df.groupby(["mes", "ticker"], as_index=False)["total"].sum().sort_values("mes")
