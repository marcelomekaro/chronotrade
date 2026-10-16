"""Carteiras virtuais: treine com o capital que quiser, a preço de agora ou a um preço simulado, ao vivo."""

import html

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from chronotrade import carteiras_virtuais as cv, estado, simulacao_app as sa, tema
from chronotrade.calculos import brl, pct
from chronotrade.mercado import normalizar_ticker, preco_ao_vivo, ticker_curto

st.title("Carteiras virtuais")
tema.subtitulo("Treine com quanto dinheiro quiser: compre e venda a preço de agora ou a um preço que você escolher.")
estado.exigir("virtuais")
db = estado.carteiras_virtuais()
eu = estado.identidade()[0]
demo = estado.modo_demo()
carteiras = db.listar(eu)
if estado.visitante():
    tema.aviso("Modo visitante: as carteiras virtuais ficam só nesta visita.")


def _precos(tickers) -> dict[str, float]:
    return {t: preco_ao_vivo(t, demo)[0] for t in tickers}


# --- Nova carteira ------------------------------------------------------------------------
with st.expander("➕ Nova carteira virtual", expanded=not carteiras), st.form("nova_cv", clear_on_submit=True):
    n1, n2 = st.columns([2, 1])
    nome = n1.text_input("Nome", placeholder="Ex.: Dividendos 2030, Teste de day trade, Carteira do meu filho")
    capital = n2.number_input("Capital inicial (R$)", min_value=100.0, max_value=cv.CAPITAL_MAXIMO, value=10_000.0,
                              step=1000.0, help="Qualquer valor: de R$ 100 a R$ 100 milhões.")
    o1, o2 = st.columns([2, 1])
    objetivo = o1.text_input("Objetivo (opcional)", placeholder="Ex.: chegar a R$ 500/mês de proventos")
    taxa = o2.number_input("Corretagem por ordem (R$)", 0.0, 100.0, 0.0, 0.5,
                           help="Muitas corretoras cobram zero. Os emolumentos da B3 (uns 0,03%) já entram sozinhos.")
    if st.form_submit_button("Criar carteira", type="primary"):
        try:
            nova = db.criar(eu, nome, capital, objetivo, taxa)
            st.session_state.cv_sel = nova.id
            estado.trilha("incentivo")
            st.rerun()
        except cv.ErroCarteira as erro:
            st.error(str(erro))

if not carteiras:
    tema.fala("Crie a sua primeira carteira virtual: escolha um nome e o capital (pode ser R$ 10 mil, R$ 1 milhão…). "
              "Depois é só comprar e vender a preço de mercado e acompanhar o resultado ao vivo, sem arriscar nada.")
    st.stop()

# --- Resumo de todas -----------------------------------------------------------------------
ids = [c.id for c in carteiras]
if st.session_state.get("cv_sel") not in ids:
    st.session_state.cv_sel = ids[0]
escolhida = st.pills("Carteira", ids, key="cv_sel", format_func=lambda i: next(c.nome for c in carteiras if c.id == i),
                     label_visibility="collapsed") or ids[0]
carteira = next(c for c in carteiras if c.id == escolhida)


@st.fragment(run_every="8s")
def ao_vivo():
    caixa, posicoes, realizado = db.estado(carteira)
    precos = _precos(list(posicoes))
    total, linhas = cv.avaliar(caixa, posicoes, precos)
    db.registrar_valor(carteira.id, total)
    resultado = total - carteira.capital
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        tema.janela("Valor agora", brl(total, 0 if total >= 100_000 else 2), tema.variacao(resultado, f"{pct(resultado / carteira.capital, 2, sinal=True)} "
                                                             f"desde o início"), ouro=True)
    with k2:
        tema.janela("Resultado", brl(resultado), f"Realizado: {brl(realizado)}")
    with k3:
        tema.janela("Caixa", brl(caixa), f"{pct(caixa / total if total else 0, 0)} da carteira")
    with k4:
        tema.janela("Capital inicial", brl(carteira.capital, 0), html.escape(carteira.objetivo or "Sem objetivo definido"))
    if linhas:
        df = pd.DataFrame([{"Ativo": x["ativo"], "Qtd.": int(x["quantidade"]), "Preço médio": brl(x["preco_medio"]),
                            "Preço agora": brl(x["preco"]), "Valor": brl(x["valor"]), "Resultado": brl(x["resultado"]),
                            "%": pct(x["resultado_pct"], 2, sinal=True), "Peso": x["peso"]} for x in linhas])
        st.dataframe(df, hide_index=True, width="stretch",
                     column_config={"Peso": st.column_config.ProgressColumn("Peso", format="percent", min_value=0,
                                                                            max_value=1)})
        st.caption("Atualiza sozinho a cada 8 segundos" + (" (preços fictícios do modo demonstração)." if demo else
                                                          ". Cotações do Yahoo, com o atraso normal da B3."))
    else:
        st.info("Carteira vazia: faça a primeira compra abaixo.")


ao_vivo()

