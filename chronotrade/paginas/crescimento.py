"""Crescimento do patrimônio: quanto veio dos seus aportes e quanto o dinheiro rendeu sozinho."""

from datetime import date, timedelta

import plotly.graph_objects as go
import streamlit as st

from chronotrade import estado, patrimonio as pt, simulacao_app as sa, tema
from chronotrade.calculos import brl, pct

st.title("Crescimento do patrimônio")
tema.subtitulo("Quanto a carteira cresceu, quanto veio dos seus aportes e quanto foi o dinheiro trabalhando por você.")
c = estado.carteira()
if not c.posicoes:
    tema.fala("Cadastre a sua carteira no Inventário. A partir daí o agente Sentinela tira uma foto do patrimônio "
              "todo dia, mesmo com o app fechado, e esta tela mostra a evolução.")
    st.page_link("paginas/inventario.py", label="Cadastrar minha carteira", icon="🎒")
    st.stop()

tabela, r, _ = estado.tabela_e_resumo()
estado.registrar_patrimonio(r)
eu = estado.identidade()[0]
PERIODOS = {"1m": ("1 mês", 31), "3m": ("3 meses", 92), "12m": ("12 meses", 366), "tudo": ("Tudo", 36500)}
periodo = st.segmented_control("Período", list(PERIODOS), default="12m", format_func=lambda k: PERIODOS[k][0],
                               label_visibility="collapsed") or "12m"
desde = date.today() - timedelta(days=PERIODOS[periodo][1])
serie = estado.patrimonio().serie(eu, desde)
cres = pt.crescimento(serie)

if cres is not None:
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        tema.janela("Patrimônio hoje", brl(cres.fim, 0), tema.variacao(cres.variacao, pct(cres.variacao, 1, sinal=True) +
                                                                       " com os aportes"), ouro=True)
    with k2:
        tema.janela("Seus aportes", brl(cres.aportes, 0), "dinheiro novo que você colocou")
    with k3:
        tema.janela("O dinheiro trabalhando", brl(cres.trabalho, 0), tema.variacao(cres.trabalho, "valorização e proventos"))
    with k4:
        tema.janela("Rentabilidade", pct(cres.rentabilidade, 1, sinal=True), "descontando os aportes")
    s = cres.serie
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=s["dia"], y=s["investido"] + s["caixa"], name="Dinheiro colocado", mode="lines",
                             line=dict(color=tema.cor("suave"), dash="dot", width=1.8)))
    fig.add_trace(go.Scatter(x=s["dia"], y=s["patrimonio"], name="Patrimônio", mode="lines", fill="tonexty",
                             fillcolor=tema.cor("ouro") + "26", line=dict(color=tema.cor("ouro"), width=3, shape="spline")))
    fig.update_layout(height=380, yaxis_tickprefix="R$ ", hovermode="x unified")
    tema.mostrar(fig)
    m = cres.meses
    if len(m) >= 2:
        st.subheader("Mês a mês")
        fig2 = go.Figure([go.Bar(x=m["mes"], y=m["aportes"], name="Aportes", marker_color=tema.cor("portal")),
                          go.Bar(x=m["mes"], y=m["trabalho"], name="Rendimento",
                                 marker_color=[tema.cor("jade") if v >= 0 else tema.cor("brasa") for v in m["trabalho"]])])
        fig2.update_layout(barmode="relative", height=300, yaxis_tickprefix="R$ ")
        tema.mostrar(fig2)
    if cres.trabalho > 0 and cres.aportes > 0:
        tema.fala(f"No período, para cada <b>R$ 1</b> que você colocou, o próprio dinheiro gerou "
                  f"<b>{brl(cres.trabalho / cres.aportes)}</b>. É o buy and hold diário fazendo efeito: aos poucos, os "
                  "rendimentos passam a pesar mais que os aportes.")
else:
    tema.fala("O agente Sentinela tira uma <b>foto do patrimônio por dia</b>, mesmo com o app fechado. Em poucos dias "
              "esta tela mostra quanto veio dos aportes e quanto o dinheiro rendeu. Enquanto isso, veja uma "
              "estimativa do último ano com as quantidades que você tem hoje.")
    hist = sa.historicos(tuple(tabela["ticker"]), estado.modo_demo())
    estimativa = pt.reconstruir([(t, q) for t, q in zip(tabela["ativo"], tabela["quantidade"], strict=True)], hist)
    if not estimativa.empty:
        k1, k2, k3 = st.columns(3)
        with k1:
            tema.janela("Valor hoje", brl(estimativa.iloc[-1], 0), "com as cotações mais recentes", ouro=True)
        with k2:
            var = estimativa.iloc[-1] / estimativa.iloc[0] - 1
            tema.janela("Há um ano", brl(estimativa.iloc[0], 0), tema.variacao(var, pct(var, 1, sinal=True)))
        with k3:
            tema.janela("Proventos em 12 meses", brl(r.renda_12m, 0), f"{brl(r.renda_mensal_media, 0)} por mês")
        fig = go.Figure(go.Scatter(x=estimativa.index, y=estimativa.values, mode="lines", fill="tozeroy",
                                   fillcolor=tema.cor("ouro") + "22", line=dict(color=tema.cor("ouro"), width=2.6)))
        fig.update_layout(height=360, yaxis_tickprefix="R$ ", showlegend=False)
        tema.mostrar(fig)
        tema.legenda("Estimativa: as quantidades de hoje aplicadas aos preços do último ano, sem aportes nem proventos. "
                     "Não é a sua rentabilidade real.")

with st.expander("Como o agente automatiza isto"):
    st.markdown("- **Todo dia:** o Sentinela calcula o patrimônio com as cotações e guarda uma foto.\n"
                "- **Toda segunda:** você recebe um resumo da semana (aportes, rendimento e proventos) nos seus avisos, "
                "e no e-mail, WhatsApp, Telegram ou webhook, se tiver ligado.\n"
                "- **Meta de renda:** quando a renda de proventos passa de 25%, 50%, 75% e 100% da sua meta, chega um "
                "aviso de comemoração.")
tema.aviso_legal()
