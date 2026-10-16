"""Chrono Pontos: check-in diário, conquistas, desempenho da carteira e a loja do avatar.

Como se ganha:
- check-in diário (10 pontos, mais 2 por dia de sequência, até +14; a cada 7 dias seguidos, +30);
- desempenho da carteira: uma vez por semana, se as ações e fundos que você já tinha se valorizaram,
  ganha pontos proporcionais (1 ponto por 0,1% de alta, no máximo 50). Pontos medem constância,
  não risco: a conta usa as mesmas posições do início ao fim da semana, então aportes não contam;
- conquistas de primeira vez (perfil com foto, primeiro alerta, primeira conversa no Pregão...);
- pacotes de pontos comprados no app pelo PIX.

Como se gasta: itens do avatar (terno, cartola, coroa, maleta...). Pontos não valem dinheiro, não podem
ser trocados por dinheiro nem transferidos.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

# id: (nome, categoria do avatar, preço em pontos, descrição)
CATALOGO = {
    "terno": ("Terno executivo", "traje", 300, "Paletó azul-marinho, camisa branca e gravata vermelha."),
    "colete": ("Colete e camisa", "traje", 200, "O visual do analista de mesa."),
    "terno_branco": ("Terno branco", "traje", 450, "Para quem fechou o ano no azul."),
    "smoking": ("Smoking", "traje", 800, "Gravata-borboleta e abotoadura de ouro."),
    "bone_verde": ("Boné verde", "chapeu", 120, "Clássico do pregão."),
    "panama": ("Chapéu-panamá", "chapeu", 300, "Elegância de quem vive de dividendos."),
    "cartola": ("Cartola", "chapeu", 400, "Para o investidor de longo prazo."),
    "coroa": ("Coroa", "chapeu", 1500, "Rei (ou rainha) dos proventos."),
    "cafe": ("Café da manhã", "extra", 100, "Check-in com café."),
    "oculos_escuros": ("Óculos escuros", "extra", 150, "Mercado em alta, futuro brilhante."),
    "maleta": ("Maleta", "extra", 250, "Relatórios sempre à mão."),
    "relogio_ouro": ("Relógio de ouro", "extra", 350, "Tempo no mercado vale mais que timing."),
    "trofeu": ("Troféu", "extra", 1000, "Para quem mantém a constância."),
    "moldura_ouro": ("Moldura dourada", "moldura", 300, "Para a sua foto no Pregão."),
    "moldura_neon": ("Moldura neon", "moldura", 300, "Brilho turquesa ao redor da foto."),
}
CATEGORIAS = {"traje": "Trajes", "chapeu": "Chapéus", "extra": "Acessórios", "moldura": "Molduras da foto"}

# Pacotes de pontos pagos pelo PIX: id -> (pontos, preço em reais)
PACOTES = {"p500": (500, 4.90), "p1500": (1500, 12.90), "p4000": (4000, 29.90)}

CONQUISTAS = {
    "perfil_foto": ("Rosto conhecido", 50, "Colocou foto no perfil."),
    "primeira_conversa": ("Bom dia, pregão!", 30, "Primeira mensagem no Pregão."),
    "primeiro_grafico": ("Analista de telão", 40, "Mostrou o primeiro gráfico no salão."),
    "primeiro_alerta": ("Sentinela de olho", 30, "Criou o primeiro alerta de preço."),
    "carteira": ("Inventário em dia", 50, "Cadastrou a carteira."),
    "sequencia_7": ("Uma semana firme", 70, "Sete check-ins seguidos."),
    "sequencia_30": ("Mês de disciplina", 300, "Trinta check-ins seguidos."),
    "primeiro_emoji": ("Torcida animada", 15, "Soltou o primeiro emoji no salão."),
    "primeira_frase": ("Voz no pregão", 30, "Gravou a primeira frase do avatar."),
    "estresse": ("Preparado para a tempestade", 40, "Fez o primeiro teste de estresse da carteira."),
    "maos_livres": ("Mãos livres", 30, "Deu o primeiro comando de voz com o Jarvis."),
}

MAX_DESEMPENHO = 50

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS pontos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL,
    delta INTEGER NOT NULL,
    motivo TEXT NOT NULL,
    chave TEXT,
    criado_em TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS pontos_chave ON pontos (email, chave);
CREATE TABLE IF NOT EXISTS itens_avatar (
    email TEXT NOT NULL,
    item TEXT NOT NULL,
    origem TEXT NOT NULL,
    criado_em TEXT NOT NULL,
    PRIMARY KEY (email, item)
);
CREATE TABLE IF NOT EXISTS pedidos_pontos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL,
    pacote TEXT NOT NULL,
    pontos INTEGER NOT NULL,
    valor REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'aguardando',
    criado_em TEXT NOT NULL,
    pago_em TEXT
);
"""


class ErroJogo(ValueError):
    pass


@dataclass
class Lancamento:
    delta: int
    motivo: str
    criado_em: datetime


@dataclass
class Pedido:
    id: int
    email: str
    pacote: str
    pontos: int
    valor: float
    status: str
    criado_em: datetime


