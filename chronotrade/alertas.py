"""Alertas de preço e de zona de compra, conferidos pelo agente Sentinela a cada ciclo.

- Alerta de preço: "me avise quando TAEE11 ficar abaixo de R$ 34" (ou acima de um alvo).
- Zona de compra: o Sentinela guarda quais ativos do radar estavam na zona de compra e avisa
  quando um ativo novo entra nela, pelas regras que a própria pessoa configurou.
"""

from __future__ import annotations

import json
import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from chronotrade.mercado import normalizar_ticker, ticker_curto

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS alertas_preco (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL,
    ticker TEXT NOT NULL,
    tipo TEXT NOT NULL,
    preco REAL NOT NULL,
    criado_em TEXT NOT NULL,
    disparado_em TEXT
);
CREATE INDEX IF NOT EXISTS alertas_email ON alertas_preco (email);
"""
LIMITE_POR_PESSOA = 30


class ErroAlerta(ValueError):
    pass


@dataclass
class Alerta:
    id: int
    email: str
    ticker: str
    tipo: str          # "abaixo" ou "acima"
    preco: float
    criado_em: datetime
    disparado_em: datetime | None

    @property
    def descricao(self) -> str:
        return f"{ticker_curto(self.ticker)} {'abaixo' if self.tipo == 'abaixo' else 'acima'} de R$ {self.preco:,.2f}" \
            .replace(",", "X").replace(".", ",").replace("X", ".")


class Alertas:
    def __init__(self, caminho: Path):
        self.caminho = Path(caminho)
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

    @staticmethod
    def _alerta(ln) -> Alerta:
        return Alerta(ln["id"], ln["email"], ln["ticker"], ln["tipo"], ln["preco"], datetime.fromisoformat(ln["criado_em"]),
                      datetime.fromisoformat(ln["disparado_em"]) if ln["disparado_em"] else None)

    def criar(self, email: str, ticker: str, tipo: str, preco: float) -> Alerta:
        ticker = (ticker or "").strip().upper()
        if not re.match(r"^[A-Z0-9]{4,8}(\.SA)?$", ticker):
            raise ErroAlerta("Informe um ativo, como TAEE11.")
        if tipo not in ("abaixo", "acima"):
            raise ErroAlerta("Escolha abaixo ou acima.")
        if not preco or preco <= 0:
            raise ErroAlerta("Informe um preço maior que zero.")
        if len(self.listar(email)) >= LIMITE_POR_PESSOA:
            raise ErroAlerta(f"Limite de {LIMITE_POR_PESSOA} alertas. Apague algum antes.")
        agora = datetime.now().isoformat(timespec="seconds")
        with self._con() as con:
            cur = con.execute("INSERT INTO alertas_preco (email, ticker, tipo, preco, criado_em) VALUES (?, ?, ?, ?, ?)",
                              (email, normalizar_ticker(ticker), tipo, float(preco), agora))
            id_ = int(cur.lastrowid)
        return Alerta(id_, email, normalizar_ticker(ticker), tipo, float(preco), datetime.fromisoformat(agora), None)

    def listar(self, email: str) -> list[Alerta]:
        with self._con() as con:
            linhas = con.execute("SELECT * FROM alertas_preco WHERE email = ? ORDER BY disparado_em IS NOT NULL, id DESC",
                                 (email,)).fetchall()
        return [self._alerta(ln) for ln in linhas]

    def remover(self, email: str, id_: int) -> None:
        with self._con() as con:
            con.execute("DELETE FROM alertas_preco WHERE email = ? AND id = ?", (email, id_))

    def reativar(self, email: str, id_: int) -> None:
        with self._con() as con:
            con.execute("UPDATE alertas_preco SET disparado_em = NULL WHERE email = ? AND id = ?", (email, id_))

    def verificar(self, email: str, obter, agora: datetime | None = None) -> list[tuple[Alerta, float]]:
        """Confere os alertas ativos; os que bateram ficam marcados e voltam na lista."""
        agora = agora or datetime.now()
        disparados = []
        for a in [x for x in self.listar(email) if x.disparado_em is None]:
            preco = getattr(obter(a.ticker), "preco", None)
            if not preco:
                continue
            if (a.tipo == "abaixo" and preco <= a.preco) or (a.tipo == "acima" and preco >= a.preco):
                with self._con() as con:
                    con.execute("UPDATE alertas_preco SET disparado_em = ? WHERE id = ?",
                                (agora.isoformat(timespec="seconds"), a.id))
                disparados.append((a, float(preco)))
        return disparados


def zonas_novas(pasta: Path, na_zona: list[str]) -> list[str]:
    """Quais ativos entraram na zona de compra desde a última conferência (guarda o estado na pasta da pessoa)."""
    arquivo = pasta / "zona_compra.json"
    try:
        antes = set(json.loads(arquivo.read_text(encoding="utf-8"))) if arquivo.exists() else None
    except (OSError, ValueError):
        antes = None
    agora = sorted(set(na_zona))
    try:
        pasta.mkdir(parents=True, exist_ok=True)
        arquivo.write_text(json.dumps(agora), encoding="utf-8")
    except OSError:
        pass
    if antes is None:  # primeira vez: só guarda, sem avisar tudo de uma vez
        return []
    return [t for t in agora if t not in antes]
