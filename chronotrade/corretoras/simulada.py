"""Carteira simulada: treine compras e vendas com preços reais, sem dinheiro real.

Ordens a mercado executam no último preço. Ordens limitadas ficam pendentes e o
agente Sentinela as executa quando o preço alcança o limite. Tudo fica num
arquivo JSON na pasta do usuário.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from chronotrade.corretoras.base import (
    Corretora,
    ErroCorretora,
    Ordem,
    PosicaoCorretora,
    ResultadoOrdem,
)
from chronotrade.mercado import normalizar_ticker

SALDO_INICIAL = 100_000.0


class CorretoraSimulada(Corretora):
    nome = "Carteira simulada"
    dinheiro_real = False

    def __init__(self, pasta: Path, preco: Callable[[str], float | None] | None = None, saldo_inicial: float = SALDO_INICIAL):
        self.arquivo = Path(pasta) / "corretora_simulada.json"
        self._preco = preco
        if not self.arquivo.exists():
            self._gravar({"saldo": saldo_inicial, "posicoes": {}, "ordens": []})

    # -- armazenamento -------------------------------------------------------

    def _ler(self) -> dict:
        return json.loads(self.arquivo.read_text(encoding="utf-8"))

    def _gravar(self, dados: dict) -> None:
        self.arquivo.parent.mkdir(parents=True, exist_ok=True)
        self.arquivo.write_text(json.dumps(dados, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    def preco(self, ticker: str) -> float | None:
        if self._preco is None:
            from chronotrade.mercado import carregar_ativo

            return carregar_ativo(ticker).preco
        return self._preco(ticker)

    # -- consulta -------------------------------------------------------------------

    def posicoes(self) -> list[PosicaoCorretora]:
        return [PosicaoCorretora(t, p["quantidade"], p["preco_medio"]) for t, p in self._ler()["posicoes"].items()
                if p["quantidade"] > 0]

    def saldo(self) -> float:
        return float(self._ler()["saldo"])

    def ordens(self) -> list[ResultadoOrdem]:
        return [self._resultado(o) for o in reversed(self._ler()["ordens"])]

    @staticmethod
    def _resultado(o: dict) -> ResultadoOrdem:
        ordem = Ordem(o["ticker"], o["lado"], int(o["quantidade"]), o["tipo"], o.get("preco_limite"),
                      datetime.fromisoformat(o["criada_em"]))
        return ResultadoOrdem(o["id"], o["situacao"], o.get("preco"), o.get("mensagem", ""), ordem)

    # -- ordens ----------------------------------------------------------------------

    def enviar(self, ordem: Ordem) -> ResultadoOrdem:
        ordem.ticker = normalizar_ticker(ordem.ticker)
        ordem.validar()
        dados = self._ler()
        registro = {**asdict(ordem), "criada_em": ordem.criada_em.isoformat(timespec="seconds"),
                    "id": uuid.uuid4().hex[:10], "situacao": "pendente", "preco": None, "mensagem": ""}
        preco = self.preco(ordem.ticker)
        if preco is None:
            registro.update(situacao="recusada", mensagem="Sem cotação para este ativo agora.")
        elif ordem.tipo == "mercado" or self._alcancou(ordem, preco):
            self._executar(dados, registro, preco)
        else:
            registro["mensagem"] = "Aguardando o preço chegar ao limite."
        dados["ordens"].append(registro)
        self._gravar(dados)
        return self._resultado(registro)

    @staticmethod
    def _alcancou(ordem: Ordem, preco: float) -> bool:
        if ordem.tipo != "limitada":
            return True
        return preco <= ordem.preco_limite if ordem.lado == "compra" else preco >= ordem.preco_limite

    def _executar(self, dados: dict, registro: dict, preco: float) -> None:
        qtd, ticker = int(registro["quantidade"]), registro["ticker"]
        pos = dados["posicoes"].setdefault(ticker, {"quantidade": 0, "preco_medio": 0.0})
        if registro["lado"] == "compra":
            custo = qtd * preco
            if custo > dados["saldo"] + 1e-6:
                registro.update(situacao="recusada", mensagem="Saldo insuficiente na carteira simulada.")
                return
            total = pos["quantidade"] + qtd
            pos["preco_medio"] = (pos["quantidade"] * pos["preco_medio"] + custo) / total
            pos["quantidade"] = total
            dados["saldo"] -= custo
        else:
            if qtd > pos["quantidade"]:
                registro.update(situacao="recusada", mensagem="Quantidade maior do que a posição.")
                return
            pos["quantidade"] -= qtd
            dados["saldo"] += qtd * preco
        registro.update(situacao="executada", preco=round(preco, 2),
                        mensagem=f"Executada em {datetime.now():%d/%m %H:%M}")

    def processar_pendentes(self) -> list[ResultadoOrdem]:
        """Executa as ordens limitadas cujo preço foi alcançado. Usado pelo agente."""
        dados = self._ler()
        executadas = []
        for registro in dados["ordens"]:
            if registro["situacao"] != "pendente":
                continue
            preco = self.preco(registro["ticker"])
            ordem = self._resultado(registro).ordem
            if preco is not None and self._alcancou(ordem, preco):
                self._executar(dados, registro, preco)
                executadas.append(self._resultado(registro))
        if executadas:
            self._gravar(dados)
        return executadas

    def cancelar(self, id_ordem: str) -> None:
        dados = self._ler()
        for registro in dados["ordens"]:
            if registro["id"] == id_ordem and registro["situacao"] == "pendente":
                registro.update(situacao="cancelada", mensagem="Cancelada por você.")
                self._gravar(dados)
                return
        raise ErroCorretora("Só ordens pendentes podem ser canceladas.")

    def zerar(self, saldo_inicial: float = SALDO_INICIAL) -> None:
        self._gravar({"saldo": saldo_inicial, "posicoes": {}, "ordens": []})
