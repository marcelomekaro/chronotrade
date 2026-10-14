"""Próximo Aporte: onde colocar o dinheiro do mês, com preço de entrada e preço justo."""

import copy

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from chronotrade import calculos, estado, radar as radar_mod, tecnica, tema
from chronotrade.calculos import brl, brl_curto, pct
from chronotrade.carteira import CLASSES
from chronotrade.mercado import normalizar_ticker, ticker_curto

st.title("Próximo Aporte")
estado.exigir("aporte")
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
plano = copy.deepcopy(c)
plano.margem_seguranca, plano.taxa_bazin, plano.observar = margem / 100, taxa / 100, observar
_, r, dados = estado.tabela_e_resumo() if c.posicoes else (pd.DataFrame(), None, {})
with st.spinner("Analisando preços, fundamentos e gráfico de cada ativo…"):
    radar = radar_mod.montar(plano, estado.ativo, dados)
if radar.empty:
    tema.fala("Cadastre a carteira no Inventário ou escreva alguns ativos para acompanhar nos parâmetros acima.")
    st.stop()
if estado.modo_demo():
    tema.aviso("Modo demonstração ligado: preços e proventos são fictícios.")
usar_tecnica = estado.permite("tecnica")

st.subheader("Radar de preços")
icones = {calculos.ZONA_COMPRA: "🟢", calculos.ABAIXO_JUSTO: "🟡", calculos.ACIMA_JUSTO: "🔴", calculos.SEM_DADOS: "⚪"}
icones_momento = {tecnica.FAVORAVEL: "⬆️ Favorável", tecnica.NEUTRO: "➖ Neutro", tecnica.ESTICADO: "⚠️ Esticado",
                  tecnica.SEM_HISTORICO: "—"}

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
    "Momento técnico": radar["momento"].map(icones_momento) if usar_tecnica else "Plano Médio",
    "Tendência": radar["tendencia"] if usar_tecnica else "",
    "Próximo provento": radar["proximo_provento"].map(lambda d: f"{d:%d/%m}" if d else "—"),
    "Métodos": radar["metodos"],
}), hide_index=True, width="stretch", height=36 * (len(radar) + 1) + 4)

# --- Análise técnica de um ativo ------------------------------------------------------------
st.subheader("Gráfico e momento técnico")
if not usar_tecnica:
    estado.liberado("tecnica")
else:
    escolhido = st.selectbox("Ativo", radar["ativo"].tolist(), key="ativo_tecnico")
    linha = radar[radar["ativo"] == escolhido].iloc[0]
    hist = estado.ativo(linha["ticker"]).historico.copy()
    if pd.DatetimeIndex(hist.index).tz is not None:
        hist.index = pd.DatetimeIndex(hist.index).tz_localize(None)
    hist = hist.iloc[-504:]
    fig_t = go.Figure()
    fig_t.add_trace(go.Scatter(x=hist.index, y=hist, name="Preço", line=dict(color=tema.CORES["texto"], width=1.6),
                               hovertemplate="%{x|%d/%m/%Y}: R$ %{y:,.2f}<extra></extra>"))
    completo = estado.ativo(linha["ticker"]).historico
    for janela, cor, nome in ((50, tema.CORES["ouro"], "Média 50 dias"), (200, tema.CORES["portal"], "Média 200 dias")):
        media = completo.rolling(janela).mean()
        media.index = pd.DatetimeIndex(media.index).tz_localize(None) if pd.DatetimeIndex(media.index).tz is not None else media.index
        media = media.reindex(hist.index)
        fig_t.add_trace(go.Scatter(x=media.index, y=media, name=nome, line=dict(color=cor, width=2),
                                   hovertemplate=f"{nome}: R$ %{{y:,.2f}}<extra></extra>"))
    if pd.notna(linha["entrada"]):
        fig_t.add_hline(y=linha["entrada"], line=dict(color=tema.CORES["jade"], dash="dash"),
                        annotation_text="Preço de entrada", annotation_font_color=tema.CORES["jade"])
    fig_t.update_layout(height=340, yaxis_tickprefix="R$ ", hovermode="x unified")
    tema.mostrar(fig_t)
    ifr_txt = f"{linha['ifr']:.0f}" if pd.notna(linha["ifr"]) else "—"
    tema.fala(f"<b>{escolhido}</b>: momento <b>{linha['momento']}</b>, tendência {linha['tendencia'].lower()}, "
              f"IFR {ifr_txt}.<br>" + "<br>".join("• " + m for m in str(linha["motivos_tecnicos"]).split("; ")))

# --- Plano do aporte ------------------------------------------------------------------
st.subheader("Como dividir o aporte")
compras, sobra = calculos.dividir_aporte(radar if usar_tecnica else radar.drop(columns="fator_tecnico"), dinheiro, metas)
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
                 "mais abaixo do preço justo recebe mais, e o momento técnico aumenta ou reduz esse peso. "
                 "Ativos acima do preço justo ficam de fora.")

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
tema.aviso_legal()
