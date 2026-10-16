"""Trilha sonora: botão flutuante com música gerada no navegador (incentivo, tensão, euforia, felicidade).

A trilha automática muda de clima com o que acontece no app: euforia quando a carteira sobe forte no dia, tensão
no teste de estresse, felicidade no check-in e nas conquistas, incentivo nos aportes. A pessoa também pode enviar
uma música própria (fica em static/musicas e toca em repetição).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import streamlit as st

_PASTA = Path(__file__).parent / "componentes" / "trilha"
PASTA_MUSICAS = Path(__file__).parent / "static" / "musicas"
TIPOS = {"mp3": "audio/mpeg", "ogg": "audio/ogg", "wav": "audio/wav", "m4a": "audio/mp4"}
TAMANHO_MAXIMO = 12 * 1024 * 1024
_componente = None


def _comp():
    global _componente
    if _componente is None:
        import streamlit.components.v1 as components

        _componente = components.declare_component("trilha_sonora", path=str(_PASTA))
    return _componente


def guardar_musica(dados: bytes, nome_arquivo: str) -> str:
    """Salva a música enviada e devolve o endereço para tocar (app/static/musicas/...)."""
    extensao = nome_arquivo.rsplit(".", 1)[-1].lower()
    if extensao not in TIPOS:
        raise ValueError("Use MP3, OGG, WAV ou M4A.")
    if len(dados) > TAMANHO_MAXIMO:
        raise ValueError("Música grande demais: até 12 MB.")
    PASTA_MUSICAS.mkdir(parents=True, exist_ok=True)
    nome = hashlib.sha256(dados).hexdigest()[:24] + "." + extensao
    (PASTA_MUSICAS / nome).write_bytes(dados)
    copia = _pasta_persistente()
    copia.mkdir(parents=True, exist_ok=True)
    (copia / nome).write_bytes(dados)  # cópia na pasta de dados: volta depois de um novo deploy
    return f"app/static/musicas/{nome}"


def _pasta_persistente() -> Path:
    from chronotrade.carteira import pasta_dados

    return pasta_dados() / "musicas"


def restaurar_musicas() -> int:
    """Depois de um deploy (Render, Docker), a pasta static volta vazia: copia as músicas da pasta de dados."""
    origem = _pasta_persistente()
    if not origem.exists():
        return 0
    PASTA_MUSICAS.mkdir(parents=True, exist_ok=True)
    n = 0
    for arq in origem.iterdir():
        if arq.suffix.lstrip(".") in TIPOS and not (PASTA_MUSICAS / arq.name).exists():
            (PASTA_MUSICAS / arq.name).write_bytes(arq.read_bytes())
            n += 1
    return n


@st.cache_resource
def _restaurar_uma_vez() -> int:
    try:
        return restaurar_musicas()
    except OSError:
        return 0


def botao() -> None:
    """Desenha o botão da trilha no canto da tela (ao lado do Jarvis)."""
    from chronotrade import estado

    _restaurar_uma_vez()
    try:
        musica, nome = estado.pregao().musica_de(estado.identidade()[0])
    except Exception:
        musica, nome = None, None
    _comp()(evento=st.session_state.get("trilha_evento"), minha_musica=musica, minha_nome=nome, key="trilha_sonora",
            default=None)
