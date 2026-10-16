"""Simulador de mercado, Jarvis mãos livres, emojis e frases do Pregão."""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from chronotrade import audio, jarvis, moderacao, pregao as pg, simulador as sim

POS = [{"ativo": "TAEE11", "classe": "Ação", "valor": 10_000, "renda_12m": 900, "beta": 0.6},
       {"ativo": "MXRF11", "classe": "FII", "valor": 5_000, "renda_12m": 600},
       {"ativo": "IVVB11", "classe": "BDR", "valor": 3_000}]


def test_estresse_aplica_choque_beta_e_corte_de_proventos():
    r = sim.estresse(POS, sim.CENARIOS["covid"], caixa=500, aporte_mensal=1000)
    taee = r.por_ativo.set_index("ativo").loc["TAEE11"]
    assert taee["choque"] == pytest.approx(-0.47 * 0.6)
    assert r.antes == 18_500 and r.depois < r.antes
    assert r.renda_depois == pytest.approx(1500 * 0.75)
    assert r.caminho["mes"].iloc[-1] == 1 + 10 + 12      # queda + volta + 12 meses depois
    assert r.ganho_aportando > 0 and 0 < r.desconto_medio < 0.5
    # quem aporta na queda tem mais do que quem não aporta, no fim
    assert r.caminho["com_aporte"].iloc[-1] > r.caminho["sem_aporte"].iloc[-1]


def test_cenario_de_um_dia_e_cenario_livre():
    trilha = sim.trajetoria(-0.09, 0, 2, depois=0)
    assert trilha[0] == 1 and trilha[1] == pytest.approx(0.91) and trilha[-1] == pytest.approx(1)
    livre = sim.cenario_livre(-0.3, -0.1, 0.2)
    r = sim.estresse(POS, livre)
    assert r.por_ativo.set_index("ativo").loc["IVVB11", "choque"] == pytest.approx(0.2)
    tabela = sim.todos_os_cenarios(POS)
    assert set(tabela["chave"]) == set(sim.CENARIOS)
    assert tabela.set_index("chave").loc["crise_2008", "queda"] < tabela.set_index("chave").loc["joesley", "queda"]


def test_beta_estimado_e_limitado():
    datas = pd.bdate_range("2025-01-01", periods=300)
    rng = np.random.default_rng(3)
    ibov = pd.Series(100 * np.cumprod(1 + rng.normal(0, 0.01, 300)), index=datas)
    dobro = pd.Series(100 * np.cumprod(1 + 2.5 * ibov.pct_change().fillna(0)), index=datas)
    assert sim.beta(dobro, ibov) == 1.6                  # limitado
    assert sim.beta(ibov, ibov) == pytest.approx(1.0)
    assert sim.beta(ibov.head(20), ibov) == 1.0          # pouco dado: neutro


def test_intencoes_antes_e_depois():
    r = sim.simular_intencoes([{"ativo": "TAEE11", "classe": "Ação", "quantidade": 100, "preco_medio": 30}],
                              [sim.Intencao("TAEE11", "compra", 100), sim.Intencao("MXRF11", "compra", 50, 10, "FII"),
                               sim.Intencao("BBAS3", "venda", 10)],
                              {"TAEE11": 40.0}, {"TAEE11": 4.0, "MXRF11": 1.2}, caixa=10_000)
    depois = r.depois.set_index("ativo")
    assert depois.loc["TAEE11", "quantidade"] == 200 and depois.loc["TAEE11", "preco_medio"] == pytest.approx(35)
    assert r.custo == pytest.approx(4000 + 500) and r.caixa_depois == pytest.approx(5500)
    assert r.resumo("depois")["renda_12m"] == pytest.approx(800 + 60)
    assert any("BBAS3" in a for a in r.avisos)            # venda de quem não tem: avisada
    falta = sim.simular_intencoes([], [sim.Intencao("TAEE11", "compra", 100)], {"TAEE11": 40.0}, {}, caixa=0)
    assert falta.caixa_depois == -4000 and "faltariam" in falta.avisos[0]


