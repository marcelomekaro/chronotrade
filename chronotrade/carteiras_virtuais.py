"""Carteiras virtuais: quantas a pessoa quiser, com o capital que quiser, operando a preço de mercado ou a um
preço escolhido ("e se eu tivesse comprado a R$ 30?"). Ninguém manda ordem para corretora: é treino e estudo.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

CAPITAL_MAXIMO = 100_000_000.0
CARTEIRAS_MAXIMO = 12
CORES = ["#34D399", "#38BDF8", "#F2C14E", "#A78BFA", "#FB7185", "#FFB347"]

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS cv_carteiras (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL,
    nome TEXT NOT NULL,
    capital REAL NOT NULL,
    objetivo TEXT DEFAULT '',
    cor TEXT DEFAULT '#34D399',
    taxa_corretagem REAL NOT NULL DEFAULT 0,
    criada_em TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cv_operacoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    carteira_id INTEGER NOT NULL,
    quando TEXT NOT NULL,
    ticker TEXT NOT NULL,
    classe TEXT NOT NULL DEFAULT 'Ação',
    lado TEXT NOT NULL,
    quantidade REAL NOT NULL,
    preco REAL NOT NULL,
    taxas REAL NOT NULL DEFAULT 0,
    origem TEXT NOT NULL DEFAULT 'mercado'
);
CREATE INDEX IF NOT EXISTS cv_operacoes_carteira ON cv_operacoes (carteira_id, id);
CREATE TABLE IF NOT EXISTS cv_historico (
    carteira_id INTEGER NOT NULL,
    dia TEXT NOT NULL,
    valor REAL NOT NULL,
    PRIMARY KEY (carteira_id, dia)
);
"""

EMOLUMENTOS = 0.0003  # B3, aproximado (negociação + liquidação)


class ErroCarteira(ValueError):
    pass


@dataclass
class CarteiraVirtual:
    id: int
    email: str
    nome: str
    capital: float
    objetivo: str
    cor: str
    taxa_corretagem: float
    criada_em: datetime


@dataclass
class OperacaoVirtual:
    id: int
    carteira_id: int
    quando: datetime
    ticker: str
    classe: str
    lado: str
    quantidade: float
    preco: float
    taxas: float
    origem: str          # "mercado" (preço da hora) ou "simulado" (preço escolhido)

    @property
    def valor(self) -> float:
        return self.quantidade * self.preco


@dataclass
class Posicao:
    ticker: str
    classe: str
    quantidade: float
    preco_medio: float


