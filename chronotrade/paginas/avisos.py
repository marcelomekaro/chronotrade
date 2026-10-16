"""Avisos: dicas do Sentinela, alertas de preço, zona de compra, menções e mensagens, num lugar só."""

import streamlit as st

from chronotrade import alertas as alertas_mod, estado, telegram, tema
from chronotrade.calculos import brl
from chronotrade.carteira import pasta_dados
from chronotrade.mercado import ticker_curto

ICONES = {"sentinela": "🛡️", "provento": "📅", "ordem": "🔌", "assinatura": "💳", "admin": "🔔", "alerta": "🎯",
          "zona": "🟢", "mencao": "💬", "privada": "✉️", "conexao": "🔗", "pontos": "🏆"}

st.title("Avisos")
tema.subtitulo("Dicas do Sentinela, alertas de preço, menções e mensagens, num lugar só.")
email = estado.email_avisos()
caixa = estado.caixa_avisos()
banco_alertas = alertas_mod.Alertas(pasta_dados() / "contas.db")

caixa_tab, alertas_tab, canais_tab = st.tabs(["🔔 Caixa de avisos", "🎯 Alertas de preço", "📲 Onde receber"])

with caixa_tab:
    col1, col2 = st.columns([1, 1])
    if estado.permite("avisos_app") and col1.button("Pedir uma dica agora", type="primary",
                                                      help="O agente Sentinela analisa a carteira e manda a dica já."):
        with st.spinner("O Sentinela está analisando a sua carteira…"):
            resumo = estado.rodar_sentinela_agora()
        if resumo.get("dicas"):
            st.success("Dica pronta! Ela está no topo da lista.")
        else:
            st.info("Cadastre a carteira no Inventário para receber dicas.")
    if col2.button("Marcar todos como lidos"):
        caixa.marcar_lidos(email)
        st.rerun()
    filtro = st.segmented_control("Mostrar", ["Tudo", "Dicas", "Alertas", "Pregão", "Proventos"], default="Tudo",
                                  key="filtro_avisos")
    tipos = {"Dicas": {"sentinela"}, "Alertas": {"alerta", "zona"}, "Pregão": {"mencao", "privada"},
             "Proventos": {"provento"}}.get(filtro or "Tudo")
    lista = [a for a in caixa.listar(email) if tipos is None or a.tipo in tipos]
    if not lista:
        tema.fala("Nenhum aviso aqui ainda. O agente Sentinela manda a dica do próximo aporte sozinho, e você pode "
                  "criar alertas de preço na aba ao lado.")
    for a in lista:
        with st.container(border=True):
            novo = "" if a.lido else " 🔵"
            st.markdown(f"**{ICONES.get(a.tipo, '🔔')} {a.titulo}**{novo}  \n"
                        f"<span style='color:var(--suave)'>{a.criado_em:%d/%m/%Y %H:%M}</span>", unsafe_allow_html=True)
            st.text(a.texto)
            if a.tipo in ("mencao", "privada"):
                st.page_link("paginas/pregao.py", label="Abrir o Pregão", icon="🏛️")
            if a.envios:
                st.caption("Enviado também por " + a.envios)
    caixa.marcar_lidos(email)

