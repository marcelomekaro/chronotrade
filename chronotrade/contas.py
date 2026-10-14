"""Contas do Chrono Trade: cadastro por e-mail, aprovação pelo administrador e assinaturas.

Fluxo:
  1. A pessoa se cadastra com nome, e-mail e senha. A conta nasce "pendente".
  2. Ela paga (PIX ou link) e avisa. O administrador libera a conta, escolhe o
     plano e a validade, e registra o pagamento.
  3. Com a conta ativa e dentro da validade, ela entra com e-mail e senha.

Tudo fica num banco SQLite (``contas.db``) na pasta de dados. As senhas são
guardadas só como hash PBKDF2 com sal; ninguém, nem o administrador, consegue lê-las.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

ADMIN_PADRAO = "marcelomekaro@gmail.com"
PLANOS = {"gratuito": "Gratuito", "completo": "Completo"}
STATUS = {"pendente": "Aguardando liberação", "ativo": "Ativo", "bloqueado": "Bloqueado"}
TENTATIVAS_MAX = 5
BLOQUEIO_MINUTOS = 15
SESSAO_DIAS = 14
_ITERACOES = 240_000
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

CONFIG_PADRAO = {
    "preco_mensal": "19.90",
    "preco_anual": "199.00",
    "pix_chave": "",
    "pix_nome": "",
    "pix_cidade": "SAO PAULO",
    "whatsapp_admin": "",
    "limite_gratuito": "5",
    "nome_loja": "Chrono Trade",
}


def email_admin() -> str:
    return (os.environ.get("CHRONOTRADE_ADMIN_EMAIL") or ADMIN_PADRAO).strip().lower()


def modo_servidor() -> bool:
    return (os.environ.get("CHRONOTRADE_MODO") or "pessoal").strip().lower() in ("servidor", "assinatura")


class ErroConta(ValueError):
    """Erro com mensagem pronta para mostrar na tela."""


# ---------------------------------------------------------------------------
# Senhas
# ---------------------------------------------------------------------------


def hash_senha(senha: str, sal: bytes | None = None) -> str:
    sal = sal or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", senha.encode(), sal, _ITERACOES)
    return f"pbkdf2${_ITERACOES}${sal.hex()}${digest.hex()}"


def conferir_senha(senha: str, guardado: str | None) -> bool:
    if not guardado:
        return False
    try:
        _, iteracoes, sal, digest = guardado.split("$")
    except ValueError:
        return False
    calculado = hashlib.pbkdf2_hmac("sha256", senha.encode(), bytes.fromhex(sal), int(iteracoes))
    return hmac.compare_digest(calculado.hex(), digest)


def validar_senha(senha: str) -> None:
    if len(senha) < 8:
        raise ErroConta("A senha precisa de pelo menos 8 caracteres.")
    if senha.isdigit() or senha.isalpha():
        raise ErroConta("Misture letras e números na senha.")


def senha_temporaria() -> str:
    """Uma senha fácil de ditar por telefone: 3 blocos de letras e números sem confusões (0/O, 1/l)."""
    alfabeto = "abcdefghjkmnpqrstuvwxyz23456789"
    return "-".join("".join(secrets.choice(alfabeto) for _ in range(4)) for _ in range(3))


def normalizar_email(email: str) -> str:
    email = (email or "").strip().lower()
    if not _EMAIL.match(email):
        raise ErroConta("Confira o e-mail: ele precisa ter o formato nome@provedor.com.")
    return email


# ---------------------------------------------------------------------------
# Banco
# ---------------------------------------------------------------------------

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
    email TEXT PRIMARY KEY,
    nome TEXT NOT NULL,
    whatsapp TEXT DEFAULT '',
    senha_hash TEXT,
    status TEXT NOT NULL DEFAULT 'pendente',
    plano TEXT NOT NULL DEFAULT 'gratuito',
    validade TEXT,
    senha_temporaria INTEGER NOT NULL DEFAULT 0,
    tentativas INTEGER NOT NULL DEFAULT 0,
    bloqueado_ate TEXT,
    criado_em TEXT NOT NULL,
    ultimo_acesso TEXT,
    observacao TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS pagamentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL,
    valor REAL NOT NULL,
    dias INTEGER NOT NULL,
    plano TEXT NOT NULL,
    forma TEXT DEFAULT 'PIX',
    registrado_em TEXT NOT NULL,
    observacao TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS sessoes (
    token_hash TEXT PRIMARY KEY,
    email TEXT NOT NULL,
    expira_em TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS config (
    chave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);
"""


