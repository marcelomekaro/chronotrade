"""Pregão ao vivo: o salão onde os investidores andam, conversam e mostram os seus gráficos."""

import html
import re
import time
from datetime import timedelta

import plotly.graph_objects as go
import streamlit as st

from chronotrade import (
    avatar as av,
    compartilhar_whats,
    estado,
    pregao as pg,
    pregao_bot,
    salao,
    tema,
)
from chronotrade.mercado import normalizar_ticker, ticker_curto

st.title("Pregão ao vivo")
tema.subtitulo("Encontre quem investe como você: ande pelo salão, converse e mostre os seus gráficos.")
estado.exigir("pregao")
db = estado.pregao()
eu, meu_nome = estado.identidade()
perfil = db.perfil_completo(eu, meu_nome)
u = estado.usuario() if estado.servidor() else None
sou_admin = bool(u and u.admin)
demo = estado.modo_demo()
pode = estado.pode_conversar()

contagem = db.contagem_por_sala()
topo1, topo2 = st.columns([3, 2], vertical_alignment="bottom")
with topo1:
    sala = st.radio("Sala", list(pg.SALAS), horizontal=True, key="sala_pregao",
                    format_func=lambda s: f"{pg.SALAS[s][0]} ({contagem.get(s, 0) + (5 if demo and s == 'geral' else 0)})")
titulo, subtitulo = pg.SALAS[sala]
with topo2:
    b1, b2, b3 = st.columns(3)
    with b1.popover("📈 Gráfico", width="stretch", disabled=not pode, help="Mostre um gráfico na sua mesa e no telão"):
        c = estado.carteira()
        sugestoes = [ticker_curto(p.ticker) for p in c.posicoes] + [ticker_curto(t) for t in c.observar]
        escolhido = st.selectbox("Ativo", sugestoes + ["Outro…"], key="graf_ativo") if sugestoes else "Outro…"
        if escolhido == "Outro…":
            escolhido = st.text_input("Código do ativo", placeholder="TAEE11", key="graf_outro")
        periodo = st.segmented_control("Período", list(pg.PERIODOS), default="6m", key="graf_periodo",
                                       format_func=lambda k: pg.PERIODOS[k][0])
        nota = st.text_input("Comentário (opcional)", max_chars=200, key="graf_nota",
                             placeholder="Ex.: voltou para a média de 200 dias")
        if st.button("Mostrar no salão", type="primary", width="stretch"):
            try:
                db.compartilhar_grafico(sala, eu, perfil.apelido, perfil.avatar, escolhido or "", periodo or "6m", nota)
                st.toast("Gráfico na sua mesa e no telão.", icon="📈")
                estado.conquistar("primeiro_grafico")
            except pg.ErroPregao as erro:
                st.error(str(erro))
    b2.page_link("paginas/perfil.py", label="Perfil", icon="🧑")
    with b3.popover("📺 TV", width="stretch"):
        st.video(estado.config_loja().get("tv_pregao") or "https://www.youtube.com/live/XddD29d2j6w")
        tema.legenda("O administrador troca o vídeo no Painel do admin.")


@st.cache_data(ttl=600, show_spinner=False)
def _serie(ticker: str, periodo: str, demo_: bool):
    from chronotrade.mercado import carregar_ativo

    t = ticker if ticker.startswith("^") else normalizar_ticker(ticker)
    d = carregar_ativo(t, demo=demo_)
    s = salao.serie_grafico(d.historico, periodo)
    if s:
        s["ticker"] = ticker_curto(ticker) if not ticker.startswith("^") else "IBOV"
    return s


@st.cache_data(ttl=120, show_spinner=False, max_entries=200)
def _frase_publica(frase_id: int) -> dict | None:
    """Texto e áudio (data URI) de uma frase, guardados um pouco para não pesar a cada 3 segundos."""
    from chronotrade.audio import data_uri

    achada = estado.pregao().frase(frase_id)
    if not achada:
        return None
    frase, som = achada
    return {"texto": frase.texto, "audio": data_uri(som) if som else None}


def _cotacoes():
    c = estado.carteira()
    linhas = []
    for t in ["^BVSP"] + [p.ticker for p in c.posicoes[:10]]:
        d = estado.ativo(t)
        if d.preco:
            preco = f"{d.preco:,.0f}".replace(",", ".") if t == "^BVSP" else f"{d.preco:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            linhas.append(["IBOV" if t == "^BVSP" else ticker_curto(t), preco, d.variacao_dia or 0.0])
    return linhas


