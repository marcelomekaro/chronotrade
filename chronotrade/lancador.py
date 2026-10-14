"""Comando ``chronotrade``: abre o app no navegador."""

from __future__ import annotations

import sys
from pathlib import Path

TEMA = {
    "theme.base": "dark",
    "theme.primaryColor": "#F2C14E",
    "theme.backgroundColor": "#121838",
    "theme.secondaryBackgroundColor": "#1A2150",
    "theme.textColor": "#EDE6D2",
    "browser.gatherUsageStats": "false",
    "server.enableStaticServing": "true",   # serve o ícone e o manifesto do app
    "client.toolbarMode": "viewer",         # esconde os menus de desenvolvedor
}


def main() -> None:
    from streamlit.web import cli as stcli

    app = Path(__file__).with_name("app.py")
    argumentos = ["streamlit", "run", str(app)]
    for chave, valor in TEMA.items():
        argumentos += [f"--{chave}", valor]
    argumentos += sys.argv[1:]
    sys.argv = argumentos
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
