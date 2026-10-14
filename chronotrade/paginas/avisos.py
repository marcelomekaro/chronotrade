"""Avisos: as dicas do agente Sentinela, datas com e confirmações, todas num lugar."""

import streamlit as st

from chronotrade import estado, tema

ICONES = {"sentinela": "🛡️", "provento": "📅", "ordem": "🔌", "assinatura": "💳", "admin": "🔔"}

st.title("Avisos")
email = estado.email_avisos()
caixa = estado.caixa_avisos()

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

lista = caixa.listar(email)
if not lista:
    tema.fala("Nenhum aviso ainda. O agente Sentinela manda a dica do próximo aporte automaticamente; "
              "você também pode pedir uma agora.")
for a in lista:
    with st.container(border=True):
        novo = "" if a.lido else " 🔵"
        st.markdown(f"**{ICONES.get(a.tipo, '🔔')} {a.titulo}**{novo}  \n"
                    f"<span style='color:var(--suave)'>{a.criado_em:%d/%m/%Y %H:%M}</span>", unsafe_allow_html=True)
        st.text(a.texto)
        if a.envios:
            st.caption("Enviado também por " + a.envios)
caixa.marcar_lidos(email)