@st.fragment(run_every="3s")
def salao_ao_vivo():
    if pode:
        db.marcar_presenca(eu, sala, perfil.apelido, perfil.avatar)
    pessoas = db.online(sala)
    falas = db.ultima_fala(sala)
    quadros = {q.email: q for q in db.quadros(sala)}
    bios = db.perfis([p.email for p in pessoas])
    if demo and sala == "geral":
        p_demo, m_demo = pg.demo()
        pessoas += p_demo
        falas = {**{m.email: m.texto for m in m_demo}, **falas}
        quadros = {**{q.email: q for q in pg.demo_quadros()}, **quadros}
    if not any(p.email == eu for p in pessoas):  # visitante também aparece para si mesmo
        x, y = pg.lugar_inicial(eu)
        from datetime import datetime

        pessoas.append(pg.Participante(eu, perfil.apelido, perfil.avatar, datetime.now(), x, y, perfil.foto))
    ordem_falas = list(falas)[::-1]  # quem falou por último primeiro
    falas = {e: falas[e] for e in ordem_falas[:4]}
    mapa_ids = {}
    args = []
    for p in pessoas:
        pid = pg.id_publico(p.email)
        mapa_ids[pid] = p.email
        q = quadros.get(p.email)
        quadro = None
        if q:
            s = _serie(q.ticker, q.periodo, demo)
            if s:
                quadro = {**s, "nota": q.nota}
        a = av.Avatar.de_json(p.avatar) or av.sortear(p.email)
        args.append({"id": pid, "apelido": p.apelido, "avatar": av.data_uri(a, 64), "foto": p.foto,
                     "x": p.x, "y": p.y, "fala": falas.get(p.email, "")[:140], "quadro": quadro,
                     "rank": ordem_falas.index(p.email) if p.email in falas else None,
                     "bio": bios[p.email].bio if p.email in bios else "", "demo": p.email.startswith("demo-")})
    recente = max(quadros.values(), key=lambda q: q.criado_em, default=None)
    telao = None
    if recente:
        s = _serie(recente.ticker, recente.periodo, demo)
        if s:
            telao = {**s, "apelido": recente.apelido, "nota": recente.nota}
    if telao is None:
        s = _serie("^BVSP", "6m", demo)
        telao = {**s, "apelido": "Mercado", "nota": ""} if s else None
    agora = time.time()
    lista_emotes = []
    for e in db.emotes(sala):
        item = {"id": e.id, "pid": pg.id_publico(e.email), "tipo": e.tipo, "conteudo": e.conteudo,
                "idade": round(agora - e.criado_em.timestamp(), 1)}
        if e.tipo == "frase":
            dados_frase = _frase_publica(int(e.conteudo))
            if not dados_frase:
                continue
            item.update(dados_frase)
        lista_emotes.append(item)
    if demo and sala == "geral":
        lista_emotes += salao.emotes_demo(agora)
    ultima_frase = {e.email: int(e.conteudo) for e in db.emotes(sala, timedelta(minutes=3)) if e.tipo == "frase"}
    for item in args:
        email_item = mapa_ids.get(item["id"])
        if email_item in ultima_frase and email_item != eu:
            item["frase_id"] = ultima_frase[email_item]
    minhas = [{"id": f.id, "texto": f.texto, "audio": f.tem_audio} for f in db.frases(eu)] if pode else []
    acao = salao.mostrar(pg.id_publico(eu), titulo, subtitulo, args, telao, _cotacoes(),
                         "Clique no chão ou use as setas para andar. Teclas 1 a 0 soltam emojis; F abre as suas frases.",
                         key=f"salao_{sala}", emotes=lista_emotes, minhas_frases=minhas, pode=pode)
    if acao and acao.get("n") != st.session_state.get(f"salao_n_{sala}"):
        st.session_state[f"salao_n_{sala}"] = acao.get("n")
        if acao.get("acao") == "mover" and pode:
            db.mover(eu, sala, acao.get("x", 50), acao.get("y", 60))
        elif acao.get("acao") == "emoji" and pode:
            try:
                db.emote(sala, eu, acao.get("emoji", ""))
                estado.conquistar("primeiro_emoji")
            except pg.ErroPregao as erro:
                st.toast(str(erro), icon="⏳")
        elif acao.get("acao") == "frase" and pode:
            try:
                db.tocar_frase(sala, eu, int(acao.get("id", 0)))
            except (pg.ErroPregao, ValueError) as erro:
                st.toast(str(erro), icon="⏳")
        elif acao.get("acao") == "denunciar_frase" and pode:
            db.denunciar_frase(int(acao.get("id", 0)))
            st.toast("Obrigado. A moderação vai ouvir.", icon="🚩")
        elif acao.get("acao") == "privado" and acao.get("id") in mapa_ids:
            st.session_state.dm_com = mapa_ids[acao["id"]]
            st.session_state.ir_privadas = True
            st.rerun()


