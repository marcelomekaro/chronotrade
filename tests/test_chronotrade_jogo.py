"""Conta de teste, temas, pontos, loja do avatar e webhooks (sem internet)."""

import json
from datetime import date, timedelta

import pytest

from chronotrade import avatar, contas, jogo as jg, tema, webhooks


def test_conta_de_teste_entra_pelo_usuario(tmp_path):
    banco = contas.Contas(tmp_path / "c.db")
    u = banco.criar_teste("Teste", "senhaTeste1", dias=30)
    assert u.email == "teste@teste.chronotrade" and u.teste and u.login == "teste"
    assert u.status == "ativo" and u.plano == "premium" and u.dias_restantes() == 30 and u.pode_usar()
    assert banco.entrar("Teste", "senhaTeste1").email == u.email
    assert banco.entrar("  TESTE ", "senhaTeste1").email == u.email
    with pytest.raises(contas.ErroConta):
        banco.entrar("Teste", "errada123")
    with pytest.raises(contas.ErroConta, match="Já existe"):
        banco.criar_teste("teste", "outraSenha1")
    with pytest.raises(contas.ErroConta, match="8 caracteres"):
        banco.criar_teste("Ana", "curta1")
    real = banco.criar_teste("Bia", "senhaBia123", dias=7, plano="medio", email="bia@x.com")
    assert real.email == "bia@x.com" and real.teste and real.plano == "medio" and real.dias_restantes() == 7
    assert banco.pagamentos("bia@x.com")[0]["forma"] == "Cortesia"
    assert contas.email_de_login("João Silva") == "joaosilva@teste.chronotrade"
    assert contas.email_de_login("a@B.com") == "a@b.com"


def test_temas_tem_todas_as_cores():
    chaves = set(tema.TEMAS["retro"])
    assert {"retro", "verde", "laranja", "classico"} <= set(tema.TEMAS)
    for t in tema.TEMAS.values():
        assert set(t) == chaves
        assert all(t[k].startswith("#") for k in ("ceu", "ouro", "texto", "tinta"))


def test_checkin_sequencia_e_bonus(tmp_path):
    j = jg.Jogo(tmp_path / "c.db")
    d0 = date(2026, 10, 1)
    assert j.checkin("a@x", d0) == (10, 1)
    assert j.checkin("a@x", d0) is None
    assert j.checkin("a@x", d0 + timedelta(days=1)) == (12, 2)
    for i in range(2, 6):
        j.checkin("a@x", d0 + timedelta(days=i))
    pontos, seq = j.checkin("a@x", d0 + timedelta(days=6))
    assert seq == 7 and pontos == 22 + 30 + jg.CONQUISTAS["sequencia_7"][1]
    assert j.sequencia("a@x", d0 + timedelta(days=7)) == 7      # ainda não fez o de hoje
    assert j.sequencia("a@x", d0 + timedelta(days=9)) == 0      # pulou um dia
    assert j.checkin("a@x", d0 + timedelta(days=9)) == (10, 1)
    assert "sequencia_7" in j.conquistas("a@x")


def test_conquista_so_uma_vez(tmp_path):
    j = jg.Jogo(tmp_path / "c.db")
    assert j.conquistar("a@x", "perfil_foto") == 50 and j.conquistar("a@x", "perfil_foto") == 0
    assert j.saldo("a@x") == 50


class _D:
    def __init__(self, preco):
        self.preco = preco


def test_desempenho_semanal_ignora_aporte_e_queda(tmp_path):
    j = jg.Jogo(tmp_path / "c.db")
    hoje = date(2026, 10, 1)
    precos = {"A": 10.0, "B": 20.0}
    assert j.desempenho("a@x", [("A", 100), ("B", 50)], lambda t: _D(precos[t]), tmp_path, hoje) == 0
    assert json.loads((tmp_path / "jogo_semana.json").read_text())["data"] == "2026-10-01"
    precos = {"A": 10.3, "B": 20.6}  # +3% em tudo
    assert j.desempenho("a@x", [("A", 100), ("B", 50)], lambda t: _D(precos[t]), tmp_path, hoje + timedelta(days=3)) == 0
    ganhos = j.desempenho("a@x", [("A", 1000), ("B", 50)], lambda t: _D(precos[t]), tmp_path, hoje + timedelta(days=7))
    assert ganhos == 30  # 3% → 30 pontos; as 900 cotas novas de A não contam
    precos = {"A": 9.0, "B": 18.0}
    assert j.desempenho("a@x", [("A", 1000)], lambda t: _D(precos[t]), tmp_path, hoje + timedelta(days=14)) == 0
    precos = {"A": 20.0}
    assert j.desempenho("a@x", [("A", 1000)], lambda t: _D(precos[t]), tmp_path, hoje + timedelta(days=21)) == jg.MAX_DESEMPENHO


