"""Imposto de renda na bolsa: day trade e swing trade, mês a mês, com DARF e vencimento."""

from datetime import date

import pandas as pd
import streamlit as st

from chronotrade import estado, ir, simulacao_app as sa, tema
from chronotrade.calculos import brl
from chronotrade.carteira import pasta_dados
from chronotrade.mercado import ticker_curto

st.title("Imposto de renda na bolsa")
tema.subtitulo("Day trade e swing trade: quanto pagar, até quando e com qual DARF. Para conferir antes de pagar.")
estado.exigir("impostos")
eu = estado.identidade()[0]

with st.expander("📘 As regras de 2026, em resumo", expanded=False):
    st.markdown(
        "| | Swing trade (comum) | Day trade |\n|---|---|---|\n"
        "| Ações | **15%** do lucro; **isento** se vender até **R$ 20 mil** em ações no mês | **20%**, sem isenção |\n"
        "| ETFs e BDRs | **15%**, sem isenção | **20%** |\n"
        "| Fundos imobiliários | **20%**, sem isenção | **20%** |\n"
        "| IRRF (\"dedo-duro\") | 0,005% sobre as vendas | 1% sobre o lucro do dia |\n\n"
        "- Prejuízo só abate lucro da mesma modalidade (day trade com day trade; comum com comum; FII com FII) e não "
        "vence: fica guardado para os meses seguintes.\n"
        "- **DARF código 6015**, até o **último dia útil do mês seguinte**. Abaixo de R$ 10 não se paga: acumula.\n"
        "- A MP 1.303/2025 (alíquota única de 17,5%) não virou lei: as regras acima seguem valendo em 2026.\n"
        "- Dividendos: desde 2026, quem recebe **mais de R$ 50 mil por mês de uma mesma empresa** tem 10% retidos "
        "na fonte (Lei 15.270/2025). Rendimentos de FII seguem isentos para a pessoa física, nas condições da lei.")

# --- Operações -------------------------------------------------------------------------------
COLUNAS = ["Data", "Operação", "Ativo", "Quantidade", "Preço", "Taxas", "Classe"]
vindas = st.session_state.pop("ir_operacoes", None)
if vindas:
    st.session_state.ir_tabela = pd.DataFrame([{
        "Data": pd.to_datetime(o["data"]).date(), "Operação": "Venda" if o["lado"] == "venda" else "Compra",
        "Ativo": o["ticker"], "Quantidade": float(o["quantidade"]), "Preço": float(o["preco"]),
        "Taxas": float(o.get("taxas") or 0), "Classe": o.get("classe") or "Ação"} for o in vindas])
    st.toast("Operações da carteira virtual carregadas (IR simulado).", icon="🧾")
if "ir_tabela" not in st.session_state:
    hoje = date.today()
    st.session_state.ir_tabela = pd.DataFrame([
        {"Data": hoje.replace(day=1), "Operação": "Compra", "Ativo": "PETR4", "Quantidade": 500.0, "Preço": 36.0,
         "Taxas": 0.0, "Classe": "Ação"},
        {"Data": hoje.replace(day=1), "Operação": "Venda", "Ativo": "PETR4", "Quantidade": 500.0, "Preço": 36.8,
         "Taxas": 0.0, "Classe": "Ação"},
        {"Data": hoje.replace(day=2), "Operação": "Compra", "Ativo": "BBAS3", "Quantidade": 1000.0, "Preço": 25.0,
         "Taxas": 0.0, "Classe": "Ação"},
        {"Data": hoje.replace(day=3), "Operação": "Venda", "Ativo": "BBAS3", "Quantidade": 1000.0, "Preço": 27.0,
         "Taxas": 0.0, "Classe": "Ação"}])

origem = st.segmented_control("De onde vêm as operações", ["digitar", "planilha", "virtual"], default="digitar",
                              format_func={"digitar": "✍️ Digitar", "planilha": "📄 Planilha da B3",
                                           "virtual": "🧪 Carteira virtual"}.get, key="ir_origem")
