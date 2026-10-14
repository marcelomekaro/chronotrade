"""Oráculo: ficha rápida de buy and hold e a análise completa dos agentes de IA."""

from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from chronotrade import calculos, estado, motor_ia, tema
from chronotrade.calculos import brl, pct
from chronotrade.mercado import normalizar_ticker, ticker_curto

st.title("Oráculo")
c = estado.carteira()
sugestao = ticker_curto(c.posicoes[0].ticker) if c.posicoes else "TAEE11"

ficha, conselho, pergaminhos = st.tabs(["Ficha rápida", "Conselho dos agentes", "Análises guardadas"])

CORES_RATING = {
    "Buy": tema.CORES["jade"], "Overweight": tema.CORES["jade"], "Hold": tema.CORES["ouro"],
    "Underweight": tema.CORES["brasa"], "Sell": tema.CORES["brasa"], "REVIEW": tema.CORES["suave"],
}

# ---------------------------------------------------------------------------
# Ficha rápida: sem IA, em segundos
# ---------------------------------------------------------------------------
with ficha:
    st.markdown("Os números que um investidor de buy and hold olha antes de comprar. Não usa IA e sai na hora.")
    escolhido = st.text_input("Ticker", value=sugestao, key="ficha_ticker").strip()
    if escolhido:
        d = estado.ativo(normalizar_ticker(escolhido))
        if not d.ok:
            st.error(f"Não encontrei cotações para {escolhido.upper()}. {d.erro}")
        else:
            if d.fonte == "demo":
                tema.aviso("Modo demonstração: estes números são fictícios.")
            hoje = pd.Timestamp.today()
            prov12 = calculos.proventos_12m(d.dividendos, hoje)
            media5 = calculos.media_anual_proventos(d.dividendos, 5, hoje)
            teto = calculos.preco_teto_bazin(media5, c.taxa_bazin)
            graham = calculos.preco_justo_graham(d.lpa, d.vpa)
            dy = calculos.dividend_yield(prov12, d.preco)
            pl = d.preco / d.lpa if d.lpa else None
            pvp = d.preco / d.vpa if d.vpa else None
            divs = d.dividendos.copy()
            if not divs.empty and pd.DatetimeIndex(divs.index).tz is not None:
                divs.index = pd.DatetimeIndex(divs.index).tz_localize(None)
            anos_pagando = sorted(set(divs.index.year)) if not divs.empty else []
            seguidos = 0
            for ano in range(hoje.year - 1, hoje.year - 11, -1):
                if ano in anos_pagando:
                    seguidos += 1
                else:
                    break

            st.subheader(d.nome or d.ticker)
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                tema.janela("Preço", brl(d.preco), tema.variacao(d.variacao_dia, pct(d.variacao_dia, 2, sinal=True)
                                                                + " no dia"), ouro=True)
            with col2:
                tema.janela("Dividend yield 12m", pct(dy), f"{brl(prov12)} por cota")
            with col3:
                margem = calculos.margem_de_seguranca(teto, d.preco)
                tema.janela("Preço teto Bazin", brl(teto),
                            tema.variacao(margem, f"{pct(margem, 0, sinal=True)} de margem") if margem is not None else
                            "Sem proventos para calcular")
            with col4:
                margem_g = calculos.margem_de_seguranca(graham, d.preco)
                tema.janela("Preço justo Graham", brl(graham),
                            tema.variacao(margem_g, f"{pct(margem_g, 0, sinal=True)} de margem") if margem_g is not None else
                            "Precisa de lucro e patrimônio positivos")

            criterios = [
                (seguidos >= 5, f"Pagou proventos em {seguidos} dos últimos anos seguidos (ideal: 5 ou mais)"),
                (dy is not None and dy >= c.taxa_bazin, f"Dividend yield de {pct(dy)} (ideal: {pct(c.taxa_bazin, 0)} ou mais)"),
                (teto is not None and d.preco <= teto, "Preço abaixo do teto Bazin"),
                (pl is not None and 0 < pl <= 15, f"P/L de {pl:.1f}".replace(".", ",") + " (ideal: entre 0 e 15)"
                 if pl is not None else "P/L indisponível"),
                (pvp is not None and pvp <= 2, f"P/VP de {pvp:.2f}".replace(".", ",") + " (ideal: até 2)"
                 if pvp is not None else "P/VP indisponível"),
            ]
            st.subheader("Checklist do buy and hold")
            for ok, texto in criterios:
                st.markdown(f"{'✅' if ok else '⬜'} {texto}")
            tema.legenda("Critérios simples para filtrar candidatos. Antes de comprar, leia o negócio da empresa: "
                       "dívida, setor e se os lucros são recorrentes.")

            hist = d.historico.copy()
            if pd.DatetimeIndex(hist.index).tz is not None:
                hist.index = pd.DatetimeIndex(hist.index).tz_localize(None)
            fig = go.Figure(go.Scatter(x=hist.index, y=hist.values, name="Preço",
                                       line=dict(color=tema.CORES["ouro"], width=2),
                                       hovertemplate="%{x|%d/%m/%Y}: R$ %{y:,.2f}<extra></extra>"))
            if teto:
                fig.add_hline(y=teto, line=dict(color=tema.CORES["jade"], dash="dash"),
                              annotation_text="Preço teto", annotation_font_color=tema.CORES["jade"])
            fig.update_layout(height=320, yaxis_tickprefix="R$ ")
            st.subheader("Preço nos últimos 5 anos")
            tema.mostrar(fig)

