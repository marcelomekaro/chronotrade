"""Linha do Tempo: projeção da carteira com aportes, proventos e reinvestimento."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from chronotrade import calculos, estado, tema
from chronotrade.calculos import brl, brl_curto, pct

st.title("Linha do Tempo")
c = estado.carteira()
if c.posicoes:
    tabela, r, _ = estado.tabela_e_resumo()
    patrimonio_hoje, dy_hoje = r.patrimonio, (r.dy or 0.06)
else:
    patrimonio_hoje, dy_hoje = 0.0, 0.06

tema.fala("Viaje para o futuro da sua carteira. Use taxas <b>reais</b> (já descontada a inflação): "
          "assim todos os valores do gráfico ficam em reais de hoje, fáceis de comparar com o seu salário.")

topo = st.container()
entrada, saida = st.columns([1, 2.4], gap="large")
with entrada:
    st.subheader("Premissas")
    inicial = st.number_input("Patrimônio inicial (R$)", min_value=0.0, step=1000.0, format="%.0f",
                              value=float(round(patrimonio_hoje)))
    aporte = st.number_input("Aporte mensal (R$)", min_value=0.0, step=100.0, format="%.0f", value=float(c.aporte_mensal))
    reajuste = st.slider("Aumento real do aporte por ano (%)", 0.0, 10.0, 0.0, 0.5, format="%.1f%%")
    valorizacao = st.slider("Valorização real das cotas por ano (%)", -2.0, 10.0, 3.0, 0.5, format="%.1f%%",
                            help="Quanto o preço sobe além da inflação. Ações boas pagadoras costumam ficar entre 1% e 4%.")
    dy = st.slider("Dividend yield por ano (%)", 0.0, 15.0, float(round(dy_hoje * 100 * 2) / 2), 0.5, format="%.1f%%",
                   help="Começa com o yield atual da sua carteira.")
    anos = st.slider("Anos", 1, 40, 25)
    reinvestir = st.toggle("Reinvestir os proventos", value=True)
    meta = st.number_input("Meta de renda mensal (R$)", min_value=0.0, step=500.0, format="%.0f", value=float(c.meta_renda_mensal))

premissas = calculos.Premissas(inicial, aporte, valorizacao / 100, dy / 100, anos, reinvestir, reajuste / 100)
cen = calculos.cenarios(premissas, meta)
base = cen["Base"]
t = base.tabela

with topo:
    fim = t.iloc[-1]
    col1, col2, col3 = st.columns(3)
    with col1:
        tema.janela(f"Patrimônio em {anos} anos", brl_curto(fim["patrimonio"]),
                    f"Você terá aportado {brl(fim['investido'], 0)}", ouro=True)
    with col2:
        tema.janela("Renda mensal ao final", brl_curto(fim["renda_mensal"]),
                    f"{pct(fim['renda_mensal'] / meta if meta else None, 0)} da meta")
    with col3:
        ganho = fim["patrimonio"] - fim["investido"]
        tema.janela("Trabalho dos juros", brl_curto(ganho),
                    f"{pct(ganho / fim['patrimonio'] if fim['patrimonio'] else None, 0)} do patrimônio final")

with saida:

    st.subheader("Patrimônio ao longo do tempo")
    pess, otim = cen["Pessimista"].tabela, cen["Otimista"].tabela
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=otim["ano"], y=otim["patrimonio"], line=dict(width=0), showlegend=False,
                             hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=pess["ano"], y=pess["patrimonio"], fill="tonexty", line=dict(width=0),
                             fillcolor="rgba(164,139,255,.18)", name="Faixa pessimista a otimista",
                             hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=t["ano"], y=t["investido"], name="Dinheiro que você colocou",
                             line=dict(color=tema.CORES["suave"], width=2, dash="dot"),
                             hovertemplate="Ano %{x:.1f}: R$ %{y:,.0f}<extra>Aportado</extra>"))
    fig.add_trace(go.Scatter(x=t["ano"], y=t["patrimonio"], name="Cenário base",
                             line=dict(color=tema.CORES["ouro"], width=3),
                             hovertemplate="Ano %{x:.1f}: R$ %{y:,.0f}<extra>Base</extra>"))
    if base.marcos:
        pontos = t.set_index("mes").loc[[m.mes for m in base.marcos]]
        fig.add_trace(go.Scatter(x=pontos["ano"], y=pontos["patrimonio"], mode="markers",
                                 marker=dict(symbol="square", size=11, color=tema.CORES["portal"],
                                             line=dict(color=tema.CORES["borda"], width=2)),
                                 text=[m.titulo for m in base.marcos], name="Marcos",
                                 hovertemplate="%{text}<br>Ano %{x:.1f}<extra></extra>"))
    fig.update_layout(height=400, xaxis_title="Anos a partir de hoje", yaxis_tickprefix="R$ ",
                      hovermode="closest")
    tema.mostrar(fig)
    tema.legenda(f"Faixa: valorização {pct(-0.03, 0)} e yield −1 ponto no pessimista; o contrário no otimista.")

    st.subheader("Renda mensal em proventos")
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=t["ano"], y=t["renda_mensal"], name="Renda mensal",
                              line=dict(color=tema.CORES["jade"], width=3), fill="tozeroy",
                              fillcolor="rgba(95,211,154,.12)",
                              hovertemplate="Ano %{x:.1f}: R$ %{y:,.0f}/mês<extra></extra>"))
    fig2.add_trace(go.Scatter(x=t["ano"], y=t["aporte"].where(t["mes"] > 0), name="Seu aporte",
                              line=dict(color=tema.CORES["suave"], width=2, dash="dot"),
                              hovertemplate="Aporte: R$ %{y:,.0f}<extra></extra>"))
    if meta:
        fig2.add_hline(y=meta, line=dict(color=tema.CORES["ouro"], width=2, dash="dash"),
                       annotation_text=f"Meta {brl(meta, 0)}", annotation_position="top left",
                       annotation_font_color=tema.CORES["ouro"])
    fig2.update_layout(height=320, xaxis_title="Anos a partir de hoje", yaxis_tickprefix="R$ ")
    tema.mostrar(fig2)

st.subheader("As eras da sua jornada")
if base.marcos:
    n = min(3, len(base.marcos))
    por_coluna = -(-len(base.marcos) // n)
    colunas = st.columns(n)
    for i, m in enumerate(base.marcos):
        with colunas[i // por_coluna]:
            tema.era(f"Daqui a {calculos.meses_para_texto(m.mes)}", m.titulo, m.descricao)
else:
    st.info("Nenhum marco é alcançado com estas premissas. Aumente o prazo ou o aporte.")

st.subheader("Cenários lado a lado")
marcos_ano = sorted({a for a in (5, 10, 15, 20, 30) if a < anos} | {anos})
linhas = []
for nome, proj in cen.items():
    tab = proj.tabela.set_index("mes")
    for a in marcos_ano:
        linha = tab.loc[a * 12]
        linhas.append({"Cenário": nome, "Ano": a, "Patrimônio": brl(linha["patrimonio"], 0),
                       "Renda mensal": brl(linha["renda_mensal"], 0)})
quadro = pd.DataFrame(linhas).pivot(index="Ano", columns="Cenário", values=["Patrimônio", "Renda mensal"])
quadro = quadro.reindex(columns=["Pessimista", "Base", "Otimista"], level=1)
st.dataframe(quadro, width="stretch")
tema.legenda("Projeção é um exercício, não uma promessa: empresas cortam proventos e os preços oscilam.")
