"""Análise técnica para quem faz aportes: o momento do preço, não previsão de curto prazo.

Para buy and hold a pergunta técnica é simples: comprar agora ou esperar um pouco?
Usamos poucos indicadores conhecidos e explicáveis:

- Médias móveis de 50 e 200 pregões: dizem a tendência.
- IFR (RSI) de 14 pregões: diz se o preço caiu ou subiu demais em pouco tempo.
- Distância da máxima de 52 semanas: quanto o preço já devolveu.

O resultado é um "momento de compra" (Favorável, Neutro ou Esticado) e um
fator que o planejador de aportes usa para dar mais ou menos peso ao ativo.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

FAVORAVEL = "Favorável"
NEUTRO = "Neutro"
ESTICADO = "Esticado"
SEM_HISTORICO = "Sem histórico"

FATOR = {FAVORAVEL: 1.3, NEUTRO: 1.0, ESTICADO: 0.6, SEM_HISTORICO: 1.0}


def ifr(precos: pd.Series, periodo: int = 14) -> pd.Series:
    """Índice de Força Relativa (RSI) pelo método de Wilder."""
    delta = precos.diff()
    ganhos = delta.clip(lower=0).ewm(alpha=1 / periodo, adjust=False, min_periods=periodo).mean()
    perdas = (-delta.clip(upper=0)).ewm(alpha=1 / periodo, adjust=False, min_periods=periodo).mean()
    rs = ganhos / perdas.replace(0, float("nan"))
    resultado = 100 - 100 / (1 + rs)
    return resultado.where(perdas != 0, 100.0)


@dataclass
class Diagnostico:
    preco: float | None
    mm50: float | None
    mm200: float | None
    ifr14: float | None
    tendencia: str            # Alta, Baixa ou Lateral
    dist_mm200: float | None  # quanto o preço está acima (+) ou abaixo (−) da MM200
    dist_maxima: float | None  # quanto está abaixo da máxima de 52 semanas (negativo)
    momento: str
    motivos: list[str]

    @property
    def fator(self) -> float:
        return FATOR[self.momento]


def diagnosticar(precos: pd.Series) -> Diagnostico:
    """Lê o histórico de fechamentos e devolve o momento de compra com os motivos."""
    serie = pd.Series(precos).dropna()
    if len(serie) < 60:
        return Diagnostico(float(serie.iloc[-1]) if len(serie) else None, None, None, None,
                           "Indefinida", None, None, SEM_HISTORICO, ["Histórico curto demais para a análise técnica."])
    preco = float(serie.iloc[-1])
    mm50 = float(serie.rolling(50).mean().iloc[-1])
    mm200 = float(serie.rolling(200).mean().iloc[-1]) if len(serie) >= 200 else None
    valor_ifr = float(ifr(serie).iloc[-1])
    maxima = float(serie.iloc[-252:].max())
    dist_maxima = preco / maxima - 1
    dist_mm200 = preco / mm200 - 1 if mm200 else None

    if mm200 is None:
        tendencia = "Alta" if preco > mm50 else "Baixa"
    elif mm50 > mm200 * 1.01 and preco > mm200:
        tendencia = "Alta"
    elif mm50 < mm200 * 0.99 and preco < mm200:
        tendencia = "Baixa"
    else:
        tendencia = "Lateral"

    motivos: list[str] = []
    pontos = 0
    if valor_ifr <= 30:
        pontos += 2
        motivos.append(f"IFR em {valor_ifr:.0f}: caiu forte em pouco tempo (sobrevendido)")
    elif valor_ifr <= 45:
        pontos += 1
        motivos.append(f"IFR em {valor_ifr:.0f}: preço respirando, sem euforia")
    elif valor_ifr >= 70:
        pontos -= 2
        motivos.append(f"IFR em {valor_ifr:.0f}: subiu rápido demais (sobrecomprado)")
    if dist_mm200 is not None and dist_mm200 >= 0.20:
        pontos -= 1
        motivos.append(f"{dist_mm200:.0%} acima da média de 200 dias: preço esticado".replace(".", ","))
    if tendencia == "Alta" and preco <= mm50 * 1.01:
        pontos += 1
        motivos.append("Tendência de alta e preço perto da média de 50 dias: recuo dentro da alta")
    if dist_maxima <= -0.25:
        pontos += 1
        motivos.append(f"{-dist_maxima:.0%} abaixo da máxima de 52 semanas".replace(".", ","))
    if tendencia == "Baixa":
        motivos.append("Tendência de baixa: prefira aportes parcelados")

    momento = FAVORAVEL if pontos >= 2 else (ESTICADO if pontos <= -2 else NEUTRO)
    if not motivos:
        motivos.append("Sem sinais fortes: preço dentro do comportamento normal")
    return Diagnostico(preco, mm50, mm200, valor_ifr, tendencia, dist_mm200, dist_maxima, momento, motivos)