class Jogo:
    def __init__(self, caminho: Path):
        self.caminho = Path(caminho)
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

    # -- pontos ------------------------------------------------------------------------

    def saldo(self, email: str) -> int:
        with self._con() as con:
            return int(con.execute("SELECT COALESCE(SUM(delta), 0) FROM pontos WHERE email = ?", (email,)).fetchone()[0])

    def extrato(self, email: str, limite: int = 30) -> list[Lancamento]:
        with self._con() as con:
            linhas = con.execute("SELECT delta, motivo, criado_em FROM pontos WHERE email = ? ORDER BY id DESC LIMIT ?",
                                 (email, limite)).fetchall()
        return [Lancamento(ln["delta"], ln["motivo"], datetime.fromisoformat(ln["criado_em"])) for ln in linhas]

    def creditar(self, email: str, delta: int, motivo: str, chave: str | None = None,
                 agora: datetime | None = None) -> bool:
        """Lança pontos. Com ``chave``, só lança uma vez (check-in do dia, conquista, semana)."""
        agora = agora or datetime.now()
        try:
            with self._con() as con:
                con.execute("INSERT INTO pontos (email, delta, motivo, chave, criado_em) VALUES (?, ?, ?, ?, ?)",
                            (email, int(delta), motivo, chave, agora.isoformat(timespec="seconds")))
            return True
        except sqlite3.IntegrityError:
            return False

    # -- check-in diário -----------------------------------------------------------------

    def _dias_de_checkin(self, email: str) -> set[date]:
        with self._con() as con:
            linhas = con.execute("SELECT chave FROM pontos WHERE email = ? AND chave LIKE 'checkin:%'", (email,)).fetchall()
        return {date.fromisoformat(ln["chave"].split(":", 1)[1]) for ln in linhas}

    def sequencia(self, email: str, hoje: date | None = None) -> int:
        """Quantos dias seguidos, terminando hoje (ou ontem, se ainda não fez hoje)."""
        hoje = hoje or date.today()
        dias = self._dias_de_checkin(email)
        d = hoje if hoje in dias else hoje - timedelta(days=1)
        n = 0
        while d in dias:
            n += 1
            d -= timedelta(days=1)
        return n

    def fez_checkin(self, email: str, hoje: date | None = None) -> bool:
        return (hoje or date.today()) in self._dias_de_checkin(email)

    def checkin(self, email: str, hoje: date | None = None) -> tuple[int, int] | None:
        """Faz o check-in do dia. Devolve (pontos ganhos, sequência) ou None se já tinha feito."""
        hoje = hoje or date.today()
        if self.fez_checkin(email, hoje):
            return None
        seq = self.sequencia(email, hoje) + 1
        pontos = 10 + min(seq - 1, 7) * 2
        agora = datetime.combine(hoje, datetime.now().time())
        if not self.creditar(email, pontos, f"Check-in diário (sequência de {seq})", f"checkin:{hoje.isoformat()}", agora):
            return None
        if seq % 7 == 0:
            self.creditar(email, 30, f"Bônus de {seq} dias seguidos", f"bonus_seq:{hoje.isoformat()}", agora)
            pontos += 30
        if seq >= 7:
            pontos += self.conquistar(email, "sequencia_7", agora)
        if seq >= 30:
            pontos += self.conquistar(email, "sequencia_30", agora)
        return pontos, seq

    # -- conquistas ----------------------------------------------------------------------

    def conquistar(self, email: str, conquista: str, agora: datetime | None = None) -> int:
        nome, pontos, _ = CONQUISTAS[conquista]
        return pontos if self.creditar(email, pontos, f"Conquista: {nome}", f"conquista:{conquista}", agora) else 0

    def conquistas(self, email: str) -> set[str]:
        with self._con() as con:
            linhas = con.execute("SELECT chave FROM pontos WHERE email = ? AND chave LIKE 'conquista:%'", (email,)).fetchall()
        return {ln["chave"].split(":", 1)[1] for ln in linhas}

    # -- desempenho semanal da carteira ----------------------------------------------------

    def desempenho(self, email: str, posicoes: list[tuple[str, float]], obter, pasta: Path,
                   hoje: date | None = None) -> int:
        """Uma vez por semana: pontos pela valorização das posições que já existiam no começo da semana.

        ``posicoes`` = [(ticker, quantidade)]. Guarda a foto dos preços em ``pasta/jogo_semana.json``.
        """
        hoje = hoje or date.today()
        arquivo = pasta / "jogo_semana.json"
        try:
            foto = json.loads(arquivo.read_text(encoding="utf-8")) if arquivo.exists() else None
        except (OSError, ValueError):
            foto = None
        precos = {}
        for ticker, qtd in posicoes:
            preco = getattr(obter(ticker), "preco", None)
            if preco and qtd > 0:
                precos[ticker] = (float(preco), float(qtd))
        ganhos = 0
        if foto and date.fromisoformat(foto["data"]) <= hoje - timedelta(days=7):
            antes = depois = 0.0
            for ticker, (p0, q0) in foto["precos"].items():
                if ticker in precos:
                    antes += p0 * q0
                    depois += precos[ticker][0] * q0  # mesmas quantidades: aporte não conta
            if antes > 0:
                retorno = depois / antes - 1
                if retorno > 0:
                    ganhos = min(MAX_DESEMPENHO, int(round(retorno * 1000)))
                    if ganhos and not self.creditar(email, ganhos, f"Carteira valorizou {retorno * 100:.1f}% na semana"
                                                    .replace(".", ","), f"semana:{hoje.isoformat()}"):
                        ganhos = 0
            foto = None
        if foto is None and precos:
            try:
                pasta.mkdir(parents=True, exist_ok=True)
                arquivo.write_text(json.dumps({"data": hoje.isoformat(), "precos": precos}), encoding="utf-8")
            except OSError:
                pass
        return ganhos

    # -- loja ------------------------------------------------------------------------------

    def itens(self, email: str) -> set[str]:
        with self._con() as con:
            return {ln["item"] for ln in con.execute("SELECT item FROM itens_avatar WHERE email = ?", (email,))}

    def comprar(self, email: str, item: str, agora: datetime | None = None) -> int:
        """Troca pontos por um item. Devolve o saldo novo."""
        if item not in CATALOGO:
            raise ErroJogo("Item desconhecido.")
        if item in self.itens(email):
            raise ErroJogo("Você já tem esse item.")
        nome, _, preco, _ = CATALOGO[item]
        if self.saldo(email) < preco:
            raise ErroJogo(f"Faltam {preco - self.saldo(email)} pontos para {nome}.")
        agora = agora or datetime.now()
        with self._con() as con:
            con.execute("INSERT INTO pontos (email, delta, motivo, chave, criado_em) VALUES (?, ?, ?, ?, ?)",
                        (email, -preco, f"Comprou: {nome}", f"compra:{item}", agora.isoformat(timespec="seconds")))
            con.execute("INSERT INTO itens_avatar VALUES (?, ?, 'pontos', ?)", (email, item, agora.isoformat(timespec="seconds")))
        return self.saldo(email)

    def dar_item(self, email: str, item: str, origem: str = "presente") -> None:
        with self._con() as con:
            con.execute("INSERT OR IGNORE INTO itens_avatar VALUES (?, ?, ?, ?)",
                        (email, item, origem, datetime.now().isoformat(timespec="seconds")))

    # -- pacotes pagos ---------------------------------------------------------------------

    def pedir_pacote(self, email: str, pacote: str) -> Pedido:
        if pacote not in PACOTES:
            raise ErroJogo("Pacote desconhecido.")
        with self._con() as con:
            aberto = con.execute("SELECT * FROM pedidos_pontos WHERE email = ? AND pacote = ? AND status = 'aguardando'",
                                 (email, pacote)).fetchone()
            if aberto:
                return self._pedido(aberto)
            pontos, valor = PACOTES[pacote]
            cur = con.execute("INSERT INTO pedidos_pontos (email, pacote, pontos, valor, criado_em) VALUES (?, ?, ?, ?, ?)",
                              (email, pacote, pontos, valor, datetime.now().isoformat(timespec="seconds")))
            ln = con.execute("SELECT * FROM pedidos_pontos WHERE id = ?", (cur.lastrowid,)).fetchone()
        return self._pedido(ln)

    @staticmethod
    def _pedido(ln) -> Pedido:
        return Pedido(ln["id"], ln["email"], ln["pacote"], ln["pontos"], ln["valor"], ln["status"],
                      datetime.fromisoformat(ln["criado_em"]))

    def pedidos(self, status: str | None = "aguardando", email: str | None = None) -> list[Pedido]:
        sql, args = "SELECT * FROM pedidos_pontos WHERE 1 = 1", []
        if status:
            sql += " AND status = ?"
            args.append(status)
        if email:
            sql += " AND email = ?"
            args.append(email)
        with self._con() as con:
            return [self._pedido(ln) for ln in con.execute(sql + " ORDER BY id DESC", args).fetchall()]

    def confirmar_pedido(self, id_: int) -> Pedido:
        with self._con() as con:
            ln = con.execute("SELECT * FROM pedidos_pontos WHERE id = ?", (id_,)).fetchone()
            if ln is None or ln["status"] != "aguardando":
                raise ErroJogo("Pedido não encontrado ou já confirmado.")
            con.execute("UPDATE pedidos_pontos SET status = 'pago', pago_em = ? WHERE id = ?",
                        (datetime.now().isoformat(timespec="seconds"), id_))
        p = self._pedido(ln)
        self.creditar(p.email, p.pontos, f"Pacote de {p.pontos} pontos (PIX)", f"pedido:{p.id}")
        return p

    def cancelar_pedido(self, id_: int) -> None:
        with self._con() as con:
            con.execute("UPDATE pedidos_pontos SET status = 'cancelado' WHERE id = ? AND status = 'aguardando'", (id_,))

    def apagar_dados(self, email: str) -> None:
        with self._con() as con:
            for tabela in ("pontos", "itens_avatar", "pedidos_pontos"):
                con.execute(f"DELETE FROM {tabela} WHERE email = ?", (email,))
