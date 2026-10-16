"""Avisos pelo Telegram: gratuito, sem limite de mensagens e fácil de ligar.

Como ligar (uma vez, pelo administrador):
1. No Telegram, fale com @BotFather, crie um bot e copie o token.
2. No .env: TELEGRAM_BOT_TOKEN=... e TELEGRAM_BOT_USUARIO=nome_do_seu_bot (sem @).

Cada pessoa liga o próprio aviso em Avisos: o app mostra um link t.me/seu_bot?start=CÓDIGO.
Ela toca, aperta "Começar" no Telegram, e o agente Sentinela vincula a conversa à conta.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sqlite3
import urllib.parse
import urllib.request
from contextlib import contextmanager, suppress
from datetime import datetime
from pathlib import Path

API = "https://api.telegram.org/bot{token}/{metodo}"

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS telegram_vinculos (
    email TEXT PRIMARY KEY,
    chat_id TEXT NOT NULL,
    vinculado_em TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS telegram_estado (
    chave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);
"""


def configurado() -> bool:
    return bool(os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_BOT_USUARIO"))


def codigo(email: str) -> str:
    """Código de vínculo da pessoa (não revela o e-mail; muda se o token do bot mudar)."""
    segredo = (os.environ.get("CHRONOTRADE_SEGREDO") or os.environ.get("TELEGRAM_BOT_TOKEN") or "chrono").encode()
    return "ct" + hmac.new(segredo, email.encode(), hashlib.sha256).hexdigest()[:14]


def link(email: str) -> str:
    return f"https://t.me/{os.environ.get('TELEGRAM_BOT_USUARIO', '').lstrip('@')}?start={codigo(email)}"


def _chamar(metodo: str, dados: dict, http=None) -> dict:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    pedido = urllib.request.Request(API.format(token=token, metodo=metodo),
                                    data=urllib.parse.urlencode(dados).encode(), method="POST")
    if http:
        return http(pedido)
    with urllib.request.urlopen(pedido, timeout=20) as resposta:
        return json.loads(resposta.read())


class Telegram:
    def __init__(self, caminho: Path, http=None):
        self.caminho = Path(caminho)
        self.http = http
        with self._con() as con:
            con.executescript(_ESQUEMA)

    @contextmanager
    def _con(self):
        con = sqlite3.connect(self.caminho, timeout=10)
        con.row_factory = sqlite3.Row
        try:
            yield con
            con.commit()
        finally:
            con.close()

    def chat_de(self, email: str) -> str | None:
        with self._con() as con:
            ln = con.execute("SELECT chat_id FROM telegram_vinculos WHERE email = ?", (email,)).fetchone()
        return ln["chat_id"] if ln else None

    def desvincular(self, email: str) -> None:
        with self._con() as con:
            con.execute("DELETE FROM telegram_vinculos WHERE email = ?", (email,))

    def vincular(self, email: str, chat_id: str) -> None:
        with self._con() as con:
            con.execute("INSERT INTO telegram_vinculos VALUES (?, ?, ?) ON CONFLICT(email) DO UPDATE SET "
                        "chat_id = excluded.chat_id, vinculado_em = excluded.vinculado_em",
                        (email, str(chat_id), datetime.now().isoformat(timespec="seconds")))

    def enviar(self, email: str, texto: str) -> str:
        chat = self.chat_de(email)
        if not chat:
            return "sem Telegram vinculado"
        if not configurado():
            return "Telegram não configurado"
        try:
            r = _chamar("sendMessage", {"chat_id": chat, "text": texto[:4000], "disable_web_page_preview": "true"}, self.http)
            return "enviado" if r.get("ok") else f"erro: {r.get('description', 'desconhecido')}"
        except Exception as erro:
            return f"erro: {erro}"

    def processar_atualizacoes(self, emails: list[str]) -> int:
        """Lê o /start CÓDIGO que as pessoas mandaram ao bot e vincula cada conversa à conta. Devolve quantos vinculou."""
        if not configurado():
            return 0
        with self._con() as con:
            ln = con.execute("SELECT valor FROM telegram_estado WHERE chave = 'offset'").fetchone()
        offset = int(ln["valor"]) if ln else 0
        try:
            r = _chamar("getUpdates", {"offset": offset, "timeout": 0, "allowed_updates": '["message"]'}, self.http)
        except Exception:
            return 0
        por_codigo = {codigo(e): e for e in emails}
        vinculados = 0
        for upd in r.get("result", []):
            offset = max(offset, int(upd.get("update_id", 0)) + 1)
            msg = upd.get("message") or {}
            texto = (msg.get("text") or "").strip()
            chat = (msg.get("chat") or {}).get("id")
            if texto.startswith("/start") and chat:
                partes = texto.split()
                email = por_codigo.get(partes[1]) if len(partes) > 1 else None
                if email:
                    self.vincular(email, str(chat))
                    vinculados += 1
                    resposta = "Pronto! Os avisos do Chrono Trade vão chegar aqui. Buy and hold diário, prosperidade no longo prazo."
                else:
                    resposta = "Não reconheci o código. Abra o link pela tela Avisos do Chrono Trade."
                with suppress(Exception):
                    _chamar("sendMessage", {"chat_id": chat, "text": resposta}, self.http)
        with self._con() as con:
            con.execute("INSERT INTO telegram_estado VALUES ('offset', ?) ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor",
                        (str(offset),))
        return vinculados
