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


def test_avaliar_preco():
    a = calculos.avaliar_preco(30.0, 40.0, 50.0, margem=0.10)  # justo 45, entrada 40,5
    assert a["alvo"] == pytest.approx(45.0) and a["entrada"] == pytest.approx(40.5)
    assert a["situacao"] == calculos.ZONA_COMPRA
    assert calculos.avaliar_preco(44.0, 40.0, 50.0)["situacao"] == calculos.ABAIXO_JUSTO
    assert calculos.avaliar_preco(60.0, 40.0, None)["situacao"] == calculos.ACIMA_JUSTO
    assert calculos.avaliar_preco(10.0, None, None)["situacao"] == calculos.SEM_DADOS


def _candidatos():
    return pd.DataFrame([
        {"ativo": "AAA3", "classe": "Ação", "preco": 10.0, "valor": 1000.0, "potencial": 0.30,
         "situacao": calculos.ZONA_COMPRA},
        {"ativo": "BBB4", "classe": "Ação", "preco": 20.0, "valor": 3000.0, "potencial": -0.10,
         "situacao": calculos.ACIMA_JUSTO},
        {"ativo": "CCCC11", "classe": "FII", "preco": 100.0, "valor": 0.0, "potencial": 0.10,
         "situacao": calculos.ABAIXO_JUSTO},
    ])


def test_dividir_aporte_respeita_metas_e_precos():
    compras, sobra = calculos.dividir_aporte(_candidatos(), 1000.0, {"Ação": 50, "FII": 50})
    assert "BBB4" not in set(compras["ativo"])          # acima do preço justo não entra
    assert (compras["valor_compra"].sum() + sobra) == pytest.approx(1000.0)
    assert sobra < 10.0                                   # a sobra não compra nem a cota mais barata
    fii = compras.loc[compras["ativo"] == "CCCC11", "valor_compra"].sum()
    assert fii >= 500.0                                   # a classe mais longe da meta recebe mais


def test_dividir_aporte_sem_opcoes_guarda_em_caixa():
    c = _candidatos()
    c["situacao"] = calculos.ACIMA_JUSTO
    compras, sobra = calculos.dividir_aporte(c, 800.0, {"Ação": 100})
    assert compras.empty and sobra == 800.0


# --- Contas, PIX e relatório -------------------------------------------------

from datetime import date, datetime, timedelta  # noqa: E402

from chronotrade import contas, pix, relatorio  # noqa: E402


@pytest.fixture
def banco(tmp_path, monkeypatch):
    monkeypatch.setenv("CHRONOTRADE_ADMIN_EMAIL", "chefe@exemplo.com")
    return contas.Contas(tmp_path / "contas.db")


def test_cadastro_nasce_pendente_e_senha_nao_fica_em_texto(banco):
    u = banco.cadastrar("Ana", "Ana@Exemplo.com", "senha123")
    assert u.email == "ana@exemplo.com" and u.status == "pendente" and not u.pode_usar()
    assert b"senha123" not in banco.caminho.read_bytes()
    with pytest.raises(contas.ErroConta):
        banco.cadastrar("Ana", "ana@exemplo.com", "outra123")


def test_ninguem_se_cadastra_como_admin(banco):
    with pytest.raises(contas.ErroConta, match="reservado"):
        banco.cadastrar("Intruso", "chefe@exemplo.com", "senha123")
    banco.garantir_admin("inicial123")
    admin = banco.entrar("chefe@exemplo.com", "inicial123")
    assert admin.admin and admin.plano_completo() and admin.senha_temporaria


def test_senha_fraca_e_email_invalido(banco):
    with pytest.raises(contas.ErroConta):
        banco.cadastrar("Ana", "ana@exemplo.com", "12345678")
    with pytest.raises(contas.ErroConta):
        banco.cadastrar("Ana", "sem-arroba", "senha123")


