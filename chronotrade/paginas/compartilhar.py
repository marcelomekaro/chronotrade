"""Compartilhar: relatório para imprimir ou salvar em PDF, e um resumo para mandar no WhatsApp."""

from datetime import date

import streamlit as st
import streamlit.components.v1 as componentes

from chronotrade import estado, relatorio, tema

st.title("Compartilhar")
estado.exigir("compartilhar")
c = estado.carteira()
if not c.posicoes:
    tema.fala("Cadastre a carteira no Inventário para gerar o relatório.")
    st.stop()

tabela, r, dados = estado.tabela_e_resumo()
estado.avisar_fontes(dados)

col1, col2 = st.columns([1, 1])
titulo = col1.text_input("Título do relatório", value="Minha carteira")
ocultar = col2.toggle("Ocultar valores em reais", value=True,
                      help="Mostra só porcentagens: a estratégia aparece, o tamanho do seu patrimônio não.")
plano = st.session_state.get("plano_aporte")
incluir_plano = plano is not None and st.checkbox("Incluir o plano do próximo aporte", value=True)

pagina = relatorio.gerar(c, tabela, r, ocultar_valores=ocultar,
                         plano_aporte=plano if incluir_plano else None, titulo=titulo)

botoes = st.columns([1, 1, 2])
botoes[0].download_button("Baixar relatório", pagina.encode("utf-8"),
                          file_name=f"chronotrade_{date.today():%Y-%m-%d}.html", mime="text/html", type="primary",
                          help="Abra o arquivo no navegador para imprimir, salvar em PDF ou enviar por e-mail.")
with botoes[1].popover("Resumo para WhatsApp"):
    st.code(relatorio.resumo_texto(c, tabela, r, ocultar_valores=ocultar), language=None)
    st.caption("Use o ícone de copiar no canto do quadro.")

st.subheader("Prévia")
tema.legenda("O botão no fim da prévia abre a impressão. No destino da impressão, escolha Salvar como PDF.")
componentes.html(pagina, height=1100, scrolling=True)
