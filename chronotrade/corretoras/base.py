"""O contrato que toda corretora do Chrono Trade cumpre."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


class ErroCorretora(RuntimeError):
    """Erro com mensagem pronta para a tela."""


@dataclass
class PosicaoCorretora:
    ticker: str
    quantidade: float
    preco_medio: float


@dataclass
class Ordem:
    ticker: str
    lado: str                 # "compra" ou "venda"
    quantidade: int
    tipo: str = "mercado"     # "mercado" ou "limitada"
    preco_limite: float | None = None
    criada_em: datetime = field(default_factory=datetime.now)

    def validar(self) -> None:
        if self.lado not in ("compra", "venda"):
            raise ErroCorretora("A ordem precisa ser de compra ou de venda.")
        if self.quantidade <= 0:
            raise ErroCorretora("A quantidade precisa ser maior que zero.")
        if self.tipo == "limitada" and not (self.preco_limite and self.preco_limite > 0):
            raise ErroCorretora("Informe o preço limite da ordem.")


@dataclass
class ResultadoOrdem:
    id: str
    situacao: str             # "executada", "pendente", "recusada" ou "cancelada"
    preco: float | None
    mensagem: str
    ordem: Ordem


class Corretora(ABC):
    """Uma conta numa corretora: ver posições e saldo, mandar e acompanhar ordens."""

    nome: str = "corretora"
    dinheiro_real: bool = False

    @abstractmethod
    def posicoes(self) -> list[PosicaoCorretora]: ...

    @abstractmethod
    def saldo(self) -> float: ...

    @abstractmethod
    def enviar(self, ordem: Ordem) -> ResultadoOrdem: ...

    @abstractmethod
    def ordens(self) -> list[ResultadoOrdem]: ...

    def cancelar(self, id_ordem: str) -> None:
        raise ErroCorretora("Esta corretora não permite cancelar pelo app.")
