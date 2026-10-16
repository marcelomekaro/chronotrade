"""Inventário: cadastrar a carteira e ver o raio-x de cada posição."""

import pandas as pd
import streamlit as st

from chronotrade import estado, tema
from chronotrade.calculos import brl, pct
from chronotrade.carteira import CLASSES, ler_csv

st.title("Inventário")
tema.subtitulo("Os ativos que você tem, com quantidade, preço médio e quanto cada um rende.")
c = estado.carteira()


def _limitar_plano_gratuito() -> list[str]:
    limite = estado.limite_ativos()
    if limite is None or len(c.posicoes) <= limite:
        return []
    cortados = [p.ticker for p in c.posicoes[limite:]]
    c.posicoes = c.posicoes[:limite]
    return [f"O plano Básico acompanha até {limite} ativos; o Médio e o Premium não têm limite. "
            f"Ficaram de fora: {', '.join(cortados)}."]


tema.fala("Cadastre cada ativo com a <b>quantidade</b> e o <b>preço médio</b> que aparecem na sua corretora. "
          "Escreva o ticker sem o .SA (por exemplo PETR4 ou HGLG11). "
          "Os dados ficam só no seu computador, na pasta <code>.chronotrade</code>.")

# --- Plano ---------------------------------------------------------------------
st.subheader("Seu plano")
col1, col2, col3, col4 = st.columns(4)
aporte = col1.number_input("Aporte mensal (R$)", min_value=0.0, format="%.0f", step=100.0, value=float(c.aporte_mensal))
meta = col2.number_input("Meta de renda mensal (R$)", min_value=0.0, format="%.0f", step=500.0, value=float(c.meta_renda_mensal))
caixa = col3.number_input("Dinheiro em caixa (R$)", min_value=0.0, format="%.0f", step=100.0, value=float(c.caixa))
taxa = col4.number_input("Proventos mínimos para o preço teto (% ao ano)", min_value=1.0, max_value=20.0,
                         step=0.5, value=float(c.taxa_bazin * 100), format="%.1f",
                         help="Método Bazin: só vale comprar se os proventos médios renderem pelo menos esta taxa.")

# --- Posições -----------------------------------------------------------------------
st.subheader("Posições")
editada = st.data_editor(
    c.como_tabela_editavel(),
    num_rows="dynamic",
    width="stretch",
    hide_index=True,
    key="editor_carteira",
    column_config={
        "Ticker": st.column_config.TextColumn(required=True, max_chars=12),
        "Classe": st.column_config.SelectboxColumn(options=CLASSES, required=False,
                                                   help="Se deixar vazio, adivinho: final 11 vira FII."),
        "Quantidade": st.column_config.NumberColumn(min_value=0, step=1, format="localized"),
        "Preço médio": st.column_config.NumberColumn("Preço médio (R$)", min_value=0, step=0.01,
                                                     format="localized"),
    },
)

botao, importar, exportar = st.columns([1, 1.4, 1])
with botao:
    if st.button("Salvar carteira", type="primary"):
        avisos = c.atualizar_de_tabela(editada)
        c.aporte_mensal, c.meta_renda_mensal, c.caixa, c.taxa_bazin = aporte, meta, caixa, taxa / 100
        avisos += _limitar_plano_gratuito()
        for a in avisos:
            st.warning(a)
        if estado.salvar():
            st.success(f"Carteira salva com {len(c.posicoes)} posições.")
        else:
            st.info("No modo visitante a carteira vale até você fechar o navegador. "
                    "Crie a sua conta para guardar.")
with importar:
    arquivo = st.file_uploader("Importar planilha CSV", type=["csv"],
                               help="Colunas: ticker; quantidade; preço médio; classe (as duas últimas são opcionais).")
    if arquivo is not None and st.button("Usar esta planilha"):
        try:
            avisos = c.atualizar_de_tabela(ler_csv(arquivo.getvalue())) + _limitar_plano_gratuito()
            estado.salvar()
            st.success(f"Importei {len(c.posicoes)} posições.")
            for a in avisos:
                st.warning(a)
            st.rerun()
        except ValueError as erro:
            st.error(str(erro))
with exportar:
    st.download_button("Baixar carteira em CSV",
                       c.como_tabela_editavel().to_csv(sep=";", index=False, decimal=",").encode("utf-8-sig"),
                       file_name="carteira_chronotrade.csv", mime="text/csv")

if not c.posicoes:
    st.stop()

# --- Raio-x ----------------------------------------------------------------------
st.subheader("Raio-x da carteira")
tabela, r, dados = estado.tabela_e_resumo()
estado.avisar_fontes(dados)

def _num(v, casas=0):
    return "—" if v is None or pd.isna(v) else f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


margem = (tabela["teto_bazin"] - tabela["preco"]) / tabela["teto_bazin"]
vista = pd.DataFrame({
    "Ativo": tabela["ativo"],
    "Classe": tabela["classe"],
    "Qtd": tabela["quantidade"].map(_num),
    "Preço médio": tabela["preco_medio"].map(brl),
    "Preço hoje": tabela["preco"].map(brl),
    "Dia": tabela["variacao_dia"].map(lambda v: pct(v, 2, sinal=True)),
    "Valor": tabela["valor"].map(lambda v: brl(v, 0)),
    "Resultado": tabela["resultado_pct"].map(lambda v: pct(v, sinal=True)),
    "Peso": tabela["peso"].map(pct),
    "DY 12m": tabela["dy"].map(pct),
    "Yield on cost": tabela["yoc"].map(pct),
    "Preço teto Bazin": tabela["teto_bazin"].map(brl),
    "Margem até o teto": margem.map(lambda v: pct(v, 0, sinal=True)),
})


def _cor(valor: str) -> str:
    if valor.startswith("+"):
        return f"color: {tema.CORES['jade']}"
    if valor.startswith("-"):
        return f"color: {tema.CORES['brasa']}"
    return ""


st.dataframe(
    vista.style.map(_cor, subset=["Dia", "Resultado", "Margem até o teto"]),
    hide_index=True, width="stretch",
    column_config={"Margem até o teto": st.column_config.TextColumn(
        help="Positivo: o preço está abaixo do teto. Negativo: está acima.")},
)
tema.legenda(f"Total investido {brl(r.custo)}, valendo hoje {brl(r.patrimonio - r.caixa)}. "
           "O preço teto usa a média de proventos dos últimos 5 anos. É um filtro, não uma ordem de compra.")
