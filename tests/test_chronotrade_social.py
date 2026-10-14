"""Testes do Pregão, notícias, conexões (MT5/Profit), Conector do PC, Jarvis e MCP (sem internet)."""

import io
import json
from datetime import date, datetime, timedelta

import pytest

from chronotrade import (
    avatar,
    cena,
    conexoes as cx,
    contas,
    jarvis,
    mcp_servidor,
    noticias,
    ponte,
    pregao as pg,
)
from chronotrade.carteira import Carteira, Posicao
from chronotrade.corretoras.base import Corretora, ErroCorretora, PosicaoCorretora

AGORA = datetime(2026, 10, 14, 10, 0, 0)


# --- Avatar e cena -------------------------------------------------------------------------


def test_avatar_estavel_e_ida_e_volta():
    a = avatar.sortear("ana@x.com")
    assert a == avatar.sortear("ana@x.com")
    assert avatar.Avatar.de_json(a.json()) == a
    assert avatar.Avatar.de_json("{quebrado") is None
    desenho = avatar.svg(a, 48, "Ana")
    assert desenho.startswith("<svg") and "<title>Ana</title>" in desenho


def test_cena_escapa_html_e_mostra_balao():
    html = cena.salao([("a@x", "<b>Ana</b>", None)], {"a@x": "<script>oi</script>"}, eu="a@x",
                      cotacoes=[("PETR4", 38.5, 0.012), ("VALE3", None, None)])
    assert "<script>oi" not in html and "&lt;script&gt;" in html
    assert "&lt;b&gt;Ana" in html
    assert "1 pessoa online" in html
    assert "PETR4 38,50" in html and "VALE3" not in html
    assert html.count("ct-lugar vazio") == 7


# --- Pregão ---------------------------------------------------------------------------------


def test_pregao_presenca_mensagens_e_moderacao(tmp_path):
    p = pg.Pregao(tmp_path / "c.db")
    p.marcar_presenca("a@x", "geral", "Ana", None, AGORA)
    p.marcar_presenca("b@x", "geral", "Bia", None, AGORA - timedelta(minutes=5))
    assert [x.email for x in p.online("geral", AGORA)] == ["a@x"]
    m = p.enviar("geral", "a@x", "Ana", None, "  Olhando $TAEE11   e PETR4 hoje ", AGORA)
    assert m.texto == "Olhando $TAEE11 e PETR4 hoje" and m.tickers == ["TAEE11", "PETR4"]
    with pytest.raises(pg.ErroPregao, match="Calma"):
        p.enviar("geral", "a@x", "Ana", None, "de novo", AGORA + timedelta(seconds=1))
    with pytest.raises(pg.ErroPregao):
        p.enviar("geral", "a@x", "Ana", None, "x" * 501, AGORA + timedelta(seconds=10))
    with pytest.raises(pg.ErroPregao):
        p.enviar("sala-falsa", "a@x", "Ana", None, "oi", AGORA + timedelta(seconds=10))
    assert p.ultima_fala("geral", agora=AGORA) == {"a@x": m.texto}
    p.denunciar(m.id)
    assert [d.id for d in p.denunciadas()] == [m.id]
    p.remover(m.id)
    assert p.listar("geral") == [] and p.denunciadas() == []
    p.silenciar("a@x", 24, AGORA)
    with pytest.raises(pg.ErroPregao, match="silenciado"):
        p.enviar("geral", "a@x", "Ana", None, "oi", AGORA + timedelta(minutes=1))


def test_pregao_perfil_padrao_e_salvo(tmp_path):
    p = pg.Pregao(tmp_path / "c.db")
    apelido, av = p.perfil("marcelo@x.com", "Marcelo Mekaro")
    assert apelido == "Marcelo" and avatar.Avatar.de_json(av)
    with pytest.raises(pg.ErroPregao):
        p.salvar_perfil("marcelo@x.com", "M", av)
    p.salvar_perfil("marcelo@x.com", "  Mekaro   B3 ", av)
    assert p.perfil("marcelo@x.com")[0] == "Mekaro B3"
    pessoas, msgs = pg.demo(AGORA)
    assert len(pessoas) == len(msgs) == 5 and all(m.id < 0 for m in msgs)


