"""Avisos: a caixa de entrada do app e os canais de envio (e-mail e WhatsApp).

- No app: todo aviso fica guardado e aparece como pop-up na próxima vez que a
  pessoa abrir o Chrono Trade, além da tela Avisos.
- E-mail: por SMTP (Gmail com "senha de app", Outlook, Hostinger...). Configure
  CHRONOTRADE_SMTP_HOST, _PORTA, _USUARIO, _SENHA e _REMETENTE no .env.
- WhatsApp: pela API oficial da Meta (WhatsApp Cloud API). Exige conta WhatsApp
  Business; fora da conversa aberta pelo cliente, só modelos aprovados podem ser
  enviados e a Meta cobra por mensagem. Configure WHATSAPP_TOKEN, WHATSAPP_PHONE_ID
  e, para mensagens fora da conversa, WHATSAPP_MODELO (modelo com 1 variável de texto).
"""

from __future__ import annotations

import json
import os
import smtplib
import sqlite3
import ssl
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS avisos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL,
    criado_em TEXT NOT NULL,
    tipo TEXT NOT NULL,
    titulo TEXT NOT NULL,
    texto TEXT NOT NULL,
    lido INTEGER NOT NULL DEFAULT 0,
    mostrado INTEGER NOT NULL DEFAULT 0,
    envios TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS avisos_email ON avisos (email, lido);