with alertas_tab:
    if estado.liberado("alertas"):
        tema.fala("Diga o preço que te interessa e o <b>Sentinela</b> avisa quando chegar, no app e nos canais que "
                  "você ligou. Ele também avisa sozinho quando um ativo do seu radar entra na <b>zona de compra</b>.")
        c = estado.carteira()
        sugestoes = [ticker_curto(p.ticker) for p in c.posicoes] + [ticker_curto(t) for t in c.observar]
        with st.form("novo_alerta", clear_on_submit=True):
            c1, c2, c3 = st.columns([2, 1.3, 1.5])
            ativo = c1.selectbox("Ativo", sugestoes + ["Outro…"]) if sugestoes else "Outro…"
            outro = c1.text_input("Código do ativo", placeholder="TAEE11") if ativo == "Outro…" else ""
            tipo = c2.radio("Quando ficar", ["abaixo", "acima"], format_func=str.capitalize, horizontal=True)
            preco = c3.number_input("de (R$)", min_value=0.0, step=0.10, format="%.2f")
            if st.form_submit_button("Criar alerta", type="primary"):
                ticker = outro if ativo == "Outro…" else ativo
                try:
                    a = banco_alertas.criar(email, ticker, tipo, preco)
                    estado.conquistar("primeiro_alerta")
                    atual = estado.ativo(a.ticker).preco
                    texto_ok = f"Alerta criado: {a.descricao}." + (f" Hoje está em {brl(atual)}." if atual else "")
                    st.success(texto_ok.replace("$", "\\$"))
                except alertas_mod.ErroAlerta as erro:
                    st.error(str(erro))
        for a in banco_alertas.listar(email):
            col_a, col_b, col_c = st.columns([4, 1, 1], vertical_alignment="center")
            atual = estado.ativo(a.ticker).preco
            estado_txt = (f"disparou em {a.disparado_em:%d/%m %H:%M}" if a.disparado_em else "vigiando")
            linha_alerta = f"**{a.descricao}**  \n{estado_txt}" + (f", hoje {brl(atual)}" if atual else "")
            col_a.markdown(linha_alerta.replace("$", "\\$"))
            if a.disparado_em and col_b.button("Reativar", key=f"re{a.id}"):
                banco_alertas.reativar(email, a.id)
                st.rerun()
            if col_c.button("Apagar", key=f"ap{a.id}"):
                banco_alertas.remover(email, a.id)
                st.rerun()
        tema.legenda("Alertas são lembretes de preço que você mesmo define. Não são recomendação de compra ou venda.")

with canais_tab:
    st.markdown("**No app:** sempre ligado, com pop-up quando chega algo novo.")
    st.markdown("**E-mail e WhatsApp:** escolha em Minha conta (conforme o plano).")
    st.subheader("Telegram (grátis)")
    if not telegram.configurado():
        st.caption("O administrador ainda não ligou o bot do Telegram (TELEGRAM_BOT_TOKEN e TELEGRAM_BOT_USUARIO no .env).")
    elif not estado.permite("avisos_telegram"):
        estado.liberado("avisos_telegram")
    else:
        tg = telegram.Telegram(pasta_dados() / "contas.db")
        if tg.chat_de(email):
            st.success("Telegram ligado. Os avisos chegam lá também.")
            if st.button("Desligar o Telegram"):
                tg.desvincular(email)
                st.rerun()
        else:
            st.markdown("1. Toque no botão abaixo e aperte **Começar** no Telegram.  \n"
                        "2. Pronto: em até uma hora o Sentinela vincula e manda uma confirmação.")
            st.link_button("Ligar avisos no Telegram", telegram.link(email), type="primary")

with canais_tab:
    st.subheader("Discord, Slack, Teams, Google Chat, Zapier ou Make")
    if not estado.permite("avisos_telegram"):
        estado.liberado("avisos_telegram")
    else:
        from chronotrade import webhooks

        wh = webhooks.Webhooks(pasta_dados() / "contas.db")
        atual = wh.de(email)
        if atual:
            st.success(f"Avisos indo também para o {webhooks.servico(atual)}.")
            c1, c2 = st.columns(2)
            if c1.button("Mandar um teste"):
                st.info("Resultado: " + webhooks.enviar(atual, "Teste do Chrono Trade", "Se você está lendo isto, funcionou!"))
            if c2.button("Desligar o webhook"):
                wh.remover(email)
                st.rerun()
        with st.form("webhook"):
            url = st.text_input("Endereço do webhook", placeholder="https://discord.com/api/webhooks/…",
                                help="No Discord: Configurações do canal → Integrações → Webhooks → Copiar URL.")
            if st.form_submit_button("Salvar webhook"):
                try:
                    st.success(f"Pronto: avisos também no {wh.salvar(email, url)}.")
                except webhooks.ErroWebhook as erro:
                    st.error(str(erro))
        tema.legenda("Use para levar as dicas do Sentinela ao grupo do seu clube de investimentos ou para automações "
                     "(planilhas, e-mail, CRM) no Zapier ou Make.")