def test_futuros_por_blocos():
    ret = pd.Series(np.random.default_rng(1).normal(0.001, 0.01, 400))
    f = sim.simular_futuros(ret, 10_000, meses=12, aporte_mensal=500, caminhos=500)
    assert list(f.faixas.columns) == ["mes", "p5", "p25", "p50", "p75", "p95"]
    ultima = f.faixas.iloc[-1]
    assert ultima["p5"] < ultima["p50"] < ultima["p95"] and f.aportado == 16_000
    assert 0 <= f.chance_prejuizo <= 1
    assert sim.simular_futuros(ret.head(10), 10_000) is None


def test_jarvis_palavra_de_ativacao_e_ruido():
    assert jarvis.tirar_ativacao("Jarvis, cotação da Taesa") == (True, "cotação da Taesa")
    assert jarvis.tirar_ativacao("ok Jarvis abrir a agenda") == (True, "abrir a agenda")
    assert jarvis.tirar_ativacao("Javis, faz o check-in")[0]                     # parecida de verdade
    assert jarvis.tirar_ativacao("Jardis e se vier uma crise como a de 2008")[0]  # meio parecida + comando
    assert not jarvis.tirar_ativacao("Já vi, isso é ótimo")[0]                    # meio parecida + conversa
    assert not jarvis.tirar_ativacao("Avise quando a Taesa cair")[0]
    assert jarvis.ruido("Obrigado.") and jarvis.ruido("  ") and not jarvis.ruido("cotação da Taesa")
    assert jarvis.corrigir("fazer o chiquinho no peibão") == "fazer o check-in no pregão"


@pytest.mark.parametrize("frase,acao,extra", [
    ("faz o meu check-in", "checkin", None),
    ("e se vier uma crise como a da covid?", "estresse", "covid"),
    ("simular crise de 2008", "estresse", "crise_2008"),
    ("e se o mercado cair 30%", "estresse", "livre:-0.3"),
    ("aplausos no pregão", "emoji", "👏"),
    ("soltar um foguete no salão", "emoji", "🚀"),
    ("fala a minha segunda frase", "frase", "2"),
    ("mudar o tema para verde", "tema", "verde"),
    ("tenho avisos novos?", "avisos", None),
    ("confirmar", "confirmar", None),
    ("cancela", "cancelar", None),
    ("para de ouvir", "parar", None),
    ("repete", "repetir", None),
])
def test_jarvis_comandos_do_app(frase, acao, extra):
    cmd = jarvis.entender(frase)
    assert cmd.acao == acao and cmd.extra == extra


def test_jarvis_intencao_e_acoes_do_contexto():
    cmd = jarvis.entender("simular compra de 100 TAEE11")
    assert (cmd.acao, cmd.ticker, cmd.lado, cmd.quantidade) == ("intencao", "TAEE11", "compra", 100)
    assert jarvis.entender("comprar 100 TAEE11").acao == "ordem"     # sem "simular" continua sendo ordem
    assert jarvis.entender("abrir o simulador").pagina == "simulador"
    ctx = jarvis.Contexto(carteira=None, obter=lambda t: None, acoes={"checkin": lambda c: "feito"})
    assert jarvis.executar(jarvis.entender("check-in"), ctx).texto == "feito"
    assert "dentro do app" in jarvis.executar(jarvis.entender("aplausos no pregão"), ctx).texto
    nav = jarvis.executar(jarvis.entender("abrir a loja"), ctx)
    assert nav.abrir and nav.pagina == "paginas/loja.py"


def test_moderacao_das_frases():
    assert moderacao.conferir("Bom dia, pregão!") is None
    assert moderacao.conferir("Lucro garantido aqui") and moderacao.conferir("veja www.golpe.com")
    assert moderacao.conferir("me chama 19 99999-0000") and moderacao.conferir("seu idiota")


