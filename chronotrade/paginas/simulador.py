"""Simulador de mercado: crises que a B3 já viveu, compras e vendas antes de fazer e os futuros possíveis."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from chronotrade import estado, simulacao_app as sa, simulador, tema
from chronotrade.calculos import brl, pct
from chronotrade.mercado import normalizar_ticker, ticker_curto

st.title("Simulador de mercado")
tema.subtitulo("Teste a carteira contra crises, simule compras e vendas antes de fazer e veja os futuros possíveis.")
estado.exigir("estresse")
c = estado.carteira()

if not c.posicoes:
    tema.fala("Cadastre a sua carteira para simular. Ou veja como funciona com a carteira de exemplo.")
    col1, col2, _ = st.columns([1, 1, 2])
    col1.page_link("paginas/inventario.py", label="Cadastrar minha carteira", icon="🎒")
    if col2.button("Usar a carteira de exemplo"):
        estado.usar_exemplo()
        st.rerun()
    st.stop()

ABAS = {"estresse": "🌪️ Teste de estresse", "intencoes": "🎯 Simular intenções", "futuros": "🔭 Futuros possíveis"}
if st.session_state.get("sim_aba") in ABAS:
    st.session_state.sim_aba_atual = st.session_state.pop("sim_aba")
aba = st.segmented_control("Simulação", list(ABAS), format_func=ABAS.get, key="sim_aba_atual",
                           label_visibility="collapsed") or "estresse"
COR = tema.cor


def _linha(fig: go.Figure, y, nome: str, cor: str, traco: str = "solid", largura: float = 2.6):
    fig.add_trace(go.Scatter(y=y, mode="lines", name=nome, line=dict(color=cor, width=largura, dash=traco, shape="spline",
                                                                     smoothing=0.6)))


# ---------------------------------------------------------------------------
# 1. Teste de estresse
# ---------------------------------------------------------------------------
if aba == "estresse":
    posicoes = sa.posicoes_estresse()
    opcoes = list(simulador.CENARIOS) + ["livre"]
    pedido = st.session_state.pop("sim_cenario", None)
    if pedido:
        st.session_state.sim_cenario_sel = "livre" if pedido.startswith("livre:") else pedido
        if pedido.startswith("livre:"):
            st.session_state.sim_livre_acoes = int(round(float(pedido.split(":")[1]) * 100))
    st.session_state.setdefault("sim_cenario_sel", "covid")
    st.session_state.setdefault("sim_livre_acoes", -30)
    escolha = st.pills("Crise", opcoes, key="sim_cenario_sel",
                       format_func=lambda k: "✏️ Montar a minha" if k == "livre" else simulador.CENARIOS[k].nome) or "covid"
    if escolha == "livre":
        with st.container(border=True):
            l1, l2, l3 = st.columns(3)
            acoes = l1.slider("Ações e ETFs", -80, 0, key="sim_livre_acoes", format="%d%%")
            fiis = l2.slider("Fundos imobiliários", -60, 0, -15, format="%d%%")
            fora = l3.slider("Exterior (BDRs)", -50, 50, 0, format="%d%%")
            l4, l5, l6 = st.columns(3)
            corte = l4.slider("Corte nos proventos", 0, 60, 15, format="%d%%")
            meses_q = l5.slider("Meses até o fundo", 0, 24, 3)
            meses_v = l6.slider("Meses para voltar", 1, 48, 12)
        cen = simulador.cenario_livre(acoes / 100, fiis / 100, fora / 100, corte / 100, meses_q, meses_v)
    else:
        cen = simulador.CENARIOS[escolha]
    aporte = st.number_input("Aporte mensal durante a crise (R$)", 0.0, 1_000_000.0, float(c.aporte_mensal), 100.0,
                             help="Quem segue aportando compra mais barato na queda. Ponha 0 para ver sem aportes.")
    r = simulador.estresse(posicoes, cen, c.caixa, aporte)
    estado.conquistar("estresse")
    if st.session_state.get("_trilha_cenario") != escolha:
        st.session_state._trilha_cenario = escolha
        estado.trilha("tensao")

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        tema.janela("No fundo da crise", brl(r.depois, 0), tema.variacao(r.queda, pct(r.queda, 1, sinal=True)), ouro=True)
    with k2:
        tema.janela("Perda no papel", brl(r.perda, 0), "Só vira perda real se vender")
    with k3:
        tema.janela("Proventos por mês", brl(r.renda_depois / 12, 0),
                    f"Hoje: {brl(r.renda_antes / 12, 0)}" + (f" (corte de {pct(cen.corte_proventos, 0)})" if cen.corte_proventos else ""))
    with k4:
        volta = cen.meses_queda + cen.meses_recuperacao
        tema.janela("Volta ao topo", f"{volta} {'mês' if volta == 1 else 'meses'}", cen.quando.capitalize() if escolha != "livre" else "No seu cenário")

    tema.fala(f"<b>{cen.nome}.</b> {cen.historia}<br><br>{sa.frase_estresse(r, aporte)}")

    g1, g2 = st.columns([3, 2], gap="large")
    with g1:
        st.subheader("O caminho, mês a mês")
        cam = r.caminho
        fig = go.Figure()
        _linha(fig, cam["aportado"], "Dinheiro colocado", COR("suave"), "dot", 1.6)
        _linha(fig, cam["sem_aporte"], "Sem novos aportes", COR("brasa"))
        if aporte:
            _linha(fig, cam["com_aporte"], f"Aportando {brl(aporte, 0)}/mês", COR("jade"), largura=3.2)
        fig.update_layout(height=360, yaxis_tickprefix="R$ ", xaxis_title="meses a partir de hoje", hovermode="x unified")
        tema.mostrar(fig)
    with g2:
        st.subheader("Impacto em cada ativo")
        t = r.por_ativo.sort_values("perda")
        fig2 = go.Figure(go.Bar(x=t["perda"], y=t["ativo"], orientation="h",
                                marker_color=[COR("brasa") if v < 0 else COR("jade") for v in t["perda"]],
                                text=[pct(v, 0, sinal=True) for v in t["choque"]], textposition="outside",
                                hovertemplate="%{y}: R$ %{x:,.0f}<extra></extra>"))
        fig2.update_layout(height=360, xaxis_tickprefix="R$ ", showlegend=False, margin=dict(r=60))
        tema.mostrar(fig2)
        tema.legenda("Ações e ETFs são ajustados pela sensibilidade de cada um ao Ibovespa no último ano (beta).")

    st.subheader("Todas as crises, lado a lado")
    comp = simulador.todos_os_cenarios(posicoes, c.caixa)
    st.dataframe(pd.DataFrame({"Crise": comp["cenario"], "Quando": comp["quando"],
                               "Queda da carteira": comp["queda"].map(lambda v: pct(v, 1, sinal=True)),
                               "Perda no papel": comp["perda"].map(lambda v: brl(v, 0)),
                               "Proventos/mês": (comp["renda_depois"] / 12).map(lambda v: brl(v, 0)),
                               "Volta (meses)": comp["meses_volta"]}),
                 hide_index=True, width="stretch")
    tema.legenda("Quedas aproximadas do topo ao fundo de cada período, para estudo. O passado não se repete igual: "
                 "isto não é previsão nem recomendação de investimento.")

# ---------------------------------------------------------------------------
# 2. Intenções: e se eu comprar ou vender?
# ---------------------------------------------------------------------------
elif aba == "intencoes":
    st.markdown("Escreva o que você pensa em fazer. Nada é enviado: o app só mostra como a carteira ficaria.")
    pedidas = st.session_state.pop("sim_intencoes", None)
    if pedidas:
        st.session_state.sim_tabela_intencoes = pd.DataFrame(
            [{"Operação": "Compra" if p["lado"] == "compra" else "Venda", "Ativo": p["ticker"],
              "Quantidade": float(p["quantidade"]), "Preço (opcional)": p.get("preco") or float("nan")} for p in pedidas])
    if "sim_tabela_intencoes" not in st.session_state:
        sugestao = ticker_curto(c.observar[0]) if c.observar else ticker_curto(c.posicoes[0].ticker)
        st.session_state.sim_tabela_intencoes = pd.DataFrame(
            [{"Operação": "Compra", "Ativo": sugestao, "Quantidade": 100.0, "Preço (opcional)": float("nan")}])
    editado = st.data_editor(
        st.session_state.sim_tabela_intencoes, num_rows="dynamic", width="stretch", key="sim_editor",
        column_config={"Operação": st.column_config.SelectboxColumn(options=["Compra", "Venda"], required=True),
                       "Ativo": st.column_config.TextColumn(help="Código, ex.: TAEE11", required=True),
                       "Quantidade": st.column_config.NumberColumn(min_value=1, step=1, format="%d"),
                       "Preço (opcional)": st.column_config.NumberColumn(min_value=0.01, format="R$ %.2f",
                                                                         help="Vazio = preço de agora")})
    intencoes = []
    for _, ln in editado.dropna(subset=["Ativo"]).iterrows():
        tk = ticker_curto(normalizar_ticker(str(ln["Ativo"])))
        if not tk or not ln.get("Quantidade"):
            continue
        preco = ln.get("Preço (opcional)")
        intencoes.append(simulador.Intencao(tk, "venda" if ln["Operação"] == "Venda" else "compra", float(ln["Quantidade"]),
                                            float(preco) if pd.notna(preco) and preco else None, sa.classe_provavel(tk)))
    if not intencoes:
        st.info("Adicione pelo menos uma linha com ativo e quantidade.")
        st.stop()
    r = sa.simular(intencoes)
    a, d = r.resumo("antes"), r.resumo("depois")

    def _nivel(hhi: float) -> str:
        return "baixa" if hhi < 0.10 else ("média" if hhi < 0.18 else "alta")

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        tema.janela("Dinheiro da operação", brl(abs(r.custo), 0), "sai do caixa" if r.custo >= 0 else "entra no caixa", ouro=True)
    with k2:
        tema.janela("Caixa depois", brl(r.caixa_depois, 0), tema.variacao(r.caixa_depois, "falta dinheiro") if r.caixa_depois < 0
                    else f"Hoje: {brl(r.caixa_antes, 0)}")
    with k3:
        delta = d["renda_mes"] - a["renda_mes"]
        tema.janela("Proventos por mês", brl(d["renda_mes"], 0), tema.variacao(delta, f"{brl(delta, 0)} por mês"))
    with k4:
        tema.janela("Concentração", _nivel(d["concentracao"]).capitalize(),
                    f"Maior: {d['maior_ativo']} com {pct(d['maior_peso'], 0)} (antes {_nivel(a['concentracao'])})")
    for aviso in r.avisos:
        tema.aviso(aviso)

    g1, g2 = st.columns([3, 2], gap="large")
    with g1:
        st.subheader("Peso de cada ativo")
        ativos = list(dict.fromkeys(list(r.depois["ativo"]) + list(r.antes["ativo"])))
        pa = r.antes.set_index("ativo")["peso"].reindex(ativos).fillna(0)
        pd_ = r.depois.set_index("ativo")["peso"].reindex(ativos).fillna(0)
        fig = go.Figure([go.Bar(name="Hoje", x=ativos, y=pa, marker_color=COR("suave"), opacity=.55),
                         go.Bar(name="Depois", x=ativos, y=pd_, marker_color=COR("ouro"))])
        fig.update_layout(barmode="group", height=340, yaxis_tickformat=".0%", bargap=.25)
        tema.mostrar(fig)
    with g2:
        st.subheader("Por tipo de ativo")
        metas = {k: (v / 100 if v and v > 1 else v) for k, v in (c.metas_classe or {}).items()}
        classes = sorted(set(a["por_classe"]) | set(d["por_classe"]) | set(metas))
        st.dataframe(pd.DataFrame({"Tipo": classes,
                                   "Hoje": [pct(a["por_classe"].get(k, 0), 0) for k in classes],
                                   "Depois": [pct(d["por_classe"].get(k, 0), 0) for k in classes],
                                   "Sua meta": [pct(metas[k], 0) if metas.get(k) else "—" for k in classes]}),
                     hide_index=True, width="stretch")
        crise = simulador.CENARIOS["covid"]
        antes_cr = simulador.estresse(sa.posicoes_de_tabela(r.antes), crise)
        depois_cr = simulador.estresse(sa.posicoes_de_tabela(r.depois), crise)
        tema.fala(f"Numa crise como a da <b>Covid</b>, a carteira cairia <b>{pct(-antes_cr.queda, 0)}</b> hoje e "
                  f"<b>{pct(-depois_cr.queda, 0)}</b> depois dessas operações.")

    if estado.permite("simulador") and st.button("Fazer na carteira simulada", type="primary"):
        from chronotrade import jarvis_app

        for it in intencoes:
            st.write(f"{it.lado.capitalize()} {it.quantidade:g} {it.ticker}: " + jarvis_app.executar_ordem(
                {"ticker": it.ticker, "lado": it.lado, "quantidade": int(it.quantidade), "preco": it.preco}))
    tema.legenda("Simulação com os preços e proventos dos últimos 12 meses. Não é recomendação: a decisão é sua.")

# ---------------------------------------------------------------------------
# 3. Futuros possíveis
# ---------------------------------------------------------------------------
else:
    tabela, resumo, _ = estado.tabela_e_resumo()
    f1, f2 = st.columns(2)
    meses = f1.slider("Olhar quantos meses à frente", 6, 60, 12, step=6)
    aporte = f2.number_input("Aporte mensal (R$)", 0.0, 1_000_000.0, float(c.aporte_mensal), 100.0, key="fut_aporte")
    pesos = dict(zip(tabela["ativo"], tabela["peso"], strict=False))
    hist = sa.historicos(tuple(tabela["ticker"]), estado.modo_demo())
    ret = simulador.retornos_carteira(hist, pesos)
    fut = simulador.simular_futuros(ret, float(tabela["valor"].sum()), meses, aporte)
    if fut is None:
        st.info("Ainda não há histórico de preços suficiente para simular. Tente mais tarde.")
        st.stop()
    fx = fut.faixas

    def _mil(v: float) -> str:
        return f"{v / 1000:,.1f} mil".replace(",", "X").replace(".", ",").replace("X", ".") if v < 1_000_000 else \
            f"{v / 1_000_000:,.2f} mi".replace(".", ",")
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        tema.janela("Cenário do meio", brl(fx["p50"].iloc[-1], 0), f"em {meses} meses", ouro=True)
    with k2:
        tema.janela("Faixa provável", f"{_mil(fx['p25'].iloc[-1])} a {_mil(fx['p75'].iloc[-1])}", "metade dos caminhos termina aqui")
    with k3:
        tema.janela("Chance de prejuízo", pct(fut.chance_prejuizo, 0), f"terminar abaixo de {brl(fut.aportado, 0)} colocados")
    with k4:
        tema.janela("Um mês ruim", pct(fut.pior_mes_95, 1, sinal=True), "acontece 1 vez a cada 20 meses")
    fig = go.Figure()
    x = fx["mes"]
    fig.add_trace(go.Scatter(x=list(x) + list(x[::-1]), y=list(fx["p95"]) + list(fx["p5"][::-1]), fill="toself",
                             fillcolor=COR("ouro") + "22", line=dict(width=0), name="9 em cada 10 caminhos", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=list(x) + list(x[::-1]), y=list(fx["p75"]) + list(fx["p25"][::-1]), fill="toself",
                             fillcolor=COR("ouro") + "44", line=dict(width=0), name="Metade dos caminhos", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=x, y=fx["p50"], mode="lines", name="Cenário do meio", line=dict(color=COR("ouro"), width=3)))
    fig.add_trace(go.Scatter(x=x, y=[float(tabela["valor"].sum()) + aporte * m for m in x], mode="lines",
                             name="Dinheiro colocado", line=dict(color=COR("suave"), dash="dot", width=1.6)))
    fig.update_layout(height=400, yaxis_tickprefix="R$ ", xaxis_title="meses a partir de hoje", hovermode="x unified")
    tema.mostrar(fig)
    tema.fala("Cada caminho sorteia meses reais dos últimos dois anos da sua carteira e os junta em sequência. "
              "Quanto mais longe, mais larga a faixa: ninguém sabe o futuro, mas dá para saber o tamanho do susto.")
    tema.legenda("Simulação estatística com base no passado recente, sem proventos. Não é previsão nem recomendação.")
