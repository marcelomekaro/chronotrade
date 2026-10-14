"""Conexões com plataformas de negociação: perfis, teste, sincronização e o cofre de senhas.

Cada pessoa guarda um ou mais perfis (MetaTrader 5, Profit, simulada). Um perfil
tem os campos públicos (servidor, conta, caminho) e, só no modo pessoal, as senhas
num cofre criptografado no próprio computador. Na versão online, as plataformas
rodam no PC do usuário e conversam com o servidor pelo Conector do PC (ponte).
"""

from __future__ import annotations

import contextlib
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from chronotrade.carteira import Carteira, Posicao
from chronotrade.corretoras import Corretora, ErroCorretora, PosicaoCorretora, abrir
from chronotrade.mercado import normalizar_ticker, parece_fii, ticker_curto


@dataclass(frozen=True)
class Campo:
    chave: str
    rotulo: str
    ajuda: str = ""
    secreto: bool = False
    obrigatorio: bool = False


PLATAFORMAS = {
    "mt5": {
        "nome": "MetaTrader 5",
        "icone": "📈",
        "resumo": "Gratuito, oferecido por várias corretoras. O terminal precisa estar instalado e logado no Windows.",
        "passos": [
            "Peça à sua corretora o acesso ao MetaTrader 5 para ações da B3 e instale o terminal.",
            "Abra o MetaTrader 5 e entre com a sua conta (fica logado).",
            "Aqui, só toque em Testar conexão. Conta e servidor são opcionais se o terminal já estiver logado.",
        ],
        "campos": [
            Campo("login", "Número da conta", "Opcional se o terminal já está logado."),
            Campo("servidor", "Servidor da corretora", "Aparece na tela de login do MT5."),
            Campo("caminho_terminal", "Caminho do terminal64.exe", "Só se tiver mais de um MetaTrader instalado."),
            Campo("senha", "Senha da conta", "Opcional se o terminal já está logado.", secreto=True),
        ],
    },
    "profit": {
        "nome": "Profit (Nelogica)",
        "icone": "📊",
        "resumo": "Usa a ProfitDLL, uma licença à parte que a Nelogica fornece com uma chave de ativação.",
        "passos": [
            "Contrate a ProfitDLL com a Nelogica e baixe o arquivo ProfitDLL64.dll.",
            "No terminal do Chrono Trade: pip install profitdll-wrapper",
            "Preencha a chave de ativação, o usuário e a senha da Nelogica e toque em Testar conexão.",
        ],
        "campos": [
            Campo("dll", "Caminho do ProfitDLL64.dll", r"Ex.: C:\Nelogica\ProfitDLL64.dll", obrigatorio=True),
            Campo("corretora_id", "Código da corretora", "Opcional; a Nelogica informa."),
            Campo("chave_ativacao", "Chave de ativação da ProfitDLL", secreto=True, obrigatorio=True),
            Campo("usuario", "Usuário Nelogica", secreto=True, obrigatorio=True),
            Campo("senha", "Senha Nelogica", secreto=True, obrigatorio=True),
        ],
    },
    "simulada": {
        "nome": "Carteira simulada",
        "icone": "🎮",
        "resumo": "R$ 100.000 de mentira para treinar ordens com preços de mercado.",
        "passos": ["Nada a instalar: já está pronta na tela Corretora."],
        "campos": [],
    },
}


@dataclass
class Perfil:
    tipo: str
    apelido: str
    campos: dict = field(default_factory=dict)
    auto_sincronizar: bool = False
    ultima_sincronizacao: str | None = None
    ultimo_teste: str | None = None
    situacao: str = "Não testada"

    @property
    def id(self) -> str:
        return f"{self.tipo}:{self.apelido}"


# ---------------------------------------------------------------------------
# Perfis
# ---------------------------------------------------------------------------


