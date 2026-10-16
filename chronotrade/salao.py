"""O salão interativo do Pregão: componente com avatares que andam, balões e gráficos nas mesas."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from chronotrade.pregao import PERIODOS

_PASTA = Path(__file__).parent / "componentes" / "salao"
_componente = None


def _comp():
    global _componente
    if _componente is None:
        import streamlit.components.v1 as components

        _componente = components.declare_component("salao_chrono", path=str(_PASTA))
    return _componente


def serie_grafico(historico: pd.Series, periodo: str = "6m", pontos: int = 90) -> dict | None:
    """Fechamentos do período, reduzidos para desenhar rápido: serie, datas, variação e último preço."""
    if historico is None or len(historico) < 2:
        return None
    dias = PERIODOS.get(periodo, PERIODOS["6m"])[1]
    s = historico.dropna().tail(dias)
    if len(s) < 2:
        return None
    passo = max(1, len(s) // pontos)
    reduzida = s.iloc[::passo]
    if reduzida.index[-1] != s.index[-1]:
        reduzida = pd.concat([reduzida, s.tail(1)])
    def data(d):
        try:
            return pd.Timestamp(d).strftime("%d/%m/%Y")
        except (ValueError, TypeError):
            return ""
    return {"serie": [round(float(v), 2) for v in reduzida.values], "datas": [data(s.index[0]), data(s.index[-1])],
            "var": float(s.iloc[-1] / s.iloc[0] - 1) if s.iloc[0] else None, "ultimo": round(float(s.iloc[-1]), 2),
            "periodo_nome": PERIODOS.get(periodo, PERIODOS["6m"])[0]}


def mostrar(eu: str, titulo: str, subtitulo: str, pessoas: list[dict], telao: dict | None, cotacoes: list,
            dica: str, key: str, altura: int | None = None, emotes: list[dict] | None = None,
            minhas_frases: list[dict] | None = None, pode: bool = False):
    """Desenha o salão e devolve a última ação da pessoa ({acao: mover|privado|emoji|frase, ...}) ou None."""
    from chronotrade.pregao import EMOJI_NOMES, EMOJIS

    return _comp()(eu=eu, titulo=titulo, subtitulo=subtitulo, pessoas=pessoas, telao=telao, cotacoes=cotacoes,
                   dica=dica, altura=altura, emotes=emotes or [], minhas_frases=minhas_frases or [],
                   emojis=EMOJIS, emoji_nomes=EMOJI_NOMES, pode=pode, key=key, default=None)


def emotes_demo(agora: float, intervalo: int = 6) -> list[dict]:
    """Os participantes de demonstração soltam um emoji de vez em quando, para o salão parecer vivo."""
    from chronotrade.pregao import _DEMO, EMOJIS, id_publico

    balde = int(agora // intervalo)
    saida = []
    for b in (balde - 1, balde):
        idade = agora - b * intervalo
        if 0 <= idade < 8:
            email = _DEMO[b % len(_DEMO)][0]
            saida.append({"id": -b, "pid": id_publico(email), "tipo": "emoji", "conteudo": EMOJIS[(b * 7) % len(EMOJIS)],
                          "idade": round(idade, 1)})
    return saida


def sparkline(serie: list[float], largura: int = 160, altura: int = 44) -> str:
    """Mini gráfico como <img> (SVG embutido), para a conversa."""
    import base64

    if not serie or len(serie) < 2:
        return ""
    mn, mx = min(serie), max(serie)
    amp = (mx - mn) or 1
    pts = " ".join(f"{i / (len(serie) - 1) * largura:.1f},{altura - 3 - (v - mn) / amp * (altura - 6):.1f}"
                   for i, v in enumerate(serie))
    cor = "#5FD39A" if serie[-1] >= serie[0] else "#F06A5D"
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{largura}" height="{altura}" viewBox="0 0 {largura} {altura}">'
           f'<rect width="100%" height="100%" rx="4" fill="#05071A"/>'
           f'<polyline points="{pts}" fill="none" stroke="{cor}" stroke-width="2"/></svg>')
    return (f'<img alt="mini gráfico" width="{largura}" height="{altura}" '
            f'src="data:image/svg+xml;base64,{base64.b64encode(svg.encode()).decode()}">')
