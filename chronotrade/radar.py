"""Radar de preços: o diagnóstico de cada ativo usado no Próximo Aporte e pelo agente Sentinela.

Junta, para cada ativo da carteira e da lista de observação:
- fundamentos: preço teto Bazin, preço justo Graham, preço de entrada e situação;
- técnica: tendência, IFR e momento de compra;
- proventos: dividend yield e o próximo pagamento esperado.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

import pandas as pd

from chronotrade import agenda, calculos, tecnica
from chronotrade.carteira import Carteira, montar_tabela
from chronotrade.mercado import DadosAtivo, parece_fii, ticker_curto


def montar(carteira: Carteira, obter: Callable[[str], DadosAtivo], dados: dict[str, DadosAtivo] | None = None,
           hoje: date | None = None) -> pd.DataFrame:
    """Uma linha por ativo, já ordenada: zona de compra primeiro, depois o maior potencial."""
    hoje = hoje or date.today()
    dados = dict(dados or {})
    for p in carteira.posicoes:
        dados.setdefault(p.ticker, obter(p.ticker))
    tabela = montar_tabela(carteira, dados, pd.Timestamp(hoje))
    ja_tem = set(tabela["ticker"]) if not tabela.empty else set()
    tickers = list(tabela["ticker"]) if not tabela.empty else []
    tickers += [t for t in carteira.observar if t not in ja_tem]

    linhas = []
    for ticker in tickers:
        d = dados.get(ticker) or obter(ticker)
        media5 = calculos.media_anual_proventos(d.dividendos, 5, pd.Timestamp(hoje))
        teto = calculos.preco_teto_bazin(media5, carteira.taxa_bazin)
        graham = calculos.preco_justo_graham(d.lpa, d.vpa)
        avaliacao = calculos.avaliar_preco(d.preco, teto, graham, carteira.margem_seguranca)
        diag = tecnica.diagnosticar(d.historico)
        if ticker in ja_tem:
            linha = tabela[tabela["ticker"] == ticker].iloc[0]
            classe, valor, qtd = linha["classe"], float(linha["valor"]), float(linha["quantidade"])
        else:
            classe, valor, qtd = ("FII" if parece_fii(ticker) else "Ação"), 0.0, 0.0
        prov12 = calculos.proventos_12m(d.dividendos, pd.Timestamp(hoje))
        proximos = agenda.prever(ticker, d.dividendos, max(qtd, 1.0), hoje, meses=3, confirmado=d.proximo_provento)
        linhas.append({
            "ticker": ticker, "ativo": ticker_curto(ticker), "classe": classe, "preco": d.preco or 0.0,
            "valor": valor, "quantidade": qtd, "na_carteira": ticker in ja_tem,
            "dy": calculos.dividend_yield(prov12, d.preco), "prov12": prov12,
            **avaliacao,
            "momento": diag.momento, "fator_tecnico": diag.fator, "tendencia": diag.tendencia,
            "ifr": diag.ifr14, "motivos_tecnicos": "; ".join(diag.motivos),
            "proximo_provento": proximos[0].data if proximos else None,
            "proximo_valor": proximos[0].valor_por_cota if proximos else None,
            "fonte": d.fonte,
        })
    radar = pd.DataFrame(linhas)
    if radar.empty:
        return radar
    ordem = {calculos.ZONA_COMPRA: 0, calculos.ABAIXO_JUSTO: 1, calculos.ACIMA_JUSTO: 2, calculos.SEM_DADOS: 3}
    radar["_ordem"] = radar["situacao"].map(ordem)
    radar["_pontos"] = radar["potencial"].fillna(-1) * radar["fator_tecnico"]
    return radar.sort_values(["_ordem", "_pontos"], ascending=[True, False]).drop(columns=["_ordem", "_pontos"]) \
        .reset_index(drop=True)