if origem == "planilha":
    arquivo = st.file_uploader("Planilha de negociação (CSV ou Excel)", type=["csv", "xlsx", "xls"],
                               help="Na Área do Investidor da B3: Extratos → Negociação → baixar em Excel. "
                                    "Também serve qualquer planilha com data, compra/venda, ativo, quantidade e preço.")
    if arquivo is not None:
        try:
            df = pd.read_csv(arquivo, sep=None, engine="python") if arquivo.name.lower().endswith(".csv") \
                else pd.read_excel(arquivo)
            ops = ir.ler_planilha(df)
            st.session_state.ir_tabela = pd.DataFrame([{
                "Data": o.data, "Operação": "Venda" if o.lado == "venda" else "Compra", "Ativo": o.ticker,
                "Quantidade": o.quantidade, "Preço": o.preco, "Taxas": o.taxas,
                "Classe": sa.classe_provavel(o.ticker) if o.classe == "Ação" else o.classe} for o in ops])
            st.success(f"{len(ops)} operações importadas.")
        except Exception as erro:
            st.error(f"Não consegui ler a planilha: {erro}")
elif origem == "virtual":
    carteiras = estado.carteiras_virtuais().listar(eu)
    if not carteiras:
        st.info("Você ainda não tem carteiras virtuais.")
        st.page_link("paginas/virtuais.py", label="Criar uma carteira virtual", icon="🧪")
    else:
        cid = st.selectbox("Carteira virtual", [c.id for c in carteiras],
                           format_func=lambda i: next(c.nome for c in carteiras if c.id == i))
        if st.button("Carregar operações"):
            ops = estado.carteiras_virtuais().operacoes(cid)
            st.session_state.ir_tabela = pd.DataFrame([{
                "Data": o.quando.date(), "Operação": "Venda" if o.lado == "venda" else "Compra", "Ativo": o.ticker,
                "Quantidade": o.quantidade, "Preço": o.preco, "Taxas": o.taxas, "Classe": o.classe} for o in ops],
                columns=COLUNAS)
            st.rerun()

tabela = st.data_editor(
    st.session_state.ir_tabela, num_rows="dynamic", width="stretch", key="ir_editor",
    column_config={"Data": st.column_config.DateColumn(format="DD/MM/YYYY", required=True),
                   "Operação": st.column_config.SelectboxColumn(options=["Compra", "Venda"], required=True),
                   "Ativo": st.column_config.TextColumn(required=True),
                   "Quantidade": st.column_config.NumberColumn(min_value=0, step=1, format="%d"),
                   "Preço": st.column_config.NumberColumn(min_value=0.0, format="R$ %.2f"),
                   "Taxas": st.column_config.NumberColumn(min_value=0.0, format="R$ %.2f",
                                                          help="Corretagem + emolumentos da nota"),
                   "Classe": st.column_config.SelectboxColumn(options=["Ação", "FII", "ETF", "BDR"], required=True)})

with st.expander("Posição e prejuízos de antes destas operações"):
    usar_inventario = st.toggle("Usar o meu Inventário como posição inicial", value=False,
                                help="Se você vendeu ações compradas antes, o preço médio do Inventário entra no cálculo.")
    p1, p2, p3 = st.columns(3)
    prej_comum = p1.number_input("Prejuízo a compensar: comum (R$)", 0.0, step=100.0)
    prej_day = p2.number_input("Prejuízo a compensar: day trade (R$)", 0.0, step=100.0)
    prej_fii = p3.number_input("Prejuízo a compensar: FII (R$)", 0.0, step=100.0)

operacoes = []
for _, ln in tabela.dropna(subset=["Data", "Ativo"]).iterrows():
    if not ln.get("Quantidade") or not ln.get("Preço"):
        continue
    operacoes.append(ir.Operacao(pd.to_datetime(ln["Data"]).date(), str(ln["Ativo"]).upper().strip(),
                                 "venda" if ln["Operação"] == "Venda" else "compra", float(ln["Quantidade"]),
                                 float(ln["Preço"]), ln.get("Classe") or "Ação", float(ln.get("Taxas") or 0)))
if not operacoes:
    st.info("Adicione operações para calcular.")
    st.stop()
