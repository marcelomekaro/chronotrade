"""Cálculos de buy and hold do Chrono Trade.

Funções puras, sem internet e sem Streamlit, para poderem ser testadas sozinhas:
proventos, preço teto, número mágico e projeção da carteira ao longo do tempo.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import pandas as pd

# ---------------------------------------------------------------------------
# Proventos
# ---------------------------------------------------------------------------


def _sem_fuso(serie: pd.Series) -> pd.Series:
    """Datas sem fuso horário, para comparar com qualquer data de referência."""
    if serie is None or serie.empty:
        return pd.Series(dtype=float)
    serie = serie.copy()
    indice = pd.DatetimeIndex(serie.index)
    if indice.tz is not None:
        indice = indice.tz_localize(None)
    serie.index = indice
    return serie.sort_index()


def proventos_12m(dividendos: pd.Series, hoje: pd.Timestamp | None = None) -> float:
    """Soma dos proventos por ação pagos nos últimos 12 meses."""
    serie = _sem_fuso(dividendos)
    if serie.empty:
        return 0.0
    hoje = pd.Timestamp(hoje or pd.Timestamp.today()).tz_localize(None).normalize()
    inicio = hoje - pd.DateOffset(years=1)
    return float(serie[(serie.index > inicio) & (serie.index <= hoje)].sum())


def media_anual_proventos(dividendos: pd.Series, anos: int = 5,
                          hoje: pd.Timestamp | None = None) -> float:
    """Média anual dos proventos por ação nos últimos ``anos`` anos completos.

    Usa só os anos em que houve pagamento dentro da janela, para não punir uma
    empresa listada há menos tempo.
    """
    serie = _sem_fuso(dividendos)
    if serie.empty:
        return 0.0
    hoje = pd.Timestamp(hoje or pd.Timestamp.today()).tz_localize(None)
    ultimo_ano = hoje.year - 1
    janela = serie[(serie.index.year > ultimo_ano - anos) & (serie.index.year <= ultimo_ano)]
    if janela.empty:
        return proventos_12m(serie, hoje)
    por_ano = janela.groupby(janela.index.year).sum()
    return float(por_ano.mean())


def proventos_por_mes(dividendos: pd.Series, quantidade: float,
                      meses: int = 24, hoje: pd.Timestamp | None = None) -> pd.Series:
    """Proventos recebidos por mês (R$) para uma quantidade de ações."""
    serie = _sem_fuso(dividendos)
    hoje = pd.Timestamp(hoje or pd.Timestamp.today()).tz_localize(None)
    fim = hoje.to_period("M")
    periodos = pd.period_range(fim - (meses - 1), fim, freq="M")
    if serie.empty:
        return pd.Series(0.0, index=periodos)
    mensal = (serie * quantidade).groupby(serie.index.to_period("M")).sum()
    return mensal.reindex(periodos, fill_value=0.0)


def dividend_yield(proventos_ano: float, preco: float | None) -> float | None:
    """Dividend yield (proventos do ano ÷ preço), em fração: 0,08 = 8%."""
    if not preco or preco <= 0:
        return None
    return proventos_ano / preco


def yield_on_cost(proventos_ano: float, preco_medio: float | None) -> float | None:
    """Rendimento sobre o preço que você pagou (preço médio)."""
    return dividend_yield(proventos_ano, preco_medio)


# ---------------------------------------------------------------------------
# Preço justo / preço teto
# ---------------------------------------------------------------------------


def preco_teto_bazin(media_proventos_ano: float, taxa_minima: float = 0.06) -> float | None:
    """Método Bazin: o maior preço que ainda paga ``taxa_minima`` em proventos."""
    if media_proventos_ano <= 0 or taxa_minima <= 0:
        return None
    return media_proventos_ano / taxa_minima


def preco_justo_graham(lpa: float | None, vpa: float | None) -> float | None:
    """Fórmula de Graham: √(22,5 × LPA × VPA). Só vale com lucro e patrimônio positivos."""
    if lpa is None or vpa is None or lpa <= 0 or vpa <= 0:
        return None
    return math.sqrt(22.5 * lpa * vpa)


def margem_de_seguranca(preco_referencia: float | None, preco_atual: float | None) -> float | None:
    """Quanto o preço atual está abaixo (+) ou acima (−) do preço de referência."""
    if not preco_referencia or not preco_atual or preco_referencia <= 0:
        return None
    return (preco_referencia - preco_atual) / preco_referencia


def numero_magico(preco: float | None, proventos_ano_por_acao: float) -> int | None:
    """Ações necessárias para que os proventos de um mês comprem mais uma ação."""
    if not preco or preco <= 0 or proventos_ano_por_acao <= 0:
        return None
    mensal = proventos_ano_por_acao / 12
    return math.ceil(round(preco / mensal, 6))


# ---------------------------------------------------------------------------
# Projeção
# ---------------------------------------------------------------------------


@dataclass
class Premissas:
    patrimonio_inicial: float
    aporte_mensal: float
    valorizacao_anual: float      # crescimento do preço, em fração (0,04 = 4% ao ano)
    dividend_yield_anual: float   # proventos sobre o patrimônio, em fração
    anos: int = 20
    reinvestir: bool = True
    reajuste_aporte_anual: float = 0.0  # aumento do aporte a cada 12 meses


@dataclass
class Marco:
    mes: int
    titulo: str
    descricao: str


@dataclass
class Projecao:
    tabela: pd.DataFrame
    marcos: list[Marco] = field(default_factory=list)


def _anual_para_mensal(taxa_anual: float) -> float:
    return (1 + taxa_anual) ** (1 / 12) - 1


def projetar(p: Premissas, meta_renda_mensal: float | None = None) -> Projecao:
    """Simula a carteira mês a mês.

    A cada mês: o patrimônio valoriza, paga proventos (DY ÷ 12) e recebe o
    aporte. Com ``reinvestir`` os proventos voltam para a carteira; sem ele, se
    acumulam à parte como renda recebida.
    """
    g = _anual_para_mensal(p.valorizacao_anual)
    dy_mes = p.dividend_yield_anual / 12
    patrimonio = float(p.patrimonio_inicial)
    aporte = float(p.aporte_mensal)
    investido = float(p.patrimonio_inicial)
    renda_acumulada = 0.0

    linhas = [{
        "mes": 0, "ano": 0.0, "patrimonio": patrimonio, "investido": investido,
        "renda_mensal": patrimonio * dy_mes, "proventos_acumulados": 0.0, "aporte": 0.0,
    }]
    for mes in range(1, p.anos * 12 + 1):
        if mes > 1 and (mes - 1) % 12 == 0:
            aporte *= 1 + p.reajuste_aporte_anual
        patrimonio *= 1 + g
        renda = patrimonio * dy_mes
        renda_acumulada += renda
        if p.reinvestir:
            patrimonio += renda
        patrimonio += aporte
        investido += aporte
        linhas.append({
            "mes": mes, "ano": mes / 12, "patrimonio": patrimonio, "investido": investido,
            "renda_mensal": renda, "proventos_acumulados": renda_acumulada, "aporte": aporte,
        })

    tabela = pd.DataFrame(linhas)
    return Projecao(tabela=tabela, marcos=_marcos(tabela, meta_renda_mensal))


def _primeiro(tabela: pd.DataFrame, condicao: pd.Series) -> int | None:
    meses = tabela.loc[condicao & (tabela["mes"] > 0), "mes"]
    return int(meses.iloc[0]) if not meses.empty else None


def _marcos(t: pd.DataFrame, meta: float | None) -> list[Marco]:
    """As "eras" da jornada: momentos que mudam a vida de quem faz buy and hold."""
    marcos: list[Marco] = []
    inicial_renda = float(t["renda_mensal"].iloc[0])
    inicial_patr = float(t["patrimonio"].iloc[0])

    for valor in (100, 1_000, 5_000):
        if inicial_renda < valor:
            mes = _primeiro(t, t["renda_mensal"] >= valor)
            if mes:
                marcos.append(Marco(mes, f"Renda de R$ {valor:,.0f}/mês".replace(",", "."),
                                    f"Os proventos passam a pagar R$ {valor:,.0f} por mês.".replace(",", ".")))

    mes = _primeiro(t, (t["renda_mensal"] >= t["aporte"]) & (t["aporte"] > 0))
    if mes and t["renda_mensal"].iloc[0] < t["aporte"].iloc[1]:
        marcos.append(Marco(mes, "Bola de neve",
                            "Os proventos do mês já superam o seu aporte."))

    for valor, nome in ((100_000, "R$ 100 mil"), (500_000, "R$ 500 mil"), (1_000_000, "R$ 1 milhão")):
        if inicial_patr < valor:
            mes = _primeiro(t, t["patrimonio"] >= valor)
            if mes:
                marcos.append(Marco(mes, f"Patrimônio de {nome}", f"A carteira atinge {nome}."))

    if meta and inicial_renda < meta:
        mes = _primeiro(t, t["renda_mensal"] >= meta)
        if mes:
            marcos.append(Marco(mes, "Meta de renda",
                                f"Os proventos alcançam a sua meta de R$ {meta:,.0f}/mês.".replace(",", ".")))

    return sorted(marcos, key=lambda m: m.mes)


def cenarios(p: Premissas, meta: float | None = None, delta_valorizacao: float = 0.03,
             delta_dy: float = 0.01) -> dict[str, Projecao]:
    """Pessimista, base e otimista: o mesmo plano com premissas mais duras ou mais leves."""
    def variar(dv: float, dd: float) -> Premissas:
        return Premissas(
            patrimonio_inicial=p.patrimonio_inicial, aporte_mensal=p.aporte_mensal,
            valorizacao_anual=p.valorizacao_anual + dv,
            dividend_yield_anual=max(0.0, p.dividend_yield_anual + dd),
            anos=p.anos, reinvestir=p.reinvestir, reajuste_aporte_anual=p.reajuste_aporte_anual,
        )

    return {
        "Pessimista": projetar(variar(-delta_valorizacao, -delta_dy), meta),
        "Base": projetar(p, meta),
        "Otimista": projetar(variar(delta_valorizacao, delta_dy), meta),
    }


def meses_para_texto(meses: int) -> str:
    anos, resto = divmod(meses, 12)
    partes = []
    if anos:
        partes.append(f"{anos} ano" + ("s" if anos > 1 else ""))
    if resto:
        partes.append(f"{resto} " + ("meses" if resto > 1 else "mês"))
    return " e ".join(partes) or "agora"


def brl(valor: float | None, casas: int = 2) -> str:
    """Formata em reais no padrão brasileiro: R$ 1.234,56."""
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return "—"
    texto = f"{abs(valor):,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("-R$ " if valor < 0 else "R$ ") + texto


def brl_curto(valor: float | None) -> str:
    """Valores grandes encurtados para caber numa janela: R$ 2,56 mi."""
    if valor is None:
        return "—"
    if abs(valor) >= 1_000_000:
        return "R$ " + f"{valor / 1_000_000:.2f}".replace(".", ",") + " mi"
    return brl(valor, 0)


MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def mes_ano(data) -> str:
    """'2026-03-01' → 'mar/26'."""
    return f"{MESES[data.month - 1]}/{data.year % 100:02d}"


def pct(valor: float | None, casas: int = 1, sinal: bool = False) -> str:
    """Formata uma fração como porcentagem brasileira: 0,0815 → 8,2%."""
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return "—"
    formato = f"{{:{'+' if sinal else ''}.{casas}f}}"
    return formato.format(valor * 100).replace(".", ",") + "%"


# ---------------------------------------------------------------------------
# Próximo aporte: preço justo, preço de entrada e divisão do dinheiro
# ---------------------------------------------------------------------------

ZONA_COMPRA = "Zona de compra"
ABAIXO_JUSTO = "Abaixo do preço justo"
ACIMA_JUSTO = "Acima do preço justo"
SEM_DADOS = "Sem dados para calcular"


def avaliar_preco(preco: float | None, teto_bazin: float | None, graham: float | None,
                  margem: float = 0.10) -> dict:
    """Preço justo (alvo), preço de entrada e situação de um ativo.

    O preço justo é a média dos métodos disponíveis (Bazin e Graham). O preço de
    entrada é o preço justo menos a margem de segurança escolhida pelo usuário.
    """
    metodos = {nome: v for nome, v in (("Bazin", teto_bazin), ("Graham", graham)) if v and v > 0}
    if not metodos or not preco:
        return {"alvo": None, "entrada": None, "potencial": None, "situacao": SEM_DADOS,
                "metodos": ", ".join(metodos) or "—"}
    alvo = sum(metodos.values()) / len(metodos)
    entrada = alvo * (1 - margem)
    if preco <= entrada:
        situacao = ZONA_COMPRA
    elif preco <= alvo:
        situacao = ABAIXO_JUSTO
    else:
        situacao = ACIMA_JUSTO
    return {"alvo": alvo, "entrada": entrada, "potencial": alvo / preco - 1,
            "situacao": situacao, "metodos": " e ".join(metodos)}


def dividir_aporte(candidatos: pd.DataFrame, dinheiro: float, metas_classe: dict[str, float]) -> tuple[pd.DataFrame, float]:
    """Divide o dinheiro do aporte em cotas inteiras.

    ``candidatos`` precisa das colunas: ativo, classe, preco, valor (quanto já tem),
    potencial e situacao. Regras, em ordem:
      1. Cada classe recebe dinheiro na proporção do que falta para a sua meta (%).
      2. Dentro da classe, só entram ativos abaixo do preço justo; quem está na zona
         de compra pesa o dobro, e o peso cresce com o potencial até o alvo.
      3. As cotas são inteiras; a sobra compra mais cotas de quem tem maior peso e,
         se ainda sobrar, fica em caixa.
    Devolve a tabela de compras e o dinheiro que sobrou.
    """
    colunas = ["ativo", "classe", "preco", "cotas", "valor_compra", "peso_decisao"]
    if candidatos.empty or dinheiro <= 0:
        return pd.DataFrame(columns=colunas), max(dinheiro, 0.0)

    c = candidatos.copy()
    c["elegivel"] = c["situacao"].isin([ZONA_COMPRA, ABAIXO_JUSTO]) & c["preco"].gt(0)
    c["peso_decisao"] = 0.0
    c.loc[c["elegivel"], "peso_decisao"] = c.loc[c["elegivel"], "potencial"].clip(lower=0.01) * \
        c.loc[c["elegivel"], "situacao"].map({ZONA_COMPRA: 2.0, ABAIXO_JUSTO: 1.0})

    total_meta = sum(v for v in metas_classe.values() if v > 0) or 1.0
    futuro = float(c.drop_duplicates("ativo")["valor"].sum()) + dinheiro
    classes_com_opcao = set(c.loc[c["elegivel"], "classe"])
    faltas = {}
    for classe, meta in metas_classe.items():
        if meta <= 0 or classe not in classes_com_opcao:
            continue
        atual = float(c.loc[c["classe"] == classe, "valor"].sum())
        faltas[classe] = max(meta / total_meta * futuro - atual, 0.0)
    if not faltas:
        return pd.DataFrame(columns=colunas), dinheiro
    soma = sum(faltas.values())
    if soma <= 0:  # todas as classes já passaram da meta: divide pela própria meta
        faltas = {k: metas_classe[k] for k in faltas}
        soma = sum(faltas.values())

    c["orcamento"] = 0.0
    for classe, falta in faltas.items():
        verba = dinheiro * falta / soma
        grupo = c["elegivel"] & (c["classe"] == classe)
        pesos = c.loc[grupo, "peso_decisao"]
        c.loc[grupo, "orcamento"] = verba * pesos / pesos.sum()

    c["cotas"] = 0
    c.loc[c["elegivel"], "cotas"] = (c.loc[c["elegivel"], "orcamento"] // c.loc[c["elegivel"], "preco"]).astype(int)
    sobra = dinheiro - float((c["cotas"] * c["preco"]).sum())

    # A sobra compra mais cotas, começando por quem tem maior peso.
    ordem = c[c["elegivel"]].sort_values("peso_decisao", ascending=False).index
    comprou = True
    while comprou:
        comprou = False
        for i in ordem:
            if c.at[i, "preco"] <= sobra:
                c.at[i, "cotas"] += 1
                sobra -= c.at[i, "preco"]
                comprou = True
                break

    c["valor_compra"] = c["cotas"] * c["preco"]
    compras = c[c["cotas"] > 0].sort_values("valor_compra", ascending=False)
    return compras[colunas].reset_index(drop=True), round(sobra, 2)