# --- Notícias -------------------------------------------------------------------------------

RSS = b"""<?xml version="1.0"?><rss><channel>
<item><title>Taesa aprova dividendos - InfoMoney</title><link>https://ex.com/1</link>
<source url="https://infomoney.com.br">InfoMoney</source><pubDate>Tue, 13 Oct 2026 12:00:00 GMT</pubDate>
<description>&lt;p&gt;Valor de R$ 1,20&lt;/p&gt;</description></item></channel></rss>"""

ATOM = b"""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom" xmlns:yt="http://www.youtube.com/xml/schemas/2015">
<entry><yt:videoId>abcdefghijk</yt:videoId><title>Live da B3</title><link rel="alternate" href="https://www.youtube.com/watch?v=abcdefghijk"/>
<author><name>Canal B3</name></author><published>2026-10-13T10:00:00+00:00</published></entry></feed>"""


def test_noticias_rss_e_youtube():
    item = noticias.interpretar(RSS, "Google")[0]
    assert item.titulo == "Taesa aprova dividendos" and item.fonte == "InfoMoney"
    assert item.resumo == "Valor de R$ 1,20" and item.data == datetime(2026, 10, 13, 12)
    video = noticias.interpretar(ATOM, "YouTube")[0]
    assert video.video_id == "abcdefghijk" and video.fonte == "Canal B3"
    assert noticias.buscar("google:x", "G", baixar=lambda r: RSS)[0].link == "https://ex.com/1"
    assert noticias.buscar("https://quebrado", "G", baixar=lambda r: b"<nao xml") == []


def test_noticias_enderecos_e_config():
    assert noticias.resolver("google:B3 hoje").startswith("https://news.google.com/rss/search?q=B3%20hoje")
    canal = "UC" + "a" * 22
    assert noticias.resolver(f"https://www.youtube.com/channel/{canal}").endswith(f"channel_id={canal}")
    assert noticias.resolver(canal).endswith(canal)
    assert noticias.id_video("https://www.youtube.com/live/XddD29d2j6w?si=1") == "XddD29d2j6w"
    assert noticias.busca_do_ativo("TAEE11.SA") == '"TAEE11" OR "Taesa"'
    assert noticias.ler_fontes("") == noticias.FONTES_PADRAO
    assert noticias.ler_fontes("B3 | google:B3\nhttps://x.com/feed") == [("B3", "google:B3"),
                                                                        ("https://x.com/feed", "https://x.com/feed")]
    assert noticias.ler_fontes('[["A", "https://a"]]') == [("A", "https://a")]
    assert noticias.ler_canais("Canal | https://yt/c\nUCxyz\n") == ["https://yt/c", "UCxyz"]


# --- Conexões -------------------------------------------------------------------------------


class _Falsa(Corretora):
    nome = "falsa"

    def __init__(self, posicoes):
        self._p = posicoes

    def posicoes(self):
        return self._p

    def saldo(self):
        return 1234.5

    def enviar(self, ordem):
        raise ErroCorretora("não")

    def ordens(self):
        return []


def test_conexoes_comparar_e_aplicar():
    c = Carteira([Posicao("TAEE11.SA", 100, 30.0, "Ação"), Posicao("ITSA4.SA", 50, 9.0, "Ação"),
                  Posicao("WEGE3.SA", 10, 40.0, "Ação")])
    vindas = [PosicaoCorretora("TAEE11", 100, 30.0), PosicaoCorretora("ITSA4", 80, 9.5),
              PosicaoCorretora("MXRF11", 200, 10.0), PosicaoCorretora("ZERO3", 0, 1.0)]
    tipos = {m.ticker: m.tipo for m in cx.comparar(c, vindas)}
    assert tipos == {"TAEE11.SA": "igual", "ITSA4.SA": "alterado", "MXRF11.SA": "novo", "WEGE3.SA": "fora da corretora"}
    assert cx.aplicar(c, vindas) == 2
    assert {p.ticker: p.quantidade for p in c.posicoes} == {"TAEE11.SA": 100, "ITSA4.SA": 80, "WEGE3.SA": 10,
                                                            "MXRF11.SA": 200}
    assert next(p for p in c.posicoes if p.ticker == "MXRF11.SA").classe == "FII"
    assert cx.aplicar(c, vindas, remover_ausentes=True) == 1
    assert "WEGE3.SA" not in {p.ticker for p in c.posicoes}


