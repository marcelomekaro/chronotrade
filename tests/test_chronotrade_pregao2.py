"""Pregão interativo, perfis com foto, chat, robô, alertas, Telegram, B3 e agenda (sem internet)."""

import io
import json
import sqlite3
from datetime import date, datetime, timedelta

import pandas as pd
import pytest

from chronotrade import (
    agenda,
    alertas,
    avatar,
    b3,
    jarvis,
    pregao as pg,
    pregao_bot,
    salao,
    telegram,
)
from chronotrade.carteira import Carteira, Posicao

AGORA = datetime(2026, 10, 16, 10, 0, 0)


def test_migra_banco_antigo_e_guarda_foto_bio(tmp_path):
    caminho = tmp_path / "c.db"
    con = sqlite3.connect(caminho)
    con.executescript("CREATE TABLE perfis_pregao (email TEXT PRIMARY KEY, apelido TEXT NOT NULL, avatar TEXT);"
                      "INSERT INTO perfis_pregao VALUES ('a@x', 'Ana', NULL);")
    con.close()
    p = pg.Pregao(caminho)
    assert p.perfil_completo("a@x").apelido == "Ana"
    p.salvar_perfil("a@x", "Ana B3", "{}", foto="data:image/png;base64,AAA", bio="  Dividendos   desde 2019 ")
    perfil = p.perfil_completo("a@x")
    assert (perfil.foto, perfil.bio) == ("data:image/png;base64,AAA", "Dividendos desde 2019")
    p.salvar_perfil("a@x", "Ana B3", "{}")  # foto=False mantém
    assert p.perfil_completo("a@x").foto
    p.remover_foto("a@x")
    assert p.perfil_completo("a@x").foto is None


def test_apelido_unico_e_reservado(tmp_path):
    p = pg.Pregao(tmp_path / "c.db")
    p.salvar_perfil("a@x", "Rafa", "{}")
    with pytest.raises(pg.ErroPregao, match="outra pessoa"):
        p.salvar_perfil("b@x", "rafa", "{}")
    with pytest.raises(pg.ErroPregao, match="reservado"):
        p.salvar_perfil("b@x", "Mestre do Pregão", "{}")
    with pytest.raises(pg.ErroPregao):
        p.salvar_perfil("b@x", "<script>", "{}")
    assert p.email_por_apelido("RAFA") == "a@x"
    p.salvar_perfil("b@x", "Bia Dividendos", "{}")
    assert p.mencionados("bom dia @bia dividendos e @Rafa!") == ["b@x", "a@x"]
    assert p.mencionados("sem menção") == []


def test_posicao_no_salao_fica_dentro_da_sala(tmp_path):
    p = pg.Pregao(tmp_path / "c.db")
    p.marcar_presenca("a@x", "geral", "Ana", None)
    x0, y0 = pg.lugar_inicial("a@x")
    assert (p.online("geral")[0].x, p.online("geral")[0].y) == (x0, y0)
    assert p.mover("a@x", "geral", 150, -5) == (97, 34)
    p.marcar_presenca("a@x", "geral", "Ana", None)  # presença não mexe na posição
    assert (p.online("geral")[0].x, p.online("geral")[0].y) == (97, 34)
    assert pg.id_publico("a@x") != "a@x" and len(pg.id_publico("a@x")) == 12


def test_respostas_reacoes_mencoes_e_apagar(tmp_path):
    p = pg.Pregao(tmp_path / "c.db")
    m1 = p.enviar("geral", "a@x", "Ana", None, "Olá @Bia, viu $TAEE11?", AGORA)
    m2 = p.enviar("geral", "b@x", "Bia", None, "Vi sim!", AGORA + timedelta(seconds=5), resposta_a=m1.id)
    assert pg.mencoes(m1.texto) == ["Bia"]
    assert p.listar("geral")[-1].resposta_a == m1.id
    assert p.reagir(m1.id, "b@x", "🔥") is True and p.reagir(m1.id, "c@x", "🔥") is True
    assert p.reacoes([m1.id, m2.id]) == {m1.id: {"🔥": 2}}
    assert p.reagir(m1.id, "b@x", "🔥") is False
    with pytest.raises(pg.ErroPregao):
        p.reagir(m1.id, "b@x", "💩")
    assert p.apagar_propria(m2.id, "a@x") is False and p.apagar_propria(m2.id, "b@x") is True
    assert [m.id for m in p.listar("geral")] == [m1.id]
    assert p.participou("a@x") and not p.participou("z@x")