@dataclass
class Usuario:
    email: str
    nome: str
    whatsapp: str
    status: str
    plano: str
    validade: date | None
    senha_temporaria: bool
    criado_em: datetime
    ultimo_acesso: datetime | None
    observacao: str

    @property
    def admin(self) -> bool:
        return self.email == email_admin()

    @property
    def id_pasta(self) -> str:
        return hashlib.sha256(self.email.encode()).hexdigest()[:16]

    def dias_restantes(self, hoje: date | None = None) -> int | None:
        if self.admin:
            return None
        if self.validade is None:
            return None
        return (self.validade - (hoje or date.today())).days

    def vencido(self, hoje: date | None = None) -> bool:
        dias = self.dias_restantes(hoje)
        return dias is not None and dias < 0

    def pode_usar(self, hoje: date | None = None) -> bool:
        return self.status == "ativo" and not self.vencido(hoje)

    def plano_completo(self, hoje: date | None = None) -> bool:
        return self.admin or (self.pode_usar(hoje) and self.plano == "completo")


def _data(texto: str | None) -> date | None:
    return date.fromisoformat(texto) if texto else None


def _quando(texto: str | None) -> datetime | None:
    return datetime.fromisoformat(texto) if texto else None


class Contas:
    """Acesso ao banco de contas. Use uma instância por processo."""

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

    # -- leitura ------------------------------------------------------------

    def _usuario(self, linha) -> Usuario | None:
        if linha is None:
            return None
        return Usuario(
            email=linha["email"], nome=linha["nome"], whatsapp=linha["whatsapp"] or "",
            status=linha["status"], plano=linha["plano"], validade=_data(linha["validade"]),
            senha_temporaria=bool(linha["senha_temporaria"]), criado_em=_quando(linha["criado_em"]),
            ultimo_acesso=_quando(linha["ultimo_acesso"]), observacao=linha["observacao"] or "",
        )

    def buscar(self, email: str) -> Usuario | None:
        with self._con() as con:
            return self._usuario(con.execute("SELECT * FROM usuarios WHERE email = ?",
                                             (email.strip().lower(),)).fetchone())

    def listar(self) -> list[Usuario]:
        with self._con() as con:
            linhas = con.execute("SELECT * FROM usuarios ORDER BY criado_em DESC").fetchall()
        return [self._usuario(linha) for linha in linhas]

    def pagamentos(self, email: str | None = None) -> list[dict]:
        with self._con() as con:
            if email:
                linhas = con.execute("SELECT * FROM pagamentos WHERE email = ? ORDER BY registrado_em DESC",
                                     (email,)).fetchall()
            else:
                linhas = con.execute("SELECT * FROM pagamentos ORDER BY registrado_em DESC").fetchall()
        return [dict(linha) for linha in linhas]

    # -- cadastro e entrada -------------------------------------------------

    def cadastrar(self, nome: str, email: str, senha: str, whatsapp: str = "", *, interno: bool = False) -> Usuario:
        email = normalizar_email(email)
        if email == email_admin() and not interno:
            # Ninguém se cadastra como administrador pela tela: a conta nasce de CHRONOTRADE_ADMIN_SENHA
            # ou do comando chronotrade-admin, que só quem controla o servidor consegue usar.
            raise ErroConta("Este e-mail é reservado. Use outro e-mail para se cadastrar.")
        nome = (nome or "").strip()
        if len(nome) < 2:
            raise ErroConta("Escreva o seu nome.")
        validar_senha(senha)
        if self.buscar(email):
            raise ErroConta("Este e-mail já tem cadastro. Use Entrar, ou peça uma senha nova ao suporte.")
        status, plano = ("ativo", "completo") if email == email_admin() else ("pendente", "gratuito")
        with self._con() as con:
            con.execute(
                "INSERT INTO usuarios (email, nome, whatsapp, senha_hash, status, plano, criado_em) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (email, nome, re.sub(r"\D", "", whatsapp or ""), hash_senha(senha), status, plano,
                 datetime.now().isoformat(timespec="seconds")))
        return self.buscar(email)

    def entrar(self, email: str, senha: str, agora: datetime | None = None) -> Usuario:
        """Confere e-mail e senha. Devolve o usuário mesmo pendente ou vencido: a tela decide o que mostrar."""
        agora = agora or datetime.now()
        email = (email or "").strip().lower()
        with self._con() as con:
            linha = con.execute("SELECT * FROM usuarios WHERE email = ?", (email,)).fetchone()
            erro = ErroConta("E-mail ou senha incorretos.")
            if linha is None:
                conferir_senha(senha, hash_senha("x"))  # mesmo tempo de resposta com e sem cadastro
                raise erro
            if linha["bloqueado_ate"] and datetime.fromisoformat(linha["bloqueado_ate"]) > agora:
                raise ErroConta(f"Muitas tentativas erradas. Tente de novo depois das "
                                f"{datetime.fromisoformat(linha['bloqueado_ate']):%H:%M}.")
            senha_ok = conferir_senha(senha, linha["senha_hash"])
            if not senha_ok:
                tentativas = linha["tentativas"] + 1
                bloqueio = (agora + timedelta(minutes=BLOQUEIO_MINUTOS)).isoformat(timespec="seconds") \
                    if tentativas >= TENTATIVAS_MAX else None
                con.execute("UPDATE usuarios SET tentativas = ?, bloqueado_ate = ? WHERE email = ?",
                            (0 if bloqueio else tentativas, bloqueio, email))
        if not senha_ok:  # fora do "with": a contagem de tentativas precisa ser gravada antes do erro
            raise erro
        with self._con() as con:
            con.execute("UPDATE usuarios SET tentativas = 0, bloqueado_ate = NULL, ultimo_acesso = ? "
                        "WHERE email = ?", (agora.isoformat(timespec="seconds"), email))
        return self.buscar(email)

    def garantir_admin(self, senha_inicial: str | None) -> None:
        """Cria a conta do administrador na primeira vez, com a senha de CHRONOTRADE_ADMIN_SENHA."""
        if self.buscar(email_admin()) or not senha_inicial:
            return
        self.cadastrar("Administrador", email_admin(), senha_inicial, interno=True)
        with self._con() as con:
            con.execute("UPDATE usuarios SET senha_temporaria = 1 WHERE email = ?", (email_admin(),))

    def trocar_senha(self, email: str, atual: str, nova: str) -> None:
        self.entrar(email, atual)
        validar_senha(nova)
        with self._con() as con:
            con.execute("UPDATE usuarios SET senha_hash = ?, senha_temporaria = 0 WHERE email = ?",
                        (hash_senha(nova), email))

    # -- sessão lembrada ----------------------------------------------------

    def criar_sessao(self, email: str, dias: int = SESSAO_DIAS) -> str:
        token = secrets.token_urlsafe(32)
        with self._con() as con:
            con.execute("DELETE FROM sessoes WHERE expira_em < ?", (datetime.now().isoformat(),))
            con.execute("INSERT INTO sessoes VALUES (?, ?, ?)",
                        (hashlib.sha256(token.encode()).hexdigest(), email,
                         (datetime.now() + timedelta(days=dias)).isoformat(timespec="seconds")))
        return token

    def sessao(self, token: str) -> Usuario | None:
        if not token:
            return None
        with self._con() as con:
            linha = con.execute("SELECT email, expira_em FROM sessoes WHERE token_hash = ?",
                                (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
        if linha is None or datetime.fromisoformat(linha["expira_em"]) < datetime.now():
            return None
        return self.buscar(linha["email"])

    def encerrar_sessao(self, token: str) -> None:
        with self._con() as con:
            con.execute("DELETE FROM sessoes WHERE token_hash = ?", (hashlib.sha256(token.encode()).hexdigest(),))

    def encerrar_todas(self, email: str) -> None:
        with self._con() as con:
            con.execute("DELETE FROM sessoes WHERE email = ?", (email,))

    # -- administração ------------------------------------------------------

    def liberar(self, email: str, plano: str, dias: int, valor: float = 0.0, forma: str = "PIX",
                observacao: str = "", hoje: date | None = None) -> Usuario:
        """Ativa ou renova: soma os dias a partir da validade atual (se ainda vale) ou de hoje."""
        u = self.buscar(email)
        if u is None:
            raise ErroConta("Conta não encontrada.")
        if plano not in PLANOS:
            raise ErroConta("Plano desconhecido.")
        hoje = hoje or date.today()
        base = u.validade if u.validade and u.validade >= hoje else hoje
        validade = base + timedelta(days=dias)
        with self._con() as con:
            con.execute("UPDATE usuarios SET status = 'ativo', plano = ?, validade = ? WHERE email = ?",
                        (plano, validade.isoformat(), u.email))
            if valor or dias:
                con.execute("INSERT INTO pagamentos (email, valor, dias, plano, forma, registrado_em, observacao) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (u.email, float(valor), int(dias), plano, forma,
                             datetime.now().isoformat(timespec="seconds"), observacao))
        return self.buscar(email)

    def mudar_status(self, email: str, status: str) -> None:
        if status not in STATUS:
            raise ErroConta("Situação desconhecida.")
        if email == email_admin() and status != "ativo":
            raise ErroConta("A conta do administrador não pode ser bloqueada.")
        with self._con() as con:
            con.execute("UPDATE usuarios SET status = ? WHERE email = ?", (status, email))
        if status == "bloqueado":
            self.encerrar_todas(email)

    def redefinir_senha(self, email: str) -> str:
        """Gera uma senha temporária. Na próxima entrada a pessoa é convidada a trocá-la."""
        if self.buscar(email) is None:
            raise ErroConta("Conta não encontrada.")
        senha = senha_temporaria()
        with self._con() as con:
            con.execute("UPDATE usuarios SET senha_hash = ?, senha_temporaria = 1, tentativas = 0, "
                        "bloqueado_ate = NULL WHERE email = ?", (hash_senha(senha), email))
        self.encerrar_todas(email)
        return senha

    def anotar(self, email: str, observacao: str) -> None:
        with self._con() as con:
            con.execute("UPDATE usuarios SET observacao = ? WHERE email = ?", (observacao, email))

    def excluir(self, email: str) -> None:
        if email == email_admin():
            raise ErroConta("A conta do administrador não pode ser excluída.")
        with self._con() as con:
            con.execute("DELETE FROM usuarios WHERE email = ?", (email,))
            con.execute("DELETE FROM sessoes WHERE email = ?", (email,))

    # -- configurações da loja ----------------------------------------------

    def config(self) -> dict[str, str]:
        with self._con() as con:
            linhas = con.execute("SELECT chave, valor FROM config").fetchall()
        return {**CONFIG_PADRAO, **{linha["chave"]: linha["valor"] for linha in linhas}}

    def salvar_config(self, valores: dict[str, str]) -> None:
        with self._con() as con:
            for chave, valor in valores.items():
                if chave in CONFIG_PADRAO:
                    con.execute("INSERT INTO config VALUES (?, ?) ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor",
                                (chave, str(valor).strip()))

    # -- números para o painel ----------------------------------------------

    def indicadores(self, hoje: date | None = None) -> dict:
        hoje = hoje or date.today()
        usuarios = [u for u in self.listar() if not u.admin]
        ativos = [u for u in usuarios if u.pode_usar(hoje)]
        mes = hoje.strftime("%Y-%m")
        receita_mes = sum(p["valor"] for p in self.pagamentos() if p["registrado_em"].startswith(mes))
        return {
            "ativos": len(ativos),
            "completos": sum(1 for u in ativos if u.plano == "completo"),
            "pendentes": sum(1 for u in usuarios if u.status == "pendente"),
            "vencendo": [u for u in ativos if (u.dias_restantes(hoje) or 99) <= 7],
            "vencidos": [u for u in usuarios if u.status == "ativo" and u.vencido(hoje)],
            "receita_mes": receita_mes,
        }


# ---------------------------------------------------------------------------
# Comando: chronotrade-admin (para usar no terminal do servidor)
# ---------------------------------------------------------------------------


def main() -> None:
    import argparse

    import tradingagents  # noqa: F401  (carrega o .env)
    from chronotrade.carteira import pasta_dados

    parser = argparse.ArgumentParser(prog="chronotrade-admin", description="Administração das contas do Chrono Trade.")
    sub = parser.add_subparsers(dest="acao", required=True)
    s = sub.add_parser("senha", help="Gera uma senha temporária para uma conta (inclusive a do administrador).")
    s.add_argument("email")
    sub.add_parser("listar", help="Lista as contas.")
    args = parser.parse_args()

    contas = Contas(pasta_dados() / "contas.db")
    if args.acao == "senha":
        email = args.email.strip().lower()
        if contas.buscar(email) is None and email == email_admin():
            senha = senha_temporaria()
            contas.cadastrar("Administrador", email, senha, interno=True)
            print(f"Conta de administrador criada. Senha temporária: {senha}")
            return
        print(f"Senha temporária de {email}: {contas.redefinir_senha(email)}")
    else:
        for u in contas.listar():
            validade = f"{u.validade:%d/%m/%Y}" if u.validade else "-"
            print(f"{u.email:35} {STATUS[u.status]:22} {PLANOS[u.plano]:10} até {validade}")


if __name__ == "__main__":
    main()
