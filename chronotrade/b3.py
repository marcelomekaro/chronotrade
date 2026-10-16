"""Importar a posição da Área do Investidor da B3 (gratuita, oficial e com todas as corretoras juntas).

Na B3: investidor.b3.com.br → Extratos → Posição → baixar em Excel. O arquivo traz uma aba por tipo
(Ações, ETF, BDR, Fundos...) com "Código de Negociação" e "Quantidade". Ele não traz o preço médio,
então o app mantém o preço médio que você já tinha e, para ativos novos, usa o preço de fechamento como
ponto de partida (você ajusta depois no Inventário).
"""

from __future__ import annotations

import io
import re
import unicodedata

import pandas as pd

from chronotrade.corretoras.base import PosicaoCorretora
from chronotrade.mercado import normalizar_ticker

_TICKER = re.compile(r"^[A-Z]{4}\d{1,2}[A-Z]?$")


class ErroB3(ValueError):
    pass


def _norm(texto) -> str:
    t = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", t).strip()


def _numero(v) -> float | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    t = str(v).strip().replace("R$", "").replace(" ", "")
    if not t or t in ("-", "--"):
        return None
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


def _tabelas(dados: bytes, nome: str) -> list[pd.DataFrame]:
    nome = nome.lower()
    try:
        if nome.endswith((".xlsx", ".xls")):
            return list(pd.read_excel(io.BytesIO(dados), sheet_name=None, dtype=object).values())
        texto = dados.decode("utf-8-sig", errors="ignore")
        sep = ";" if texto.count(";") > texto.count(",") else ","
        return [pd.read_csv(io.StringIO(texto), sep=sep, dtype=object)]
    except Exception as erro:
        raise ErroB3(f"Não consegui ler o arquivo: {erro}. Baixe de novo em Extratos → Posição.") from erro


def ler_posicao(dados: bytes, nome: str) -> list[dict]:
    """Uma linha por ativo: ticker, quantidade (somando as corretoras) e preço de fechamento."""
    somas: dict[str, dict] = {}
    for tabela in _tabelas(dados, nome):
        colunas = {_norm(c): c for c in tabela.columns}
        cod = next((colunas[c] for c in colunas if "codigo de negociacao" in c), None)
        qtd = colunas.get("quantidade") or next((colunas[c] for c in colunas if c.startswith("quantidade")), None)
        fech = next((colunas[c] for c in colunas if "preco de fechamento" in c or "preco de fech" in c), None)
        if cod is None or qtd is None:
            continue
        for _, linha in tabela.iterrows():
            ticker = str(linha[cod] or "").strip().upper()
            q = _numero(linha[qtd])
            if not _TICKER.match(ticker) or not q:
                continue
            ticker = ticker[:-1] if ticker.endswith("F") and len(ticker) > 5 else ticker  # mercado fracionário
            item = somas.setdefault(ticker, {"ticker": ticker, "quantidade": 0.0, "fechamento": None})
            item["quantidade"] += q
            item["fechamento"] = item["fechamento"] or _numero(linha[fech]) if fech else item["fechamento"]
    if not somas:
        raise ErroB3("Não achei ativos no arquivo. Use o Excel de Extratos → Posição da Área do Investidor da B3.")
    return list(somas.values())


def para_posicoes(linhas: list[dict], carteira) -> tuple[list[PosicaoCorretora], list[str]]:
    """Converte para o formato das conexões. Mantém o preço médio que já existe na carteira."""
    atuais = {p.ticker: p for p in carteira.posicoes}
    posicoes, sem_preco_medio = [], []
    for ln in linhas:
        t = normalizar_ticker(ln["ticker"])
        if t in atuais:
            pm = atuais[t].preco_medio
        else:
            pm = ln["fechamento"] or 0.0
            sem_preco_medio.append(ln["ticker"])
        posicoes.append(PosicaoCorretora(ln["ticker"], ln["quantidade"], pm))
    return posicoes, sem_preco_medio
