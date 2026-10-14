"""Pregão: a sala virtual onde os investidores cadastrados se encontram e conversam.

Guarda presença (quem está online em cada sala), mensagens e moderação no mesmo
banco SQLite das contas. Regras simples para a conversa ficar boa:
- no máximo uma mensagem a cada 3 segundos por pessoa e 500 caracteres;
- o administrador pode apagar mensagens e silenciar participantes;
- qualquer um pode denunciar uma mensagem.
"""

from __future__ import annotations

import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

SALAS = {
    "geral": ("Pregão geral", "Conversa aberta sobre o mercado"),
    "dividendos": ("Mesa dos dividendos", "Proventos, datas com e renda passiva"),
    "fiis": ("Mesa dos FIIs", "Fundos imobiliários"),
    "iniciantes": ("Primeiros aportes", "Dúvidas de quem está começando"),
}
ONLINE_POR = timedelta(minutes=2)
INTERVALO_MINIMO = timedelta(seconds=3)
TAMANHO_MAXIMO = 500
_TICKER = re.compile(r"\$?\b([A-Z]{4}\d{1,2})\b")

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS presenca (
    email TEXT NOT NULL,
    sala TEXT NOT NULL,
    apelido TEXT NOT NULL,
    avatar TEXT,
    visto_em TEXT NOT NULL,
    PRIMARY KEY (email, sala)
);
CREATE TABLE IF NOT EXISTS mensagens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sala TEXT NOT NULL,
    email TEXT NOT NULL,
    apelido TEXT NOT NULL,
    avatar TEXT,
    texto TEXT NOT NULL,
    tickers TEXT DEFAULT '',
    criado_em TEXT NOT NULL,
    removida INTEGER NOT NULL DEFAULT 0,
    denuncias INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS mensagens_sala ON mensagens (sala, id);
