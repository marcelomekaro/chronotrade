"""Portal: onde a carteira está hoje e quanto falta para a meta de renda."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from chronotrade import calculos, estado, primeiros_passos, tema
from chronotrade.calculos import brl, pct

st.title("Portal")
tema.subtitulo("Onde a sua carteira está hoje e quanto falta para a renda que você quer.")
c = estado.carteira()
primeiros_passos.mostrar()

if not c.posicoes:
    tema.fala("Seu inventário está vazio. Cadastre as ações e fundos que você tem, "
              "com quantidade e preço médio, e o Portal mostra quanto a carteira rende "
              "e quando ela alcança a sua meta de renda.")
    col1, col2, _ = st.columns([1, 1, 2])
    with col1:
        st.page_link("paginas/inventario.py", label="Cadastrar minha carteira", icon="🎒")
    with col2:
        if st.button("Ver com uma carteira de exemplo"):
            estado.usar_exemplo()
            st.rerun()
    st.stop()

tabela, r, dados = estado.tabela_e_resumo()
estado.avisar_fontes(dados)

# --- A linha do tempo até a meta ------------------------------------------------
meta = c.meta_renda_mensal or 0
premissas = calculos.Premissas(
    patrimonio_inicial=r.patrimonio, aporte_mensal=c.aporte_mensal,
    valorizacao_anual=0.04, dividend_yield_anual=r.dy or 0.06, anos=40, reinvestir=True,
)
projecao = calculos.projetar(premissas, meta)
chegada = next((m for m in projecao.marcos if m.titulo == "Meta de renda"), None)

st.subheader(f"Rumo a {brl(meta, 0)} por mês em proventos".replace("$", "\\$"))
tema.linha_do_tempo(r.renda_mensal_media / meta if meta else 0,
                    f"Hoje: {brl(r.renda_mensal_media, 0)}/mês", f"Meta: {brl(meta, 0)}/mês")

if meta and r.renda_mensal_media >= meta:
    tempo = "Sua carteira <b>já paga a meta</b>. Hora de pensar numa meta nova no Inventário."
elif chegada:
    tempo = (f"Mantendo o aporte de <b>{brl(c.aporte_mensal, 0)}</b> e reinvestindo os proventos, "
             f"a meta chega em <b>{calculos.meses_para_texto(chegada.mes)}</b>.")
else:
    tempo = "Com o aporte atual, a meta não é alcançada em 40 anos. Ajuste o plano na Linha do Tempo."
tema.fala(
    f"Nos últimos 12 meses a carteira pagou <b>{brl(r.renda_12m)}</b>, "
    f"uma média de <b>{brl(r.renda_mensal_media)}</b> por mês. {tempo}"
    "<br><span style='color:var(--suave);font-size:.92rem'>Premissas: valorização de 4% ao ano e o "
    "dividend yield atual da carteira. Mude na Linha do Tempo.</span>"
)

# --- Números do dia -------------------------------------------------------------
col1, col2, col3, col4 = st.columns(4)
with col1:
    tema.janela("Patrimônio", brl(r.patrimonio, 0),
                f"Caixa: {brl(r.caixa, 0)}", ouro=True)
with col2:
    tema.janela("Resultado sobre o custo", brl(r.resultado, 0),
                tema.variacao(r.resultado_pct, pct(r.resultado_pct, sinal=True)))
with col3:
    tema.janela("Proventos em 12 meses", brl(r.renda_12m, 0),
                f"{brl(r.renda_mensal_media, 0)} por mês em média")
with col4:
    tema.janela("Dividend yield", pct(r.dy), f"Sobre o preço pago (yield on cost): {pct(r.yoc)}")

# --- Gráficos -------------------------------------------------------------------
esq, dir_ = st.columns([1, 1.25])
with esq:
    st.subheader("Onde está o seu dinheiro")
    t = tabela.sort_values("valor")
    fig = go.Figure(go.Bar(
        x=t["valor"], y=t["ativo"], orientation="h",
        marker=dict(color=[tema.CORES_CLASSE.get(k, "#C9A36A") for k in t["classe"]],
                    line=dict(color="#0A0E26", width=1)),
        text=[pct(p) for p in t["peso"]], textposition="outside", cliponaxis=False,
        customdata=t["classe"],
        hovertemplate="%{y} (%{customdata})<br>%{x:,.2f} reais<extra></extra>",
    ))
    fig.update_layout(height=max(260, 34 * len(t) + 60), xaxis_title=None, yaxis_title=None,
                      xaxis=dict(showticklabels=False, showgrid=False))
    tema.mostrar(fig)
    por_classe = tabela.groupby("classe")["peso"].sum().sort_values(ascending=False)
    tema.legenda("Por classe: " + ", ".join(f"{k} {pct(v, 0)}" for k, v in por_classe.items()))

with dir_:
    st.subheader("Carteira de hoje × Ibovespa, últimos 12 meses")
    curvas = {}
    for _, linha in tabela.iterrows():
        d = dados.get(linha["ticker"])
        if d is not None and d.ok and len(d.historico) > 20:
            h = d.historico.copy()
            h.index = pd.DatetimeIndex(h.index).tz_localize(None) if h.index.tz is not None else h.index
            ultimo_ano = h[h.index >= h.index[-1] - pd.DateOffset(years=1)]
            curvas[linha["ticker"]] = ultimo_ano / ultimo_ano.iloc[0] * linha["peso"]
    if curvas:
        carteira_curva = pd.concat(curvas, axis=1).ffill().dropna().sum(axis=1)
        carteira_curva = carteira_curva / carteira_curva.iloc[0] - 1
        fig2 = go.Figure()
        ibov = estado.ativo("^BVSP").historico
        if not ibov.empty:
            ibov.index = pd.DatetimeIndex(ibov.index).tz_localize(None) if ibov.index.tz is not None else ibov.index
            ibov = ibov[ibov.index >= carteira_curva.index[0]]
            ibov = ibov / ibov.iloc[0] - 1
            fig2.add_trace(go.Scatter(x=ibov.index, y=ibov, name="Ibovespa",
                                      line=dict(color=tema.CORES["suave"], width=2, dash="dot")))
        fig2.add_trace(go.Scatter(x=carteira_curva.index, y=carteira_curva, name="Sua carteira",
                                  line=dict(color=tema.CORES["ouro"], width=3)))
        fig2.update_layout(height=340, yaxis_tickformat=".0%", hovermode="x unified")
        tema.mostrar(fig2)
        tema.legenda("Simula as posições de hoje mantidas durante o último ano, sem proventos. "
                   "Não é a sua rentabilidade real, porque você comprou em datas diferentes.")
    else:
        st.info("Ainda não há histórico de preços suficiente para comparar.")