def test_liberar_renovar_e_vencer(banco):
    banco.cadastrar("Ana", "ana@exemplo.com", "senha123")
    hoje = date(2026, 10, 14)
    u = banco.liberar("ana@exemplo.com", "completo", 30, valor=19.9, hoje=hoje)
    assert u.validade == date(2026, 11, 13) and u.plano_completo(hoje)
    u = banco.liberar("ana@exemplo.com", "completo", 30, valor=19.9, hoje=hoje)  # renova somando
    assert u.validade == date(2026, 12, 13)
    assert u.vencido(date(2026, 12, 14)) and not u.pode_usar(date(2026, 12, 14))
    assert len(banco.pagamentos("ana@exemplo.com")) == 2


def test_bloqueio_apos_tentativas_erradas(banco):
    banco.cadastrar("Ana", "ana@exemplo.com", "senha123")
    agora = datetime(2026, 10, 14, 10, 0)
    for _ in range(contas.TENTATIVAS_MAX):
        with pytest.raises(contas.ErroConta):
            banco.entrar("ana@exemplo.com", "errada000", agora=agora)
    with pytest.raises(contas.ErroConta, match="Muitas tentativas"):
        banco.entrar("ana@exemplo.com", "senha123", agora=agora)
    assert banco.entrar("ana@exemplo.com", "senha123", agora=agora + timedelta(minutes=16))


def test_senha_temporaria_e_troca(banco):
    banco.cadastrar("Ana", "ana@exemplo.com", "senha123")
    temporaria = banco.redefinir_senha("ana@exemplo.com")
    assert banco.entrar("ana@exemplo.com", temporaria).senha_temporaria
    banco.trocar_senha("ana@exemplo.com", temporaria, "novaSenha9")
    assert not banco.entrar("ana@exemplo.com", "novaSenha9").senha_temporaria


def test_sessao_lembrada_e_bloqueio_encerra(banco):
    banco.cadastrar("Ana", "ana@exemplo.com", "senha123")
    token = banco.criar_sessao("ana@exemplo.com")
    assert banco.sessao(token).email == "ana@exemplo.com"
    banco.mudar_status("ana@exemplo.com", "bloqueado")
    assert banco.sessao(token) is None


def test_config_e_indicadores(banco):
    banco.salvar_config({"preco_mensal": "24.90", "inexistente": "x"})
    assert banco.config()["preco_mensal"] == "24.90" and "inexistente" not in banco.config()
    banco.cadastrar("Ana", "ana@exemplo.com", "senha123")
    banco.cadastrar("Beto", "beto@exemplo.com", "senha123")
    banco.liberar("ana@exemplo.com", "completo", 5, valor=24.9)
    ind = banco.indicadores()
    assert ind["ativos"] == 1 and ind["pendentes"] == 1 and len(ind["vencendo"]) == 1
    assert ind["receita_mes"] == pytest.approx(24.9)


def test_pix_crc_e_campos():
    assert pix.crc16("123456789") == "29B1"  # vetor de teste do CRC16-CCITT
    codigo = pix.copia_e_cola("ana@exemplo.com", "Márcelo Mekaro", "São Paulo", 19.9, "CT123")
    assert codigo.startswith("000201") and "br.gov.bcb.pix" in codigo
    assert "540519.90" in codigo and "5914MARCELO MEKARO" in codigo and "6009SAO PAULO" in codigo
    assert codigo[-8:-4] == "6304" and pix.crc16(codigo[:-4]) == codigo[-4:]
    assert pix.qr_png(codigo)[:4] == b"\x89PNG"
    assert pix.link_whatsapp("(11) 99999-0000", "oi").startswith("https://wa.me/5511999990000?text=oi")


def test_relatorio_oculta_valores():
    c = Carteira(posicoes=[Posicao("TAEE11.SA", 100, 30.0), Posicao("MXRF11.SA", 200, 10.0, "FII")])
    dados = {p.ticker: carregar_ativo(p.ticker, demo=True) for p in c.posicoes}
    tabela = montar_tabela(c, dados)
    r = resumir(tabela)
    oculto = relatorio.gerar(c, tabela, r, ocultar_valores=True)
    aberto = relatorio.gerar(c, tabela, r, ocultar_valores=False)
    assert "R$" not in oculto
    assert calculos.brl(r.patrimonio, 0) in aberto
    assert "window.print()" in oculto
    assert "R$" not in relatorio.resumo_texto(c, tabela, r, ocultar_valores=True)
