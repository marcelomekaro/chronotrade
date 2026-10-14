"""Conexão com corretoras: uma interface comum e as implementações.

- ``simulada``: carteira simulada, com ordens a mercado e limitadas. Funciona já.
- ``mt5``: MetaTrader 5 (Windows, terminal da corretora aberto e logado).

Para ligar outra corretora no futuro, crie um módulo com uma classe que herda de
``base.Corretora`` e registre aqui em ``DISPONIVEIS``.
"""

from chronotrade.corretoras.base import (
    Corretora,
    ErroCorretora,
    Ordem,
    PosicaoCorretora,
    ResultadoOrdem,
)

DISPONIVEIS = {
    "simulada": "Carteira simulada (sem dinheiro real)",
    "mt5": "MetaTrader 5 (corretora real, só no Windows)",
}


def abrir(tipo: str, pasta, **opcoes) -> Corretora:
    if tipo == "simulada":
        from chronotrade.corretoras.simulada import CorretoraSimulada

        return CorretoraSimulada(pasta, **opcoes)
    if tipo == "mt5":
        from chronotrade.corretoras.mt5 import CorretoraMT5

        return CorretoraMT5(**opcoes)
    raise ErroCorretora(f"Corretora desconhecida: {tipo}")


__all__ = ["DISPONIVEIS", "Corretora", "ErroCorretora", "Ordem", "PosicaoCorretora", "ResultadoOrdem", "abrir"]