def test_audio_prepara_frase():
    taxa = 44_100
    t = np.arange(int(taxa * 1.0)) / taxa
    voz = 0.5 * np.sin(2 * np.pi * 220 * t).astype(np.float32)
    sinal = np.concatenate([np.zeros(taxa, np.float32), voz, np.zeros(taxa, np.float32)])
    wav, segundos = audio.preparar_frase(audio.para_wav(sinal, taxa))
    amostras, nova = audio.ler_wav(wav)
    assert nova == 16_000 and 1.0 <= segundos <= 1.4 and len(amostras) / nova == pytest.approx(segundos, abs=0.05)
    with pytest.raises(audio.ErroAudio):
        audio.preparar_frase(audio.para_wav(np.zeros(taxa, np.float32), taxa))
    longo, seg = audio.preparar_frase(audio.para_wav(np.tile(voz, 12), taxa))
    assert seg == 8.0
    assert audio.data_uri(b"RIFF").startswith("data:audio/wav;base64,")


def test_emojis_e_frases_no_pregao(tmp_path):
    db = pg.Pregao(tmp_path / "p.db")
    agora = datetime(2026, 10, 16, 12, 0, 0)
    e = db.emote("geral", "a@x", "🚀", agora)
    assert e.tipo == "emoji" and e.conteudo == "🚀"
    with pytest.raises(pg.ErroPregao):
        db.emote("geral", "a@x", "👏", agora + timedelta(seconds=0.5))      # calma
    with pytest.raises(pg.ErroPregao):
        db.emote("geral", "a@x", "💩", agora + timedelta(seconds=5))        # fora da lista
    assert [x.conteudo for x in db.emotes("geral", agora=agora + timedelta(seconds=3))] == ["🚀"]
    assert db.emotes("geral", agora=agora + timedelta(seconds=30)) == []

    f = db.salvar_frase("a@x", "  Bom   dia, pregão! ", b"RIFF123", "gravada", agora)
    assert f.texto == "Bom dia, pregão!" and f.tem_audio
    with pytest.raises(pg.ErroPregao):
        db.salvar_frase("a@x", "Lucro garantido!")
    with pytest.raises(pg.ErroPregao):
        db.tocar_frase("geral", "b@x", f.id)                                  # frase de outra pessoa
    t = db.tocar_frase("geral", "a@x", f.id, agora + timedelta(seconds=10))
    assert t.tipo == "frase" and t.conteudo == str(f.id)
    frase, som = db.frase(f.id)
    assert som == b"RIFF123" and frase.origem == "gravada"
    for i in range(pg.FRASES_MAXIMO - 1):
        db.salvar_frase("a@x", f"Frase {i}")
    with pytest.raises(pg.ErroPregao):
        db.salvar_frase("a@x", "Uma a mais")
    db.denunciar_frase(f.id)
    assert [x.id for x in db.frases_denunciadas()] == [f.id]
    assert db.apagar_frase(f.id, "b@x") is False and db.apagar_frase(f.id, "a@x") is True
    db.apagar_dados("a@x")
    assert db.frases("a@x") == [] and db.emotes("geral", timedelta(days=2), agora) == []


def test_emotes_demo_e_salao():
    from chronotrade import salao

    lista = salao.emotes_demo(600.5)
    assert lista and all(e["tipo"] == "emoji" and e["conteudo"] in pg.EMOJIS and e["idade"] < 8 for e in lista)


def test_temas_modernos_completos():
    from chronotrade import tema

    chaves = set(tema.TEMAS["retro"])
    assert tema.TEMA_PADRAO == "moderno"
    for nome, t in tema.TEMAS.items():
        assert set(t) == chaves, nome
        assert t["estilo"] in ("moderno", "retro")
    modelo = tema._modelo(tema.TEMAS["oceano"])
    assert modelo.layout.font.color == tema.TEMAS["oceano"]["texto"]
