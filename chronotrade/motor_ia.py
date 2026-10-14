"""Ponte entre o Chrono Trade e os agentes do TradingAgents.

Monta a configuração, roda a análise mostrando o progresso de cada etapa e guarda
o resultado em ``~/.chronotrade/oraculo/`` para consultar depois.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from chronotrade.carteira import pasta_dados
from chronotrade.mercado import ticker_curto

ANALISTAS = {
    "market": "Técnico (preço e indicadores)",
    "fundamentals": "Fundamentalista (balanços)",
    "news": "Notícias",
    "social": "Sentimento (redes sociais)",
}

# Modelos sugeridos quando o .env não diz quais usar: rápidos e do plano gratuito.
MODELOS_PADRAO = {
    "google": ("gemini-3.5-flash-lite", "gemini-3.8-flash"),
    "ollama": ("qwen3:4b", "qwen3:4b"),
    "openai": ("gpt-6-luna", "gpt-6-sol"),
    "anthropic": ("claude-sonnet-5", "claude-sonnet-5"),
    "groq": ("", ""),
}

ETAPAS = [
    ("analistas", "Analistas coletam dados"),
    ("pesquisa", "Debate otimista × pessimista"),
    ("trader", "Trader monta a proposta"),
    ("risco", "Comitê de risco"),
    ("decisao", "Gestor decide"),
]

ROTULOS = {
    "Buy": "Comprar", "Overweight": "Aumentar posição", "Hold": "Manter",
    "Underweight": "Reduzir posição", "Sell": "Vender", "REVIEW": "Revisar manualmente",
}


@dataclass
class Configuracao:
    provedor: str
    modelo_rapido: str
    modelo_profundo: str


def configuracao_do_ambiente() -> Configuracao:
    """Lê o provedor e os modelos do .env, completando com sugestões gratuitas."""
    import tradingagents  # noqa: F401  (carrega o .env)

    provedor = (os.environ.get("TRADINGAGENTS_LLM_PROVIDER") or "google").lower()
    rapido, profundo = MODELOS_PADRAO.get(provedor, ("", ""))
    return Configuracao(
        provedor=provedor,
        modelo_rapido=os.environ.get("TRADINGAGENTS_QUICK_THINK_LLM") or rapido,
        modelo_profundo=os.environ.get("TRADINGAGENTS_DEEP_THINK_LLM") or profundo,
    )


def chave_configurada(provedor: str) -> bool:
    from tradingagents.llm_clients.api_key_env import PROVIDER_API_KEY_ENV

    variavel = PROVIDER_API_KEY_ENV.get(provedor)
    return variavel is None or bool(os.environ.get(variavel))


def pasta_analises(base: Path | None = None) -> Path:
    pasta = (base or pasta_dados()) / "oraculo"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


@dataclass
class Resultado:
    ticker: str
    data: str
    rating: str
    estado: dict
    pasta: Path


def analisar(ticker: str, data: str, analistas: list[str], cfg: Configuracao,
             carteira=None, rodadas: int = 1,
             ao_progredir: Callable[[str, str], None] | None = None,
             base: Path | None = None) -> Resultado:
    """Roda a análise completa. ``ao_progredir(etapa, texto)`` recebe cada avanço."""
    from tradingagents.agents.rating import run_rating
    from tradingagents.default_config import build_default_config
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    avisar = ao_progredir or (lambda *_: None)
    config = build_default_config()
    config.update({
        "llm_provider": cfg.provedor,
        "quick_think_llm": cfg.modelo_rapido,
        "deep_think_llm": cfg.modelo_profundo,
        "output_language": "Portuguese",
        "max_debate_rounds": rodadas,
        "max_risk_discuss_rounds": rodadas,
        "benchmark_ticker": None,
    })
    if base is not None:  # cada assinante com a sua própria memória de decisões
        config["memory_log_path"] = str(base / "memoria" / "trading_memory.md")
    if not os.environ.get("TRADINGAGENTS_LLM_MAX_RETRIES") and cfg.provedor == "google":
        config["llm_max_retries"] = 10   # o plano gratuito limita pedidos por minuto

    ordem = [a for a in ANALISTAS if a in analistas]
    grafo = TradingAgentsGraph(ordem, config=config)
    portfolio = carteira.portfolio_context() if carteira is not None else None
    estado_inicial = grafo.create_run_state(ticker, data, "stock", portfolio)
    argumentos = grafo.propagator.get_graph_args()

    avisar("analistas", "Os analistas começaram a trabalhar.")
    relatorios_vistos: set[str] = set()
    nomes_relatorio = {
        "market_report": "Técnico", "sentiment_report": "Sentimento",
        "news_report": "Notícias", "fundamentals_report": "Fundamentalista",
    }
    final: dict = {}
    for _mensagens, pedaco in grafo.stream_run(estado_inicial, **argumentos):
        if not pedaco:
            continue
        final.update(pedaco)
        for chave, nome in nomes_relatorio.items():
            if pedaco.get(chave) and chave not in relatorios_vistos:
                relatorios_vistos.add(chave)
                avisar("analistas", f"Relatório {nome} pronto.")
        if pedaco.get("investment_plan"):
            avisar("pesquisa", "O debate entre otimista e pessimista terminou.")
        if pedaco.get("trader_investment_plan"):
            avisar("trader", "O trader montou a proposta.")
        risco = pedaco.get("risk_debate_state") or {}
        if risco.get("history"):
            avisar("risco", "O comitê de risco está discutindo.")
        if pedaco.get("final_trade_decision"):
            avisar("decisao", "O gestor tomou a decisão final.")

    grafo.record_decision(ticker, data, final)
    rating = run_rating(final)
    pasta = pasta_analises(base) / f"{ticker_curto(ticker)}_{datetime.now():%Y%m%d_%H%M%S}"
    grafo.save_reports(final, ticker, save_path=pasta, html=True)
    (pasta / "chronotrade.json").write_text(json.dumps({
        "ticker": ticker, "data": data, "rating": rating, "analistas": ordem,
        "provedor": cfg.provedor, "modelos": [cfg.modelo_rapido, cfg.modelo_profundo],
        "criado_em": datetime.now().isoformat(timespec="seconds"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return Resultado(ticker, data, rating, final, pasta)


@dataclass
class AnaliseSalva:
    pasta: Path
    ticker: str
    data: str
    rating: str
    criado_em: str

    @property
    def relatorio(self) -> str:
        arquivo = self.pasta / "complete_report.md"
        return arquivo.read_text(encoding="utf-8") if arquivo.exists() else ""

    @property
    def decisao(self) -> str:
        arquivo = next(self.pasta.rglob("decision.md"), None)
        return arquivo.read_text(encoding="utf-8") if arquivo else ""

    @property
    def html(self) -> Path | None:
        arquivo = self.pasta / "complete_report.html"
        return arquivo if arquivo.exists() else None


def analises_salvas(base: Path | None = None) -> list[AnaliseSalva]:
    itens = []
    for meta in pasta_analises(base).glob("*/chronotrade.json"):
        try:
            dados = json.loads(meta.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        itens.append(AnaliseSalva(meta.parent, dados.get("ticker", "?"), dados.get("data", ""),
                                  dados.get("rating", "REVIEW"), dados.get("criado_em", "")))
    return sorted(itens, key=lambda a: a.criado_em, reverse=True)