def test_conexoes_perfis_cofre_e_teste(tmp_path):
    perfil = cx.Perfil("mt5", "XP", {"servidor": "XP-PRD", "login": "123"})
    cx.guardar(tmp_path, perfil)
    cx.guardar(tmp_path, cx.Perfil("profit", "Meu Profit", {"dll": "C:/p.dll"}))
    assert [p.id for p in cx.carregar(tmp_path)] == ["mt5:XP", "profit:Meu Profit"]
    assert cx.descrever(perfil) == "MetaTrader 5, XP-PRD, conta 123"

    cofre = cx.Cofre(tmp_path)
    cofre.gravar("mt5:XP", {"senha": "s3cr3t", "vazio": ""})
    assert cx.Cofre(tmp_path).ler("mt5:XP") == {"senha": "s3cr3t"}
    assert b"s3cr3t" not in (tmp_path / "cofre.bin").read_bytes()

    recebido = {}

    def fabrica(tipo, pasta, **opcoes):
        recebido.update(opcoes, tipo=tipo)
        return _Falsa([PosicaoCorretora("PETR4", 10, 30.0)])

    teste = cx.testar(perfil, cofre.ler("mt5:XP"), tmp_path, fabrica=fabrica)
    assert teste.ok and teste.saldo == 1234.5 and len(teste.posicoes) == 1
    assert recebido == {"tipo": "mt5", "caminho_terminal": None, "login": 123, "senha": "s3cr3t", "servidor": "XP-PRD"}

    def quebra(*a, **k):
        raise ErroCorretora("terminal fechado")

    ruim = cx.testar(perfil, {}, tmp_path, fabrica=quebra)
    assert not ruim.ok and ruim.mensagem == "terminal fechado"
    cx.marcar(tmp_path, perfil, ruim)
    assert cx.carregar(tmp_path)[-1].situacao == "Com erro"
    cx.remover(tmp_path, "mt5:XP", cofre)
    assert cofre.ler("mt5:XP") == {} and [p.id for p in cx.carregar(tmp_path)] == ["profit:Meu Profit"]


def test_opcoes_profit_converte_campos():
    p = cx.Perfil("profit", "P", {"dll": "C:/d.dll", "corretora_id": "308"})
    o = cx.opcoes(p, {"chave_ativacao": "K", "usuario": "u", "senha": "s"}, ["TAEE11.SA"])
    assert o == {"chave_ativacao": "K", "usuario": "u", "senha": "s", "dll": "C:/d.dll", "corretora_id": 308,
                 "tickers": ["TAEE11.SA"]}


def test_profit_sem_wrapper_explica_como_instalar():
    from chronotrade.corretoras import abrir

    with pytest.raises(ErroCorretora, match="profitdll-wrapper"):
        abrir("profit", None, chave_ativacao="k", usuario="u", senha="s")


def test_sentinela_sincroniza_conexoes_auto(tmp_path):
    from chronotrade.agentes.sentinela import sincronizar_conexoes
    from chronotrade.avisos import CaixaDeAvisos

    Carteira([Posicao("TAEE11.SA", 10, 30.0, "Ação")]).salvar(tmp_path / "carteira.json")
    cx.guardar(tmp_path, cx.Perfil("mt5", "XP", auto_sincronizar=True))
    cx.guardar(tmp_path, cx.Perfil("mt5", "Manual"))
    caixa = CaixaDeAvisos(tmp_path / "c.db")
    feitas = sincronizar_conexoes(tmp_path, caixa, fabrica=lambda t, p, **o: _Falsa([PosicaoCorretora("TAEE11", 25, 31.0)]))
    assert feitas == 1
    assert Carteira.carregar(tmp_path / "carteira.json").posicoes[0].quantidade == 25
    perfis = {p.apelido: p for p in cx.carregar(tmp_path)}
    assert perfis["XP"].ultima_sincronizacao and perfis["Manual"].ultima_sincronizacao is None