# ---------------------------------------------------------------------------
# Conselho dos agentes: o TradingAgents completo
# ---------------------------------------------------------------------------
with conselho:
    st.markdown("Vários agentes de IA analisam o ativo, debatem entre si e um gestor dá o veredito. "
                "Leva de 5 a 20 minutos com o Gemini gratuito. Fique nesta página até terminar.")
    if estado.modo_demo():
        tema.aviso("O conselho sempre usa dados reais da internet, mesmo com o modo demonstração ligado.")

    cfg = motor_ia.configuracao_do_ambiente()
    with st.form("conselho"):
        col1, col2 = st.columns(2)
        ticker = col1.text_input("Ticker", value=sugestao)
        dia = col2.date_input("Data da análise", value=date.today() - timedelta(days=1),
                              max_value=date.today(), format="DD/MM/YYYY")
        analistas = st.multiselect("Analistas", options=list(motor_ia.ANALISTAS),
                                   default=["market", "fundamentals"],
                                   format_func=motor_ia.ANALISTAS.get,
                                   help="Menos analistas = análise mais rápida e menos pedidos à IA.")
        usar_carteira = st.checkbox("Considerar a minha carteira", value=bool(c.posicoes),
                                    help="Os agentes sabem quanto você já tem deste ativo e o caixa disponível. "
                                         "No plano gratuito do Gemini, o Google pode ler o que é enviado.")
        with st.expander("Modelo de IA"):
            col3, col4, col5 = st.columns(3)
            provedor = col3.selectbox("Provedor", ["google", "ollama", "openai", "anthropic", "groq"],
                                      index=["google", "ollama", "openai", "anthropic", "groq"].index(cfg.provedor)
                                      if cfg.provedor in ("google", "ollama", "openai", "anthropic", "groq") else 0)
            rapido = col4.text_input("Modelo rápido (analistas)", value=cfg.modelo_rapido)
            profundo = col5.text_input("Modelo profundo (gestores)", value=cfg.modelo_profundo)
            tema.legenda("Vem do seu arquivo .env. No Gemini gratuito, use modelos Flash ou Flash-Lite; os Pro são pagos.")
        enviar = st.form_submit_button("Consultar o conselho", type="primary")

    if enviar:
        if not analistas:
            st.error("Escolha pelo menos um analista.")
        elif not motor_ia.chave_configurada(provedor):
            st.error(f"Falta a chave do provedor {provedor} no arquivo .env. Para o Gemini, preencha GOOGLE_API_KEY.")
        else:
            config = motor_ia.Configuracao(provedor, rapido.strip(), profundo.strip())
            etapas = dict(motor_ia.ETAPAS)
            feitas: list[str] = []
            with st.status("O conselho está reunido…", expanded=True) as caixa:
                quadro = st.empty()

                def progresso(etapa: str, texto: str) -> None:
                    if etapa not in feitas:
                        feitas.append(etapa)
                    linhas = [f"{'✅' if k in feitas[:-1] else ('⏳' if k == feitas[-1] else '⬜')} {nome}"
                              for k, nome in motor_ia.ETAPAS]
                    quadro.markdown("\n\n".join(linhas) + f"\n\n_{texto}_")

                try:
                    res = motor_ia.analisar(normalizar_ticker(ticker), dia.isoformat(), analistas, config,
                                            carteira=c if usar_carteira and c.posicoes else None,
                                            ao_progredir=progresso)
                    caixa.update(label=f"Veredito: {motor_ia.ROTULOS.get(res.rating, res.rating)}",
                                 state="complete", expanded=False)
                    st.session_state.ultima_analise = res.pasta.name
                except Exception as erro:  # mostra o erro em linguagem simples
                    caixa.update(label="A análise parou no meio", state="error")
                    st.error(f"{type(erro).__name__}: {erro}")
                    st.info("Se o erro fala em limite (429 ou RESOURCE_EXHAUSTED), espere um minuto e tente de novo "
                            "com menos analistas.")

    salvas = motor_ia.analises_salvas()
    ultima = next((a for a in salvas if a.pasta.name == st.session_state.get("ultima_analise")), None)
    if ultima:
        cor = CORES_RATING.get(ultima.rating, tema.CORES["suave"])
        st.markdown(tema.selo(motor_ia.ROTULOS.get(ultima.rating, ultima.rating), cor), unsafe_allow_html=True)
        st.markdown(ultima.decisao)

# ---------------------------------------------------------------------------
# Análises guardadas
# ---------------------------------------------------------------------------
with pergaminhos:
    salvas = motor_ia.analises_salvas()
    if not salvas:
        st.info("Nenhuma análise guardada ainda. Rode uma no Conselho dos agentes.")
    else:
        opcoes = {f"{ticker_curto(a.ticker)} em {a.data}: {motor_ia.ROTULOS.get(a.rating, a.rating)}": a
                  for a in salvas}
        escolha = opcoes[st.selectbox("Análise", list(opcoes))]
        cor = CORES_RATING.get(escolha.rating, tema.CORES["suave"])
        st.markdown(tema.selo(motor_ia.ROTULOS.get(escolha.rating, escolha.rating), cor), unsafe_allow_html=True)
        if escolha.html:
            st.download_button("Baixar relatório completo (HTML)", escolha.html.read_bytes(),
                               file_name=f"{ticker_curto(escolha.ticker)}_{escolha.data}.html", mime="text/html")
        st.markdown(escolha.relatorio)
