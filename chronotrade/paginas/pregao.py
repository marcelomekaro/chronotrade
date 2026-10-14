"""Pregão: o salão virtual onde os investidores do Chrono Trade se encontram e trocam ideias."""

import html

import streamlit as st

from chronotrade import cena, compartilhar_whats, estado, pregao as pg, tema
from chronotrade.avatar import Avatar, img, sortear
from chronotrade.mercado import ticker_curto

st.title("Pregão")
estado.exigir("pregao")
sala_db = estado.pregao()
eu, meu_nome = estado.identidade()
apelido, avatar_json = sala_db.perfil(eu, meu_nome)
u = estado.usuario() if estado.servidor() else None
sou_admin = bool(u and u.admin)
demo = estado.modo_demo()

contagem = sala_db.contagem_por_sala()
sala = st.radio("Sala", list(pg.SALAS), horizontal=True, key="sala_pregao",
                format_func=lambda s: f"{pg.SALAS[s][0]} ({contagem.get(s, 0) + (5 if demo and s == 'geral' else 0)})")
titulo, subtitulo = pg.SALAS[sala]

with st.expander("📺 TV do Pregão"):
    url_tv = estado.config_loja().get("tv_pregao") or "https://www.youtube.com/live/XddD29d2j6w"
    st.video(url_tv)
    tema.legenda("O administrador troca o vídeo em Painel do admin → Loja e integrações.")


def _cotacoes():
    c = estado.carteira()
    tickers = ["^BVSP"] + [p.ticker for p in c.posicoes[:10]]
    linhas = []
    for t in tickers:
        d = estado.ativo(t)
        linhas.append(("IBOV" if t == "^BVSP" else ticker_curto(t), d.preco, d.variacao_dia))
    return linhas


@st.fragment(run_every="6s")
def ao_vivo():
    if estado.pode_conversar():
        sala_db.marcar_presenca(eu, sala, apelido, avatar_json)
    pessoas = [(p.email, p.apelido, p.avatar) for p in sala_db.online(sala)]
    falas = sala_db.ultima_fala(sala)
    mensagens = sala_db.listar(sala, 25)
    if demo and sala == "geral":
        p_demo, m_demo = pg.demo()
        pessoas += [(p.email, p.apelido + " (demo)", p.avatar) for p in p_demo]
        falas = {**{m.email: m.texto for m in m_demo}, **falas}
        mensagens = m_demo + mensagens
    st.html(cena.salao(pessoas, falas, eu, titulo, subtitulo, _cotacoes()))

    st.subheader("Conversa")
    if not mensagens:
        st.caption("Ninguém falou ainda nesta sala. Puxe o assunto!")
    for m in mensagens[-25:]:
        a = Avatar.de_json(m.avatar) or sortear(m.email)
        with st.container(border=True):
            col_a, col_t, col_b = st.columns([0.07, 0.83, 0.10], vertical_alignment="center")
            with col_a:
                st.html(img(a, 40, m.apelido))
            with col_t:
                tags = "".join(f' <span class="ct-selo" style="color:var(--ouro);font-size:.8rem;padding:0 6px">{t}</span>'
                               for t in m.tickers)
                st.markdown(f"<b>{html.escape(m.apelido)}</b> <span style='color:var(--suave);font-size:.85rem'>"
                            f"{m.criado_em:%H:%M}</span>{tags}<br>{html.escape(m.texto)}", unsafe_allow_html=True)
            with col_b, st.popover("⋯"):
                compartilhar_whats.botao(f"{m.apelido} no Pregão do Chrono Trade: {m.texto}", f"msg{m.id}",
                                         estado.pasta_social(), "Compartilhar")
                if m.id > 0 and m.email != eu and st.button("Denunciar", key=f"den{m.id}"):
                    sala_db.denunciar(m.id)
                    st.toast("Obrigado. A moderação vai olhar.")
                if sou_admin and m.id > 0:
                    if st.button("Apagar", key=f"apg{m.id}"):
                        sala_db.remover(m.id)
                        st.rerun(scope="fragment")
                    if st.button("Silenciar 24h", key=f"sil{m.id}"):
                        sala_db.silenciar(m.email)
                        st.toast(f"{m.apelido} silenciado por 24 horas.")


ao_vivo()

if estado.pode_conversar():
    texto = st.chat_input(f"Falar na {titulo} como {apelido}. Use $PETR4 para marcar um ativo.")
    if texto:
        try:
            sala_db.enviar(sala, eu, apelido, avatar_json, texto)
            st.rerun()
        except pg.ErroPregao as erro:
            st.toast(str(erro), icon="⚠️")
else:
    tema.aviso("Você está olhando como visitante. Crie a sua conta para conversar no Pregão.")

with st.expander("Meu avatar e apelido"):
    atual = Avatar.de_json(avatar_json)
    from chronotrade import avatar as av

    col1, col2 = st.columns([1, 2])
    with col2:
        novo_apelido = st.text_input("Apelido", value=apelido, max_chars=18)
        c1, c2 = st.columns(2)
        pele = c1.select_slider("Pele", options=av.PELES, value=atual.pele,
                                format_func=lambda c: str(av.PELES.index(c) + 1))
        roupa = c2.select_slider("Roupa", options=av.ROUPAS, value=atual.roupa,
                                 format_func=lambda c: str(av.ROUPAS.index(c) + 1))
        cabelo = c1.selectbox("Cabelo", av.CABELOS, index=av.CABELOS.index(atual.cabelo), format_func=av.NOMES.get)
        cor = c2.select_slider("Cor do cabelo", options=av.CORES_CABELO, value=atual.cor_cabelo,
                               format_func=lambda c: str(av.CORES_CABELO.index(c) + 1))
        acessorio = st.selectbox("Acessório", av.ACESSORIOS, index=av.ACESSORIOS.index(atual.acessorio),
                                 format_func=av.NOMES.get)
        novo = Avatar(pele, cabelo, cor, roupa, acessorio)
        if st.button("Salvar avatar", type="primary", disabled=not estado.pode_conversar()):
            try:
                sala_db.salvar_perfil(eu, novo_apelido, novo.json())
                st.success("Avatar salvo.")
                st.rerun()
            except pg.ErroPregao as erro:
                st.error(str(erro))
    with col1:
        st.html(f'<div style="padding:12px;text-align:center">{img(novo, 128, novo_apelido)}</div>')

tema.legenda("As mensagens do Pregão são opiniões pessoais dos participantes, não recomendações de investimento. "
             "Não compartilhe senhas nem dados pessoais. Conteúdo ofensivo, promessas de ganho e propaganda são removidos.")