def test_grafico_compartilhado_vira_quadro_e_mensagem(tmp_path):
    p = pg.Pregao(tmp_path / "c.db")
    m = p.compartilhar_grafico("geral", "a@x", "Ana", None, "taee11.sa", "1a", "voltou para a média", AGORA)
    assert m.tipo == "grafico" and m.dados["ticker"] == "TAEE11" and m.dados["periodo"] == "1a"
    assert "$TAEE11" in m.texto and m.tickers == ["TAEE11"]
    p.compartilhar_grafico("geral", "a@x", "Ana", None, "ITSA4", "xx", "", AGORA + timedelta(seconds=10))
    quadros = p.quadros("geral", agora=AGORA + timedelta(minutes=1))
    assert [(q.ticker, q.periodo) for q in quadros] == [("ITSA4", "6m")]  # o mais recente por pessoa
    with pytest.raises(pg.ErroPregao):
        p.compartilhar_grafico("geral", "a@x", "Ana", None, "não é ticker", agora=AGORA + timedelta(minutes=2))


def test_mensagens_privadas(tmp_path):
    p = pg.Pregao(tmp_path / "c.db")
    p.enviar_privada("a@x", "b@x", "Oi Bia", AGORA)
    p.enviar_privada("b@x", "a@x", "Oi Ana", AGORA + timedelta(seconds=5))
    p.enviar_privada("a@x", "b@x", "Tudo bem?", AGORA + timedelta(seconds=10))
    assert [m.texto for m in p.conversa("a@x", "b@x")] == ["Oi Bia", "Oi Ana", "Tudo bem?"]
    assert p.nao_lidas_privadas("b@x") == 2
    assert p.conversas("b@x")[0]["nao_lidas"] == 2
    p.marcar_lidas("b@x", "a@x")
    assert p.nao_lidas_privadas("b@x") == 0
    with pytest.raises(pg.ErroPregao):
        p.enviar_privada("a@x", "a@x", "eu mesmo", AGORA + timedelta(minutes=1))
    with pytest.raises(pg.ErroPregao, match="Calma"):
        p.enviar_privada("a@x", "b@x", "rápido demais", AGORA + timedelta(seconds=11))
    p.apagar_dados("a@x")
    assert p.conversa("a@x", "b@x") == []


class _D:
    def __init__(self, preco, anterior=None, dividendos=None, prox=None):
        self.preco = preco
        self.variacao_dia = preco / anterior - 1 if anterior else None
        self.dividendos = dividendos if dividendos is not None else pd.Series(dtype=float)
        self.proximo_provento = prox


def test_robo_do_pregao():
    dados = {"TAEE11.SA": _D(36.0, 35.0, pd.Series([1.0, 1.2], index=pd.to_datetime(["2026-03-10", "2026-09-10"])),
                             (date(2026, 10, 20), 1.1)), "^BVSP": _D(130000.0, 129000.0)}
    obter = lambda t: dados.get(t, _D(None))  # noqa: E731
    assert pregao_bot.responder("bom dia", obter) is None
    assert "Comandos" in pregao_bot.responder("/ajuda", obter).texto
    assert pregao_bot.responder("/cotacao TAEE11", obter).texto == "$TAEE11: R$ 36,00, +2,86% no dia."
    assert "130.000 pontos" in pregao_bot.responder("/cotação ibov", obter).texto
    prov = pregao_bot.responder("/proventos TAEE11", obter).texto
    assert "10/09/2026" in prov and "20/10/2026" in prov
    g = pregao_bot.responder("/grafico taee11 1a olha isso", obter)
    assert (g.acao, g.dados) == ("grafico", {"ticker": "TAEE11", "periodo": "1a", "nota": "olha isso"})
    assert "Use assim" in pregao_bot.responder("/cotacao", obter).texto
    assert "2 na sala" in pregao_bot.responder("/quem", obter, ["Ana", "Bia"]).texto
    assert "Não conheço" in pregao_bot.responder("/xyz", obter).texto


