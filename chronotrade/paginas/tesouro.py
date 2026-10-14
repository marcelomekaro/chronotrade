"""Tesouro: os proventos que a carteira paga, mês a mês e ativo por ativo."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from chronotrade import calculos, estado, tema
from chronotrade.calculos import brl, pct
from chronotrade.mercado import ticker_curto

st.title("Tesouro")
c = estado.carteira()
if not c.posicoes:
    tema.fala("Cadastre a sua carteira no Inventário para ver os proventos aqui.")
    st.stop()

tabela, r, dados = estado.tabela_e_resumo()
estado.avisar_fontes(dados)

maior = tabela.sort_values("renda_12m", ascending=False).iloc[0]
col1, col2, col3 = st.columns(3)
with col1:
    tema.janela("Recebido em 12 meses", brl(r.renda_12m, 0), f"{brl(r.renda_mensal_media)} por mês em média",
                ouro=True)
with col2:
    tema.janela("Maior pagador", maior["ativo"],
                f"{brl(maior['renda_12m'], 0)} em 12 meses, {pct(maior['renda_12m'] / r.renda_12m if r.renda_12m else None, 0)} do total")
with col3:
    tema.janela("Yield on cost", pct(r.yoc), f"Dividend yield a preço de hoje: {pct(r.dy)}")

# --- Mês a mês ---------------------------------------------------------------------
st.subheader("Proventos por mês, últimos 24 meses")
mensal = {}
for p in c.posicoes:
    d = dados.get(p.ticker)
    if d is not None:
        mensal[ticker_curto(p.ticker)] = calculos.proventos_por_mes(d.dividendos, p.quantidade, meses=24)
mensal = pd.DataFrame(mensal)
if mensal.empty or mensal.to_numpy().sum() == 0:
    st.info("Nenhum provento encontrado para estes ativos nos últimos 24 meses.")
else:
    mensal = mensal.loc[:, mensal.sum() > 0]
    mensal = mensal.loc[:, mensal.sum().sort_values(ascending=False).index]
    meses = [calculos.mes_ano(p) for p in mensal.index.to_timestamp()]
    fig = go.Figure()
    for ativo in mensal.columns:
        fig.add_trace(go.Bar(x=meses, y=mensal[ativo], name=ativo,
                             hovertemplate=f"{ativo}<br>%{{x}}: R$ %{{y:,.2f}}<extra></extra>"))
    media = mensal.sum(axis=1).rolling(12, min_periods=1).mean()
    fig.add_trace(go.Scatter(x=meses, y=media, name="Média de 12 meses", mode="lines",
                             line=dict(color=tema.CORES["borda"], width=2, dash="dot")))
    fig.update_layout(barmode="stack", height=380, yaxis_tickprefix="R$ ", hovermode="x unified")
    tema.mostrar(fig)
    tema.legenda("Estimativa: multiplica os proventos por ação pela quantidade que você tem hoje. "
               "Se comprou em datas diferentes, o valor recebido de verdade foi outro.")

# --- Ativo por ativo -----------------------------------------------------------------------
st.subheader("Número mágico")
st.markdown("Quantas cotas fazem os proventos de um mês comprarem uma cota nova sozinhos. "
            "A partir daí, o ativo cresce por conta própria.")
magico = tabela[["ativo", "quantidade", "preco", "prov_12m_acao", "renda_12m", "numero_magico"]].copy()
magico = magico[magico["numero_magico"].notna()]
magico["numero_magico"] = magico["numero_magico"].astype(float)
magico["faltam"] = (magico["numero_magico"] - magico["quantidade"]).clip(lower=0)
magico["progresso"] = (magico["quantidade"] / magico["numero_magico"]).clip(upper=1)
magico = magico.sort_values("progresso", ascending=False)
if magico.empty:
    st.info("Nenhum ativo da carteira pagou proventos nos últimos 12 meses.")
else:
    def _int(v):
        return f"{v:,.0f}".replace(",", ".")

    st.dataframe(
        pd.DataFrame({
            "Ativo": magico["ativo"],
            "Você tem": magico["quantidade"].map(_int),
            "Preço": magico["preco"].map(brl),
            "Proventos por cota em 12m": magico["prov_12m_acao"].map(brl),
            "Sua renda em 12m": magico["renda_12m"].map(brl),
            "Número mágico": magico["numero_magico"].map(_int),
            "Faltam": magico["faltam"].map(_int),
            "Progresso": magico["progresso"],
        }),
        hide_index=True, width="stretch",
        column_config={"Progresso": st.column_config.ProgressColumn(min_value=0, max_value=1, format="percent")},
    )
    sem = tabela.loc[tabela["numero_magico"].isna(), "ativo"].tolist()
    if sem:
        tema.legenda("Sem proventos em 12 meses, fora da tabela: " + ", ".join(sem) + ".")

# --- Histórico de um ativo ---------------------------------------------------------------
st.subheader("Constância dos pagamentos")
escolha = st.selectbox("Ativo", tabela["ativo"].tolist())
linha = tabela[tabela["ativo"] == escolha].iloc[0]
divs = dados[linha["ticker"]].dividendos
if divs is None or divs.empty:
    st.info(f"{escolha} não tem proventos registrados no Yahoo Finance.")
else:
    serie = divs.copy()
    if pd.DatetimeIndex(serie.index).tz is not None:
        serie.index = pd.DatetimeIndex(serie.index).tz_localize(None)
    anual = serie.groupby(serie.index.year).sum().tail(10)
    ano_atual = pd.Timestamp.today().year
    cores = [tema.CORES["portal"] if a == ano_atual else tema.CORES["ouro"] for a in anual.index]
    fig3 = go.Figure(go.Bar(x=[str(a) for a in anual.index], y=anual.values, marker_color=cores,
                            text=[f"R$ {v:,.2f}".replace(".", ",") for v in anual.values],
                            textposition="outside", cliponaxis=False,
                            hovertemplate="%{x}: R$ %{y:,.2f} por cota<extra></extra>"))
    fig3.update_layout(height=320, yaxis_tickprefix="R$ ", yaxis_title="Por cota")
    tema.mostrar(fig3)
    media5 = linha["media_prov_5a"]
    tema.legenda(f"Proventos por cota em cada ano. O ano atual (em roxo) ainda não terminou. "
               f"Média dos últimos 5 anos completos: {brl(media5)} por cota; preço teto Bazin: "
               f"{brl(linha['teto_bazin'])}.")
