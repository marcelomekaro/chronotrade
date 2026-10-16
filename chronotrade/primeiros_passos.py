"""Primeiros passos: um checklist curto no Portal para a pessoa tirar o máximo do app na primeira semana."""

from __future__ import annotations

import streamlit as st

from chronotrade import alertas, conexoes, estado, telegram
from chronotrade.carteira import pasta_dados


def itens() -> list[tuple[str, bool, str, str]]:
    """(título, feito, página, rótulo do link)."""
    eu, _ = estado.identidade()
    pasta = estado.pasta()
    c = estado.carteira()
    db = estado.pregao()
    email = estado.email_avisos()
    conectou = bool(pasta and (conexoes.carregar(pasta) or (pasta / "importou_b3").exists()
                               or (pasta / "ponte_status.json").exists()))
    banco = alertas.Alertas(pasta_dados() / "contas.db")
    avisos = bool(banco.listar(email)) or bool(telegram.Telegram(pasta_dados() / "contas.db").chat_de(email))
    return [
        ("Cadastrar a carteira", bool(c.posicoes) and estado.pode_salvar(), "paginas/inventario.py", "Inventário"),
        ("Trazer da corretora ou da B3, sem digitar", conectou, "paginas/conexoes.py", "Conexões"),
        ("Criar um alerta de preço", avisos, "paginas/avisos.py", "Alertas"),
        ("Montar o seu perfil com foto", db.tem_perfil(eu), "paginas/perfil.py", "Meu perfil"),
        ("Dar um oi no Pregão ao vivo", db.participou(eu), "paginas/pregao.py", "Pregão"),
    ]


def mostrar() -> None:
    if estado.visitante() or st.session_state.get("ocultar_passos"):
        return
    lista = itens()
    feitos = sum(1 for _, ok, _, _ in lista if ok)
    if feitos == len(lista):
        return
    with st.expander(f"🚀 Primeiros passos ({feitos} de {len(lista)})", expanded=feitos < 3):
        st.progress(feitos / len(lista))
        for titulo, ok, pagina, rotulo in lista:
            col1, col2 = st.columns([4, 1.4], vertical_alignment="center")
            col1.markdown(("✅ ~~" + titulo + "~~") if ok else ("⬜ " + titulo))
            if not ok:
                col2.page_link(pagina, label=rotulo, icon="➡️")
        if st.button("Ocultar por agora", key="ocultar_passos_btn"):
            st.session_state.ocultar_passos = True
            st.rerun()
