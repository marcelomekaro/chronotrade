"""Notícias: o que sai sobre os seus ativos, a B3, o mundo dos negócios e os seus canais do YouTube."""

import json

import streamlit as st

from chronotrade import compartilhar_whats, estado, noticias, tema
from chronotrade.mercado import ticker_curto

st.title("Notícias")
estado.exigir("noticias")
c = estado.carteira()
pasta = estado.pasta_social()
demo = estado.modo_demo()


@st.cache_data(ttl=600, show_spinner=False)
def _feed(endereco: str, fonte: str) -> list[noticias.Item]:
    return noticias.buscar(endereco, fonte)


def _mostrar(itens: list[noticias.Item], chave: str) -> None:
    if not itens:
        st.info("Nada chegou desta fonte agora. Confira a internet ou tente de novo em alguns minutos.")
        return
    for i, n in enumerate(itens):
        with st.container(border=True):
            quando = f"{n.data:%d/%m %H:%M}" if n.data else ""
            st.markdown(f"**[{n.titulo}]({n.link})**  \n<span style='color:var(--suave);font-size:.88rem'>"
                        f"{n.fonte}{', ' + quando if quando else ''}</span>", unsafe_allow_html=True)
            if n.resumo and n.resumo != n.titulo:
                st.caption(n.resumo)
            col1, col2 = st.columns([1, 1])
            with col1:
                compartilhar_whats.botao(f"{n.titulo}\n{n.link}", f"{chave}{i}", pasta)
            if estado.pode_conversar() and col2.button("Levar ao Pregão", key=f"pregao_{chave}{i}"):
                eu, nome = estado.identidade()
                apelido, avatar_json = estado.pregao().perfil(eu, nome)
                try:
                    estado.pregao().enviar("geral", eu, apelido, avatar_json, f"📰 {n.titulo} {n.link}"[:500])
                    st.toast("Notícia levada ao Pregão geral.")
                except Exception as erro:
                    st.toast(str(erro), icon="⚠️")


carteira_tab, mercado_tab, videos_tab = st.tabs(["Minha carteira", "Mercado e negócios", "Vídeos"])

with carteira_tab:
    tickers = [p.ticker for p in c.posicoes] + list(c.observar)
    if not tickers:
        tema.fala("Cadastre a carteira no Inventário para ver as notícias dos seus ativos.")
    else:
        escolhido = st.selectbox("Ativo", tickers, format_func=ticker_curto)
        itens = noticias.demo([escolhido]) if demo else _feed(f"google:{noticias.busca_do_ativo(escolhido)}",
                                                                  "Google Notícias")
        if demo:
            tema.aviso("Modo demonstração: manchetes de exemplo.")
        _mostrar(itens, f"cart_{escolhido}")

with mercado_tab:
    cfg = estado.config_loja()
    fontes = noticias.ler_fontes(cfg.get("fontes_noticias"))
    nome_fonte = st.radio("Fonte", [f[0] for f in fontes], horizontal=True)
    endereco = dict(fontes)[nome_fonte]
    _mostrar(noticias.demo([]) if demo else _feed(endereco, nome_fonte), f"merc_{nome_fonte}")

with videos_tab:
    arquivo = pasta / "canais_youtube.json" if pasta else None
    meus = json.loads(arquivo.read_text(encoding="utf-8")) if arquivo and arquivo.exists() else \
        st.session_state.get("canais_visitante", [])
    padrao = noticias.ler_canais(estado.config_loja().get("canais_youtube"))
    canais = padrao + [m for m in meus if m not in padrao]

    link_video = st.text_input("Assistir a um vídeo ou live (cole o link do YouTube)",
                               placeholder="https://www.youtube.com/watch?v=…")
    if noticias.id_video(link_video):
        st.video(link_video)
        compartilhar_whats.botao(f"Olha esse vídeo: {link_video}", "video_colado", pasta)

    with st.expander("Meus canais do YouTube"):
        st.caption("Cole o link do canal no formato youtube.com/channel/UC… (no canal: Compartilhar → Copiar ID do canal).")
        novo = st.text_input("Link ou ID do canal")
        if st.button("Adicionar canal") and novo.strip():
            meus = [*meus, novo.strip()]
            if arquivo:
                arquivo.write_text(json.dumps(meus, ensure_ascii=False), encoding="utf-8")
            else:
                st.session_state.canais_visitante = meus
            st.rerun()
        for canal in meus:
            st.markdown(f"- {canal}")

    if not canais:
        st.info("Adicione canais do YouTube para ver os vídeos novos aqui.")
    for canal in canais:
        videos = [v for v in _feed(canal, "YouTube") if v.video_id][:4]
        if videos:
            st.subheader(videos[0].fonte)
            colunas = st.columns(2)
            for i, v in enumerate(videos):
                with colunas[i % 2]:
                    st.video(f"https://www.youtube.com/watch?v={v.video_id}")
                    st.caption(v.titulo)

tema.legenda("Notícias de fontes externas, reunidas por RSS. O Chrono Trade não se responsabiliza pelo conteúdo "
             "de terceiros e nada aqui é recomendação de investimento.")
