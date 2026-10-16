"""Chrono Trade: a sua carteira de buy and hold, vista como uma viagem no tempo.

Rode com:  chronotrade      (ou: streamlit run chronotrade/app.py)

Dois modos, escolhidos no .env:
- CHRONOTRADE_MODO=pessoal (padrão): só você usa, sem login.
- CHRONOTRADE_MODO=servidor: online, com cadastro por e-mail, aprovação do
  administrador e assinaturas.
"""

from __future__ import annotations

import html
import sys
from pathlib import Path

# Permite rodar com "streamlit run chronotrade/app.py" mesmo sem instalar o pacote.
_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

import streamlit as st  # noqa: E402

from chronotrade import contas, estado, marca, tema  # noqa: E402

st.set_page_config(page_title="Chrono Trade", page_icon="⏳", layout="wide",
                   initial_sidebar_state="auto")
tema.aplicar()

_P = Path(__file__).parent / "paginas"
AVISOS = st.Page(_P / "avisos.py", title="Avisos", icon="🛡️")
PREGAO = st.Page(_P / "pregao.py", title="Pregão ao vivo", icon="🏛️")
PERFIL = st.Page(_P / "perfil.py", title="Meu perfil", icon="🧑")
SECOES = {
    "Carteira": [
        st.Page(_P / "portal.py", title="Portal", icon="🌀", default=True),
        st.Page(_P / "inventario.py", title="Inventário", icon="🎒"),
        st.Page(_P / "tesouro.py", title="Tesouro", icon="💰"),
        st.Page(_P / "agenda.py", title="Agenda de proventos", icon="📅"),
        st.Page(_P / "aporte.py", title="Próximo Aporte", icon="🧭"),
        st.Page(_P / "linha_do_tempo.py", title="Linha do Tempo", icon="⏳"),
    ],
    "Mercado": [
        st.Page(_P / "noticias.py", title="Notícias e vídeos", icon="📰"),
        st.Page(_P / "oraculo.py", title="Oráculo", icon="🔮"),
        st.Page(_P / "corretora.py", title="Corretora", icon="🔌"),
    ],
    "Comunidade": [
        PREGAO,
        st.Page(_P / "jarvis.py", title="Jarvis (voz)", icon="🎙️"),
        st.Page(_P / "compartilhar.py", title="Compartilhar", icon="📜"),
    ],
    "Ajustes": [
        PERFIL,
        st.Page(_P / "conexoes.py", title="Conexões", icon="🔗"),
        AVISOS,
    ],
}
APP = [p for paginas_secao in SECOES.values() for p in paginas_secao]
CONTA = st.Page(_P / "conta.py", title="Minha conta", icon="👤")
ADMIN = st.Page(_P / "admin.py", title="Painel do admin", icon="🛡️")
TERMOS = st.Page(_P / "termos.py", title="Termos e privacidade", icon="📄")
PORTARIA = st.Page(_P / "portaria.py", title="Entrar", icon="🌀", default=True)


def _paginas() -> list[st.Page]:
    """Quais telas esta pessoa pode abrir agora."""
    if not estado.servidor():
        return APP
    if estado.visitante():
        return APP + [CONTA, TERMOS]
    u = estado.usuario()
    if u is None:
        return [PORTARIA, TERMOS]
    if u.admin:
        return APP + [ADMIN, CONTA, TERMOS]
    if not u.pode_usar():  # pendente, vencida ou bloqueada: só a conta, para pagar
        conta = st.Page(_P / "conta.py", title="Minha conta", icon="👤", default=True)
        return [conta, TERMOS]
    return APP + [CONTA, TERMOS]


def _retrato_lateral() -> None:
    from chronotrade.avatar import retrato

    p = estado.perfil_atual()
    st.html(f'<div style="display:flex;align-items:center;gap:10px;margin:2px 0 6px">'
            f'{retrato(p.avatar, p.foto, p.email, 40, p.apelido)}<div style="font-size:.9rem;color:var(--suave)">'
            f'No Pregão: <b style="color:var(--ouro)">{html.escape(p.apelido)}</b></div></div>')


def _cartao_usuario() -> None:
    u = estado.usuario()
    if (not estado.servidor()) or (u is not None and u.pode_usar()):
        _retrato_lateral()
    if estado.visitante():
        st.markdown("**Modo visitante**  \nDados fictícios, nada é guardado.")
        if st.button("Criar conta ou entrar", type="primary", width="stretch"):
            estado.sair()
            st.rerun()
        return
    if u is None:
        return
    if u.admin:
        st.markdown(f"**Administrador**  \n{u.email}")
        pendentes = estado.banco().indicadores()["pendentes"]
        if pendentes:
            st.markdown(f"🔔 {pendentes} cadastro(s) aguardando liberação")
        return
    linha = f"**{u.nome.split()[0]}**  \nPlano {contas.PLANOS[u.plano]}"
    dias = u.dias_restantes()
    if u.status == "pendente":
        linha = f"**{u.nome.split()[0]}**  \nCadastro aguardando liberação"
    elif dias is not None:
        linha += f", até {u.validade:%d/%m}" if dias >= 0 else ", vencido"
    st.markdown(linha)
    if dias is not None and 0 <= dias <= 5:
        st.markdown(f"⏰ Faltam {dias} dias. Renove em Minha conta.")


if estado.servidor():
    estado.restaurar_sessao()
paginas = _paginas()
navegacao = st.navigation(paginas, position="hidden")

if paginas[0] is not PORTARIA:
    with st.sidebar:
        st.markdown(f'<div class="ct-marca">{marca.NOME}<small>{marca.SLOGAN_CURTO}</small></div>',
                    unsafe_allow_html=True)
        _cartao_usuario()
        st.write("")
        nao_lidos = estado.caixa_avisos().nao_lidos(estado.email_avisos()) if AVISOS in paginas else 0
        privadas = estado.pregao().nao_lidas_privadas(estado.identidade()[0]) if PREGAO in paginas else 0
        secoes = {nome: [p for p in lista if p in paginas] for nome, lista in SECOES.items()}
        extras = [p for p in paginas if p not in APP]
        if extras:
            secoes["Conta"] = extras
        for nome, lista in secoes.items():
            if not lista:
                continue
            st.markdown(f'<div class="ct-secao">{nome}</div>', unsafe_allow_html=True)
            for pagina in lista:
                if pagina is AVISOS and nao_lidos:
                    st.page_link(pagina, label=f"Avisos ({nao_lidos})")
                elif pagina is PREGAO and privadas:
                    st.page_link(pagina, label=f"Pregão ao vivo ({privadas} ✉️)")
                else:
                    st.page_link(pagina)
        st.divider()
        if APP[0] in paginas:
            estado.modo_demo()  # garante o valor inicial antes do botão
            st.toggle("Modo demonstração", key="demo", disabled=estado.visitante(),
                      help="Usa cotações e proventos fictícios. Útil para conhecer o app sem internet.")
        st.caption("Ferramenta de estudo. Não é recomendação de investimento. "
                   "As decisões e os riscos dos aportes são do investidor.")

if AVISOS in paginas:  # pop-up dos avisos novos (dica do Sentinela, data com, pagamento confirmado)
    for aviso in estado.caixa_avisos().para_mostrar(estado.email_avisos())[:3]:
        st.toast(f"**{aviso.titulo}**  \nVeja em Avisos.", icon="🛡️")

estado.iniciar_agente()
navegacao.run()
