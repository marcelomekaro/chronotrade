"""API do Chrono Trade: recebe as posições do Conector do PC (MetaTrader 5 / Profit).

Por que existe: o MetaTrader 5 e a ProfitDLL só rodam no Windows de quem investe.
Na versão online, o servidor não alcança o PC da pessoa. Então o Conector do PC
(``chronotrade-ponte``) lê as posições lá e manda para cá, com um token pessoal
gerado na tela Conexões. Senha de corretora nunca passa pelo servidor.

Rodar:  chronotrade-api            (porta 8502; o Caddy encaminha /api/* para cá)
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from chronotrade import conexoes, contas
from chronotrade.carteira import Carteira, pasta_dados
from chronotrade.corretoras.base import PosicaoCorretora

MAX_POSICOES = 300


class PosicaoEnviada(BaseModel):
    ticker: str = Field(max_length=16)
    quantidade: float
    preco_medio: float = 0.0


class Envio(BaseModel):
    plataforma: str = Field(pattern="^(mt5|profit|outra)$")
    posicoes: list[PosicaoEnviada] = Field(max_length=MAX_POSICOES)
    remover_ausentes: bool = False


def _banco() -> contas.Contas:
    return contas.Contas(pasta_dados() / "contas.db")


def pasta_do_usuario(u: contas.Usuario) -> Path:
    if not contas.modo_servidor():
        return pasta_dados()
    destino = pasta_dados() / "usuarios" / u.id_pasta
    destino.mkdir(parents=True, exist_ok=True)
    return destino


def receber_posicoes(u: contas.Usuario, plataforma: str, posicoes: list[dict], remover_ausentes: bool = False,
                     pasta: Path | None = None) -> dict:
    """Junta as posições recebidas na carteira da pessoa e registra o status da ponte."""
    pasta = pasta or pasta_do_usuario(u)
    lidas = []
    for p in posicoes[:MAX_POSICOES]:
        try:
            ticker = str(p["ticker"]).strip().upper()
            quantidade = float(p.get("quantidade", 0))
            preco = float(p.get("preco_medio", 0))
        except (KeyError, TypeError, ValueError):
            continue
        if ticker and 0 <= quantidade < 1e9 and 0 <= preco < 1e7:
            lidas.append(PosicaoCorretora(ticker, quantidade, preco))
    arquivo = pasta / "carteira.json"
    carteira = Carteira.carregar(arquivo)
    mudou = conexoes.aplicar(carteira, lidas, remover_ausentes)
    carteira.salvar(arquivo)
    status = {"plataforma": plataforma, "recebido_em": datetime.now().isoformat(timespec="seconds"),
              "posicoes": len(lidas), "mudancas": mudou}
    (pasta / "ponte_status.json").write_text(json.dumps(status, ensure_ascii=False), encoding="utf-8")
    return status


def status_ponte(pasta: Path | None) -> dict | None:
    if pasta is None:
        return None
    arquivo = pasta / "ponte_status.json"
    try:
        return json.loads(arquivo.read_text(encoding="utf-8")) if arquivo.exists() else None
    except (OSError, ValueError):
        return None


def criar_app(banco: contas.Contas | None = None):
    from fastapi import FastAPI, Header, HTTPException

    app = FastAPI(title="Chrono Trade API", version="1.0",
                  description="Conector do PC: MetaTrader 5 e Profit enviam as posições para a sua carteira.")

    def dono(authorization: str | None) -> contas.Usuario:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(401, "Envie o token do Conector do PC (Authorization: Bearer ct_...).")
        u = (banco or _banco()).dono_do_token(authorization.split(" ", 1)[1].strip())
        if u is None:
            raise HTTPException(401, "Token inválido ou revogado. Gere outro na tela Conexões.")
        if not u.pode_usar():
            raise HTTPException(403, "A assinatura não está ativa. Renove em Minha conta.")
        if not u.libera("ponte"):
            raise HTTPException(403, "O Conector do PC faz parte do plano Premium.")
        return u

    @app.get("/api/saude")
    def saude():
        return {"ok": True, "app": "Chrono Trade", "hora": datetime.now().isoformat(timespec="seconds")}

    @app.get("/api/eu")
    def eu(authorization: str | None = Header(default=None)):
        u = dono(authorization)
        return {"email": u.email, "nome": u.nome, "plano": u.plano_efetivo}

    @app.post("/api/ponte/posicoes")
    def posicoes(envio: Envio, authorization: str | None = Header(default=None)):
        u = dono(authorization)
        return receber_posicoes(u, envio.plataforma, [p.model_dump() for p in envio.posicoes], envio.remover_ausentes)

    return app


def main() -> None:
    import uvicorn

    uvicorn.run(criar_app(), host=os.environ.get("CHRONOTRADE_API_HOST", "0.0.0.0"),
                port=int(os.environ.get("CHRONOTRADE_API_PORTA", "8502")))


if __name__ == "__main__":
    main()
