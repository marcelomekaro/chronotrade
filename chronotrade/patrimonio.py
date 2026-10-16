"""Crescimento do patrimônio: uma foto por dia (tirada pelo agente Sentinela ou ao abrir o app).

Cada foto guarda o patrimônio, o quanto foi investido (custo) e a renda de proventos. Com isso dá para separar
o que cresceu por **aportes** (dinheiro novo) do que cresceu por **valorização e proventos** (o dinheiro trabalhando).
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import pandas as pd

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS patrimonio_diario (
    email TEXT NOT NULL,
    dia TEXT NOT NULL,
    patrimonio REAL NOT NULL,
    investido REAL NOT NULL,
    caixa REAL NOT NULL DEFAULT 0,
    renda_12m REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (email, dia)
);
"""


@dataclass
class Crescimento:
    serie: pd.DataFrame          # dia, patrimonio, investido, caixa, renda_12m, ganho
    inicio: float
    fim: float
    aportes: float               # quanto entrou de dinheiro novo no período
    trabalho: float              # quanto o dinheiro rendeu sozinho (valorização + proventos guardados)
    variacao: float | None       # variação do patrimônio no período
    rentabilidade: float | None  # rendimento descontando os aportes (aproximado, método de Dietz)
    meses: pd.DataFrame          # mes, patrimonio, aportes, trabalho


class Patrimonio:
    def __init__(self, caminho: Path):
        self.caminho = Path(caminho)
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        with self._con() as con:
            con.executescript(_ESQUEMA)

    @contextmanager
    def _con(self):
        con = sqlite3.connect(self.caminho, timeout=10)
        con.row_factory = sqlite3.Row
        try:
            yield con
            con.commit()
        finally:
            con.close()

    def registrar(self, email: str, patrimonio: float, investido: float, caixa: float = 0.0, renda_12m: float = 0.0,
                  dia: date | None = None) -> None:
        """Guarda (ou atualiza) a foto do dia."""
        dia = dia or date.today()
        with self._con() as con:
            con.execute("INSERT INTO patrimonio_diario VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(email, dia) DO UPDATE SET "
                        "patrimonio = excluded.patrimonio, investido = excluded.investido, caixa = excluded.caixa, "
                        "renda_12m = excluded.renda_12m",
                        (email, dia.isoformat(), round(patrimonio, 2), round(investido, 2), round(caixa, 2),
                         round(renda_12m, 2)))

    def serie(self, email: str, desde: date | None = None) -> pd.DataFrame:
        with self._con() as con:
            linhas = con.execute("SELECT dia, patrimonio, investido, caixa, renda_12m FROM patrimonio_diario "
                                 "WHERE email = ? AND dia >= ? ORDER BY dia",
                                 (email, (desde or date(1900, 1, 1)).isoformat())).fetchall()
        df = pd.DataFrame([dict(x) for x in linhas], columns=["dia", "patrimonio", "investido", "caixa", "renda_12m"])
        if not df.empty:
            df["dia"] = pd.to_datetime(df["dia"])
        return df

    def apagar_dados(self, email: str) -> None:
        with self._con() as con:
            con.execute("DELETE FROM patrimonio_diario WHERE email = ?", (email,))


def crescimento(serie: pd.DataFrame) -> Crescimento | None:
    """Separa aportes de rendimento. Aporte = aumento do dinheiro investido + caixa entre duas fotos."""
    if serie is None or len(serie) < 2:
        return None
    s = serie.sort_values("dia").reset_index(drop=True).copy()
    s["dinheiro"] = s["investido"] + s["caixa"]
    s["aporte"] = s["dinheiro"].diff().fillna(0.0)
    s["ganho"] = s["patrimonio"].diff().fillna(0.0) - s["aporte"]
    inicio, fim = float(s["patrimonio"].iloc[0]), float(s["patrimonio"].iloc[-1])
    aportes = float(s["aporte"].sum())
    trabalho = fim - inicio - aportes
    base = inicio + aportes / 2  # Dietz simples: o aporte ficou, em média, metade do período
    rent = trabalho / base if base > 0 else None
    s["mes"] = s["dia"].dt.strftime("%Y-%m")
    meses = s.groupby("mes").agg(patrimonio=("patrimonio", "last"), aportes=("aporte", "sum"),
                                 trabalho=("ganho", "sum")).reset_index()
    return Crescimento(s[["dia", "patrimonio", "investido", "caixa", "renda_12m", "ganho"]], inicio, fim, aportes,
                       trabalho, (fim / inicio - 1) if inicio else None, rent, meses)


def reconstruir(posicoes: list[tuple[str, float]], historicos: dict[str, pd.Series], dias: int = 365) -> pd.Series:
    """Estimativa do patrimônio no passado com as quantidades de HOJE (para quem acabou de começar a usar)."""
    partes = []
    for ticker, qtd in posicoes:
        h = historicos.get(ticker)
        if h is None or len(h) < 2:
            continue
        s = h.dropna()
        idx = pd.to_datetime(s.index)
        if getattr(idx, "tz", None) is not None:
            idx = idx.tz_localize(None)
        partes.append(pd.Series(s.values * qtd, index=idx.normalize()).groupby(level=0).last().rename(ticker))
    if not partes:
        return pd.Series(dtype=float)
    df = pd.concat(partes, axis=1).sort_index().ffill().dropna(how="any")
    return df.sum(axis=1).tail(dias)


def agora() -> datetime:
    return datetime.now()
