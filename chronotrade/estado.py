"""Estado compartilhado entre as páginas: a carteira aberta e os dados de mercado."""

from __future__ import annotations

import copy
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from chronotrade import carteira as cart, licenca
from chronotrade.mercado import DadosAtivo, carregar_ativo


def modo_demo() -> bool:
    if "demo" not in st.session_state:
        st.session_state.demo = os.environ.get("CHRONOTRADE_DEMO", "").lower() in ("1", "true", "sim")
    return st.session_state.demo


# ---------------------------------------------------------------------------
# Plano de acesso
# ---------------------------------------------------------------------------


def licenca_atual() -> licenca.Licenca | None:
    return st.session_state.get("licenca")


def plano_completo() -> bool:
    """No modo pessoal tudo é liberado; no modo assinatura, só com chave válida."""
    return not licenca.assinatura_ativa() or licenca_atual() is not None


def pasta() -> Path | None:
    """Onde os dados deste usuário ficam. None = não guardar (plano gratuito)."""
    if not licenca.assinatura_ativa():
        return cart.pasta_dados()
    lic = licenca_atual()
    if lic is None:
        return None
    destino = cart.pasta_dados() / "assinantes" / lic.id_usuario
    destino.mkdir(parents=True, exist_ok=True)
    return destino


def exigir_plano_completo(recurso: str) -> None:
    """Para a página quando o plano não cobre o recurso, mostrando o convite para assinar."""
    if not liberado(recurso):
        st.stop()


def liberado(recurso: str) -> bool:
    """True se o plano cobre o recurso; senão mostra o convite para assinar e devolve False."""
    if plano_completo():
        return True
    from chronotrade import tema

    preco = licenca.preco_divulgado()
    tema.fala(f"<b>{recurso}</b> faz parte do plano completo"
              f"{' (' + preco + ')' if preco else ''}. Com ele você também guarda a carteira, "
              "usa o Oráculo de IA e gera relatórios para imprimir.")
    if licenca.link_pagamento():
        st.link_button("Assinar o plano completo", licenca.link_pagamento(), type="primary")
    st.caption("Já assinou? Cole a sua chave de acesso na barra lateral.")
    return False


# ---------------------------------------------------------------------------
# Carteira
# ---------------------------------------------------------------------------


def _arquivo_carteira() -> Path | None:
    destino = pasta()
    return destino / "carteira.json" if destino else None


def carteira() -> cart.Carteira:
    if "carteira" not in st.session_state:
        arquivo = _arquivo_carteira()
        st.session_state.carteira = cart.Carteira.carregar(arquivo) if arquivo else cart.Carteira()
    return st.session_state.carteira


def recarregar_carteira() -> None:
    st.session_state.pop("carteira", None)


def usar_exemplo() -> None:
    st.session_state.carteira = copy.deepcopy(cart.EXEMPLO)


def pode_salvar() -> bool:
    return _arquivo_carteira() is not None


def salvar() -> bool:
    arquivo = _arquivo_carteira()
    if arquivo is None:
        return False
    carteira().salvar(arquivo)
    return True


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
