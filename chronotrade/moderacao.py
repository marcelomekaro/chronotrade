"""Filtro simples para textos públicos curtos (frases dos avatares).

Não substitui a moderação humana (denúncias e o painel do admin); só barra o óbvio:
promessa de ganho, links, telefones e palavrões comuns.
"""

from __future__ import annotations

import re
import unicodedata

_PROMESSAS = re.compile(r"\b(lucro|ganho|retorno|renda) garantid[oa]s?\b|\bsem risco\b|\bdobr\w+ (o |seu )?dinheiro\b"
                        r"|\bfique rico\b|\bgaranto\b")
_LINK = re.compile(r"(https?://|www\.|\b[\w-]+\.(com|net|org|io|me|br)\b)")
_TELEFONE = re.compile(r"\d[\d\s().-]{8,}\d")
_PALAVROES = {"porra", "caralho", "merda", "puta", "puto", "fdp", "vagabundo", "vagabunda", "otario", "otaria",
              "babaca", "idiota", "imbecil", "arrombado", "cuzao", "buceta", "viado", "macaco", "retardado"}


def _sem_acento(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()


def conferir(texto: str) -> str | None:
    """None se o texto pode ser publicado; senão, o motivo em português."""
    t = _sem_acento(texto or "")
    if _PROMESSAS.search(t):
        return "Sem promessas de ganho: elas são proibidas pelas regras do Pregão (e pela CVM)."
    if _LINK.search(t):
        return "Frases não podem ter links."
    if _TELEFONE.search(t):
        return "Frases não podem ter telefone."
    palavras = set(re.findall(r"[a-z]+", t))
    if palavras & _PALAVROES:
        return "Essa frase tem palavras que não combinam com o Pregão."
    return None
