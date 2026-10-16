"""Agenda de proventos: quando e quanto os próximos dividendos devem cair."""

from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from chronotrade import agenda, calculos, estado, tema
from chronotrade.calculos import brl
from chronotrade.mercado import ticker_curto

st.title("Agenda de proventos")
estado.exigir("agenda")
c = estado.carteira()
if not c.posicoes:
    tema.fala("Cadastre a carteira no Inventário para montar a agenda dos seus dividendos.")
    st.stop()

dados = estado.dados_da_carteira()
estado.avisar_fontes(dados)
hoje = date.today()
eventos: list[agenda.Evento] = []
for p in c.posicoes:
    d = dados.get(p.ticker)
    if d is not None:
        eventos += agenda.prever(p.ticker, d.dividendos, p.quantidade, hoje, meses=12, confirmado=d.proximo_provento)
eventos.sort(key=lambda e: e.data)

if not eventos:
    tema.fala("Não encontrei pagamentos recorrentes nos últimos dois anos para os ativos da carteira.")
    st.stop()

proximos_30 = [e for e in eventos if e.data <= hoje + timedelta(days=30)]
st.download_button("📅 Levar para a minha agenda (Google, Outlook, celular)", agenda.ics(eventos),
                   file_name="chronotrade_proventos.ics", mime="text/calendar",
                   help="Baixe e abra o arquivo: as datas com entram no seu calendário, com lembrete um dia antes.")
total_12m = sum(e.total for e in eventos)
col1, col2, col3 = st.columns(3)
with col1:
    tema.janela("Próximos 30 dias", brl(sum(e.total for e in proximos_30), 0), f"{len(proximos_30)} pagamentos esperados",
                ouro=True)
with col2:
    tema.janela("Próximos 12 meses", brl(total_12m, 0), f"{brl(total_12m / 12, 0)} por mês em média")
with col3:
    prox = eventos[0]
    tema.janela("Próxima data com", f"{prox.data:%d/%m}", f"{ticker_curto(prox.ticker)}, {prox.situacao.lower()}")

st.subheader("Mês a mês")
tabela_mes = agenda.por_mes(eventos)
meses = sorted(tabela_mes["mes"].unique())
rotulos = [calculos.mes_ano(m.to_timestamp()) for m in meses]
fig = go.Figure()
for ticker in tabela_mes.groupby("ticker")["total"].sum().sort_values(ascending=False).index:
    parte = tabela_mes[tabela_mes["ticker"] == ticker].set_index("mes")["total"].reindex(meses, fill_value=0)
    fig.add_trace(go.Bar(x=rotulos, y=parte.values, name=ticker_curto(ticker),
                         hovertemplate=f"{ticker_curto(ticker)}<br>%{{x}}: R$ %{{y:,.2f}}<extra></extra>"))
fig.update_layout(barmode="stack", height=360, yaxis_tickprefix="R$ ", hovermode="x unified")
tema.mostrar(fig)

st.subheader("Calendário")
st.dataframe(pd.DataFrame({
    "Data com": [f"{e.data:%d/%m/%Y}" for e in eventos],
    "Ativo": [ticker_curto(e.ticker) for e in eventos],
    "Por cota": [brl(e.valor_por_cota) for e in eventos],
    "Cotas": [f"{e.quantidade:,.0f}".replace(",", ".") for e in eventos],
    "Você recebe (aprox.)": [brl(e.total) for e in eventos],
    "Situação": [("✅ " if e.situacao == agenda.CONFIRMADO else "🔮 ") + e.situacao for e in eventos],
}), hide_index=True, width="stretch", height=min(36 * (len(eventos) + 1) + 4, 640))
tema.legenda("Confirmado: data com já anunciada pela empresa (fonte: Yahoo Finance). Previsto: repete os meses e "
             "valores dos últimos dois anos. O pagamento costuma cair de dias a semanas depois da data com. "
             "Empresas podem mudar ou cancelar proventos.")
tema.aviso_legal()
