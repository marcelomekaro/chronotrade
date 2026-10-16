"""Imposto de renda (day trade e swing), crescimento do patrimônio, carteiras virtuais, admin e crédito."""

from datetime import date, datetime

import pandas as pd
import pytest

from chronotrade import carteiras_virtuais as cv, contas, ir, jarvis, marca, patrimonio as pt

D = date


def test_swing_acima_de_20_mil_paga_15_por_cento():
    ops = [ir.Operacao(D(2026, 3, 2), "BBAS3", "compra", 1000, 25.0), ir.Operacao(D(2026, 3, 10), "BBAS3", "venda", 1000, 27.0)]
    m = ir.apurar(ops).meses[0]
    assert m.vendas_acoes == 27_000 and not m.isento
    assert m.lucro["comum"] == pytest.approx(2000) and m.imposto["comum"] == pytest.approx(300)
    assert m.irrf["comum"] == pytest.approx(1.35) and m.darf == pytest.approx(298.65)
    assert m.vencimento == D(2026, 4, 30)


def test_swing_ate_20_mil_e_isento_mas_etf_nao():
    ops = [ir.Operacao(D(2026, 3, 2), "TAEE11", "compra", 500, 30.0), ir.Operacao(D(2026, 3, 20), "TAEE11", "venda", 500, 36.0),
           ir.Operacao(D(2026, 3, 2), "BOVA11", "compra", 100, 120.0, "ETF"),
           ir.Operacao(D(2026, 3, 20), "BOVA11", "venda", 100, 130.0, "ETF")]
    m = ir.apurar(ops).meses[0]
    assert m.isento and m.lucro_isento == pytest.approx(3000)
    assert m.lucro["comum"] == pytest.approx(1000) and m.imposto["comum"] == pytest.approx(150)


def test_day_trade_20_por_cento_irrf_1_e_compensacao_separada():
    ops = [ir.Operacao(D(2026, 1, 5), "PETR4", "compra", 1000, 36.0), ir.Operacao(D(2026, 1, 5), "PETR4", "venda", 1000, 35.0),
           ir.Operacao(D(2026, 2, 3), "PETR4", "compra", 1000, 36.0), ir.Operacao(D(2026, 2, 3), "PETR4", "venda", 1000, 38.0),
           ir.Operacao(D(2026, 2, 4), "VALE3", "compra", 400, 60.0), ir.Operacao(D(2026, 2, 20), "VALE3", "venda", 400, 55.0)]
    a = ir.apurar(ops)
    jan, fev = a.meses
    assert jan.lucro["day"] == pytest.approx(-1000) and jan.darf == 0 and jan.prejuizo_acumulado["day"] == 1000
    assert fev.lucro["day"] == pytest.approx(2000) and fev.prejuizo_usado["day"] == pytest.approx(1000)
    assert fev.imposto["day"] == pytest.approx(200) and fev.irrf["day"] == pytest.approx(20)
    # prejuízo do swing não abate day trade: fica guardado
    assert fev.prejuizo_acumulado["comum"] == pytest.approx(2000) and fev.darf == pytest.approx(180)


def test_fii_20_por_cento_sem_isencao_e_darf_minimo_acumula():
    ops = [ir.Operacao(D(2026, 5, 4), "MXRF11", "compra", 100, 10.0, "FII"),
           ir.Operacao(D(2026, 5, 20), "MXRF11", "venda", 100, 10.3, "FII"),
           ir.Operacao(D(2026, 6, 1), "MXRF11", "compra", 1000, 10.0, "FII"),
           ir.Operacao(D(2026, 6, 22), "MXRF11", "venda", 1000, 10.5, "FII")]
    mai, jun = ir.apurar(ops).meses
    assert mai.imposto["fii"] == pytest.approx(6) and mai.darf == 0          # abaixo de R$ 10: acumula
    assert jun.acumulado_anterior == pytest.approx(6) and jun.darf == pytest.approx(6 + 100)


def test_preco_medio_posicao_inicial_e_aviso_sem_posicao():
    ops = [ir.Operacao(D(2026, 7, 1), "ITUB4", "compra", 100, 30.0, taxas=10),
           ir.Operacao(D(2026, 7, 15), "ITUB4", "compra", 100, 34.0),
           ir.Operacao(D(2026, 7, 30), "WEGE3", "venda", 10, 50.0)]
    a = ir.apurar(ops, posicoes_iniciais={"ITUB4": (100, 28.0)})
    q, pm = a.posicoes["ITUB4"]
    assert q == 300 and pm == pytest.approx((2800 + 3010 + 3400) / 300)
    assert any("WEGE3" in x for x in a.avisos)


def test_ultimo_dia_util_e_planilha_b3():
    assert ir.ultimo_dia_util(2026, 5) == D(2026, 5, 29)      # 31/05/2026 é domingo
    df = pd.DataFrame({"Data do Negócio": ["02/03/2026", "10/03/2026"], "Tipo de Movimentação": ["Compra", "Venda"],
                       "Código de Negociação": ["BBAS3F", "BBAS3"], "Quantidade": [10, 10], "Preço": ["25,00", "27,50"]})
    ops = ir.ler_planilha(df)
    assert [(o.ticker, o.lado, o.preco) for o in ops] == [("BBAS3", "compra", 25.0), ("BBAS3", "venda", 27.5)]
    assert ops[0].data == D(2026, 3, 2)
    with pytest.raises(ValueError):
        ir.ler_planilha(pd.DataFrame({"x": [1]}))