def carregar(pasta: Path) -> list[Perfil]:
    arquivo = pasta / "conexoes.json"
    if not arquivo.exists():
        return []
    try:
        return [Perfil(**p) for p in json.loads(arquivo.read_text(encoding="utf-8"))]
    except (OSError, ValueError, TypeError):
        return []


def salvar(pasta: Path, perfis: list[Perfil]) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "conexoes.json").write_text(json.dumps([asdict(p) for p in perfis], ensure_ascii=False, indent=2),
                                         encoding="utf-8")


def guardar(pasta: Path, perfil: Perfil) -> None:
    perfis = [p for p in carregar(pasta) if p.id != perfil.id] + [perfil]
    salvar(pasta, perfis)


def remover(pasta: Path, id_: str, cofre: Cofre | None = None) -> None:
    salvar(pasta, [p for p in carregar(pasta) if p.id != id_])
    if cofre:
        cofre.apagar(id_)


# ---------------------------------------------------------------------------
# Cofre: senhas criptografadas no computador da pessoa (modo pessoal)
# ---------------------------------------------------------------------------


class Cofre:
    def __init__(self, pasta: Path):
        from cryptography.fernet import Fernet

        self.arquivo = pasta / "cofre.bin"
        chave_arquivo = pasta / ".chave_cofre"
        if not chave_arquivo.exists():
            pasta.mkdir(parents=True, exist_ok=True)
            chave_arquivo.write_bytes(Fernet.generate_key())
            with contextlib.suppress(OSError):
                os.chmod(chave_arquivo, 0o600)
        self._f = Fernet(chave_arquivo.read_bytes())

    def _tudo(self) -> dict:
        if not self.arquivo.exists():
            return {}
        try:
            return json.loads(self._f.decrypt(self.arquivo.read_bytes()))
        except Exception:
            return {}

    def ler(self, id_: str) -> dict:
        return self._tudo().get(id_, {})

    def gravar(self, id_: str, segredos: dict) -> None:
        tudo = self._tudo()
        tudo[id_] = {k: v for k, v in segredos.items() if v}
        self.arquivo.write_bytes(self._f.encrypt(json.dumps(tudo).encode()))

    def apagar(self, id_: str) -> None:
        tudo = self._tudo()
        tudo.pop(id_, None)
        self.arquivo.write_bytes(self._f.encrypt(json.dumps(tudo).encode()))


# ---------------------------------------------------------------------------
# Usar a conexão
# ---------------------------------------------------------------------------


def opcoes(perfil: Perfil, segredos: dict, tickers: list[str] | None = None) -> dict:
    valores = {**perfil.campos, **{k: v for k, v in segredos.items() if v}}
    if perfil.tipo == "mt5":
        return {"caminho_terminal": valores.get("caminho_terminal") or None,
                "login": int(valores["login"]) if str(valores.get("login", "")).strip().isdigit() else None,
                "senha": valores.get("senha") or None, "servidor": valores.get("servidor") or None}
    if perfil.tipo == "profit":
        return {"chave_ativacao": valores.get("chave_ativacao"), "usuario": valores.get("usuario"),
                "senha": valores.get("senha"), "dll": valores.get("dll") or None,
                "corretora_id": int(valores["corretora_id"]) if str(valores.get("corretora_id", "")).isdigit() else None,
                "tickers": tickers or []}
    return {}


def conectar(perfil: Perfil, segredos: dict, pasta: Path | None = None, tickers: list[str] | None = None,
             fabrica=abrir) -> Corretora:
    if perfil.tipo == "simulada":
        return fabrica("simulada", pasta)
    return fabrica(perfil.tipo, None, **opcoes(perfil, segredos, tickers))


@dataclass
class Teste:
    ok: bool
    mensagem: str
    saldo: float | None = None
    posicoes: list[PosicaoCorretora] = field(default_factory=list)