iniciais = {ticker_curto(p.ticker): (p.quantidade, p.preco_medio) for p in estado.carteira().posicoes} \
    if usar_inventario else None
apuracao = ir.apurar(operacoes, {"comum": prej_comum, "day": prej_day, "fii": prej_fii}, iniciais)

# --- Resultado ------------------------------------------------------------------------------------
ultimo = apuracao.meses[-1] if apuracao.meses else None
proximo = next((m for m in apuracao.meses if m.darf > 0 and m.vencimento >= date.today()), None)
k1, k2, k3, k4 = st.columns(4)
with k1:
    tema.janela("DARF a pagar (total)", brl(apuracao.total_darf), f"código {ir.CODIGO_DARF}", ouro=True)
with k2:
    tema.janela("Próximo vencimento", f"{proximo.vencimento:%d/%m/%Y}" if proximo else "Nada a pagar",
                f"{brl(proximo.darf)} de {proximo.mes[5:]}/{proximo.mes[:4]}" if proximo else "Confira os meses abaixo")
with k3:
    pre = ultimo.prejuizo_acumulado if ultimo else {"comum": 0, "day": 0, "fii": 0}
    tema.janela("Prejuízo guardado", brl(sum(pre.values())),
                f"Comum {brl(pre['comum'], 0)} · Day {brl(pre['day'], 0)} · FII {brl(pre['fii'], 0)}")
with k4:
    tema.janela("Vendas de ações no último mês", brl(ultimo.vendas_acoes if ultimo else 0, 0),
                "✅ dentro da isenção de R$ 20 mil" if ultimo and ultimo.isento else "acima de R$ 20 mil: sem isenção")
for aviso in apuracao.avisos[:5]:
    tema.aviso(aviso)

linhas = []
for m in apuracao.meses:
    linhas.append({"Mês": f"{m.mes[5:]}/{m.mes[:4]}", "Vendas de ações": brl(m.vendas_acoes, 0),
                   "Lucro isento": brl(m.lucro_isento) if m.lucro_isento else "—",
                   "Swing": brl(m.lucro["comum"]), "Day trade": brl(m.lucro["day"]), "FII": brl(m.lucro["fii"]),
                   "Prejuízo usado": brl(sum(m.prejuizo_usado.values())),
                   "Imposto": brl(sum(m.imposto.values())), "IRRF": brl(sum(m.irrf.values())),
                   "DARF": brl(m.darf) if m.darf else ("acumula" if m.devido else "—"),
                   "Vence": f"{m.vencimento:%d/%m/%Y}" if m.darf else ""})
st.subheader("Mês a mês")
st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch")

with st.expander("Cada resultado realizado"):
    st.dataframe(pd.DataFrame([{"Data": f"{r.data:%d/%m/%Y}", "Ativo": r.ticker, "Modalidade": ir.NOMES[r.modalidade],
                                "Qtd.": int(r.quantidade), "Venda": brl(r.venda), "Custo": brl(r.custo),
                                "Lucro": brl(r.lucro)} for r in apuracao.resultados]), hide_index=True, width="stretch")

if proximo:
    tema.fala(f"Para pagar: gere o DARF no <b>Sicalc Web</b> da Receita com o código <b>{ir.CODIGO_DARF}</b>, "
              f"período de apuração <b>{proximo.mes[5:]}/{proximo.mes[:4]}</b>, valor <b>{brl(proximo.darf)}</b>, "
              f"até <b>{proximo.vencimento:%d/%m/%Y}</b>. Depois do prazo entram multa e juros.")
    if not estado.visitante() and st.button("🔔 Me lembrar do vencimento", type="primary"):
        n = ir.Lembretes(pasta_dados() / "contas.db").guardar(eu, apuracao)
        st.toast(f"Pronto: o agente Sentinela avisa {n} DARF(s) 5 dias antes de vencer.", icon="🔔")
tema.legenda("Calculadora de estudo e conferência, com feriados fora da conta do vencimento. Confirme com um contador "
             "e com a Receita Federal. Não é consultoria tributária nem recomendação de investimento.")
