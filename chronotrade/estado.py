"""Estado compartilhado entre as páginas: a carteira aberta e os dados de mercado."""

from __future__ import annotations

import copy
import os

import pandas as pd
import streamlit as st

from chronotrade import carteira as cart
from chronotrade.mercado import DadosAtivo, carregar_ativo


def modo_demo() -> bool:
    if "demo" not in st.session_state:
        st.session_state.demo = os.environ.get("CHRONOTRADE_DEMO", "").lower() in ("1", "true", "sim")
    return st.session_state.demo


def carteira() -> cart.Carteira:
    if "carteira" not in st.session_state:
        st.session_state.carteira = cart.Carteira.carregar()
    return st.session_state.carteira


def usar_exemplo() -> None:
    st.session_state.carteira = copy.deepcopy(cart.EXEMPLO)


def salvar() -> None:
    carteira().salvar()


class _SemDados(Exception):
    """Falha de busca: sai do cache para a próxima tentativa buscar de novo."""

    def __init__(self, dados: DadosAtivo):
        super().__init__(dados.erro)
        self.dados = dados


@st.cache_data(ttl=900, show_spinner=False)
def _ativo(ticker: str, demo: bool) -> DadosAtivo:
    dados = carregar_ativo(ticker, demo=demo)
    if not dados.ok:
        raise _SemDados(dados)
    return dados


def ativo(ticker: str) -> DadosAtivo:
    try:
        return _ativo(ticker, modo_demo())
    except _SemDados as falha:
        return falha.dados


def dados_da_carteira() -> dict[str, DadosAtivo]:
    c = carteira()
    if not c.posicoes:
        return {}
    with st.spinner("Buscando cotações e proventos…"):
        return {p.ticker: ativo(p.ticker) for p in c.posicoes}


def tabela_e_resumo() -> tuple[pd.DataFrame, cart.Resumo, dict[str, DadosAtivo]]:
    c = carteira()
    dados = dados_da_carteira()
    tabela = cart.montar_tabela(c, dados)
    return tabela, cart.resumir(tabela, c.caixa), dados


def avisar_fontes(dados: dict[str, DadosAtivo]) -> None:
    """Explica quando algum número não veio de dados reais."""
    from chronotrade import tema

    if modo_demo():
        tema.aviso("Modo demonstração ligado: cotações e proventos são fictícios. Desligue na barra lateral para ver dados reais.")
        return
    faltando = [d.ticker for d in dados.values() if not d.ok]
    if faltando:
        tema.aviso("Sem cotação para " + ", ".join(faltando) +
                   ". Usei o preço médio no lugar. Confira o ticker ou a sua internet.")
