"""Fecha o Chrono Trade que está rodando em segundo plano."""
import os
import signal
from pathlib import Path

pid_arq = Path(os.environ.get("CHRONOTRADE_HOME") or Path.home() / ".chronotrade") / "servidor.pid"
try:
    pid = int(pid_arq.read_text().strip())
    if os.name == "nt":  # no Windows, encerra o processo pelo número (e os filhos dele)
        import subprocess

        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    else:
        os.kill(pid, signal.SIGTERM)
except Exception:
    pass
pid_arq.unlink(missing_ok=True)