def testar(perfil: Perfil, segredos: dict, pasta: Path | None = None, tickers: list[str] | None = None,
           fabrica=abrir) -> Teste:
    try:
        corretora = conectar(perfil, segredos, pasta, tickers, fabrica)
        posicoes = corretora.posicoes()
        saldo = corretora.saldo()
    except ErroCorretora as erro:
        return Teste(False, str(erro))
    except Exception as erro:  # qualquer falha da plataforma vira mensagem legível
        return Teste(False, f"A plataforma respondeu com erro: {type(erro).__name__}: {erro}")
    return Teste(True, f"Conectado: {len(posicoes)} posições encontradas.", saldo, posicoes)


@dataclass
class Mudanca:
    ticker: str
    tipo: str            # "novo", "alterado", "igual" ou "fora da corretora"
    antes: float
    depois: float
    preco_medio: float


def comparar(carteira: Carteira, posicoes: list[PosicaoCorretora]) -> list[Mudanca]:
    """O que muda no Inventário se trouxermos as posições da corretora."""
    atuais = {p.ticker: p for p in carteira.posicoes}
    vindas = {normalizar_ticker(p.ticker): p for p in posicoes if p.quantidade}
    mudancas = []
    for t, p in vindas.items():
        if t not in atuais:
            mudancas.append(Mudanca(t, "novo", 0.0, p.quantidade, p.preco_medio))
        elif abs(atuais[t].quantidade - p.quantidade) > 1e-9 or abs(atuais[t].preco_medio - p.preco_medio) > 0.005:
            mudancas.append(Mudanca(t, "alterado", atuais[t].quantidade, p.quantidade, p.preco_medio))
        else:
            mudancas.append(Mudanca(t, "igual", p.quantidade, p.quantidade, p.preco_medio))
    for t, p in atuais.items():
        if t not in vindas:
            mudancas.append(Mudanca(t, "fora da corretora", p.quantidade, p.quantidade, p.preco_medio))
    return mudancas


def aplicar(carteira: Carteira, posicoes: list[PosicaoCorretora], remover_ausentes: bool = False) -> int:
    """Traz as posições da corretora para o Inventário. Devolve quantos ativos mudaram."""
    mudancas = comparar(carteira, posicoes)
    atuais = {p.ticker: p for p in carteira.posicoes}
    for m in mudancas:
        if m.tipo in ("novo", "alterado"):
            classe = atuais[m.ticker].classe if m.ticker in atuais else ("FII" if parece_fii(m.ticker) else "Ação")
            atuais[m.ticker] = Posicao(m.ticker, m.depois, m.preco_medio, classe)
        elif m.tipo == "fora da corretora" and remover_ausentes:
            atuais.pop(m.ticker, None)
    carteira.posicoes = list(atuais.values())
    return sum(1 for m in mudancas if m.tipo in ("novo", "alterado") or
               (remover_ausentes and m.tipo == "fora da corretora"))


def marcar(pasta: Path, perfil: Perfil, teste: Teste | None = None, sincronizou: bool = False) -> None:
    agora = datetime.now().isoformat(timespec="seconds")
    if teste is not None:
        perfil.ultimo_teste = agora
        perfil.situacao = "Conectada" if teste.ok else "Com erro"
    if sincronizou:
        perfil.ultima_sincronizacao = agora
    guardar(pasta, perfil)


def descrever(perfil: Perfil) -> str:
    info = PLATAFORMAS[perfil.tipo]
    partes = [info["nome"]]
    if perfil.campos.get("servidor"):
        partes.append(perfil.campos["servidor"])
    if perfil.campos.get("login"):
        partes.append(f"conta {perfil.campos['login']}")
    return ", ".join(partes)


__all__ = ["PLATAFORMAS", "Campo", "Cofre", "Mudanca", "Perfil", "Teste", "aplicar", "carregar", "comparar",
           "conectar", "descrever", "guardar", "marcar", "remover", "salvar", "testar", "ticker_curto"]
