"""Avisos em outros apps por webhook: Discord, Slack, Microsoft Teams, Google Chat, Zapier e Make.

Cada pessoa cola o endereço do webhook em Avisos → Onde receber. Por segurança, só endereços HTTPS
desses serviços são aceitos (o servidor nunca chama endereços internos ou desconhecidos).
"""

from __future__ import annotations

import json
import sqlite3
import urllib.request
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

PERMITIDOS = {
    "discord.com": "Discord", "discordapp.com": "Discord", "hooks.slack.com": "Slack",
    "chat.googleapis.com": "Google Chat", "hooks.zapier.com": "Zapier", "hook.us1.make.com": "Make",
    "hook.eu1.make.com": "Make", "hook.us2.make.com": "Make", "hook.eu2.make.com": "Make",
}
_SUFIXOS_TEAMS = (".webhook.office.com", ".logic.azure.com")


class ErroWebhook(ValueError):
    pass


def servico(url: str) -> str:
    """Nome do serviço, ou erro se o endereço não for aceito."""
    partes = urlparse((url or "").strip())
    host = (partes.hostname or "").lower()
    if partes.scheme != "https" or not host:
        raise ErroWebhook("Use o endereço https completo do webhook.")
    if host in PERMITIDOS:
        return PERMITIDOS[host]
    if host.endswith(_SUFIXOS_TEAMS):
        return "Microsoft Teams"
    raise ErroWebhook("Aceitamos webhooks do Discord, Slack, Microsoft Teams, Google Chat, Zapier e Make.")


def corpo(url: str, titulo: str, texto: str) -> dict:
    nome = servico(url)
    mensagem = f"{titulo}\n\n{texto}"[:1900]
    if nome == "Discord":
        return {"content": mensagem, "username": "Chrono Trade"}
    if nome in ("Zapier", "Make"):
        return {"titulo": titulo, "texto": texto, "app": "Chrono Trade"}
    return {"text": mensagem}  # Slack, Teams (cartão simples) e Google Chat


def enviar(url: str, titulo: str, texto: str, http=None) -> str:
    try:
        dados = json.dumps(corpo(url, titulo, texto)).encode()
    except ErroWebhook as erro:
        return f"erro: {erro}"
    pedido = urllib.request.Request(url, data=dados, method="POST", headers={"Content-Type": "application/json"})
    try:
        if http:
            http(pedido)
        else:
            urllib.request.urlopen(pedido, timeout=15).read()
        return "enviado"
    except Exception as erro:
        return f"erro: {erro}"


class Webhooks:
    def __init__(self, caminho: Path, http=None):
        self.caminho, self.http = Path(caminho), http
        with self._con() as con:
            con.execute("CREATE TABLE IF NOT EXISTS webhooks (email TEXT PRIMARY KEY, url TEXT NOT NULL, criado_em TEXT NOT NULL)")

    @contextmanager
    def _con(self):
        con = sqlite3.connect(self.caminho, timeout=10)
        con.row_factory = sqlite3.Row
        try:
            yield con
            con.commit()
        finally:
            con.close()

    def de(self, email: str) -> str | None:
        with self._con() as con:
            ln = con.execute("SELECT url FROM webhooks WHERE email = ?", (email,)).fetchone()
        return ln["url"] if ln else None

    def salvar(self, email: str, url: str) -> str:
        nome = servico(url)
        with self._con() as con:
            con.execute("INSERT INTO webhooks VALUES (?, ?, ?) ON CONFLICT(email) DO UPDATE SET url = excluded.url",
                        (email, url.strip(), datetime.now().isoformat(timespec="seconds")))
        return nome

    def remover(self, email: str) -> None:
        with self._con() as con:
            con.execute("DELETE FROM webhooks WHERE email = ?", (email,))

    def avisar(self, email: str, titulo: str, texto: str) -> str | None:
        url = self.de(email)
        return enviar(url, titulo, texto, self.http) if url else None