salao_ao_vivo()


# ---------------------------------------------------------------------------
# Conversa da sala e mensagens privadas
# ---------------------------------------------------------------------------

def _texto_html(texto: str) -> str:
    seguro = html.escape(texto)
    seguro = re.sub(r"@([\wÀ-ÿ.\-]{2,18})", r'<b style="color:var(--ouro)">@\1</b>', seguro)
    seguro = re.sub(r"\$([A-Z]{4}\d{1,2})\b", r'<b style="color:var(--ouro)">\1</b>', seguro)
    return seguro.replace("$", "&#36;").replace("\n", "<br>")


@st.dialog("Gráfico compartilhado", width="large")
def _ver_grafico(ticker: str, periodo: str, autor: str, nota: str):
    from chronotrade.mercado import carregar_ativo

    t = ticker if ticker.startswith("^") else normalizar_ticker(ticker)
    d = carregar_ativo(t, demo=demo)
    dias = pg.PERIODOS.get(periodo, pg.PERIODOS["6m"])[1]
    h = d.historico.dropna().tail(dias)
    if h.empty:
        st.info("Sem dados para esse ativo agora.")
        return
    fig = go.Figure(go.Scatter(x=h.index, y=h.values, mode="lines", name=ticker_curto(t), line=dict(width=2)))
    if len(d.historico) >= 200:
        mm = d.historico.rolling(200).mean().tail(dias)
        fig.add_trace(go.Scatter(x=mm.index, y=mm.values, mode="lines", name="Média 200 dias", line=dict(dash="dot")))
    fig.update_layout(height=360, title=f"{ticker_curto(t)}, {pg.PERIODOS.get(periodo, ('', 0))[0]}, por {autor}",
                      yaxis_tickprefix="R$ ")
    tema.mostrar(fig)
    if nota:
        st.markdown(f"> {_texto_html(nota)}", unsafe_allow_html=True)
    tema.legenda("Opinião de quem compartilhou. Não é recomendação de investimento.")


ABAS = {"sala": "💬 Conversa da sala", "privadas": "✉️ Mensagens privadas"}
nao_lidas = db.nao_lidas_privadas(eu)
if st.session_state.pop("ir_privadas", False):
    st.session_state.aba_pregao = "privadas"
aba = st.segmented_control("Ver", list(ABAS), key="aba_pregao", label_visibility="collapsed",
                           format_func=lambda k: ABAS[k] + (f" ({nao_lidas})" if k == "privadas" and nao_lidas else ""))
aba = aba or "sala"

