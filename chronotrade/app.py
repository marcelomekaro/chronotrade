"""Chrono Trade: a sua carteira de buy and hold, vista como uma viagem no tempo.

Rode com:  chronotrade      (ou: streamlit run chronotrade/app.py)
"""

from __future__ import annotations

import sys
from pathlib import Path

# Permite rodar com "streamlit run chronotrade/app.py" mesmo sem instalar o pacote.
_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

import streamlit as st  # noqa: E402

from chronotrade import estado, tema  # noqa: E402

st.set_page_config(page_title="Chrono Trade", page_icon="⏳", layout="wide")
tema.aplicar()

_PAGINAS = Path(__file__).parent / "paginas"
paginas = [
    st.Page(_PAGINAS / "portal.py", title="Portal", icon="🌀", default=True),
    st.Page(_PAGINAS / "inventario.py", title="Inventário", icon="🎒"),
    st.Page(_PAGINAS / "tesouro.py", title="Tesouro", icon="💰"),
    st.Page(_PAGINAS / "linha_do_tempo.py", title="Linha do Tempo", icon="⏳"),
    st.Page(_PAGINAS / "oraculo.py", title="Oráculo", icon="🔮"),
]
navegacao = st.navigation(paginas, position="hidden")

with st.sidebar:
    st.markdown('<div class="ct-marca">Chrono Trade<small>Buy and hold na B3, um ano de cada vez</small></div>',
                unsafe_allow_html=True)
    st.write("")
    for pagina in paginas:
        st.page_link(pagina)
    st.divider()
    estado.modo_demo()  # garante o valor inicial antes do botão
    st.toggle("Modo demonstração", key="demo",
              help="Usa cotações e proventos fictícios. Útil para conhecer o app sem internet.")
    st.caption("Ferramenta de estudo. Não é recomendação de investimento.")

navegacao.run()
