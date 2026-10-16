"""Pregão: a sala virtual onde os investidores cadastrados se encontram, andam, conversam e mostram gráficos.

Guarda no mesmo banco SQLite das contas:
- perfis (apelido único, avatar em pixel art, foto e bio);
- presença e posição de cada pessoa no salão (x, y em % da tela);
- mensagens da sala, com respostas, reações, menções (@apelido) e gráficos compartilhados;
- mensagens privadas entre duas pessoas;
- moderação (denúncia, remoção, silêncio).

Regras para a conversa ficar boa: uma mensagem a cada 3 segundos por pessoa, até 500 caracteres.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
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
REACOES = ["👍", "🔥", "💡", "🤔"]
PERIODOS = {"1m": ("1 mês", 21), "6m": ("6 meses", 126), "1a": ("1 ano", 252), "5a": ("5 anos", 1260)}
BOT_EMAIL, BOT_APELIDO = "bot:mestre", "Mestre do Pregão"
_TICKER = re.compile(r"\$?\b([A-Z]{4}\d{1,2})\b")
_MENCAO = re.compile(r"@([\wÀ-ÿ.\-]{2,18})")
_APELIDO = re.compile(r"^[\wÀ-ÿ .\-]{2,18}$")

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
CREATE TABLE IF NOT EXISTS reacoes (
    msg_id INTEGER NOT NULL,
    email TEXT NOT NULL,
    emoji TEXT NOT NULL,
    PRIMARY KEY (msg_id, email, emoji)
);
CREATE TABLE IF NOT EXISTS privadas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    de TEXT NOT NULL,
    para TEXT NOT NULL,
    texto TEXT NOT NULL,
    criado_em TEXT NOT NULL,
    lida INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS privadas_para ON privadas (para, lida);
CREATE TABLE IF NOT EXISTS quadros (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sala TEXT NOT NULL,
    email TEXT NOT NULL,
    apelido TEXT NOT NULL,
    ticker TEXT NOT NULL,
    periodo TEXT NOT NULL,
    nota TEXT DEFAULT '',
    criado_em TEXT NOT NULL
);
"""

# Colunas novas em bancos antigos: (tabela, coluna, definição)
_MIGRACOES = [
    ("perfis_pregao", "foto", "TEXT"),
    ("perfis_pregao", "bio", "TEXT DEFAULT ''"),
    ("perfis_pregao", "tema", "TEXT"),
    ("presenca", "x", "REAL"),
    ("presenca", "y", "REAL"),
    ("mensagens", "resposta_a", "INTEGER"),
    ("mensagens", "tipo", "TEXT DEFAULT 'texto'"),
    ("mensagens", "dados", "TEXT"),
]


class ErroPregao(ValueError):
    pass


@dataclass
class Perfil:
    email: str
    apelido: str
    avatar: str
    foto: str | None = None
    bio: str = ""


@dataclass
class Participante:
    email: str
    apelido: str
    avatar: str | None
    visto_em: datetime
    x: float = 50.0
    y: float = 60.0
    foto: str | None = None


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
    resposta_a: int | None = None
    tipo: str = "texto"
    dados: dict = field(default_factory=dict)


@dataclass
class Privada:
    id: int
    de: str
    para: str
    texto: str
    criado_em: datetime
    lida: bool


@dataclass
class Quadro:
    id: int
    sala: str
    email: str
    apelido: str
    ticker: str
    periodo: str
    nota: str
    criado_em: datetime


def tickers_no_texto(texto: str) -> list[str]:
    vistos: list[str] = []
    for t in _TICKER.findall(texto.upper()):
        if t not in vistos:
            vistos.append(t)
    return vistos[:5]


def mencoes(texto: str) -> list[str]:
    return list(dict.fromkeys(m.rstrip(".-") for m in _MENCAO.findall(texto or "")))[:5]


def id_publico(email: str) -> str:
    """Identificador que pode ir para o navegador dos outros (não revela o e-mail)."""
    return hashlib.sha1(email.encode()).hexdigest()[:12]


def lugar_inicial(email: str) -> tuple[float, float]:
    r = random.Random(email)
    return round(r.uniform(10, 90), 1), round(r.uniform(42, 88), 1)


def _limitar(v: float, minimo: float, maximo: float) -> float:
    return round(max(minimo, min(maximo, float(v))), 1)


