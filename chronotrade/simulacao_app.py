"""Ponte entre o simulador (contas puras) e os dados do app (carteira, cotações, históricos)."""

from __future__ import annotations

import streamlit as st

from chronotrade import calculos, estado, simulador
from chronotrade.calculos import brl, pct
from chronotrade.mercado import normalizar_ticker, ticker_curto


def posicoes_estresse() -> list[dict]:
    """A carteira de hoje no formato do teste de estresse, com o beta de cada ativo."""
    tabela, _, dados = estado.tabela_e_resumo()
    if tabela.empty:
        return []
    ibov = estado.ativo("^BVSP").historico
    saida = []
    for _, ln in tabela.iterrows():
        d = dados.get(ln["ticker"])
        b = simulador.beta(d.historico if d else None, ibov) if ln["classe"] in ("Ação", "ETF") else 1.0
        saida.append({"ativo": ln["ativo"], "classe": ln["classe"], "valor": float(ln["valor"]),
                      "renda_12m": float(ln["renda_12m"]), "beta": b})
    return saida


def cenario(chave: str) -> simulador.Cenario:
    """Chave de CENARIOS ou 'livre:-0.3' (queda de 30% nas ações)."""
    if chave.startswith("livre:"):
        queda = float(chave.split(":", 1)[1])
        return simulador.cenario_livre(queda, queda * 0.6, queda * 0.4, corte_proventos=min(0.3, -queda / 2))
    return simulador.CENARIOS.get(chave, simulador.CENARIOS["covid"])


def frase_estresse(r: simulador.ResultadoEstresse, aporte: float) -> str:
    c = r.cenario
    abertura = "No seu cenário" if c.nome == "Cenário próprio" else f"Se vier uma crise como a de {c.quando} ({c.nome})"
    texto = (f"{abertura}, a sua carteira cairia cerca de {pct(-r.queda, 0)}, "
             f"de {brl(r.antes, 0)} para {brl(r.depois, 0)}. Os proventos iriam de {brl(r.renda_antes / 12, 0)} "
             f"para {brl(r.renda_depois / 12, 0)} por mês.")
    if aporte and r.ganho_aportando > 0:
        texto += (f" Mantendo o aporte de {brl(aporte, 0)} por mês, você compraria em média {pct(r.desconto_medio, 0)} "
                  f"mais barato e, na volta do mercado, teria {brl(r.ganho_aportando, 0)} a mais do que sem a crise.")
    return texto + " É uma simulação para estudo, não uma previsão."


def precos_e_proventos(tickers: list[str]) -> tuple[dict[str, float], dict[str, float], dict[str, str]]:
    """Preço atual, proventos de 12 meses por ação e nome, por código curto."""
    precos, prov, nomes = {}, {}, {}
    for tk in tickers:
        d = estado.ativo(normalizar_ticker(tk))
        curto = ticker_curto(tk)
        if d.preco:
            precos[curto] = float(d.preco)
        prov[curto] = calculos.proventos_12m(d.dividendos) if d.dividendos is not None else 0.0
        nomes[curto] = d.nome
    return precos, prov, nomes


def carteira_atual() -> list[dict]:
    c = estado.carteira()
    return [{"ativo": ticker_curto(p.ticker), "classe": p.classe, "quantidade": float(p.quantidade),
             "preco_medio": float(p.preco_medio)} for p in c.posicoes]


def classe_provavel(ticker: str) -> str:
    curto = ticker_curto(ticker)
    for p in estado.carteira().posicoes:
        if ticker_curto(p.ticker) == curto:
            return p.classe
    if curto.endswith("34") or curto.endswith("35"):
        return "BDR"
    if curto in ("BOVA11", "IVVB11", "SMAL11", "DIVO11", "HASH11", "XINA11"):
        return "ETF"
    return "FII" if curto.endswith("11") and curto not in ("TAEE11", "SAPR11", "KLBN11", "SANB11", "ALUP11", "ENGI11") else "Ação"


def simular(intencoes: list[simulador.Intencao]) -> simulador.ResultadoIntencao:
    atual = carteira_atual()
    tickers = list({p["ativo"] for p in atual} | {i.ticker for i in intencoes})
    precos, prov, _ = precos_e_proventos(tickers)
    return simulador.simular_intencoes(atual, intencoes, precos, prov, estado.carteira().caixa)


def frase_intencao(it: simulador.Intencao, r: simulador.ResultadoIntencao) -> str:
    antes, depois = r.resumo("antes"), r.resumo("depois")
    tk = it.ticker
    peso_antes = float(r.antes.loc[r.antes["ativo"] == tk, "peso"].sum()) if not r.antes.empty else 0.0
    peso_depois = float(r.depois.loc[r.depois["ativo"] == tk, "peso"].sum()) if not r.depois.empty else 0.0
    verbo = "Comprando" if it.lado == "compra" else "Vendendo"
    fluxo = f"saem {brl(abs(r.custo), 0)} do caixa" if r.custo >= 0 else f"entram {brl(abs(r.custo), 0)} no caixa"
    texto = (f"{verbo} {it.quantidade:g} {tk}, {fluxo}. {tk} passaria de {pct(peso_antes, 0)} para {pct(peso_depois, 0)} "
             f"da carteira e a renda de proventos iria de {brl(antes['renda_mes'], 0)} para {brl(depois['renda_mes'], 0)} por mês.")
    if r.avisos:
        texto += " " + " ".join(r.avisos)
    return texto


@st.cache_data(ttl=900, show_spinner=False)
def historicos(tickers: tuple[str, ...], demo: bool) -> dict:
    from chronotrade.mercado import carregar_ativo

    return {ticker_curto(t): carregar_ativo(t, demo=demo).historico for t in tickers}


def posicoes_de_tabela(tabela) -> list[dict]:
    """Linhas do simulador de intenções (ativo, classe, valor, renda_12m) → formato do estresse, com beta."""
    ibov = estado.ativo("^BVSP").historico
    saida = []
    for _, ln in tabela.iterrows():
        b = 1.0
        if ln["classe"] in ("Ação", "ETF"):
            b = simulador.beta(estado.ativo(normalizar_ticker(ln["ativo"])).historico, ibov)
        saida.append({"ativo": ln["ativo"], "classe": ln["classe"], "valor": float(ln["valor"]),
                      "renda_12m": float(ln["renda_12m"]), "beta": b})
    return saida
