"""Testes dos cálculos e da carteira do Chrono Trade (sem internet)."""

import math

import pandas as pd
import pytest

from chronotrade import calculos
from chronotrade.carteira import Carteira, Posicao, ler_csv, montar_tabela, resumir
from chronotrade.mercado import carregar_ativo, normalizar_ticker

HOJE = pd.Timestamp("2026-10-14")


def _divs():
    datas = pd.to_datetime(["2024-03-10", "2024-09-10", "2025-03-10", "2025-09-10",
                            "2025-12-10", "2026-03-10", "2026-09-10"]).tz_localize("America/Sao_Paulo")
    return pd.Series([1.0, 1.0, 1.5, 1.5, 0.5, 2.0, 2.0], index=datas)


def test_proventos_12m_conta_so_o_ultimo_ano():
    assert calculos.proventos_12m(_divs(), HOJE) == pytest.approx(0.5 + 2.0 + 2.0)


def test_media_anual_usa_anos_completos():
    # 2024 = 2.0, 2025 = 3.5 → média 2.75
    assert calculos.media_anual_proventos(_divs(), 5, HOJE) == pytest.approx(2.75)


def test_proventos_por_mes_multiplica_pela_quantidade():
    mensal = calculos.proventos_por_mes(_divs(), 10, meses=12, hoje=HOJE)
    assert len(mensal) == 12
    assert mensal[pd.Period("2026-09", "M")] == pytest.approx(20.0)


def test_preco_teto_e_graham():
    assert calculos.preco_teto_bazin(3.0, 0.06) == pytest.approx(50.0)
    assert calculos.preco_justo_graham(2.0, 10.0) == pytest.approx(math.sqrt(450))
    assert calculos.preco_justo_graham(-1.0, 10.0) is None


def test_numero_magico():
    # R$ 1,20/ano por ação → R$ 0,10/mês; ação a R$ 10 → 100 ações
    assert calculos.numero_magico(10.0, 1.2) == 100


def test_projecao_sem_crescimento_soma_aportes():
    p = calculos.Premissas(10_000, 1_000, 0.0, 0.0, anos=1)
    t = calculos.projetar(p).tabela
    assert t["patrimonio"].iloc[-1] == pytest.approx(22_000)
    assert t["investido"].iloc[-1] == pytest.approx(22_000)


def test_projecao_reinvestir_rende_mais():
    base = {"patrimonio_inicial": 50_000, "aporte_mensal": 500, "valorizacao_anual": 0.03,
            "dividend_yield_anual": 0.08, "anos": 10}
    com = calculos.projetar(calculos.Premissas(**base, reinvestir=True)).tabela
    sem = calculos.projetar(calculos.Premissas(**base, reinvestir=False)).tabela
    assert com["patrimonio"].iloc[-1] > sem["patrimonio"].iloc[-1]
    assert com["renda_mensal"].iloc[-1] > sem["renda_mensal"].iloc[-1]


def test_marcos_incluem_meta_e_bola_de_neve():
    p = calculos.Premissas(20_000, 1_000, 0.04, 0.08, anos=30)
    marcos = calculos.projetar(p, meta_renda_mensal=3_000).marcos
    titulos = [m.titulo for m in marcos]
    assert "Meta de renda" in titulos and "Bola de neve" in titulos
    assert [m.mes for m in marcos] == sorted(m.mes for m in marcos)


def test_formatacao_brasileira():
    assert calculos.brl(1234.5) == "R$ 1.234,50"
    assert calculos.pct(0.0815) == "8,2%"
    assert calculos.meses_para_texto(27) == "2 anos e 3 meses"


def test_normalizar_ticker():
    assert normalizar_ticker("petr4") == "PETR4.SA"
    assert normalizar_ticker("HGLG11") == "HGLG11.SA"
    assert normalizar_ticker("AAPL") == "AAPL"
    assert normalizar_ticker("^BVSP") == "^BVSP"


def test_carteira_salva_e_carrega(tmp_path):
    c = Carteira(posicoes=[Posicao("ITUB4.SA", 100, 30.0)], aporte_mensal=700)
    caminho = c.salvar(tmp_path / "c.json")
    lida = Carteira.carregar(caminho)
    assert lida.posicoes[0].ticker == "ITUB4.SA" and lida.aporte_mensal == 700


def test_tabela_editada_normaliza_e_avisa():
    c = Carteira()
    df = pd.DataFrame([
        {"Ticker": "itub4", "Classe": None, "Quantidade": 10, "Preço médio": "30,50"},
        {"Ticker": "HGLG11", "Classe": None, "Quantidade": 5, "Preço médio": 150},
        {"Ticker": "ITUB4", "Classe": "Ação", "Quantidade": 3, "Preço médio": 1},
        {"Ticker": "VALE3", "Classe": "Ação", "Quantidade": 0, "Preço médio": 1},
    ])
    avisos = c.atualizar_de_tabela(df)
    assert [p.ticker for p in c.posicoes] == ["ITUB4.SA", "HGLG11.SA"]
    assert c.posicoes[0].preco_medio == pytest.approx(30.5)
    assert c.posicoes[1].classe == "FII"
    assert len(avisos) == 2


def test_ler_csv_brasileiro():
    df = ler_csv("Ativo;Qtd;Preço médio\nPETR4;100;32,10\n".encode())
    assert df.iloc[0]["Ticker"] == "PETR4" and df.iloc[0]["Preço médio"] == "32,10"


def test_tabela_e_resumo_em_modo_demo():
    c = Carteira(posicoes=[Posicao("TAEE11.SA", 100, 30.0), Posicao("MXRF11.SA", 200, 10.0, "FII")])
    dados = {p.ticker: carregar_ativo(p.ticker, demo=True) for p in c.posicoes}
    tabela = montar_tabela(c, dados)
    r = resumir(tabela, caixa=100)
    assert r.patrimonio == pytest.approx(tabela["valor"].sum() + 100)
    assert tabela["peso"].sum() == pytest.approx(1.0)
    assert r.renda_12m > 0