def test_loja_e_pacotes(tmp_path):
    j = jg.Jogo(tmp_path / "c.db")
    with pytest.raises(jg.ErroJogo, match="Faltam"):
        j.comprar("a@x", "terno")
    j.creditar("a@x", 500, "teste")
    assert j.comprar("a@x", "terno") == 200 and j.itens("a@x") == {"terno"}
    with pytest.raises(jg.ErroJogo, match="já tem"):
        j.comprar("a@x", "terno")
    p = j.pedir_pacote("a@x", "p500")
    assert j.pedir_pacote("a@x", "p500").id == p.id      # não duplica pedido aberto
    j.confirmar_pedido(p.id)
    assert j.saldo("a@x") == 700 and j.pedidos("aguardando") == []
    with pytest.raises(jg.ErroJogo):
        j.confirmar_pedido(p.id)
    j.dar_item("a@x", "coroa")
    assert "coroa" in j.itens("a@x")
    j.apagar_dados("a@x")
    assert j.saldo("a@x") == 0 and j.itens("a@x") == set()


def test_itens_aparecem_no_avatar_e_carregam_jsons_antigos():
    antigo = avatar.Avatar.de_json('{"pele": "#F1C27D", "cabelo": "curto", "cor_cabelo": "#2B1B0E", '
                                   '"roupa": "#2B3BA0", "acessorio": "gravata"}')
    assert antigo.traje == "casual" and antigo.chapeu == "nenhum"
    com_itens = avatar.Avatar(traje="smoking", chapeu="cartola", extra="maleta")
    pixels = avatar._itens(com_itens)
    assert any(y < 0 for _, y, _ in pixels)                  # a cartola passa da cabeça
    assert 'viewBox="0 -3 12 19"' in avatar.svg(com_itens)
    for item, (_, categoria, preco, _) in jg.CATALOGO.items():
        assert preco > 0 and categoria in jg.CATEGORIAS
        if categoria != "moldura":
            assert avatar._itens(avatar.Avatar(**{categoria: item})), item
    foto = avatar.retrato(avatar.Avatar(moldura="moldura_ouro").json(), "data:image/png;base64,AA", "a", 40)
    assert "#F2C14E" in foto


def test_webhooks_so_servicos_conhecidos():
    assert webhooks.servico("https://discord.com/api/webhooks/1/abc") == "Discord"
    assert webhooks.servico("https://hooks.slack.com/services/T/B/X") == "Slack"
    assert webhooks.servico("https://empresa.webhook.office.com/x") == "Microsoft Teams"
    for ruim in ("http://discord.com/api/webhooks/1", "https://localhost/x", "https://169.254.169.254/",
                 "https://discord.com.evil.io/x", "javascript:alert(1)"):
        with pytest.raises(webhooks.ErroWebhook):
            webhooks.servico(ruim)
    assert webhooks.corpo("https://discord.com/api/webhooks/1/a", "T", "x")["content"] == "T\n\nx"
    assert webhooks.corpo("https://hooks.zapier.com/hooks/catch/1", "T", "x") == {"titulo": "T", "texto": "x",
                                                                                 "app": "Chrono Trade"}
    enviados = []
    assert webhooks.enviar("https://hooks.slack.com/s", "T", "x", http=enviados.append) == "enviado"
    assert json.loads(enviados[0].data) == {"text": "T\n\nx"}


def test_webhooks_guardados(tmp_path):
    enviados = []
    wh = webhooks.Webhooks(tmp_path / "c.db", http=enviados.append)
    assert wh.avisar("a@x", "T", "x") is None
    assert wh.salvar("a@x", "https://discord.com/api/webhooks/1/a") == "Discord"
    assert wh.avisar("a@x", "T", "x") == "enviado" and len(enviados) == 1
    wh.remover("a@x")
    assert wh.de("a@x") is None