def test_serie_do_grafico_e_sparkline():
    h = pd.Series(range(1, 301), index=pd.date_range("2025-01-01", periods=300), dtype=float)
    s = salao.serie_grafico(h, "6m", pontos=60)
    assert s["serie"][-1] == 300.0 and len(s["serie"]) <= 64 and s["datas"][1] == h.index[-1].strftime("%d/%m/%Y")
    assert s["var"] == pytest.approx(300 / 175 - 1) and s["periodo_nome"] == "6 meses"
    assert salao.serie_grafico(pd.Series(dtype=float)) is None
    assert salao.sparkline([1, 2, 3]).startswith("<img")


def test_foto_processada_sem_exif_e_pequena():
    from PIL import Image

    b = io.BytesIO()
    Image.new("RGB", (1200, 800), (10, 120, 200)).save(b, "JPEG")
    uri = avatar.processar_foto(b.getvalue())
    assert uri.startswith("data:image/jpeg;base64,") and len(uri) < 40_000
    assert avatar.processar_foto(b.getvalue(), estilo_pixel=True).startswith("data:image/png")
    with pytest.raises(ValueError):
        avatar.processar_foto(b"nao e imagem")
    assert 'border-radius:50%' in avatar.retrato(None, uri, "a@x", 40, "Ana")
    assert avatar.retrato(None, None, "a@x", 40, "Ana").startswith("<img")


def test_alertas_de_preco(tmp_path):
    banco = alertas.Alertas(tmp_path / "c.db")
    a = banco.criar("a@x", "taee11", "abaixo", 34)
    banco.criar("a@x", "PETR4", "acima", 40)
    assert a.ticker == "TAEE11.SA" and a.descricao == "TAEE11 abaixo de R$ 34,00"
    with pytest.raises(alertas.ErroAlerta):
        banco.criar("a@x", "TAEE11", "lado", 1)
    precos = {"TAEE11.SA": _D(33.5), "PETR4.SA": _D(38.0)}
    disparados = banco.verificar("a@x", lambda t: precos[t])
    assert [(x.ticker, p) for x, p in disparados] == [("TAEE11.SA", 33.5)]
    assert banco.verificar("a@x", lambda t: precos[t]) == []  # não repete
    banco.reativar("a@x", a.id)
    assert len(banco.verificar("a@x", lambda t: precos[t])) == 1
    banco.remover("a@x", a.id)
    assert [x.ticker for x in banco.listar("a@x")] == ["PETR4.SA"]


def test_zona_de_compra_avisa_so_o_que_entrou(tmp_path):
    assert alertas.zonas_novas(tmp_path, ["TAEE11"]) == []          # primeira vez só guarda
    assert alertas.zonas_novas(tmp_path, ["TAEE11", "ITSA4"]) == ["ITSA4"]
    assert alertas.zonas_novas(tmp_path, ["ITSA4"]) == []
    assert alertas.zonas_novas(tmp_path, ["ITSA4", "TAEE11"]) == ["TAEE11"]