# --- Tokens, API e Conector do PC ----------------------------------------------------------------


def _assinante(tmp_path, plano="premium"):
    banco = contas.Contas(tmp_path / "contas.db")
    banco.cadastrar("Rafa Teste", "rafa@x.com", "senha-forte-1")
    banco.liberar("rafa@x.com", plano, 30)
    return banco


def test_tokens_gerar_usar_revogar(tmp_path):
    banco = _assinante(tmp_path)
    token = banco.gerar_token("rafa@x.com")
    assert token.startswith("ct_") and banco.dono_do_token(token).email == "rafa@x.com"
    assert banco.dono_do_token("ct_errado") is None and banco.dono_do_token("") is None
    lista = banco.tokens("rafa@x.com")
    assert len(lista) == 1 and lista[0]["ultimo_uso"] and token not in json.dumps(lista)
    banco.revogar_token("rafa@x.com", lista[0]["token_hash"])
    assert banco.dono_do_token(token) is None


def test_api_recebe_posicoes_do_conector(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from chronotrade import api

    monkeypatch.setenv("CHRONOTRADE_HOME", str(tmp_path))
    monkeypatch.setenv("CHRONOTRADE_MODO", "servidor")
    banco = _assinante(tmp_path)
    token = banco.gerar_token("rafa@x.com")
    cliente = TestClient(api.criar_app(banco))
    assert cliente.get("/api/saude").json()["ok"] is True
    corpo = {"plataforma": "mt5", "posicoes": [{"ticker": "taee11", "quantidade": 100, "preco_medio": 33.1},
                                                {"ticker": "PETR4", "quantidade": 5, "preco_medio": 30}]}
    assert cliente.post("/api/ponte/posicoes", json=corpo).status_code == 401
    assert cliente.post("/api/ponte/posicoes", json=corpo, headers={"Authorization": "Bearer ct_x"}).status_code == 401
    r = cliente.post("/api/ponte/posicoes", json=corpo, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200 and r.json()["posicoes"] == 2 and r.json()["mudancas"] == 2
    u = banco.buscar("rafa@x.com")
    pasta = tmp_path / "usuarios" / u.id_pasta
    assert {p.ticker for p in Carteira.carregar(pasta / "carteira.json").posicoes} == {"TAEE11.SA", "PETR4.SA"}
    assert api.status_ponte(pasta)["plataforma"] == "mt5"
    assert cliente.post("/api/ponte/posicoes", json={**corpo, "plataforma": "x"},
                        headers={"Authorization": f"Bearer {token}"}).status_code == 422
    banco.liberar("rafa@x.com", "medio", 1)  # muda para um plano sem o Conector
    r = cliente.post("/api/ponte/posicoes", json=corpo, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403 and "Premium" in r.json()["detail"]


def test_ponte_le_e_envia():
    enviados = {}

    def http(pedido):
        enviados["url"] = pedido.full_url
        enviados["auth"] = pedido.get_header("Authorization")
        enviados["corpo"] = json.loads(pedido.data)
        return {"posicoes": 1, "mudancas": 1}

    posicoes = ponte.ler_posicoes("mt5", [], fabrica=lambda *a, **k: _Falsa([PosicaoCorretora("ITSA4", 3, 9.0)]))
    assert ponte.enviar("https://app.x/", "ct_t", "mt5", posicoes, http) == {"posicoes": 1, "mudancas": 1}
    assert enviados["url"] == "https://app.x/api/ponte/posicoes" and enviados["auth"] == "Bearer ct_t"
    assert enviados["corpo"]["posicoes"] == [{"ticker": "ITSA4", "quantidade": 3, "preco_medio": 9.0}]
    with pytest.raises(ErroCorretora):
        ponte.ler_posicoes("outra", [])


# --- Jarvis --------------------------------------------------------------------------------------


@pytest.mark.parametrize("texto,acao,ticker,extra", [
    ("cotação da Petrobras", "cotacao", "PETR4", {}),
    ("como está o ibovespa", "cotacao", "^BVSP", {}),
    ("petr quatro", "cotacao", "PETR4", {}),
    ("quanto vale minha carteira", "patrimonio", None, {}),
    ("abrir o pregão", "navegar", None, {"pagina": "pregao"}),
    ("vai para conexões", "navegar", None, {"pagina": "conexoes"}),
    ("qual a dica do próximo aporte?", "dica", None, {}),
    ("próximos dividendos da Taesa", "proventos", "TAEE11", {}),
    ("notícias da WEG", "noticias", "WEGE3", {}),
    ("comprar 100 TAEE11 a 35,50 reais", "ordem", "TAEE11", {"lado": "compra", "quantidade": 100, "preco": 35.5}),
    ("vende cem ações da vale três", "ordem", "VALE3", {"lado": "venda", "quantidade": 100}),
    ("compre duzentas e cinquenta cotas de mxrf onze", "ordem", "MXRF11", {"quantidade": 250}),
    ("compra 1 lote de bbas3", "ordem", "BBAS3", {"quantidade": 100}),
    ("devo comprar PETR4?", "conversa", "PETR4", {}),
    ("manda a cotação do Itaú no WhatsApp", "compartilhar", "ITUB4", {}),
    ("o que é dividend yield", "conversa", None, {}),
    ("ajuda", "ajuda", None, {}),
])
def test_jarvis_entende_portugues(texto, acao, ticker, extra):
    cmd = jarvis.entender(texto)
    assert (cmd.acao, cmd.ticker) == (acao, ticker)
    for chave, valor in extra.items():
        assert getattr(cmd, chave) == valor


class _Dado:
    def __init__(self, preco, anterior=None, prox=None):
        self.preco, self.variacao_dia, self.proximo_provento = preco, (preco / anterior - 1 if anterior else None), prox


def _ctx(conversar=None):
    c = Carteira([Posicao("TAEE11.SA", 100, 30.0, "Ação"), Posicao("ITSA4.SA", 10, 9.0, "Ação")])
    dados = {"TAEE11.SA": _Dado(36.0, 35.0, (date(2026, 10, 20), 1.2)), "ITSA4.SA": _Dado(10.0),
             "^BVSP": _Dado(130000.0, 129000.0), "PETR4.SA": _Dado(None)}
    return jarvis.Contexto(c, lambda t: dados.get(t, _Dado(None)), conversar=conversar,
                           resumo=lambda: {"patrimonio": 3700.0, "ativos": 2, "renda_12m": 250.0})


def test_jarvis_executa_comandos():
    ctx = _ctx()
    r = jarvis.executar(jarvis.entender("cotação TAEE11"), ctx)
    assert r.texto.startswith("TAEE11 está em R$ 36,00, alta de 2,86% no dia")
    assert "130.000 pontos" in jarvis.executar(jarvis.entender("como está o ibovespa"), ctx).texto
    assert "Não consegui" in jarvis.executar(jarvis.entender("cotação PETR4"), ctx).texto
    assert "R$ 3.700,00" in jarvis.executar(jarvis.entender("meu patrimônio"), ctx).texto
    prov = jarvis.executar(jarvis.entender("próximos proventos"), ctx)
    assert "Anunciadas: TAEE11 em 20/10, cerca de R$ 120,00" in prov.texto
    ordem = jarvis.executar(jarvis.entender("comprar 100 TAEE11"), ctx)
    assert ordem.ordem == {"ticker": "TAEE11", "lado": "compra", "quantidade": 100, "preco": None}
    assert "simulada" in ordem.texto
    assert jarvis.executar(jarvis.entender("comprar TAEE11"), ctx).ordem is None
    assert jarvis.executar(jarvis.entender("abrir agenda"), ctx).pagina == "paginas/agenda.py"
    assert "CVM" in jarvis.executar(jarvis.entender("devo comprar PETR4?"), ctx).texto


def test_jarvis_conversa_tem_trava_legal():
    pedidos = []

    def llm(mensagens):
        pedidos.append(mensagens)
        return "Você pode comprar ações que pagam dividendos."

    r = jarvis.executar(jarvis.entender("explique o que é preço teto"), _ctx(llm))
    assert jarvis.AVISO_CURTO in r.texto
    assert pedidos[0][0]["role"] == "system" and "Nunca recomende" in pedidos[0][0]["content"]
    assert "R$ 3.700,00" in pedidos[0][0]["content"]


class _Resp(io.BytesIO):
    pass


def test_cliente_openjarvis_fala_o_protocolo():
    chamadas = []

    def abrir(pedido, tempo):
        chamadas.append(pedido)
        if pedido.full_url.endswith("/v1/speech/health"):
            return _Resp(b'{"available": true}')
        if pedido.full_url.endswith("/health"):
            return _Resp(b'{"status":"ok"}')
        if pedido.full_url.endswith("/transcribe"):
            return _Resp(b'{"text": " cota\\u00e7\\u00e3o da taesa "}')
        if pedido.full_url.endswith("/synthesize"):
            return _Resp(b"RIFF....WAVE")
        return _Resp(json.dumps({"choices": [{"message": {"content": " Oi! "}}]}).encode())

    c = jarvis.Cliente("http://pc:8000/", chave="k", abrir=abrir)
    assert c.saude() == {"online": True, "voz": True, "detalhe": "OpenJarvis conectado com voz."}
    assert c.transcrever(b"AUDIO") == "cotação da taesa"
    multipart = chamadas[-1]
    assert b'name="file"; filename="fala.wav"' in multipart.data and b"AUDIO" in multipart.data
    assert multipart.get_header("Authorization") == "Bearer k"
    assert c.sintetizar("oi") == b"RIFF....WAVE"
    assert c.conversar([{"role": "user", "content": "oi"}]) == "Oi!"

    def fora(pedido, tempo):
        raise OSError("recusado")

    assert jarvis.Cliente("http://pc:8000", abrir=fora).saude()["online"] is False
    assert jarvis.Cliente("http://pc:8000", abrir=fora).conversar([]) is None


def test_jarvis_config_mcp_e_voz_do_navegador():
    trecho = jarvis.config_mcp()
    assert trecho.startswith("[tools.mcp]\nenabled = true")
    servidores = json.loads(trecho.split("servers = '")[1].rstrip("'\n"))
    assert servidores == [{"name": "chronotrade", "command": "chronotrade-mcp", "args": []}]
    assert '"</script>' not in jarvis.falar_no_navegador('oi"</script>')


# --- Servidor MCP --------------------------------------------------------------------------


def test_mcp_protocolo(tmp_path, monkeypatch):
    monkeypatch.setenv("CHRONOTRADE_HOME", str(tmp_path))
    monkeypatch.setenv("CHRONOTRADE_DEMO", "1")
    ini = mcp_servidor.responder({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                  "params": {"protocolVersion": "2025-03-26"}})
    assert ini["result"]["serverInfo"]["name"] == "chronotrade"
    assert mcp_servidor.responder({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    nomes = {f["name"] for f in mcp_servidor.responder({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]}
    assert nomes == {"resumo_carteira", "proximos_proventos", "dica_aporte", "cotacao", "noticias_ativo"}
    vazia = mcp_servidor.responder({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                                    "params": {"name": "resumo_carteira", "arguments": {}}})
    assert "vazia" in vazia["result"]["content"][0]["text"]
    Carteira([Posicao("TAEE11.SA", 100, 30.0, "Ação")]).salvar(tmp_path / "carteira.json")
    resumo = mcp_servidor.responder({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                                     "params": {"name": "resumo_carteira", "arguments": {}}})
    assert "TAEE11" in resumo["result"]["content"][0]["text"] and resumo["result"]["isError"] is False
    dica = mcp_servidor.responder({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                                   "params": {"name": "dica_aporte", "arguments": {}}})
    assert "não é recomendação" in dica["result"]["content"][0]["text"]
    cot = mcp_servidor.responder({"jsonrpc": "2.0", "id": 6, "method": "tools/call",
                                  "params": {"name": "cotacao", "arguments": {"ticker": "itsa4"}}})
    assert cot["result"]["content"][0]["text"].startswith("ITSA4: R$")
    erro = mcp_servidor.responder({"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": "x"}})
    assert erro["error"]["code"] == -32602
    assert mcp_servidor.responder({"jsonrpc": "2.0", "id": 8, "method": "resources/list"})["error"]["code"] == -32601