if aba == "sala":
    @st.fragment(run_every="4s")
    def conversa():
        mensagens = db.listar(sala, 30)
        if demo and sala == "geral":
            mensagens = sorted(pg.demo()[1] + mensagens, key=lambda m: m.criado_em)
        if not mensagens:
            st.caption("Ninguém falou ainda nesta sala. Puxe o assunto! Dica: digite /ajuda para ver os comandos.")
        perfis = db.perfis(list({m.email for m in mensagens}))
        reacoes = db.reacoes([m.id for m in mensagens if m.id > 0])
        por_id = {m.id: m for m in mensagens}
        for m in mensagens[-30:]:
            robo = m.email == pg.BOT_EMAIL
            foto = perfis[m.email].foto if m.email in perfis else None
            retrato = ('<div style="font-size:30px;line-height:40px">🤖</div>' if robo else
                       av.retrato(m.avatar, foto, m.email, 40, m.apelido))
            with st.container(border=True):
                col_a, col_t, col_b = st.columns([0.07, 0.83, 0.10], vertical_alignment="top")
                with col_a:
                    st.html(retrato)
                with col_t:
                    citacao = ""
                    if m.resposta_a:
                        orig = por_id.get(m.resposta_a) or db.buscar_mensagem(m.resposta_a)
                        if orig:
                            citacao = (f'<div style="border-left:3px solid var(--suave);padding-left:8px;color:var(--suave);'
                                       f'font-size:.85rem;margin-bottom:4px">↪ {html.escape(orig.apelido)}: '
                                       f'{_texto_html(orig.texto[:90])}</div>')
                    cor = "var(--ouro)" if robo else "inherit"
                    chips = "".join(f'<span style="border:1px solid var(--borda,#3a4170);border-radius:12px;padding:0 7px;'
                                    f'margin-right:4px;font-size:.85rem">{e} {n}</span>' for e, n in reacoes.get(m.id, {}).items())
                    st.markdown(f'{citacao}<b style="color:{cor}">{html.escape(m.apelido)}</b> '
                                f'<span style="color:var(--suave);font-size:.85rem">{m.criado_em:%H:%M}</span><br>'
                                f'{_texto_html(m.texto)}' + (f'<div style="margin-top:4px">{chips}</div>' if chips else ""),
                                unsafe_allow_html=True)
                    if m.tipo == "grafico" and m.dados.get("ticker"):
                        s = _serie(m.dados["ticker"], m.dados.get("periodo", "6m"), demo)
                        if s:
                            st.html(salao.sparkline(s["serie"], 220, 50))
                with col_b, st.popover("⋯"):
                    if m.id > 0 and pode:
                        if st.button("↪ Responder", key=f"resp{m.id}", width="stretch"):
                            st.session_state.responder_a = m.id
                            st.rerun()
                        cols = st.columns(len(pg.REACOES))
                        for i, emoji in enumerate(pg.REACOES):
                            if cols[i].button(emoji, key=f"r{m.id}{i}"):
                                db.reagir(m.id, eu, emoji)
                                st.rerun(scope="fragment")
                    if m.tipo == "grafico" and m.dados.get("ticker") and \
                            st.button("📈 Ver gráfico", key=f"vg{m.id}", width="stretch"):
                        _ver_grafico(m.dados["ticker"], m.dados.get("periodo", "6m"), m.apelido, m.dados.get("nota", ""))
                    compartilhar_whats.botao(f"{m.apelido} no Pregão do Chrono Trade: {m.texto}", f"msg{m.id}",
                                             estado.pasta_social(), "Compartilhar")
                    if m.id > 0 and m.email == eu and st.button("🗑️ Apagar", key=f"apg_eu{m.id}", width="stretch"):
                        db.apagar_propria(m.id, eu)
                        st.rerun(scope="fragment")
                    if m.id > 0 and m.email not in (eu, pg.BOT_EMAIL) and st.button("Denunciar", key=f"den{m.id}"):
                        db.denunciar(m.id)
                        st.toast("Obrigado. A moderação vai olhar.")
                    if sou_admin and m.id > 0 and m.email != eu:
                        if st.button("Apagar (admin)", key=f"apg{m.id}"):
                            db.remover(m.id)
                            st.rerun(scope="fragment")
                        if st.button("Silenciar 24h", key=f"sil{m.id}"):
                            db.silenciar(m.email)
                            st.toast(f"{m.apelido} silenciado por 24 horas.")

    conversa()

    if pode:
        resp = db.buscar_mensagem(st.session_state.get("responder_a") or 0)
        if resp:
            c1, c2 = st.columns([6, 1], vertical_alignment="center")
            c1.markdown(f"↪ Respondendo a **{html.escape(resp.apelido)}**: {_texto_html(resp.texto[:80])}",
                        unsafe_allow_html=True)
            if c2.button("✕", help="Cancelar resposta"):
                st.session_state.responder_a = None
                st.rerun()
        texto = st.chat_input(f"Falar na {titulo} como {perfil.apelido}. Use @apelido, $TAEE11 ou /ajuda")
        if texto:
            try:
                online = [p.apelido for p in db.online(sala)]
                comando = pregao_bot.responder(texto, estado.ativo, online)
                if comando is None:
                    msg = db.enviar(sala, eu, perfil.apelido, perfil.avatar, texto,
                                    resposta_a=resp.id if resp else None)
                    avisados = set()
                    citados = db.mencionados(texto) + [e for e in map(db.email_por_apelido, pg.mencoes(texto)) if e]
                    for alvo in citados:
                        if alvo and alvo != eu and alvo not in avisados:
                            avisados.add(alvo)
                            estado.avisar(alvo, "mencao", f"{perfil.apelido} citou você no Pregão", texto[:300])
                    if resp and resp.email not in (eu, pg.BOT_EMAIL) and resp.email not in avisados:
                        estado.avisar(resp.email, "mencao", f"{perfil.apelido} respondeu você no Pregão", texto[:300])
                    st.session_state.responder_a = None
                    estado.conquistar("primeira_conversa")
                elif comando.acao == "grafico":
                    d = comando.dados
                    db.compartilhar_grafico(sala, eu, perfil.apelido, perfil.avatar, d["ticker"], d["periodo"], d["nota"])
                    estado.conquistar("primeiro_grafico")
                else:
                    pergunta = db.enviar(sala, eu, perfil.apelido, perfil.avatar, texto)
                    db.enviar(sala, pg.BOT_EMAIL, pg.BOT_APELIDO, None, comando.texto, resposta_a=pergunta.id, tipo="bot")
                st.rerun()
            except pg.ErroPregao as erro:
                st.toast(str(erro), icon="⚠️")
    else:
        tema.aviso("Você está olhando como visitante. Crie a sua conta para conversar no Pregão.")

