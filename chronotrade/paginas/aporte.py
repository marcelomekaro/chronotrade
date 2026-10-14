"""Próximo Aporte: onde colocar o dinheiro do mês, com preço de entrada e preço justo."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from chronotrade import calculos, estado, tema
from chronotrade.calculos import brl, brl_curto, pct
from chronotrade.carteira import CLASSES
from chronotrade.mercado import normalizar_ticker, parece_fii, ticker_curto

st.title("Próximo Aporte")
estado.exigir_plano_completo("O planejador de aportes")
c = estado.carteira()

tema.fala("Diga quanto vai investir e o Chrono Trade mostra quais ativos estão abaixo do <b>preço justo</b> "
          "e como dividir o dinheiro para chegar às suas metas por classe. "
          "Os preços vêm de fórmulas com os parâmetros que <b>você</b> escolhe; confira antes de comprar.")

# --- Parâmetros ------------------------------------------------------------------
with st.expander("Parâmetros do plano", expanded=not c.posicoes):
    col1, col2 = st.columns(2)
    margem = col1.slider("Margem de segurança (%)", 0, 40, int(round(c.margem_seguranca * 100)), 5,
                         help="Desconto exigido sobre o preço justo para considerar a zona de compra.")
    taxa = col2.slider("Proventos mínimos para o preço teto Bazin (% ao ano)", 3.0, 12.0,
                       float(c.taxa_bazin * 100), 0.5, format="%.1f%%")
    st.markdown("**Metas por classe** (quanto de cada classe você quer na carteira)")
    colunas = st.columns(len(CLASSES))
    metas = {classe: col.number_input(f"{classe} (%)", 0.0, 100.0, float(c.metas_classe.get(classe, 0.0)), 5.0,
                                      format="%.0f", key=f"meta_{classe}")
             for classe, col in zip(CLASSES, colunas, strict=True)}
    soma_metas = sum(metas.values())
    if abs(soma_metas - 100) > 0.5:
        tema.aviso(f"As metas somam {soma_metas:.0f}%. Uso a proporção entre elas, mas o ideal é somar 100%.")
    observar_txt = st.text_input("Ativos para acompanhar que você ainda não tem (separe por vírgula)",
                                 value=", ".join(ticker_curto(t) for t in c.observar))
    if st.button("Guardar parâmetros"):
        c.margem_seguranca, c.taxa_bazin, c.metas_classe = margem / 100, taxa / 100, metas
        c.observar = [normalizar_ticker(t) for t in observar_txt.split(",") if t.strip()]
        st.success("Parâmetros guardados." if estado.salvar() else "Parâmetros valem até fechar o navegador.")

observar = [normalizar_ticker(t) for t in observar_txt.split(",") if t.strip()]
dinheiro = st.number_input("Quanto vai investir agora (R$)", min_value=0.0, step=100.0, format="%.0f",
                           value=float(c.aporte_mensal + c.caixa),
                           help="Começa com o aporte mensal mais o caixa da carteira.")

# --- Radar de preços ------------------------------------------------------------------
tabela, r, dados = estado.tabela_e_resumo() if c.posicoes else (pd.DataFrame(), None, {})
linhas = []
ja_tem = set(tabela["ticker"]) if not tabela.empty else set()
for ticker in list(tabela["ticker"] if not tabela.empty else []) + [t for t in observar if t not in ja_tem]:
    d = dados.get(ticker) or estado.ativo(ticker)
    hoje = pd.Timestamp.today()
    media5 = calculos.media_anual_proventos(d.dividendos, 5, hoje)
    teto = calculos.preco_teto_bazin(media5, taxa / 100)
    graham = calculos.preco_justo_graham(d.lpa, d.vpa)
    avaliacao = calculos.avaliar_preco(d.preco, teto, graham, margem / 100)
    if ticker in ja_tem:
        linha_carteira = tabela[tabela["ticker"] == ticker].iloc[0]
        classe, valor = linha_carteira["classe"], float(linha_carteira["valor"])
    else:
        classe, valor = ("FII" if parece_fii(ticker) else "Ação"), 0.0
    prov12 = calculos.proventos_12m(d.dividendos, hoje)
    linhas.append({"ticker": ticker, "ativo": ticker_curto(ticker), "classe": classe, "preco": d.preco or 0.0,
                   "valor": valor, "dy": calculos.dividend_yield(prov12, d.preco), "prov12": prov12,
                   "na_carteira": ticker in ja_tem, **avaliacao})
radar = pd.DataFrame(linhas)

if radar.empty:
    tema.fala("Cadastre a carteira no Inventário ou escreva alguns ativos para acompanhar nos parâmetros acima.")
    st.stop()
if estado.modo_demo():
    tema.aviso("Modo demonstração ligado: preços e proventos são fictícios.")

st.subheader("Radar de preços")
icones = {calculos.ZONA_COMPRA: "🟢", calculos.ABAIXO_JUSTO: "🟡", calculos.ACIMA_JUSTO: "🔴", calculos.SEM_DADOS: "⚪"}
ordem = {calculos.ZONA_COMPRA: 0, calculos.ABAIXO_JUSTO: 1, calculos.ACIMA_JUSTO: 2, calculos.SEM_DADOS: 3}
radar = radar.assign(_o=radar["situacao"].map(ordem)).sort_values(["_o", "potencial"], ascending=[True, False])

grafico = radar[radar["alvo"].notna()]
if not grafico.empty:
    fig = go.Figure()
    for _, ln in grafico.iloc[::-1].iterrows():
        fig.add_trace(go.Scatter(x=[ln["entrada"], ln["alvo"]], y=[ln["ativo"]] * 2, mode="lines",
                                 line=dict(color="rgba(233,225,200,.35)", width=10), showlegend=False,
                                 hoverinfo="skip"))
    g = grafico.iloc[::-1]
    fig.add_trace(go.Scatter(x=g["entrada"], y=g["ativo"], mode="markers", name="Preço de entrada",
                             marker=dict(symbol="line-ns", size=16, line=dict(width=3, color=tema.CORES["jade"])),
                             hovertemplate="%{y}: entrada R$ %{x:,.2f}<extra></extra>"))
    fig.add_trace(go.Scatter(x=g["alvo"], y=g["ativo"], mode="markers", name="Preço justo (alvo)",
                             marker=dict(symbol="line-ns", size=16, line=dict(width=3, color=tema.CORES["ouro"])),
                             hovertemplate="%{y}: preço justo R$ %{x:,.2f}<extra></extra>"))
    cores = g["situacao"].map({calculos.ZONA_COMPRA: tema.CORES["jade"], calculos.ABAIXO_JUSTO: tema.CORES["ouro"],
                               calculos.ACIMA_JUSTO: tema.CORES["brasa"]})
    fig.add_trace(go.Scatter(x=g["preco"], y=g["ativo"], mode="markers", name="Preço hoje",
                             marker=dict(symbol="square", size=12, color=cores,
                                         line=dict(color=tema.CORES["borda"], width=2)),
                             hovertemplate="%{y}: hoje R$ %{x:,.2f}<extra></extra>"))
    fig.update_layout(height=max(260, 40 * len(g) + 90), xaxis_tickprefix="R$ ",
                      xaxis_title="Preço por cota")
    tema.mostrar(fig)
    tema.legenda("Cada linha vai do preço de entrada (traço verde) ao preço justo (traço dourado). "
                 "O quadrado é o preço de hoje: verde na zona de compra, dourado abaixo do justo, vermelho acima.")

st.dataframe(pd.DataFrame({
    "": radar["situacao"].map(icones),
    "Ativo": radar["ativo"] + radar["na_carteira"].map({True: "", False: " (novo)"}),
    "Classe": radar["classe"],
    "Preço hoje": radar["preco"].map(brl),
    "Preço de entrada": radar["entrada"].map(brl),
    "Preço justo (alvo)": radar["alvo"].map(brl),
    "Até o alvo": radar["potencial"].map(lambda v: pct(v, 0, sinal=True)),
    "DY 12m": radar["dy"].map(pct),
    "Métodos": radar["metodos"],
}), hide_index=True, width="stretch", height=36 * (len(radar) + 1) + 4)

# --- Plano do aporte ------------------------------------------------------------------
st.subheader("Como dividir o aporte")
compras, sobra = calculos.dividir_aporte(radar, dinheiro, metas)
if compras.empty:
    tema.fala(f"Nenhum ativo do radar está abaixo do preço justo com estes parâmetros. "
              f"Uma opção é guardar os <b>{brl(dinheiro, 0)}</b> em caixa e esperar preços melhores.")
else:
    compras = compras.merge(radar[["ativo", "prov12", "situacao"]], on="ativo", how="left")
    renda_extra = float((compras["cotas"] * compras["prov12"]).sum()) / 12
    renda_antes = r.renda_mensal_media if r else 0.0
    col1, col2, col3 = st.columns(3)
    with col1:
        tema.janela("Vai investir", brl(dinheiro - sobra, 0), f"Sobra para o caixa: {brl(sobra)}", ouro=True)
    with col2:
        tema.janela("Renda mensal estimada", brl(renda_antes + renda_extra, 0),
                    f"Hoje {brl(renda_antes, 0)}, " + tema.variacao(renda_extra, f"{brl(renda_extra)} a mais"))
    with col3:
        tema.janela("Ativos na compra", str(len(compras)), f"{int(compras['cotas'].sum())} cotas no total")
    st.dataframe(pd.DataFrame({
        "": compras["situacao"].map(icones),
        "Ativo": compras["ativo"],
        "Classe": compras["classe"],
        "Cotas": compras["cotas"].astype(int),
        "Preço": compras["preco"].map(brl),
        "Total": compras["valor_compra"].map(brl),
    }), hide_index=True, width="stretch")
    st.session_state.plano_aporte = {"compras": compras, "sobra": sobra, "dinheiro": dinheiro}
    tema.legenda("Regras: cada classe recebe na proporção do que falta para a meta; dentro dela, quem está "
                 "mais abaixo do preço justo recebe mais. Ativos acima do preço justo ficam de fora.")

# --- Evolução do patrimônio ---------------------------------------------------------------
st.subheader("Evolução do patrimônio com este ritmo")
patrimonio = (r.patrimonio if r else 0.0)
dy_carteira = (r.dy if r and r.dy else 0.06)
anos = st.slider("Anos à frente", 5, 30, 15, key="anos_aporte")
com = calculos.projetar(calculos.Premissas(patrimonio, c.aporte_mensal, 0.03, dy_carteira, anos, True)).tabela
sem = calculos.projetar(calculos.Premissas(patrimonio, 0.0, 0.03, dy_carteira, anos, True)).tabela
fig2 = go.Figure()
fig2.add_trace(go.Scatter(x=sem["ano"], y=sem["patrimonio"], name="Se parar de aportar hoje",
                          line=dict(color=tema.CORES["suave"], width=2, dash="dot"),
                          hovertemplate="Ano %{x:.1f}: R$ %{y:,.0f}<extra></extra>"))
fig2.add_trace(go.Scatter(x=com["ano"], y=com["patrimonio"], name=f"Aportando {brl(c.aporte_mensal, 0)} por mês",
                          line=dict(color=tema.CORES["ouro"], width=3),
                          hovertemplate="Ano %{x:.1f}: R$ %{y:,.0f}<extra></extra>"))
fig2.update_layout(height=340, xaxis_title="Anos a partir de hoje", yaxis_tickprefix="R$ ")
tema.mostrar(fig2)
diferenca = com["patrimonio"].iloc[-1] - sem["patrimonio"].iloc[-1]
tema.legenda(f"Em {anos} anos, manter os aportes soma {brl_curto(diferenca)} ao patrimônio. Premissas: valorização "
             f"real de 3% ao ano, dividend yield de {pct(dy_carteira)} e proventos reinvestidos. "
             "Ajuste tudo na Linha do Tempo.")
tema.legenda("Cálculo automático com parâmetros escolhidos por você. Não é recomendação de compra ou venda.")
