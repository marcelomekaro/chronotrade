"""Compartilhar no WhatsApp: contatos (amigo, consultor, família) e o botão usado em todo o app.

O app não lê nem guarda conversas: ele abre o WhatsApp com a mensagem pronta e
a pessoa escolhe se envia. Os contatos ficam na pasta de dados do usuário.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

import streamlit as st

from chronotrade.avisos import numero_whatsapp

TIPOS = ["Amigo", "Consultor", "Família", "Assessor", "Outro"]
RODAPE = "\n\n(Compartilhado pelo Chrono Trade. Ideia pessoal, não é recomendação de investimento.)"


def carregar(pasta: Path | None) -> list[dict]:
    if pasta is None:
        return st.session_state.get("contatos_visitante", [])
    arquivo = pasta / "contatos.json"
    try:
        return json.loads(arquivo.read_text(encoding="utf-8")) if arquivo.exists() else []
    except (OSError, json.JSONDecodeError):
        return []


def salvar(pasta: Path | None, contatos: list[dict]) -> None:
    if pasta is None:
        st.session_state.contatos_visitante = contatos
        return
    (pasta / "contatos.json").write_text(json.dumps(contatos, ensure_ascii=False, indent=2), encoding="utf-8")


def link(texto: str, numero: str = "") -> str:
    destino = numero_whatsapp(numero)
    return f"https://wa.me/{destino}?text={quote(texto)}" if destino else f"https://wa.me/?text={quote(texto)}"


def botao(texto: str, chave: str, pasta: Path | None, rotulo: str = "Compartilhar no WhatsApp") -> None:
    """Um botão que abre a lista de contatos; cada um abre o WhatsApp com a mensagem pronta."""
    mensagem = texto.strip() + RODAPE
    with st.popover(f"💬 {rotulo}", width="content"):
        st.caption("Mensagem que vai ser enviada:")
        st.text(mensagem[:600] + ("…" if len(mensagem) > 600 else ""))
        for c in carregar(pasta):
            st.link_button(f"{c['nome']} ({c['tipo']})", link(mensagem, c["numero"]), width="stretch")
        st.link_button("Escolher no WhatsApp", link(mensagem), width="stretch")
        st.caption("Cadastre amigos e consultores em Conexões → Contatos.")