else:
    if not pode:
        tema.aviso("Mensagens privadas são para quem tem conta.")
    else:
        conversas = db.conversas(eu)
        candidatos = {c["outro"]: c for c in conversas}
        for p in db.online():
            if p.email != eu:
                candidatos.setdefault(p.email, {"outro": p.email, "nao_lidas": 0})
        alvo_pedido = st.session_state.get("dm_com")
        if alvo_pedido and alvo_pedido not in candidatos and not alvo_pedido.startswith("demo-"):
            candidatos[alvo_pedido] = {"outro": alvo_pedido, "nao_lidas": 0}
        perfis = db.perfis(list(candidatos))
        nomes = {e: (perfis[e].apelido if e in perfis else db.perfil_completo(e).apelido) for e in candidatos}
        if not candidatos:
            st.info("Ninguém para conversar ainda. Clique em alguém no salão para mandar uma mensagem.")
        else:
            opcoes = list(candidatos)
            indice = opcoes.index(alvo_pedido) if alvo_pedido in opcoes else 0
            com = st.selectbox("Conversar com", opcoes, index=indice,
                               format_func=lambda e: nomes[e] + (f" ({candidatos[e]['nao_lidas']} novas)"
                                                                 if candidatos[e].get("nao_lidas") else ""))
            st.session_state.dm_com = com
            db.marcar_lidas(eu, com)
            for msg in db.conversa(eu, com):
                minha = msg.de == eu
                with st.chat_message("user" if minha else "assistant", avatar="🧑" if minha else "💬"):
                    st.markdown(f"**{'Você' if minha else html.escape(nomes[com])}** "
                                f"<span style='color:var(--suave);font-size:.8rem'>{msg.criado_em:%d/%m %H:%M}</span><br>"
                                f"{_texto_html(msg.texto)}", unsafe_allow_html=True)
            with st.form("privada", clear_on_submit=True):
                texto_dm = st.text_input(f"Mensagem para {nomes[com]}", max_chars=pg.TAMANHO_MAXIMO)
                if st.form_submit_button("Enviar mensagem privada", type="primary"):
                    try:
                        db.enviar_privada(eu, com, texto_dm)
                        estado.avisar(com, "privada", f"Mensagem privada de {perfil.apelido}", texto_dm[:300])
                        st.rerun()
                    except pg.ErroPregao as erro:
                        st.error(str(erro))
            if st.button("Denunciar esta conversa ao administrador"):
                from chronotrade.contas import email_admin

                trecho = "\n".join(f"{nomes.get(m.de, 'Você') if m.de != eu else perfil.apelido}: {m.texto}"
                                   for m in db.conversa(eu, com, 10))
                estado.avisar(email_admin(), "admin", f"Denúncia de conversa privada ({perfil.apelido} x {nomes[com]})",
                              trecho[:1500])
                st.toast("Enviado ao administrador.")
        tema.legenda("As mensagens privadas ficam guardadas no servidor do Chrono Trade e podem ser analisadas pela "
                     "moderação se houver denúncia. Não compartilhe senhas nem dados bancários.")

tema.legenda("As mensagens do Pregão são opiniões pessoais dos participantes, não recomendações de investimento. "
             "Conteúdo ofensivo, promessas de ganho e propaganda são removidos.")