class Pregao:
    def __init__(self, caminho: Path):
        self.caminho = Path(caminho)
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        with self._con() as con:
            con.executescript(_ESQUEMA)
            for tabela, coluna, tipo in _MIGRACOES:
                colunas = {ln["name"] for ln in con.execute(f"PRAGMA table_info({tabela})")}
                if coluna not in colunas:
                    con.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}")

    @contextmanager
    def _con(self):
        con = sqlite3.connect(self.caminho, timeout=10)
        con.row_factory = sqlite3.Row
        try:
            yield con
            con.commit()
        finally:
            con.close()

    # -- perfil (apelido, avatar, foto, bio) -----------------------------------------------

    def perfil_completo(self, email: str, nome_padrao: str = "") -> Perfil:
        from chronotrade.avatar import sortear

        with self._con() as con:
            ln = con.execute("SELECT * FROM perfis_pregao WHERE email = ?", (email,)).fetchone()
        if ln:
            return Perfil(email, ln["apelido"], ln["avatar"] or sortear(email).json(), ln["foto"], ln["bio"] or "")
        apelido = (nome_padrao or email.split("@")[0]).split()[0][:18] if (nome_padrao or "@" in email) else "Investidor"
        return Perfil(email, apelido or "Investidor", sortear(email).json())

    def perfil(self, email: str, nome_padrao: str = "") -> tuple[str, str]:
        p = self.perfil_completo(email, nome_padrao)
        return p.apelido, p.avatar

    def tem_perfil(self, email: str) -> bool:
        with self._con() as con:
            return con.execute("SELECT 1 FROM perfis_pregao WHERE email = ?", (email,)).fetchone() is not None

    def email_por_apelido(self, apelido: str) -> str | None:
        with self._con() as con:
            ln = con.execute("SELECT email FROM perfis_pregao WHERE lower(apelido) = lower(?)", (apelido.strip(),)).fetchone()
        return ln["email"] if ln else None

    def salvar_perfil(self, email: str, apelido: str, avatar_json: str, foto: str | None | bool = False,
                      bio: str | None = None) -> None:
        """Salva o perfil. ``foto=False`` mantém a foto atual; ``None`` remove; texto (data URI) troca."""
        apelido = re.sub(r"\s+", " ", apelido or "").strip()[:18]
        if len(apelido) < 2:
            raise ErroPregao("O apelido precisa de pelo menos 2 letras.")
        if not _APELIDO.match(apelido):
            raise ErroPregao("Use só letras, números, espaço, ponto ou hífen no apelido.")
        if apelido.lower() in (BOT_APELIDO.lower(), "admin", "administrador", "suporte", "chrono trade"):
            raise ErroPregao("Esse apelido é reservado. Escolha outro.")
        dono = self.email_por_apelido(apelido)
        if dono and dono != email:
            raise ErroPregao("Esse apelido já é de outra pessoa. Que tal colocar um número ou sobrenome?")
        atual = self.perfil_completo(email)
        nova_foto = atual.foto if foto is False else foto
        nova_bio = (atual.bio if bio is None else re.sub(r"\s+", " ", bio).strip())[:140]
        with self._con() as con:
            con.execute("INSERT INTO perfis_pregao (email, apelido, avatar, foto, bio) VALUES (?, ?, ?, ?, ?) "
                        "ON CONFLICT(email) DO UPDATE SET apelido = excluded.apelido, avatar = excluded.avatar, "
                        "foto = excluded.foto, bio = excluded.bio", (email, apelido, avatar_json, nova_foto, nova_bio))
            con.execute("UPDATE presenca SET apelido = ?, avatar = ? WHERE email = ?", (apelido, avatar_json, email))

    def mencionados(self, texto: str) -> list[str]:
        """E-mails de quem foi citado com @apelido (apelidos podem ter espaço: @Bia Dividendos)."""
        with self._con() as con:
            linhas = con.execute("SELECT email, apelido FROM perfis_pregao WHERE instr(lower(?), '@' || lower(apelido)) > 0 "
                                 "ORDER BY length(apelido) DESC", (texto or "",)).fetchall()
        return list(dict.fromkeys(ln["email"] for ln in linhas))[:5]

    def tema_de(self, email: str) -> str | None:
        with self._con() as con:
            ln = con.execute("SELECT tema FROM perfis_pregao WHERE email = ?", (email,)).fetchone()
        return ln["tema"] if ln else None

    def salvar_tema(self, email: str, tema: str, nome_padrao: str = "") -> None:
        if not self.tem_perfil(email):
            p = self.perfil_completo(email, nome_padrao)
            with self._con() as con:
                con.execute("INSERT OR IGNORE INTO perfis_pregao (email, apelido, avatar) VALUES (?, ?, ?)",
                            (email, self._apelido_livre(p.apelido, email), p.avatar))
        with self._con() as con:
            con.execute("UPDATE perfis_pregao SET tema = ? WHERE email = ?", (tema, email))

    def _apelido_livre(self, apelido: str, email: str) -> str:
        base, n = apelido[:15] or "Investidor", 2
        candidato = base
        while (dono := self.email_por_apelido(candidato)) and dono != email:
            candidato, n = f"{base} {n}", n + 1
        return candidato

    def remover_foto(self, email: str) -> None:
        with self._con() as con:
            con.execute("UPDATE perfis_pregao SET foto = NULL WHERE email = ?", (email,))

    def fotos(self) -> list[Perfil]:
        with self._con() as con:
            linhas = con.execute("SELECT * FROM perfis_pregao WHERE foto IS NOT NULL ORDER BY apelido").fetchall()
        return [Perfil(ln["email"], ln["apelido"], ln["avatar"], ln["foto"], ln["bio"] or "") for ln in linhas]

    def perfis(self, emails: list[str]) -> dict[str, Perfil]:
        if not emails:
            return {}
        with self._con() as con:
            linhas = con.execute(f"SELECT * FROM perfis_pregao WHERE email IN ({','.join('?' * len(emails))})",
                                 emails).fetchall()
        return {ln["email"]: Perfil(ln["email"], ln["apelido"], ln["avatar"], ln["foto"], ln["bio"] or "")
                for ln in linhas}

    # -- presença e posição no salão -----------------------------------------------------

    def marcar_presenca(self, email: str, sala: str, apelido: str, avatar: str | None, agora: datetime | None = None) -> None:
        agora = agora or datetime.now()
        x, y = lugar_inicial(email)
        with self._con() as con:
            con.execute("INSERT INTO presenca (email, sala, apelido, avatar, visto_em, x, y) VALUES (?, ?, ?, ?, ?, ?, ?) "
                        "ON CONFLICT(email, sala) DO UPDATE SET apelido = excluded.apelido, avatar = excluded.avatar, "
                        "visto_em = excluded.visto_em",
                        (email, sala, apelido, avatar, agora.isoformat(timespec="seconds"), x, y))

    def mover(self, email: str, sala: str, x: float, y: float) -> tuple[float, float]:
        x, y = _limitar(x, 3, 97), _limitar(y, 34, 94)
        with self._con() as con:
            con.execute("UPDATE presenca SET x = ?, y = ?, visto_em = ? WHERE email = ? AND sala = ?",
                        (x, y, datetime.now().isoformat(timespec="seconds"), email, sala))
        return x, y

    def sair(self, email: str) -> None:
        with self._con() as con:
            con.execute("DELETE FROM presenca WHERE email = ?", (email,))

    def online(self, sala: str | None = None, agora: datetime | None = None) -> list[Participante]:
        limite = ((agora or datetime.now()) - ONLINE_POR).isoformat(timespec="seconds")
        with self._con() as con:
            consulta = ("SELECT p.*, f.foto FROM presenca p LEFT JOIN perfis_pregao f ON f.email = p.email "
                        "WHERE p.visto_em >= ?" + (" AND p.sala = ?" if sala else "") + " ORDER BY p.visto_em DESC")
            linhas = con.execute(consulta, (limite, sala) if sala else (limite,)).fetchall()
        vistos, resultado = set(), []
        for ln in linhas:
            if ln["email"] not in vistos:
                vistos.add(ln["email"])
                x0, y0 = lugar_inicial(ln["email"])
                resultado.append(Participante(ln["email"], ln["apelido"], ln["avatar"], datetime.fromisoformat(ln["visto_em"]),
                                              ln["x"] if ln["x"] is not None else x0, ln["y"] if ln["y"] is not None else y0,
                                              ln["foto"]))
        return resultado

    def contagem_por_sala(self, agora: datetime | None = None) -> dict[str, int]:
        return {sala: len(self.online(sala, agora)) for sala in SALAS}

    # -- mensagens da sala -----------------------------------------------------------------

    def silenciado_ate(self, email: str, agora: datetime | None = None) -> datetime | None:
        with self._con() as con:
            ln = con.execute("SELECT ate FROM silenciados WHERE email = ?", (email,)).fetchone()
        if ln and datetime.fromisoformat(ln["ate"]) > (agora or datetime.now()):
            return datetime.fromisoformat(ln["ate"])
        return None

    def _conferir_envio(self, con, email: str, texto: str, agora: datetime, tabela: str = "mensagens") -> str:
        texto = re.sub(r"[ \t]+", " ", (texto or "")).strip()
        if not texto:
            raise ErroPregao("Escreva uma mensagem.")
        if len(texto) > TAMANHO_MAXIMO:
            raise ErroPregao(f"Mensagens têm até {TAMANHO_MAXIMO} caracteres.")
        ate = self.silenciado_ate(email, agora)
        if ate:
            raise ErroPregao(f"Você está silenciado até {ate:%d/%m %H:%M}.")
        coluna = "email" if tabela == "mensagens" else "de"
        ultimo = con.execute(f"SELECT MAX(criado_em) FROM {tabela} WHERE {coluna} = ?", (email,)).fetchone()[0]
        if ultimo and timedelta(0) <= agora - datetime.fromisoformat(ultimo) < INTERVALO_MINIMO:
            raise ErroPregao("Calma: espere uns segundos entre uma mensagem e outra.")
        return texto

    def enviar(self, sala: str, email: str, apelido: str, avatar: str | None, texto: str,
               agora: datetime | None = None, resposta_a: int | None = None, tipo: str = "texto",
               dados: dict | None = None) -> Mensagem:
        agora = agora or datetime.now()
        if sala not in SALAS:
            raise ErroPregao("Sala desconhecida.")
        with self._con() as con:
            if email != BOT_EMAIL:
                texto = self._conferir_envio(con, email, texto, agora)
            if resposta_a is not None and not con.execute(
                    "SELECT 1 FROM mensagens WHERE id = ? AND removida = 0", (resposta_a,)).fetchone():
                resposta_a = None
            tickers = tickers_no_texto(texto)
            cur = con.execute("INSERT INTO mensagens (sala, email, apelido, avatar, texto, tickers, criado_em, resposta_a, "
                              "tipo, dados) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                              (sala, email, apelido, avatar, texto, ",".join(tickers), agora.isoformat(timespec="seconds"),
                               resposta_a, tipo, json.dumps(dados or {}, ensure_ascii=False)))
            id_ = int(cur.lastrowid)
        if email != BOT_EMAIL:
            self.marcar_presenca(email, sala, apelido, avatar, agora)
        return Mensagem(id_, sala, email, apelido, avatar, texto, tickers, agora, 0, resposta_a, tipo, dados or {})

    def _mensagem(self, ln) -> Mensagem:
        try:
            dados = json.loads(ln["dados"] or "{}")
        except ValueError:
            dados = {}
        return Mensagem(ln["id"], ln["sala"], ln["email"], ln["apelido"], ln["avatar"], ln["texto"],
                        [t for t in (ln["tickers"] or "").split(",") if t], datetime.fromisoformat(ln["criado_em"]),
                        ln["denuncias"], ln["resposta_a"], ln["tipo"] or "texto", dados)

    def listar(self, sala: str, limite: int = 60, depois_de: int = 0) -> list[Mensagem]:
        with self._con() as con:
            linhas = con.execute("SELECT * FROM mensagens WHERE sala = ? AND removida = 0 AND id > ? "
                                 "ORDER BY id DESC LIMIT ?", (sala, depois_de, limite)).fetchall()
        return [self._mensagem(ln) for ln in reversed(linhas)]

    def buscar_mensagem(self, id_: int) -> Mensagem | None:
        with self._con() as con:
            ln = con.execute("SELECT * FROM mensagens WHERE id = ? AND removida = 0", (id_,)).fetchone()
        return self._mensagem(ln) if ln else None

    def ultima_fala(self, sala: str, desde: timedelta = timedelta(seconds=90), agora: datetime | None = None) -> dict[str, str]:
        """O que cada pessoa disse por último, nos últimos segundos (vira balão de fala na sala)."""
        limite = ((agora or datetime.now()) - desde).isoformat(timespec="seconds")
        with self._con() as con:
            linhas = con.execute("SELECT email, texto FROM mensagens WHERE sala = ? AND removida = 0 AND criado_em >= ? "
                                 "ORDER BY id", (sala, limite)).fetchall()
        return {ln["email"]: ln["texto"] for ln in linhas}

    def participou(self, email: str) -> bool:
        with self._con() as con:
            return con.execute("SELECT 1 FROM mensagens WHERE email = ? LIMIT 1", (email,)).fetchone() is not None

    def apagar_propria(self, id_: int, email: str) -> bool:
        with self._con() as con:
            cur = con.execute("UPDATE mensagens SET removida = 1 WHERE id = ? AND email = ?", (id_, email))
        return cur.rowcount > 0

    # -- reações ---------------------------------------------------------------------------

    def reagir(self, msg_id: int, email: str, emoji: str) -> bool:
        """Liga ou desliga a reação. Devolve True se ficou ligada."""
        if emoji not in REACOES:
            raise ErroPregao("Reação desconhecida.")
        with self._con() as con:
            existe = con.execute("SELECT 1 FROM reacoes WHERE msg_id = ? AND email = ? AND emoji = ?",
                                 (msg_id, email, emoji)).fetchone()
            if existe:
                con.execute("DELETE FROM reacoes WHERE msg_id = ? AND email = ? AND emoji = ?", (msg_id, email, emoji))
                return False
            con.execute("INSERT INTO reacoes VALUES (?, ?, ?)", (msg_id, email, emoji))
            return True

    def reacoes(self, ids: list[int]) -> dict[int, dict[str, int]]:
        if not ids:
            return {}
        with self._con() as con:
            linhas = con.execute(f"SELECT msg_id, emoji, COUNT(*) n FROM reacoes WHERE msg_id IN ({','.join('?' * len(ids))}) "
                                 "GROUP BY msg_id, emoji", ids).fetchall()
        saida: dict[int, dict[str, int]] = {}
        for ln in linhas:
            saida.setdefault(ln["msg_id"], {})[ln["emoji"]] = ln["n"]
        return {k: {e: v[e] for e in REACOES if e in v} for k, v in saida.items()}

    # -- gráficos compartilhados (quadros) -----------------------------------------------------

    def compartilhar_grafico(self, sala: str, email: str, apelido: str, avatar: str | None, ticker: str,
                             periodo: str = "6m", nota: str = "", agora: datetime | None = None) -> Mensagem:
        agora = agora or datetime.now()
        ticker = ticker.strip().upper().replace(".SA", "")
        if not re.match(r"^(\^?[A-Z0-9]{3,8})$", ticker):
            raise ErroPregao("Informe um ativo, como TAEE11 ou PETR4.")
        periodo = periodo if periodo in PERIODOS else "6m"
        nota = re.sub(r"\s+", " ", nota or "").strip()[:200]
        texto = f"Compartilhou o gráfico de ${ticker} ({PERIODOS[periodo][0]})" + (f": {nota}" if nota else ".")
        with self._con() as con:
            cur = con.execute("INSERT INTO quadros (sala, email, apelido, ticker, periodo, nota, criado_em) "
                              "VALUES (?, ?, ?, ?, ?, ?, ?)",
                              (sala, email, apelido, ticker, periodo, nota, agora.isoformat(timespec="seconds")))
            quadro = int(cur.lastrowid)
        return self.enviar(sala, email, apelido, avatar, texto, agora, tipo="grafico",
                           dados={"ticker": ticker, "periodo": periodo, "quadro": quadro, "nota": nota})

    def quadros(self, sala: str, desde: timedelta = timedelta(hours=6), agora: datetime | None = None) -> list[Quadro]:
        """O gráfico mais recente de cada pessoa na sala (vira o monitor ao lado do avatar)."""
        limite = ((agora or datetime.now()) - desde).isoformat(timespec="seconds")
        with self._con() as con:
            linhas = con.execute("SELECT * FROM quadros WHERE sala = ? AND criado_em >= ? ORDER BY id DESC",
                                 (sala, limite)).fetchall()
        vistos, saida = set(), []
        for ln in linhas:
            if ln["email"] not in vistos:
                vistos.add(ln["email"])
                saida.append(Quadro(ln["id"], ln["sala"], ln["email"], ln["apelido"], ln["ticker"], ln["periodo"],
                                    ln["nota"] or "", datetime.fromisoformat(ln["criado_em"])))
        return saida

    # -- mensagens privadas --------------------------------------------------------------------

    def enviar_privada(self, de: str, para: str, texto: str, agora: datetime | None = None) -> Privada:
        agora = agora or datetime.now()
        if de == para:
            raise ErroPregao("Escolha outra pessoa.")
        with self._con() as con:
            texto = self._conferir_envio(con, de, texto, agora, "privadas")
            cur = con.execute("INSERT INTO privadas (de, para, texto, criado_em) VALUES (?, ?, ?, ?)",
                              (de, para, texto, agora.isoformat(timespec="seconds")))
            id_ = int(cur.lastrowid)
        return Privada(id_, de, para, texto, agora, False)

    def conversa(self, a: str, b: str, limite: int = 50) -> list[Privada]:
        with self._con() as con:
            linhas = con.execute("SELECT * FROM privadas WHERE (de = ? AND para = ?) OR (de = ? AND para = ?) "
                                 "ORDER BY id DESC LIMIT ?", (a, b, b, a, limite)).fetchall()
        return [Privada(ln["id"], ln["de"], ln["para"], ln["texto"], datetime.fromisoformat(ln["criado_em"]),
                        bool(ln["lida"])) for ln in reversed(linhas)]

    def conversas(self, email: str) -> list[dict]:
        """Com quem a pessoa conversa: outro, última mensagem, quando e quantas não lidas."""
        with self._con() as con:
            linhas = con.execute("SELECT * FROM privadas WHERE de = ? OR para = ? ORDER BY id DESC", (email, email)).fetchall()
        resumo: dict[str, dict] = {}
        for ln in linhas:
            outro = ln["para"] if ln["de"] == email else ln["de"]
            item = resumo.setdefault(outro, {"outro": outro, "ultima": ln["texto"], "quando": ln["criado_em"],
                                             "nao_lidas": 0})
            if ln["para"] == email and not ln["lida"]:
                item["nao_lidas"] += 1
        return list(resumo.values())

    def marcar_lidas(self, email: str, de: str) -> None:
        with self._con() as con:
            con.execute("UPDATE privadas SET lida = 1 WHERE para = ? AND de = ?", (email, de))

    def nao_lidas_privadas(self, email: str) -> int:
        with self._con() as con:
            return con.execute("SELECT COUNT(*) FROM privadas WHERE para = ? AND lida = 0", (email,)).fetchone()[0]

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
        return [self._mensagem(ln) for ln in linhas]

    def apagar_dados(self, email: str) -> None:
        """LGPD: some com perfil, presença, reações e privadas da pessoa."""
        with self._con() as con:
            for sql in ("DELETE FROM perfis_pregao WHERE email = ?", "DELETE FROM presenca WHERE email = ?",
                        "DELETE FROM reacoes WHERE email = ?", "DELETE FROM privadas WHERE de = ? OR para = ?"):
                con.execute(sql, (email,) * sql.count("?"))