CREATE TABLE IF NOT EXISTS perfis_pregao (
    email TEXT PRIMARY KEY,
    apelido TEXT NOT NULL,
    avatar TEXT
);
CREATE TABLE IF NOT EXISTS silenciados (
    email TEXT PRIMARY KEY,
    ate TEXT NOT NULL
);
"""


class ErroPregao(ValueError):
    pass


@dataclass
class Participante:
    email: str
    apelido: str
    avatar: str | None
    visto_em: datetime


@dataclass
class Mensagem:
    id: int
    sala: str
    email: str
    apelido: str
    avatar: str | None
    texto: str
    tickers: list[str]
    criado_em: datetime
    denuncias: int


def tickers_no_texto(texto: str) -> list[str]:
    vistos: list[str] = []
    for t in _TICKER.findall(texto.upper()):
        if t not in vistos:
            vistos.append(t)
    return vistos[:5]


class Pregao:
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

    # -- perfil (apelido e avatar) -------------------------------------------------

    def perfil(self, email: str, nome_padrao: str = "") -> tuple[str, str]:
        from chronotrade.avatar import sortear

        with self._con() as con:
            ln = con.execute("SELECT apelido, avatar FROM perfis_pregao WHERE email = ?", (email,)).fetchone()
        if ln:
            return ln["apelido"], ln["avatar"] or sortear(email).json()
        apelido = (nome_padrao or email.split("@")[0]).split()[0][:18] or "Investidor"
        return apelido, sortear(email).json()

    def salvar_perfil(self, email: str, apelido: str, avatar_json: str) -> None:
        apelido = re.sub(r"\s+", " ", apelido or "").strip()[:18]
        if len(apelido) < 2:
            raise ErroPregao("O apelido precisa de pelo menos 2 letras.")
        with self._con() as con:
            con.execute("INSERT INTO perfis_pregao VALUES (?, ?, ?) ON CONFLICT(email) DO UPDATE SET "
                        "apelido = excluded.apelido, avatar = excluded.avatar", (email, apelido, avatar_json))

    # -- presença --------------------------------------------------------------

    def marcar_presenca(self, email: str, sala: str, apelido: str, avatar: str | None, agora: datetime | None = None) -> None:
        agora = agora or datetime.now()
        with self._con() as con:
            con.execute("INSERT INTO presenca VALUES (?, ?, ?, ?, ?) ON CONFLICT(email, sala) DO UPDATE SET "
                        "apelido = excluded.apelido, avatar = excluded.avatar, visto_em = excluded.visto_em",
                        (email, sala, apelido, avatar, agora.isoformat(timespec="seconds")))

    def sair(self, email: str) -> None:
        with self._con() as con:
            con.execute("DELETE FROM presenca WHERE email = ?", (email,))

    def online(self, sala: str | None = None, agora: datetime | None = None) -> list[Participante]:
        limite = ((agora or datetime.now()) - ONLINE_POR).isoformat(timespec="seconds")
        with self._con() as con:
            if sala:
                linhas = con.execute("SELECT * FROM presenca WHERE sala = ? AND visto_em >= ? ORDER BY visto_em DESC",
                                     (sala, limite)).fetchall()
            else:
                linhas = con.execute("SELECT * FROM presenca WHERE visto_em >= ? ORDER BY visto_em DESC",
                                     (limite,)).fetchall()
        vistos, resultado = set(), []
        for ln in linhas:
            if ln["email"] not in vistos:
                vistos.add(ln["email"])
                resultado.append(Participante(ln["email"], ln["apelido"], ln["avatar"], datetime.fromisoformat(ln["visto_em"])))
        return resultado

    def contagem_por_sala(self, agora: datetime | None = None) -> dict[str, int]:
        return {sala: len(self.online(sala, agora)) for sala in SALAS}

    # -- mensagens ----------------------------------------------------------------

    def silenciado_ate(self, email: str, agora: datetime | None = None) -> datetime | None:
        with self._con() as con:
            ln = con.execute("SELECT ate FROM silenciados WHERE email = ?", (email,)).fetchone()
        if ln and datetime.fromisoformat(ln["ate"]) > (agora or datetime.now()):
            return datetime.fromisoformat(ln["ate"])
        return None

    def enviar(self, sala: str, email: str, apelido: str, avatar: str | None, texto: str,
               agora: datetime | None = None) -> Mensagem:
        agora = agora or datetime.now()
        texto = re.sub(r"\s+", " ", (texto or "")).strip()
        if sala not in SALAS:
            raise ErroPregao("Sala desconhecida.")
        if not texto:
            raise ErroPregao("Escreva uma mensagem.")
        if len(texto) > TAMANHO_MAXIMO:
            raise ErroPregao(f"Mensagens têm até {TAMANHO_MAXIMO} caracteres.")
        ate = self.silenciado_ate(email, agora)
        if ate:
            raise ErroPregao(f"Você está silenciado até {ate:%d/%m %H:%M}.")
        with self._con() as con:
            ultimo = con.execute("SELECT MAX(criado_em) FROM mensagens WHERE email = ?", (email,)).fetchone()[0]
            if ultimo and agora - datetime.fromisoformat(ultimo) < INTERVALO_MINIMO:
                raise ErroPregao("Calma: espere uns segundos entre uma mensagem e outra.")
            tickers = tickers_no_texto(texto)
            cur = con.execute("INSERT INTO mensagens (sala, email, apelido, avatar, texto, tickers, criado_em) "
                              "VALUES (?, ?, ?, ?, ?, ?, ?)",
                              (sala, email, apelido, avatar, texto, ",".join(tickers), agora.isoformat(timespec="seconds")))
            id_ = int(cur.lastrowid)
        self.marcar_presenca(email, sala, apelido, avatar, agora)
        return Mensagem(id_, sala, email, apelido, avatar, texto, tickers, agora, 0)

    def listar(self, sala: str, limite: int = 60, depois_de: int = 0) -> list[Mensagem]:
        with self._con() as con:
            linhas = con.execute("SELECT * FROM mensagens WHERE sala = ? AND removida = 0 AND id > ? "
                                 "ORDER BY id DESC LIMIT ?", (sala, depois_de, limite)).fetchall()
        return [Mensagem(ln["id"], ln["sala"], ln["email"], ln["apelido"], ln["avatar"], ln["texto"],
                         [t for t in (ln["tickers"] or "").split(",") if t], datetime.fromisoformat(ln["criado_em"]),
                         ln["denuncias"]) for ln in reversed(linhas)]

    def ultima_fala(self, sala: str, desde: timedelta = timedelta(seconds=90), agora: datetime | None = None) -> dict[str, str]:
        """O que cada pessoa disse por último, nos últimos segundos (vira balão de fala na sala)."""
        limite = ((agora or datetime.now()) - desde).isoformat(timespec="seconds")
        with self._con() as con:
            linhas = con.execute("SELECT email, texto FROM mensagens WHERE sala = ? AND removida = 0 AND criado_em >= ? "
                                 "ORDER BY id", (sala, limite)).fetchall()
        return {ln["email"]: ln["texto"] for ln in linhas}

    # -- moderação ------------------------------------------------------------------------

    def denunciar(self, id_: int) -> None:
        with self._con() as con:
            con.execute("UPDATE mensagens SET denuncias = denuncias + 1 WHERE id = ?", (id_,))

    def remover(self, id_: int) -> None:
        with self._con() as con:
            con.execute("UPDATE mensagens SET removida = 1 WHERE id = ?", (id_,))

    def silenciar(self, email: str, horas: int = 24, agora: datetime | None = None) -> None:
        ate = ((agora or datetime.now()) + timedelta(hours=horas)).isoformat(timespec="seconds")
        with self._con() as con:
            con.execute("INSERT INTO silenciados VALUES (?, ?) ON CONFLICT(email) DO UPDATE SET ate = excluded.ate",
                        (email, ate))

    def denunciadas(self) -> list[Mensagem]:
        with self._con() as con:
            linhas = con.execute("SELECT * FROM mensagens WHERE removida = 0 AND denuncias > 0 ORDER BY denuncias DESC").fetchall()
        return [Mensagem(ln["id"], ln["sala"], ln["email"], ln["apelido"], ln["avatar"], ln["texto"], [],
                         datetime.fromisoformat(ln["criado_em"]), ln["denuncias"]) for ln in linhas]


# ---------------------------------------------------------------------------
# Demonstração: participantes fictícios para conhecer a sala sem ninguém online
# ---------------------------------------------------------------------------

_DEMO = [
    ("demo-ana", "Ana", "Alguém olhando TAEE11? A data com deve sair semana que vem."),
    ("demo-rafa", "Rafa", "Reforcei MXRF11 hoje, abaixo do meu preço de entrada."),
    ("demo-bia", "Bia", "Primeiro aporte do mês feito! Meta de R$ 500/mês em proventos."),
    ("demo-caio", "Caio", "BBAS3 ainda acima do preço justo pelos meus parâmetros, vou esperar."),
    ("demo-lu", "Lu", "Alguém usa o Sentinela no WhatsApp? Chegou a dica certinho às 9h."),
]


def demo(agora: datetime | None = None) -> tuple[list[Participante], list[Mensagem]]:
    from chronotrade.avatar import sortear

    agora = agora or datetime.now()
    pessoas = [Participante(e, n, sortear(e).json(), agora) for e, n, _ in _DEMO]
    msgs = [Mensagem(-(i + 1), "geral", e, n, sortear(e).json(), t, tickers_no_texto(t),
                     agora - timedelta(seconds=20 * (len(_DEMO) - i)), 0) for i, (e, n, t) in enumerate(_DEMO)]
    return pessoas, msgs
