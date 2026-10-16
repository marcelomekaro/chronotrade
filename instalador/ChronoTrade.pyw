"""Abre o Chrono Trade no Windows (instalado): liga o app e o navegador, sem janela preta.

Os dados e o .env (chaves) ficam em %USERPROFILE%\\.chronotrade, separados do programa: atualizar ou
desinstalar o programa não apaga a carteira.
"""
import os
import sys
import urllib.request
import webbrowser
from pathlib import Path

DADOS = Path(os.environ.get("CHRONOTRADE_HOME") or Path.home() / ".chronotrade")
DADOS.mkdir(parents=True, exist_ok=True)
PORTA = int(os.environ.get("CHRONOTRADE_PORTA", "8501"))
ENDERECO = f"http://localhost:{PORTA}"

# pythonw não tem console: tudo que o app escreveria vai para um arquivo de registro
registro = open(DADOS / "chronotrade.log", "a", encoding="utf-8", buffering=1)
sys.stdout = sys.stderr = registro

# Já está aberto? Só mostra no navegador.
try:
    urllib.request.urlopen(ENDERECO + "/_stcore/health", timeout=1.5)
    webbrowser.open(ENDERECO)
    sys.exit(0)
except Exception:
    pass

os.chdir(DADOS)  # o app procura o .env a partir daqui
try:
    from dotenv import load_dotenv

    load_dotenv(DADOS / ".env")
except Exception:
    pass
os.environ.setdefault("CHRONOTRADE_HOME", str(DADOS))
(DADOS / "servidor.pid").write_text(str(os.getpid()))


def _abrir_quando_pronto():
    """Espera o servidor responder e abre o navegador (o modo sem cabeça evita a pergunta de e-mail do Streamlit)."""
    import time

    for _ in range(240):
        try:
            urllib.request.urlopen(ENDERECO + "/_stcore/health", timeout=1.5)
            webbrowser.open(ENDERECO)
            return
        except Exception:
            time.sleep(0.5)


import threading  # noqa: E402

threading.Thread(target=_abrir_quando_pronto, daemon=True).start()
sys.argv = ["chronotrade", "--server.port", str(PORTA), "--server.headless", "true",
            "--browser.gatherUsageStats", "false", "--server.address", "localhost"]
from chronotrade.lancador import main  # noqa: E402

main()