# ---------------------------------------------------------------------------
# Demonstração: participantes fictícios para conhecer a sala sem ninguém online
# ---------------------------------------------------------------------------

_DEMO = [
    ("demo-ana", "Ana", "Alguém olhando TAEE11? A data com deve sair semana que vem.", 22, 58, "TAEE11"),
    ("demo-rafa", "Rafa", "Reforcei MXRF11 hoje, abaixo do meu preço de entrada.", 70, 50, None),
    ("demo-bia", "Bia", "Primeiro aporte do mês feito! Meta de R$ 500/mês em proventos.", 40, 78, None),
    ("demo-caio", "Caio", "BBAS3 ainda acima do preço justo pelos meus parâmetros, vou esperar.", 85, 74, "BBAS3"),
    ("demo-lu", "Lu", "Alguém usa o Sentinela no WhatsApp? Chegou a dica certinho às 9h.", 12, 86, None),
]


def demo(agora: datetime | None = None) -> tuple[list[Participante], list[Mensagem]]:
    from chronotrade.avatar import sortear

    agora = agora or datetime.now()
    pessoas = [Participante(e, n, sortear(e).json(), agora, x, y) for e, n, _, x, y, _ in _DEMO]
    msgs = [Mensagem(-(i + 1), "geral", e, n, sortear(e).json(), t, tickers_no_texto(t),
                     agora - timedelta(seconds=20 * (len(_DEMO) - i)), 0) for i, (e, n, t, *_rest) in enumerate(_DEMO)]
    return pessoas, msgs


def demo_quadros(agora: datetime | None = None) -> list[Quadro]:
    agora = agora or datetime.now()
    return [Quadro(-(i + 1), "geral", e, n, q, "6m", "", agora) for i, (e, n, _, _x, _y, q) in enumerate(_DEMO) if q]
