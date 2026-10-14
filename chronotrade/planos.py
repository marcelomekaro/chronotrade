"""Planos de assinatura: o que cada um libera e quanto custa.

Os recursos ficam numa tabela só, usada para liberar as telas, para montar o
comparativo da vitrine e para os limites (ativos, análises de IA, frequência
do agente). Mudar um plano é mudar esta tabela.
"""

from __future__ import annotations

from dataclasses import dataclass

ORDEM = ["basico", "medio", "premium"]
NOMES = {"basico": "Básico", "medio": "Médio", "premium": "Premium"}

# Recurso → plano mínimo que o libera.
RECURSOS = {
    "portal": "basico",
    "tesouro": "basico",
    "agenda": "basico",
    "linha_do_tempo": "basico",
    "ficha_rapida": "basico",
    "avisos_app": "basico",
    "pregao": "basico",
    "noticias": "basico",
    "aporte": "medio",
    "jarvis": "medio",
    "tecnica": "medio",
    "compartilhar": "medio",
    "simulador": "medio",
    "avisos_email": "medio",
    "oraculo": "premium",
    "corretora": "premium",
    "ponte": "premium",
    "avisos_whatsapp": "premium",
}

NOMES_RECURSOS = {
    "portal": "Portal com a linha do tempo até a meta de renda",
    "tesouro": "Tesouro: proventos mês a mês e número mágico",
    "agenda": "Agenda dos próximos dividendos",
    "linha_do_tempo": "Projeção do patrimônio em cenários",
    "ficha_rapida": "Ficha rápida de cada ação (Bazin, Graham, P/L, P/VP)",
    "avisos_app": "Sentinela: dica do próximo aporte no app",
    "pregao": "Pregão: sala ao vivo com outros investidores",
    "noticias": "Notícias da B3, negócios e vídeos do YouTube",
    "jarvis": "Jarvis: comandos de voz e assistente",
    "aporte": "Próximo Aporte: preço de entrada, preço justo e divisão em cotas",
    "tecnica": "Análise técnica: tendência, RSI e momento de compra",
    "compartilhar": "Relatórios para imprimir, PDF e WhatsApp",
    "simulador": "Carteira simulada com ordens de compra e venda",
    "avisos_email": "Sentinela por e-mail",
    "oraculo": "Oráculo: conselho de agentes de IA",
    "corretora": "Conexão com corretora (MetaTrader 5 e Profit) e carteira real",
    "ponte": "Conector do PC: sincroniza a corretora com a versão online",
    "avisos_whatsapp": "Sentinela por WhatsApp",
}


@dataclass(frozen=True)
class Limites:
    ativos: int | None          # None = sem limite
    analises_ia_mes: int
    sentinela: str              # "semanal" ou "diario"


LIMITES = {
    "basico": Limites(ativos=15, analises_ia_mes=0, sentinela="semanal"),
    "medio": Limites(ativos=None, analises_ia_mes=0, sentinela="semanal"),
    "premium": Limites(ativos=None, analises_ia_mes=30, sentinela="diario"),
}

PRECOS_PADRAO = {"basico": "19.90", "medio": "39.90", "premium": "79.90"}


def normalizar(plano: str | None) -> str:
    """Aceita nomes antigos (gratuito, completo) e devolve um plano válido."""
    plano = (plano or "").strip().lower()
    return {"gratuito": "basico", "completo": "premium"}.get(plano, plano if plano in ORDEM else "basico")


def nivel(plano: str) -> int:
    return ORDEM.index(normalizar(plano))


def libera(plano: str, recurso: str) -> bool:
    return nivel(plano) >= nivel(RECURSOS[recurso])


def plano_minimo(recurso: str) -> str:
    return RECURSOS[recurso]


def recursos_do_plano(plano: str) -> list[str]:
    return [r for r in RECURSOS if libera(plano, r)]


def preco_mensal(config: dict, plano: str) -> float:
    try:
        return float(str(config.get(f"preco_{plano}", PRECOS_PADRAO[plano])).replace(",", "."))
    except ValueError:
        return float(PRECOS_PADRAO[plano])


def desconto_anual(config: dict) -> float:
    try:
        return max(0.0, min(0.5, float(str(config.get("desconto_anual", "20")).replace(",", ".")) / 100))
    except ValueError:
        return 0.2


def preco(config: dict, plano: str, periodo: str) -> float:
    """Valor a pagar: mensal, ou 12 meses com o desconto anual."""
    mensal = preco_mensal(config, plano)
    if periodo == "anual":  # preço "redondo" terminado em ,90 (ex.: 190,90)
        return max(round(mensal * 12 * (1 - desconto_anual(config))) - 0.10, 0.0)
    return mensal


DIAS = {"mensal": 30, "anual": 365}