# --- Operar ------------------------------------------------------------------------------------
st.subheader("Comprar ou vender")
with st.container(border=True):
    a1, a2, a3 = st.columns([1.2, 1, 1])
    st.session_state.setdefault("cv_ativo", "TAEE11")
    ativo = ticker_curto(normalizar_ticker(a1.text_input("Ativo", key="cv_ativo", placeholder="TAEE11")))
    lado = a2.segmented_control("Operação", ["compra", "venda"], default="compra", key="cv_lado",
                                format_func=lambda x: "🟢 Compra" if x == "compra" else "🔴 Venda") or "compra"
    preco_agora, var_dia = preco_ao_vivo(ativo, demo) if ativo else (None, None)
    modo = a3.radio("Preço", ["agora", "simulado"], horizontal=True, key="cv_modo",
                    format_func=lambda x: "De agora" if x == "agora" else "Simular um preço")
    b1, b2, b3 = st.columns([1.2, 1, 1])
    if modo == "agora":
        b1.markdown(f"**{ativo}** agora: **{brl(preco_agora) if preco_agora else 'sem cotação'}**"
                    + (f" ({pct(var_dia, 2, sinal=True)} no dia)" if var_dia is not None else ""))
        preco = preco_agora
    else:
        preco = b1.number_input("Preço simulado (R$)", min_value=0.01, value=float(preco_agora or 10.0), step=0.1,
                                key="cv_preco")
    por_valor = b2.toggle("Por valor em R$", key="cv_por_valor", help="Diga quanto quer investir e o app calcula a quantidade.")
    if por_valor:
        quanto = b3.number_input("Valor (R$)", min_value=1.0, value=1000.0, step=100.0, key="cv_valor")
        qtd = int(quanto // preco) if preco else 0
        b3.caption(f"= {qtd} cotas")
    else:
        qtd = int(b3.number_input("Quantidade", min_value=1, value=100, step=1, key="cv_qtd"))
    if st.button(f"{'Comprar' if lado == 'compra' else 'Vender'} {qtd} {ativo}", type="primary", disabled=not (ativo and qtd)):
        try:
            op = db.operar(carteira.id, eu, ativo, lado, qtd, preco, sa.classe_provavel(ativo),
                           "mercado" if modo == "agora" else "simulado")
            st.toast(f"{'Compra' if lado == 'compra' else 'Venda'} de {qtd} {ativo} a {brl(op.preco)} feita.", icon="✅")
            estado.trilha("incentivo" if lado == "compra" else "felicidade")
            st.rerun()
        except cv.ErroCarteira as erro:
            st.error(str(erro))

# --- Histórico, extrato e ações ------------------------------------------------------------------
hist = db.historico(carteira.id)
ops = db.operacoes(carteira.id)
g1, g2 = st.columns([3, 2], gap="large")
with g1:
    st.subheader("Evolução")
    if len(hist) >= 2:
        fig = go.Figure(go.Scatter(x=[h[0] for h in hist], y=[h[1] for h in hist], mode="lines+markers",
                                   line=dict(color=carteira.cor, width=3, shape="spline"), fill="tozeroy",
                                   fillcolor=carteira.cor + "22"))
        fig.add_hline(y=carteira.capital, line_dash="dot", line_color=tema.cor("suave"),
                      annotation_text="capital inicial", annotation_position="top left")
        fig.update_layout(height=300, yaxis_tickprefix="R$ ", showlegend=False)
        tema.mostrar(fig)
    else:
        st.caption("O valor é guardado uma vez por dia (pelo app aberto e pelo agente). Volte amanhã para ver a curva.")
with g2:
    st.subheader("Extrato")
    if ops:
        st.dataframe(pd.DataFrame([{"Quando": o.quando.strftime("%d/%m %H:%M"), "Op.": "C" if o.lado == "compra" else "V",
                                    "Ativo": o.ticker, "Qtd.": int(o.quantidade), "Preço": brl(o.preco),
                                    "Tipo": "simulado" if o.origem == "simulado" else "mercado"} for o in reversed(ops)]),
                     hide_index=True, width="stretch", height=260)
    else:
        st.caption("Sem operações ainda.")

c1, c2, c3 = st.columns(3)
if ops and c1.button("🧾 Calcular o IR destas operações", width="stretch"):
    st.session_state.ir_operacoes = [{"data": o.quando.date().isoformat(), "ticker": o.ticker, "lado": o.lado,
                                      "quantidade": o.quantidade, "preco": o.preco, "classe": o.classe, "taxas": o.taxas}
                                     for o in ops]
    st.switch_page("paginas/impostos.py")
with c2.popover("↺ Recomeçar", width="stretch"):
    novo_capital = st.number_input("Novo capital (R$)", 100.0, cv.CAPITAL_MAXIMO, float(carteira.capital), 1000.0)
    if st.button("Zerar operações", type="primary"):
        db.recomecar(carteira.id, eu, novo_capital)
        st.rerun()
with c3.popover("🗑️ Apagar carteira", width="stretch"):
    st.write(f"Apagar **{html.escape(carteira.nome)}** e todas as operações?")
    if st.button("Apagar de vez"):
        db.apagar(carteira.id, eu)
        st.session_state.pop("cv_sel", None)
        st.rerun()

if len(carteiras) > 1:
    st.subheader("Comparar carteiras")
    linhas = []
    for c in carteiras:
        caixa, posicoes, _ = db.estado(c)
        total, _ = cv.avaliar(caixa, posicoes, _precos(list(posicoes)))
        linhas.append({"Carteira": c.nome, "Capital": brl(c.capital, 0), "Valor agora": brl(total),
                       "Resultado": pct(total / c.capital - 1, 2, sinal=True), "Ativos": len(posicoes)})
    st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch")
tema.legenda("Carteiras virtuais são treino: nenhuma ordem vai para a corretora. Não é recomendação de investimento.")