class CarteirasVirtuais:
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

    # -- carteiras ----------------------------------------------------------------------

    def criar(self, email: str, nome: str, capital: float, objetivo: str = "", taxa_corretagem: float = 0.0,
              agora: datetime | None = None) -> CarteiraVirtual:
        nome = (nome or "").strip()[:40]
        if len(nome) < 2:
            raise ErroCarteira("Dê um nome para a carteira.")
        if not 0 < capital <= CAPITAL_MAXIMO:
            raise ErroCarteira("O capital precisa ser maior que zero (até R$ 100 milhões).")
        if taxa_corretagem < 0:
            raise ErroCarteira("Corretagem não pode ser negativa.")
        if len(self.listar(email)) >= CARTEIRAS_MAXIMO:
            raise ErroCarteira(f"Você já tem {CARTEIRAS_MAXIMO} carteiras virtuais. Apague uma para criar outra.")
        agora = agora or datetime.now()
        cor = CORES[len(self.listar(email)) % len(CORES)]
        with self._con() as con:
            cur = con.execute("INSERT INTO cv_carteiras (email, nome, capital, objetivo, cor, taxa_corretagem, criada_em) "
                              "VALUES (?, ?, ?, ?, ?, ?, ?)",
                              (email, nome, float(capital), objetivo.strip()[:140], cor, float(taxa_corretagem),
                               agora.isoformat(timespec="seconds")))
            return self.buscar(int(cur.lastrowid), email, con)

    def _carteira(self, ln) -> CarteiraVirtual:
        return CarteiraVirtual(ln["id"], ln["email"], ln["nome"], ln["capital"], ln["objetivo"] or "", ln["cor"],
                               ln["taxa_corretagem"], datetime.fromisoformat(ln["criada_em"]))

    def buscar(self, carteira_id: int, email: str, con=None) -> CarteiraVirtual | None:
        if con is None:
            with self._con() as c:
                return self.buscar(carteira_id, email, c)
        ln = con.execute("SELECT * FROM cv_carteiras WHERE id = ? AND email = ?", (int(carteira_id), email)).fetchone()
        return self._carteira(ln) if ln else None

    def listar(self, email: str) -> list[CarteiraVirtual]:
        with self._con() as con:
            linhas = con.execute("SELECT * FROM cv_carteiras WHERE email = ? ORDER BY id", (email,)).fetchall()
        return [self._carteira(ln) for ln in linhas]

    def apagar(self, carteira_id: int, email: str) -> bool:
        with self._con() as con:
            cur = con.execute("DELETE FROM cv_carteiras WHERE id = ? AND email = ?", (int(carteira_id), email))
            if cur.rowcount:
                con.execute("DELETE FROM cv_operacoes WHERE carteira_id = ?", (int(carteira_id),))
                con.execute("DELETE FROM cv_historico WHERE carteira_id = ?", (int(carteira_id),))
            return cur.rowcount > 0

    def recomecar(self, carteira_id: int, email: str, capital: float | None = None) -> None:
        """Zera as operações (e opcionalmente muda o capital), mantendo o nome."""
        c = self.buscar(carteira_id, email)
        if c is None:
            raise ErroCarteira("Carteira não encontrada.")
        with self._con() as con:
            con.execute("DELETE FROM cv_operacoes WHERE carteira_id = ?", (c.id,))
            con.execute("DELETE FROM cv_historico WHERE carteira_id = ?", (c.id,))
            if capital:
                if not 0 < capital <= CAPITAL_MAXIMO:
                    raise ErroCarteira("O capital precisa ser maior que zero (até R$ 100 milhões).")
                con.execute("UPDATE cv_carteiras SET capital = ? WHERE id = ?", (float(capital), c.id))

    def apagar_dados(self, email: str) -> None:
        for c in self.listar(email):
            self.apagar(c.id, email)

    # -- operações ------------------------------------------------------------------------

    def operacoes(self, carteira_id: int) -> list[OperacaoVirtual]:
        with self._con() as con:
            linhas = con.execute("SELECT * FROM cv_operacoes WHERE carteira_id = ? ORDER BY quando, id",
                                 (int(carteira_id),)).fetchall()
        return [OperacaoVirtual(ln["id"], ln["carteira_id"], datetime.fromisoformat(ln["quando"]), ln["ticker"],
                                ln["classe"], ln["lado"], ln["quantidade"], ln["preco"], ln["taxas"], ln["origem"])
                for ln in linhas]

    def estado(self, carteira: CarteiraVirtual) -> tuple[float, dict[str, Posicao], float]:
        """(caixa, posições, resultado realizado) depois de todas as operações."""
        caixa = carteira.capital
        posicoes: dict[str, Posicao] = {}
        realizado = 0.0
        for op in self.operacoes(carteira.id):
            p = posicoes.setdefault(op.ticker, Posicao(op.ticker, op.classe, 0.0, 0.0))
            if op.lado == "compra":
                total = p.quantidade * p.preco_medio + op.valor + op.taxas
                p.quantidade += op.quantidade
                p.preco_medio = total / p.quantidade
                caixa -= op.valor + op.taxas
            else:
                realizado += op.quantidade * (op.preco - p.preco_medio) - op.taxas
                p.quantidade -= op.quantidade
                caixa += op.valor - op.taxas
                if p.quantidade <= 1e-9:
                    posicoes.pop(op.ticker)
        return round(caixa, 2), posicoes, round(realizado, 2)

    def operar(self, carteira_id: int, email: str, ticker: str, lado: str, quantidade: float, preco: float,
               classe: str = "Ação", origem: str = "mercado", quando: datetime | None = None) -> OperacaoVirtual:
        c = self.buscar(carteira_id, email)
        if c is None:
            raise ErroCarteira("Carteira não encontrada.")
        ticker = (ticker or "").strip().upper().replace(".SA", "")
        if not ticker:
            raise ErroCarteira("Informe o código do ativo.")
        if lado not in ("compra", "venda"):
            raise ErroCarteira("Escolha compra ou venda.")
        if quantidade <= 0 or quantidade != int(quantidade):
            raise ErroCarteira("A quantidade precisa ser um número inteiro maior que zero.")
        if not preco or preco <= 0:
            raise ErroCarteira(f"Sem preço para {ticker} agora. Informe um preço para simular.")
        taxas = round(c.taxa_corretagem + quantidade * preco * EMOLUMENTOS, 2)
        caixa, posicoes, _ = self.estado(c)
        if lado == "compra" and quantidade * preco + taxas > caixa + 0.005:
            raise ErroCarteira(f"Caixa insuficiente: a compra custa {_brl(quantidade * preco + taxas)} e a carteira tem "
                               f"{_brl(caixa)}.")
        if lado == "venda":
            tem = posicoes.get(ticker).quantidade if ticker in posicoes else 0
            if quantidade > tem + 1e-9:
                raise ErroCarteira(f"Você tem {tem:g} {ticker} nesta carteira.")
        quando = quando or datetime.now()
        with self._con() as con:
            cur = con.execute("INSERT INTO cv_operacoes (carteira_id, quando, ticker, classe, lado, quantidade, preco, "
                              "taxas, origem) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                              (c.id, quando.isoformat(timespec="seconds"), ticker, classe, lado, float(quantidade),
                               float(preco), taxas, origem))
        return OperacaoVirtual(int(cur.lastrowid), c.id, quando, ticker, classe, lado, float(quantidade), float(preco),
                               taxas, origem)

    # -- histórico do valor ----------------------------------------------------------------

    def registrar_valor(self, carteira_id: int, valor: float, dia: date | None = None) -> None:
        with self._con() as con:
            con.execute("INSERT INTO cv_historico VALUES (?, ?, ?) ON CONFLICT(carteira_id, dia) DO UPDATE SET "
                        "valor = excluded.valor", (int(carteira_id), (dia or date.today()).isoformat(), round(valor, 2)))

    def historico(self, carteira_id: int) -> list[tuple[date, float]]:
        with self._con() as con:
            linhas = con.execute("SELECT dia, valor FROM cv_historico WHERE carteira_id = ? ORDER BY dia",
                                 (int(carteira_id),)).fetchall()
        return [(date.fromisoformat(ln["dia"]), ln["valor"]) for ln in linhas]


def avaliar(caixa: float, posicoes: dict[str, Posicao], precos: dict[str, float]) -> tuple[float, list[dict]]:
    """Valor da carteira e linhas por ativo com os preços de agora."""
    linhas, total = [], caixa
    for p in posicoes.values():
        preco = precos.get(p.ticker) or p.preco_medio
        valor = p.quantidade * preco
        total += valor
        linhas.append({"ativo": p.ticker, "classe": p.classe, "quantidade": p.quantidade, "preco_medio": p.preco_medio,
                       "preco": preco, "valor": valor, "resultado": valor - p.quantidade * p.preco_medio,
                       "resultado_pct": preco / p.preco_medio - 1 if p.preco_medio else None})
    for ln in linhas:
        ln["peso"] = ln["valor"] / total if total else 0.0
    return round(total, 2), sorted(linhas, key=lambda x: -x["valor"])


def _brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
