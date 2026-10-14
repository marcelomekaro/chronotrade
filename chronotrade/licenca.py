"""Assinaturas do Chrono Trade: chaves de acesso com validade.

Dois modos, escolhidos no .env:

- ``CHRONOTRADE_MODO=pessoal`` (padrão): o app é seu, tudo liberado, sem chave.
- ``CHRONOTRADE_MODO=assinatura``: para hospedar e cobrar. Quem não tem chave usa o
  plano gratuito; quem paga recebe uma chave e libera o plano completo.

A chave leva o e-mail do assinante e a data de validade, assinadas com o segredo
``CHRONOTRADE_SEGREDO``. Sem o segredo ninguém consegue fabricar uma chave, e
mudar uma letra dela a invalida. O segredo fica só no servidor, nunca no GitHub.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from dataclasses import dataclass
from datetime import date, timedelta

PREFIXO = "CT-"
LIMITE_ATIVOS_GRATUITO = 5


def modo() -> str:
    return (os.environ.get("CHRONOTRADE_MODO") or "pessoal").strip().lower()


def assinatura_ativa() -> bool:
    return modo() == "assinatura"


def link_pagamento() -> str:
    return os.environ.get("CHRONOTRADE_LINK_PAGAMENTO", "").strip()


def preco_divulgado() -> str:
    return os.environ.get("CHRONOTRADE_PRECO", "").strip()


def _segredo() -> bytes:
    valor = os.environ.get("CHRONOTRADE_SEGREDO", "")
    if len(valor) < 32:
        raise RuntimeError("Defina CHRONOTRADE_SEGREDO no .env com pelo menos 32 caracteres "
                           "(gere um com: chronotrade-licenca segredo).")
    return valor.encode()


def _b64(dados: bytes) -> str:
    return base64.urlsafe_b64encode(dados).decode().rstrip("=")


def _de_b64(texto: str) -> bytes:
    return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))


@dataclass
class Licenca:
    email: str
    validade: date
    plano: str = "completo"

    @property
    def id_usuario(self) -> str:
        """Identificador estável do assinante, usado como nome da pasta dos dados dele."""
        return hashlib.sha256(self.email.strip().lower().encode()).hexdigest()[:16]

    def dias_restantes(self, hoje: date | None = None) -> int:
        return (self.validade - (hoje or date.today())).days


def gerar_chave(email: str, validade: date, segredo: bytes | None = None, plano: str = "completo") -> str:
    corpo = json.dumps({"e": email.strip().lower(), "v": validade.isoformat(), "p": plano},
                       separators=(",", ":")).encode()
    assinatura = hmac.new(segredo or _segredo(), corpo, hashlib.sha256).digest()[:16]
    return f"{PREFIXO}{_b64(corpo)}.{_b64(assinatura)}"


class ChaveInvalida(ValueError):
    pass


def verificar_chave(chave: str, segredo: bytes | None = None, hoje: date | None = None) -> Licenca:
    chave = (chave or "").strip()
    if not chave.startswith(PREFIXO) or "." not in chave:
        raise ChaveInvalida("Esta não parece uma chave do Chrono Trade. Ela começa com CT-.")
    corpo_b64, assinatura_b64 = chave[len(PREFIXO):].split(".", 1)
    try:
        corpo = _de_b64(corpo_b64)
        recebida = _de_b64(assinatura_b64)
        dados = json.loads(corpo)
    except (ValueError, json.JSONDecodeError) as erro:
        raise ChaveInvalida("A chave está incompleta. Copie de novo, inteira.") from erro
    esperada = hmac.new(segredo or _segredo(), corpo, hashlib.sha256).digest()[:16]
    if not hmac.compare_digest(esperada, recebida):
        raise ChaveInvalida("Chave inválida. Confira se copiou todos os caracteres.")
    licenca = Licenca(dados["e"], date.fromisoformat(dados["v"]), dados.get("p", "completo"))
    if licenca.dias_restantes(hoje) < 0:
        raise ChaveInvalida(f"Esta chave venceu em {licenca.validade:%d/%m/%Y}. Renove a assinatura para continuar.")
    return licenca


# ---------------------------------------------------------------------------
# Comando: chronotrade-licenca
# ---------------------------------------------------------------------------


def main() -> None:
    import argparse

    import tradingagents  # noqa: F401  (carrega o .env)

    parser = argparse.ArgumentParser(prog="chronotrade-licenca",
                                     description="Gera chaves de acesso para assinantes do Chrono Trade.")
    sub = parser.add_subparsers(dest="acao", required=True)
    sub.add_parser("segredo", help="Cria um segredo novo para colar no .env (CHRONOTRADE_SEGREDO).")
    g = sub.add_parser("gerar", help="Gera a chave de um assinante.")
    g.add_argument("--email", required=True)
    g.add_argument("--dias", type=int, default=30, help="Validade em dias (padrão: 30).")
    v = sub.add_parser("verificar", help="Confere uma chave.")
    v.add_argument("chave")
    args = parser.parse_args()

    if args.acao == "segredo":
        print(f"CHRONOTRADE_SEGREDO={secrets.token_urlsafe(48)}")
        print("Cole a linha acima no .env do servidor. Se trocar o segredo, todas as chaves antigas param de valer.")
    elif args.acao == "gerar":
        validade = date.today() + timedelta(days=args.dias)
        print(gerar_chave(args.email, validade))
        print(f"Válida até {validade:%d/%m/%Y} para {args.email}.")
    else:
        try:
            lic = verificar_chave(args.chave)
            print(f"Válida: {lic.email}, até {lic.validade:%d/%m/%Y} ({lic.dias_restantes()} dias).")
        except (ChaveInvalida, RuntimeError) as erro:
            print(f"Inválida: {erro}")


if __name__ == "__main__":
    main()