def test_telegram_vincula_pelo_codigo_e_envia(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_BOT_USUARIO", "@chrono_bot")
    pedidos = []
    cod = telegram.codigo("a@x")

    def http(pedido):
        pedidos.append((pedido.full_url.rsplit("/", 1)[1], dict(p.split("=", 1) for p in pedido.data.decode().split("&"))))
        if pedido.full_url.endswith("getUpdates"):
            return {"ok": True, "result": [{"update_id": 7, "message": {"text": f"/start {cod}", "chat": {"id": 555}}},
                                           {"update_id": 8, "message": {"text": "/start errado", "chat": {"id": 9}}}]}
        return {"ok": True}

    tg = telegram.Telegram(tmp_path / "c.db", http)
    assert telegram.link("a@x") == f"https://t.me/chrono_bot?start={cod}"
    assert tg.processar_atualizacoes(["a@x", "b@x"]) == 1
    assert tg.chat_de("a@x") == "555" and tg.chat_de("b@x") is None
    assert tg.enviar("a@x", "Olá") == "enviado"
    assert pedidos[-1][0] == "sendMessage" and pedidos[-1][1]["chat_id"] == "555"
    tg.processar_atualizacoes(["a@x"])
    assert [p for p in pedidos if p[0] == "getUpdates"][-1][1]["offset"] == "9"
    assert tg.enviar("b@x", "x") == "sem Telegram vinculado"


def test_importa_posicao_da_b3(tmp_path):
    acoes = pd.DataFrame({"Produto": ["TAEE11 - TAESA", "ITSA4 - ITAUSA", "ITSA4 - ITAUSA", "Total"],
                          "Instituição": ["XP", "XP", "RICO", ""], "Código de Negociação": ["TAEE11", "ITSA4", "ITSA4F", ""],
                          "Quantidade": [100, 50, 7, 157], "Preço de Fechamento": [36.0, 10.5, 10.5, None]})
    fiis = pd.DataFrame({"Produto": ["MXRF11"], "Código de Negociação": ["MXRF11"], "Quantidade": ["400"],
                         "Preço de Fechamento": ["9,85"]})
    arq = io.BytesIO()
    with pd.ExcelWriter(arq) as w:
        acoes.to_excel(w, sheet_name="Acoes", index=False)
        fiis.to_excel(w, sheet_name="Fundo de Investimento", index=False)
    linhas = {ln["ticker"]: ln for ln in b3.ler_posicao(arq.getvalue(), "posicao.xlsx")}
    assert linhas["ITSA4"]["quantidade"] == 57 and linhas["MXRF11"]["fechamento"] == 9.85
    carteira = Carteira([Posicao("TAEE11.SA", 80, 30.0, "Ação")])
    posicoes, sem_pm = b3.para_posicoes(list(linhas.values()), carteira)
    assert {p.ticker: p.preco_medio for p in posicoes}["TAEE11"] == 30.0
    assert sorted(sem_pm) == ["ITSA4", "MXRF11"]
    csv = "Código de Negociação;Quantidade\nBBAS3;150\n".encode()
    assert b3.ler_posicao(csv, "p.csv")[0]["ticker"] == "BBAS3"
    with pytest.raises(b3.ErroB3):
        b3.ler_posicao(b"a;b\n1;2\n", "x.csv")


def test_agenda_vira_calendario():
    ev = [agenda.Evento("TAEE11.SA", date(2026, 10, 20), 1.1, 100, agenda.CONFIRMADO)]
    texto = agenda.ics(ev)
    assert texto.startswith("BEGIN:VCALENDAR") and "DTSTART;VALUE=DATE:20261020" in texto
    assert "SUMMARY:Data com TAEE11 (~R$ 110\\,00)" in texto and texto.count("BEGIN:VEVENT") == 1
    assert "\r\n" in texto and "TRIGGER:-P1D" in texto


def test_jarvis_cria_alerta_por_voz():
    criados = []
    ctx = jarvis.Contexto(Carteira(), lambda t: _D(None), criar_alerta=lambda t, tipo, p: criados.append((t, tipo, p)))
    r = jarvis.executar(jarvis.entender("me avise quando a Taesa ficar abaixo de 34 reais"), ctx)
    assert criados == [("TAEE11", "abaixo", 34.0)] and "abaixo de R$ 34,00" in r.texto
    assert "Em qual preço" in jarvis.executar(jarvis.entender("cria um alerta para PETR4"), ctx).texto


def test_sentinela_dispara_alertas(tmp_path, monkeypatch):
    from chronotrade.agentes import sentinela
    from chronotrade.avisos import CaixaDeAvisos

    monkeypatch.setenv("CHRONOTRADE_HOME", str(tmp_path))
    caixa = CaixaDeAvisos(tmp_path / "contas.db")
    alertas.Alertas(tmp_path / "contas.db").criar(sentinela.EMAIL_LOCAL, "TAEE11", "abaixo", 40)
    resumo = sentinela.ciclo(None, caixa, obter=lambda t: _D(36.0), usar_ia=False)
    assert resumo["alertas"] == 1
    assert caixa.listar(sentinela.EMAIL_LOCAL)[0].titulo == "Alerta: TAEE11 abaixo de R$ 40,00"
    assert json.dumps(resumo)