"""


@dataclass
class Aviso:
    id: int
    email: str
    criado_em: datetime
    tipo: str
    titulo: str
    texto: str
    lido: bool
    mostrado: bool
    envios: str


class CaixaDeAvisos:
    def __init__(self, caminho: Path):
        self.caminho = Path(caminho)
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
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

    def criar(self, email: str, tipo: str, titulo: str, texto: str, envios: str = "") -> int:
        with self._con() as con:
            cur = con.execute("INSERT INTO avisos (email, criado_em, tipo, titulo, texto, envios) VALUES (?, ?, ?, ?, ?, ?)",
                              (email, datetime.now().isoformat(timespec="seconds"), tipo, titulo, texto, envios))
            return int(cur.lastrowid)

    def anotar_envio(self, id_: int, envios: str) -> None:
        with self._con() as con:
            con.execute("UPDATE avisos SET envios = ? WHERE id = ?", (envios, id_))

    def listar(self, email: str, limite: int = 50) -> list[Aviso]:
        with self._con() as con:
            linhas = con.execute("SELECT * FROM avisos WHERE email = ? ORDER BY id DESC LIMIT ?", (email, limite)).fetchall()
        return [Aviso(ln["id"], ln["email"], datetime.fromisoformat(ln["criado_em"]), ln["tipo"], ln["titulo"],
                      ln["texto"], bool(ln["lido"]), bool(ln["mostrado"]), ln["envios"] or "") for ln in linhas]

    def nao_lidos(self, email: str) -> int:
        with self._con() as con:
            return con.execute("SELECT COUNT(*) FROM avisos WHERE email = ? AND lido = 0", (email,)).fetchone()[0]

    def para_mostrar(self, email: str) -> list[Aviso]:
        """Os avisos novos que ainda não viraram pop-up; já ficam marcados como mostrados."""
        avisos = [a for a in self.listar(email, 10) if not a.mostrado]
        if avisos:
            with self._con() as con:
                con.executemany("UPDATE avisos SET mostrado = 1 WHERE id = ?", [(a.id,) for a in avisos])
        return avisos

    def marcar_lidos(self, email: str) -> None:
        with self._con() as con:
            con.execute("UPDATE avisos SET lido = 1, mostrado = 1 WHERE email = ?", (email,))

    def ultimo(self, email: str, tipo: str) -> datetime | None:
        with self._con() as con:
            linha = con.execute("SELECT MAX(criado_em) FROM avisos WHERE email = ? AND tipo = ?", (email, tipo)).fetchone()
        return datetime.fromisoformat(linha[0]) if linha and linha[0] else None

    def ja_avisado(self, email: str, tipo: str, titulo: str) -> bool:
        with self._con() as con:
            return con.execute("SELECT 1 FROM avisos WHERE email = ? AND tipo = ? AND titulo = ?",
                               (email, tipo, titulo)).fetchone() is not None


# ---------------------------------------------------------------------------
# Canais
# ---------------------------------------------------------------------------


def email_configurado() -> bool:
    return all(os.environ.get(f"CHRONOTRADE_SMTP_{k}") for k in ("HOST", "USUARIO", "SENHA"))


def whatsapp_configurado() -> bool:
    return bool(os.environ.get("WHATSAPP_TOKEN") and os.environ.get("WHATSAPP_PHONE_ID"))


def enviar_email(destino: str, assunto: str, texto: str) -> str:
    """Envia um e-mail de texto simples. Devolve 'ok' ou o motivo da falha."""
    if not email_configurado():
        return "e-mail não configurado"
    host = os.environ["CHRONOTRADE_SMTP_HOST"]
    porta = int(os.environ.get("CHRONOTRADE_SMTP_PORTA", "587"))
    usuario = os.environ["CHRONOTRADE_SMTP_USUARIO"]
    msg = EmailMessage()
    msg["Subject"] = assunto
    msg["From"] = os.environ.get("CHRONOTRADE_SMTP_REMETENTE") or usuario
    msg["To"] = destino
    msg.set_content(texto)
    try:
        if porta == 465:
            with smtplib.SMTP_SSL(host, porta, context=ssl.create_default_context(), timeout=20) as smtp:
                smtp.login(usuario, os.environ["CHRONOTRADE_SMTP_SENHA"])
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(host, porta, timeout=20) as smtp:
                smtp.starttls(context=ssl.create_default_context())
                smtp.login(usuario, os.environ["CHRONOTRADE_SMTP_SENHA"])
                smtp.send_message(msg)
        return "ok"
    except Exception as erro:  # o aviso no app continua valendo mesmo se o e-mail falhar
        return f"falhou: {type(erro).__name__}"


def numero_whatsapp(numero: str) -> str:
    digitos = "".join(ch for ch in (numero or "") if ch.isdigit())
    if digitos and not digitos.startswith("55") and len(digitos) <= 11:
        digitos = "55" + digitos
    return digitos


def enviar_whatsapp(numero: str, texto: str, enviar=None) -> str:
    """Envia pela WhatsApp Cloud API. Com WHATSAPP_MODELO, usa o modelo aprovado (1 variável)."""
    if not whatsapp_configurado():
        return "WhatsApp não configurado"
    destino = numero_whatsapp(numero)
    if not destino:
        return "sem número"
    versao = os.environ.get("WHATSAPP_API_VERSAO", "v21.0")
    url = f"https://graph.facebook.com/{versao}/{os.environ['WHATSAPP_PHONE_ID']}/messages"
    modelo = os.environ.get("WHATSAPP_MODELO")
    if modelo:
        corpo = {"messaging_product": "whatsapp", "to": destino, "type": "template",
                 "template": {"name": modelo, "language": {"code": os.environ.get("WHATSAPP_IDIOMA", "pt_BR")},
                              "components": [{"type": "body", "parameters": [{"type": "text", "text": texto[:1000]}]}]}}
    else:
        corpo = {"messaging_product": "whatsapp", "to": destino, "type": "text", "text": {"body": texto[:4000]}}
    pedido = urllib.request.Request(url, data=json.dumps(corpo).encode(), method="POST", headers={
        "Authorization": f"Bearer {os.environ['WHATSAPP_TOKEN']}", "Content-Type": "application/json"})
    try:
        (enviar or urllib.request.urlopen)(pedido, timeout=20).read()
        return "ok"
    except Exception as erro:
        return f"falhou: {type(erro).__name__}"
