"""Estado compartilhado entre as páginas: a carteira aberta e os dados de mercado."""

from __future__ import annotations

import copy
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from chronotrade import carteira as cart, contas, planos
from chronotrade.calculos import brl
from chronotrade.mercado import DadosAtivo, carregar_ativo


def modo_demo() -> bool:
    if visitante() and not st.session_state.get("demo"):
        st.session_state.demo = True  # visitante sempre vê dados fictícios
    if "demo" not in st.session_state:
        st.session_state.demo = os.environ.get("CHRONOTRADE_DEMO", "").lower() in ("1", "true", "sim")
    return st.session_state.demo


# ---------------------------------------------------------------------------
# Contas e plano de acesso
# ---------------------------------------------------------------------------


@st.cache_resource
def banco() -> contas.Contas:
    """O banco de contas, aberto uma vez por servidor."""
    b = contas.Contas(cart.pasta_dados() / "contas.db")
    b.garantir_admin(os.environ.get("CHRONOTRADE_ADMIN_SENHA"))
    return b


def servidor() -> bool:
    return contas.modo_servidor()


def usuario() -> contas.Usuario | None:
    """A conta conectada, lida de novo do banco a cada tela para refletir o que o admin mudou."""
    email = st.session_state.get("email")
    return banco().buscar(email) if email else None


def visitante() -> bool:
    return bool(st.session_state.get("visitante"))


def config_loja() -> dict[str, str]:
    return banco().config() if servidor() else dict(contas.CONFIG_PADRAO)


def conectar(u: contas.Usuario, lembrar: bool) -> None:
    for chave in ("visitante", "carteira", "demo"):
        st.session_state.pop(chave, None)
    st.session_state.email = u.email
    if lembrar:
        st.query_params["s"] = banco().criar_sessao(u.email)


def restaurar_sessao() -> None:
    """Entra de novo sozinho quando o endereço tem um token de "manter conectado" válido."""
    if st.session_state.get("email") or "s" not in st.query_params:
        return
    u = banco().sessao(st.query_params["s"])
    if u is None:
        del st.query_params["s"]
        return
    st.session_state.email = u.email


def sair() -> None:
    token = st.query_params.get("s")
    if token:
        banco().encerrar_sessao(token)
        del st.query_params["s"]
    for chave in ("email", "visitante", "carteira", "demo", "plano_aporte", "ultima_analise"):
        st.session_state.pop(chave, None)


def permite(recurso: str) -> bool:
    """Se a pessoa conectada pode usar o recurso. No modo pessoal tudo é liberado."""
    if not servidor():
        return True
    if visitante():  # o visitante conhece tudo com dados fictícios, menos o que gasta IA ou mexe em conta real
        return recurso not in ("oraculo", "corretora", "avisos_email", "avisos_whatsapp")
    u = usuario()
    return bool(u and u.libera(recurso))


def plano_atual() -> str:
    if not servidor():
        return "premium"
    u = usuario()
    return u.plano_efetivo if u else "basico"


def limite_ativos() -> int | None:
    if not servidor():
        return None
    return planos.LIMITES[plano_atual()].ativos


def pasta() -> Path | None:
    """Onde os dados deste usuário ficam. None = não guardar (visitante ou conta sem acesso)."""
    if not servidor():
        return cart.pasta_dados()
    u = usuario()
    if u is None or not u.pode_usar():
        return None
    destino = cart.pasta_dados() / "usuarios" / u.id_pasta
    destino.mkdir(parents=True, exist_ok=True)
    return destino


def exigir(recurso: str) -> None:
    """Para a página quando o plano não cobre o recurso, mostrando o convite para mudar de plano."""
    if not liberado(recurso):
        st.stop()


def liberado(recurso: str) -> bool:
    """True se o plano cobre o recurso; senão mostra o convite e devolve False."""
    if permite(recurso):
        return True
    from chronotrade import tema

    minimo = planos.plano_minimo(recurso)
    valor = planos.preco_mensal(config_loja(), minimo)
    tema.fala(f"<b>{planos.NOMES_RECURSOS[recurso]}</b> faz parte do plano <b>{planos.NOMES[minimo]}</b>, "
              f"a partir de {brl(valor)} por mês.")
    if visitante():
        st.caption("Crie a sua conta na tela de entrada (botão na barra lateral).")
    else:
        st.page_link("paginas/conta.py", label="Ver planos e mudar de plano", icon="💳")
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


# ---------------------------------------------------------------------------
# Avisos e agente Sentinela
# ---------------------------------------------------------------------------


@st.cache_resource
def caixa_avisos():
    from chronotrade.avisos import CaixaDeAvisos

    return CaixaDeAvisos(cart.pasta_dados() / "contas.db")


def email_avisos() -> str:
    """De quem são os avisos desta sessão."""
    if not servidor():
        from chronotrade.agentes.sentinela import EMAIL_LOCAL

        return EMAIL_LOCAL
    u = usuario()
    if u is not None:
        return u.email
    if "id_visitante" not in st.session_state:
        import uuid

        st.session_state.id_visitante = uuid.uuid4().hex[:12]
    return f"visitante:{st.session_state.id_visitante}"


def rodar_sentinela_agora() -> dict:
    """Pede ao Sentinela uma dica já, com a carteira aberta na tela (mesmo a de exemplo)."""
    from chronotrade.agentes import sentinela

    c = carteira()
    if not (c.posicoes or c.observar):
        return {"dicas": 0}
    plano = plano_atual() if not visitante() else "medio"
    dica = sentinela.montar_dica(c, ativo, usar_tecnica=permite("tecnica"))
    texto = sentinela.redigir_com_ia(dica) if (not visitante() and planos.nivel(plano) >= 1) else None
    u = usuario() if servidor() else None
    pessoa = sentinela.Pessoa(email_avisos(), u.nome if u else "", plano, pasta() or cart.pasta_dados(),
                              u.whatsapp if u else "", bool(u and u.aviso_email), bool(u and u.aviso_whatsapp))
    sentinela._entregar(caixa_avisos(), pessoa, "sentinela", dica.titulo, texto or dica.texto,
                        canais=u is not None)
    return {"dicas": 1}


@st.cache_resource
def iniciar_agente() -> bool:
    """Liga o Sentinela em segundo plano uma vez por servidor (desligue com CHRONOTRADE_AGENTE_AUTOMATICO=0)."""
    from chronotrade.agentes import sentinela

    return sentinela.iniciar_automatico()
