"""Servidor MCP do Chrono Trade: dá ao OpenJarvis (ou a qualquer cliente MCP) as ferramentas da carteira.

Protocolo: MCP por stdio, mensagens JSON-RPC uma por linha. Ferramentas:
- resumo_carteira      patrimônio, ativos, renda de proventos
- proximos_proventos   datas com anunciadas e previstas (30 dias)
- dica_aporte          a divisão do aporte do mês pelas regras da pessoa
- cotacao              preço e variação do dia de um ativo da B3
- noticias_ativo       manchetes recentes (Google Notícias)

No OpenJarvis, cole no ~/.openjarvis/config.toml:

    [tools.mcp]
    enabled = true
    servers = '[{"name": "chronotrade", "command": "chronotrade-mcp", "args": []}]'

Lê a carteira do modo pessoal (pasta CHRONOTRADE_HOME). Só leitura: não envia ordens.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date, timedelta

from chronotrade import agenda, noticias
from chronotrade.calculos import brl
from chronotrade.carteira import Carteira, montar_tabela, pasta_dados, resumir
from chronotrade.legal import AVISO_CURTO
from chronotrade.mercado import carregar_ativo, normalizar_ticker, ticker_curto

VERSAO_PROTOCOLO = "2025-03-26"

FERRAMENTAS = [
    {"name": "resumo_carteira", "description": "Resumo da carteira de investimentos do usuário no Chrono Trade: "
     "patrimônio, resultado, renda de proventos em 12 meses e os ativos.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "proximos_proventos", "description": "Próximas datas com de dividendos/JCP dos ativos da carteira "
     "nos próximos dias, com valor estimado.",
     "inputSchema": {"type": "object", "properties": {"dias": {"type": "integer", "default": 30}}}},
    {"name": "dica_aporte", "description": "Divisão sugerida do aporte do mês pelas regras que o próprio usuário "
     "configurou (preço justo, margem, metas). Não é recomendação de investimento.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "cotacao", "description": "Cotação atual e variação do dia de um ativo da B3 (ex.: PETR4, TAEE11, ^BVSP).",
     "inputSchema": {"type": "object", "properties": {"ticker": {"type": "string"}}, "required": ["ticker"]}},
    {"name": "criar_alerta", "description": "Cria um alerta de preço: o agente Sentinela avisa quando o ativo ficar "
     "abaixo ou acima do preço informado.",
     "inputSchema": {"type": "object", "properties": {"ticker": {"type": "string"},
                                                      "tipo": {"type": "string", "enum": ["abaixo", "acima"]},
                                                      "preco": {"type": "number"}}, "required": ["ticker", "tipo", "preco"]}},
    {"name": "noticias_ativo", "description": "Manchetes recentes sobre um ativo ou tema do mercado brasileiro.",
     "inputSchema": {"type": "object", "properties": {"termo": {"type": "string"}}, "required": ["termo"]}},
]


def _demo() -> bool:
    return os.environ.get("CHRONOTRADE_DEMO", "").lower() in ("1", "true", "sim")


def _obter(ticker: str):
    return carregar_ativo(ticker, demo=_demo())


def _carteira() -> Carteira:
    return Carteira.carregar(pasta_dados() / "carteira.json")


def resumo_carteira(_: dict) -> str:
    c = _carteira()
    if not c.posicoes:
        return "A carteira está vazia. Cadastre os ativos na tela Inventário do Chrono Trade."
    dados = {p.ticker: _obter(p.ticker) for p in c.posicoes}
    tabela = montar_tabela(c, dados)
    r = resumir(tabela, c.caixa)
    linhas = [f"Patrimônio: {brl(r.patrimonio)} (custo {brl(r.custo)}, resultado {brl(r.resultado)}).",
              f"Renda de proventos em 12 meses: {brl(r.renda_12m)} (média de {brl(r.renda_mensal_media)} por mês).",
              "Ativos:"]
    for _, ln in tabela.sort_values("valor", ascending=False).iterrows():
        linhas.append(f"- {ticker_curto(ln['ticker'])}: {ln['quantidade']:g} a {brl(ln['preco'])}, total {brl(ln['valor'])}")
    return "\n".join(linhas)


def proximos_proventos(args: dict) -> str:
    dias = int(args.get("dias") or 30)
    hoje = date.today()
    eventos = []
    for p in _carteira().posicoes:
        d = _obter(p.ticker)
        eventos += [e for e in agenda.prever(p.ticker, d.dividendos, p.quantidade, hoje, meses=max(1, dias // 30 + 1),
                                             confirmado=d.proximo_provento) if e.data <= hoje + timedelta(days=dias)]
    if not eventos:
        return f"Nenhuma data com prevista nos próximos {dias} dias."
    eventos.sort(key=lambda e: e.data)
    return "\n".join(f"- {ticker_curto(e.ticker)}: data com {e.data:%d/%m/%Y}, ~{brl(e.total)} ({e.situacao.lower()})"
                     for e in eventos[:15])


def dica_aporte(_: dict) -> str:
    from chronotrade.agentes.sentinela import montar_dica

    c = _carteira()
    if not (c.posicoes or c.observar):
        return "A carteira está vazia: sem dados para a dica do aporte."
    return montar_dica(c, _obter).texto


def cotacao(args: dict) -> str:
    ticker = str(args.get("ticker", "")).strip()
    d = _obter(normalizar_ticker(ticker))
    if not d.preco:
        return f"Sem cotação para {ticker} agora."
    var = d.variacao_dia
    extra = f", {var * 100:+.2f}% no dia".replace(".", ",") if var is not None else ""
    return f"{ticker_curto(d.ticker)}: {brl(d.preco)}{extra}."


def noticias_ativo(args: dict) -> str:
    termo = str(args.get("termo", "")).strip()
    busca = noticias.busca_do_ativo(termo) if len(termo) <= 7 else termo
    itens = noticias.demo([termo]) if _demo() else noticias.buscar("google:" + busca, "Google Notícias", limite=6)
    if not itens:
        return "Não encontrei notícias agora."
    return "\n".join(f"- {i.titulo} ({i.fonte}) {i.link}" for i in itens[:6])


def criar_alerta(args: dict) -> str:
    from chronotrade.agentes.sentinela import EMAIL_LOCAL
    from chronotrade.alertas import Alertas, ErroAlerta

    try:
        a = Alertas(pasta_dados() / "contas.db").criar(EMAIL_LOCAL, str(args.get("ticker", "")), str(args.get("tipo", "")),
                                                       float(args.get("preco") or 0))
    except (ErroAlerta, ValueError) as erro:
        return f"Não criei o alerta: {erro}"
    return f"Alerta criado: {a.descricao}. O Sentinela avisa no app e nos canais ligados."


FUNCOES = {"criar_alerta": criar_alerta, "resumo_carteira": resumo_carteira, "proximos_proventos": proximos_proventos, "dica_aporte": dica_aporte,
           "cotacao": cotacao, "noticias_ativo": noticias_ativo}


def responder(mensagem: dict) -> dict | None:
    """Trata uma mensagem JSON-RPC. Notificações (sem id) não têm resposta."""
    metodo, id_ = mensagem.get("method"), mensagem.get("id")
    if id_ is None:
        return None
    if metodo == "initialize":
        resultado = {"protocolVersion": mensagem.get("params", {}).get("protocolVersion", VERSAO_PROTOCOLO),
                     "capabilities": {"tools": {"listChanged": False}},
                     "serverInfo": {"name": "chronotrade", "version": "1.0"}}
    elif metodo == "ping":
        resultado = {}
    elif metodo == "tools/list":
        resultado = {"tools": FERRAMENTAS}
    elif metodo == "tools/call":
        params = mensagem.get("params", {})
        funcao = FUNCOES.get(params.get("name"))
        if funcao is None:
            return {"jsonrpc": "2.0", "id": id_, "error": {"code": -32602, "message": "Ferramenta desconhecida"}}
        try:
            texto = funcao(params.get("arguments") or {})
            if params.get("name") in ("dica_aporte",) and AVISO_CURTO not in texto:
                texto += "\n" + AVISO_CURTO
            resultado = {"content": [{"type": "text", "text": texto}], "isError": False}
        except Exception as erro:
            resultado = {"content": [{"type": "text", "text": f"Erro: {erro}"}], "isError": True}
    else:
        return {"jsonrpc": "2.0", "id": id_, "error": {"code": -32601, "message": f"Método não suportado: {metodo}"}}
    return {"jsonrpc": "2.0", "id": id_, "result": resultado}


def main() -> None:
    for linha in sys.stdin:
        linha = linha.strip()
        if not linha:
            continue
        try:
            resposta = responder(json.loads(linha))
        except ValueError:
            resposta = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "JSON inválido"}}
        if resposta is not None:
            sys.stdout.write(json.dumps(resposta, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
