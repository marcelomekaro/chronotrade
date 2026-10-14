"""Cobrança por PIX sem intermediário: o "copia e cola" e o QR Code de um PIX com valor.

Segue o padrão BR Code do Banco Central (EMV, com CRC16 no final). É um PIX
estático: o dinheiro cai direto na sua chave e qualquer app de banco lê o QR.
Não há confirmação automática; você confere o extrato e libera a conta.
"""

from __future__ import annotations

import io
import re
import unicodedata


def _campo(id_: str, valor: str) -> str:
    return f"{id_}{len(valor):02d}{valor}"


def _limpar(texto: str, limite: int) -> str:
    """Sem acentos e em maiúsculas, como os bancos esperam nos campos de nome e cidade."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9 ]", "", sem_acento).upper().strip()[:limite]


def crc16(dados: str) -> str:
    """CRC16-CCITT (polinômio 0x1021, início 0xFFFF), como pede o BR Code."""
    crc = 0xFFFF
    for byte in dados.encode():
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else (crc << 1)
            crc &= 0xFFFF
    return f"{crc:04X}"


def copia_e_cola(chave: str, nome: str, cidade: str, valor: float | None = None,
                 identificador: str = "***", descricao: str = "") -> str:
    """O texto do PIX "copia e cola"."""
    if not chave.strip():
        raise ValueError("Cadastre a chave PIX nas configurações da loja.")
    conta = _campo("00", "br.gov.bcb.pix") + _campo("01", chave.strip())
    if descricao:
        conta += _campo("02", _limpar(descricao, 40))
    txid = re.sub(r"[^A-Za-z0-9]", "", identificador)[:25] or "***"
    corpo = (
        _campo("00", "01")
        + _campo("26", conta)
        + _campo("52", "0000")
        + _campo("53", "986")
        + (_campo("54", f"{valor:.2f}") if valor else "")
        + _campo("58", "BR")
        + _campo("59", _limpar(nome, 25) or "RECEBEDOR")
        + _campo("60", _limpar(cidade, 15) or "BRASIL")
        + _campo("62", _campo("05", txid))
        + "6304"
    )
    return corpo + crc16(corpo)


def qr_png(texto: str, escala: int = 8) -> bytes:
    """O QR Code em PNG, pronto para st.image."""
    import segno

    saida = io.BytesIO()
    segno.make(texto, error="m").save(saida, kind="png", scale=escala, border=3,
                                      dark="#121838", light="#FFFFFF")
    return saida.getvalue()


def link_whatsapp(numero: str, mensagem: str) -> str:
    """Link que abre o WhatsApp com a mensagem já escrita."""
    from urllib.parse import quote

    digitos = re.sub(r"\D", "", numero or "")
    if digitos and not digitos.startswith("55") and len(digitos) <= 11:
        digitos = "55" + digitos
    return f"https://wa.me/{digitos}?text={quote(mensagem)}"