def test_lembretes_do_darf(tmp_path):
    a = ir.apurar([ir.Operacao(D(2026, 3, 2), "BBAS3", "compra", 1000, 25.0),
                   ir.Operacao(D(2026, 3, 10), "BBAS3", "venda", 1000, 27.0)])
    lem = ir.Lembretes(tmp_path / "x.db")
    assert lem.guardar("a@x", a) == 1
    assert lem.a_avisar("a@x", D(2026, 4, 10)) == []
    pend = lem.a_avisar("a@x", D(2026, 4, 27))
    assert pend and pend[0][0] == "2026-03"
    lem.marcar_avisado("a@x", "2026-03")
    assert lem.a_avisar("a@x", D(2026, 4, 27)) == []


def test_crescimento_separa_aportes_de_rendimento(tmp_path):
    p = pt.Patrimonio(tmp_path / "x.db")
    p.registrar("a@x", 10_000, 10_000, 0, 0, D(2026, 1, 1))
    p.registrar("a@x", 11_500, 11_000, 0, 0, D(2026, 2, 1))     # aportou 1.000, rendeu 500
    p.registrar("a@x", 12_000, 11_000, 0, 0, D(2026, 2, 15))    # rendeu 500
    p.registrar("a@x", 12_100, 11_000, 0, 0, D(2026, 2, 15))    # mesma data: atualiza
    c = pt.crescimento(p.serie("a@x"))
    assert c.aportes == pytest.approx(1000) and c.trabalho == pytest.approx(1100)
    assert c.rentabilidade == pytest.approx(1100 / 10_500) and len(c.meses) == 2
    assert pt.crescimento(p.serie("b@x")) is None
    hist = {"A": pd.Series([10.0, 11.0], index=pd.to_datetime(["2026-01-01", "2026-01-02"]))}
    assert list(pt.reconstruir([("A", 10)], hist)) == [100.0, 110.0]


def test_carteiras_virtuais(tmp_path):
    db = cv.CarteirasVirtuais(tmp_path / "x.db")
    c = db.criar("a@x", "Treino", 10_000, taxa_corretagem=2.0)
    with pytest.raises(cv.ErroCarteira):
        db.criar("a@x", "x", 10)
    db.operar(c.id, "a@x", "taee11", "compra", 100, 35.0, quando=datetime(2026, 3, 1, 10))
    with pytest.raises(cv.ErroCarteira):
        db.operar(c.id, "a@x", "TAEE11", "compra", 1000, 35.0)               # caixa insuficiente
    with pytest.raises(cv.ErroCarteira):
        db.operar(c.id, "a@x", "TAEE11", "venda", 200, 36.0)                 # não tem tudo isso
    with pytest.raises(cv.ErroCarteira):
        db.operar(c.id, "b@x", "TAEE11", "compra", 1, 35.0)                  # carteira de outra pessoa
    db.operar(c.id, "a@x", "TAEE11", "venda", 40, 40.0, origem="simulado", quando=datetime(2026, 3, 2, 10))
    caixa, pos, realizado = db.estado(c)
    taxa_compra = 2 + 3500 * cv.EMOLUMENTOS
    pm = (3500 + taxa_compra) / 100
    assert pos["TAEE11"].quantidade == 60 and pos["TAEE11"].preco_medio == pytest.approx(pm)
    assert realizado == pytest.approx(40 * (40 - pm) - (2 + 1600 * cv.EMOLUMENTOS), abs=0.02)
    total, linhas = cv.avaliar(caixa, pos, {"TAEE11": 38.0})
    assert total == pytest.approx(caixa + 60 * 38) and linhas[0]["peso"] == pytest.approx(60 * 38 / total)
    db.registrar_valor(c.id, total, D(2026, 3, 2))
    assert db.historico(c.id)[0][1] == pytest.approx(total, abs=0.01)
    db.recomecar(c.id, "a@x", 50_000)
    assert db.estado(db.buscar(c.id, "a@x"))[0] == 50_000
    assert db.apagar(c.id, "a@x") and db.listar("a@x") == []


def test_senha_do_admin_igual_ao_email(tmp_path, monkeypatch):
    monkeypatch.setenv("CHRONOTRADE_ADMIN_EMAIL", "marcelomekaro@gmail.com")
    b = contas.Contas(tmp_path / "c.db")
    b.garantir_admin(None)
    u = b.entrar("marcelomekaro@gmail.com", "marcelomekaro@gmail.com")
    assert u.admin and not u.senha_temporaria
    b.trocar_senha(u.email, "marcelomekaro@gmail.com", "OutraSenha123")
    b.senha_do_admin_igual_ao_email()
    assert b.entrar("marcelomekaro@gmail.com", "marcelomekaro@gmail.com").admin


def test_credito_do_desenvolvedor():
    html = marca.credito_html()
    assert "Marcelo Mekaro" in html and "marcelomekaro@gmail.com" in html and "wa.me/5519999650436" in html


@pytest.mark.parametrize("frase,acao,extra", [
    ("tocar música de euforia", "musica", "euforia"),
    ("parar a música", "musica", "parar"),
    ("criar carteira virtual de 50 mil", "carteira_virtual", "50000.0"),
    ("quanto meu patrimônio cresceu?", "crescimento", None),
    ("quanto de imposto eu pago?", "imposto", None),
])
def test_jarvis_novos_comandos(frase, acao, extra):
    cmd = jarvis.entender(frase)
    assert (cmd.acao, cmd.extra) == (acao, extra)
    assert jarvis.entender("abrir carteira virtual").pagina == "virtuais"
    assert jarvis.entender("abrir minha carteira").pagina == "inventario"
