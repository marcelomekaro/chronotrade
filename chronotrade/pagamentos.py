"""Cobranças com liberação automática.

Com ``MERCADOPAGO_ACCESS_TOKEN`` no .env, cada cobrança vira um PIX do Mercado Pago
(API de Orders): o app mostra o QR Code, consulta o pagamento e, quando ele é
creditado, libera ou renova a conta sozinho, sem o administrador precisar fazer
nada. O dinheiro cai na sua conta do Mercado Pago.

Sem o token, o app usa o PIX estático com a sua chave (marcelomekaro@gmail.com por
padrão): funciona em qualquer banco, mas a liberação é feita pelo administrador.
"""

from __future__ import annotations

import json
import os
import sqlite3
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

API = "https://api.mercadopago.com/v1/orders"
PAGO = {("processed", "accredited"), ("processed", "partially_refunded")}
ENCERRADO = {"expired", "canceled", "failed", "refunded"}

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS cobrancas (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL,
    plano TEXT NOT NULL,
    periodo TEXT NOT NULL,
    dias INTEGER NOT NULL,
    valor REAL NOT NULL,
    qr_texto TEXT,
    qr_base64 TEXT,
    status TEXT NOT NULL,
    criado_em TEXT NOT NULL,
    liberado_em TEXT
);
"""


def automatico() -> bool:
    return bool(os.environ.get("MERCADOPAGO_ACCESS_TOKEN"))


@dataclass
class Cobranca:
    id: str
    email: str
    plano: str
    periodo: str
    dias: int
    valor: float
    qr_texto: str
    qr_base64: str
    status: str
    criado_em: datetime
    liberado_em: datetime | None

    @property
    def paga(self) -> bool:
        return self.liberado_em is not None


Requisicao = Callable[[str, str, dict | None, dict], dict]


def _requisitar(metodo: str, url: str, corpo: dict | None, cabecalhos: dict) -> dict:
    dados = json.dumps(corpo).encode() if corpo is not None else None
    pedido = urllib.request.Request(url, data=dados, method=metodo, headers=cabecalhos)
    try:
        with urllib.request.urlopen(pedido, timeout=20) as resposta:
            return json.loads(resposta.read().decode())
    except urllib.error.HTTPError as erro:
        detalhe = erro.read().decode(errors="replace")[:300]
        raise RuntimeError(f"Mercado Pago recusou o pedido ({erro.code}): {detalhe}") from erro


class Cobrancas:
    def __init__(self, caminho: Path, requisitar: Requisicao | None = None, token: str | None = None):
        self.caminho = Path(caminho)
        self.requisitar = requisitar or _requisitar
        self.token = token or os.environ.get("MERCADOPAGO_ACCESS_TOKEN", "")
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

    def _cabecalhos(self) -> dict:
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json",
                "Accept": "application/json", "X-Idempotency-Key": str(uuid.uuid4())}

    def _linha(self, ln) -> Cobranca:
        return Cobranca(ln["id"], ln["email"], ln["plano"], ln["periodo"], ln["dias"], ln["valor"],
                        ln["qr_texto"] or "", ln["qr_base64"] or "", ln["status"],
                        datetime.fromisoformat(ln["criado_em"]),
                        datetime.fromisoformat(ln["liberado_em"]) if ln["liberado_em"] else None)

    def aberta(self, email: str, plano: str, periodo: str) -> Cobranca | None:
        """Reaproveita uma cobrança ainda válida (até 23 horas) do mesmo plano, para não gerar várias."""
        with self._con() as con:
            ln = con.execute("SELECT * FROM cobrancas WHERE email = ? AND plano = ? AND periodo = ? "
                             "AND liberado_em IS NULL ORDER BY criado_em DESC LIMIT 1",
                             (email, plano, periodo)).fetchone()
        if ln is None:
            return None
        c = self._linha(ln)
        if c.status in ENCERRADO or (datetime.now() - c.criado_em).total_seconds() > 23 * 3600:
            return None
        return c

    def criar(self, email: str, plano: str, periodo: str, dias: int, valor: float, descricao: str) -> Cobranca:
        existente = self.aberta(email, plano, periodo)
        if existente:
            return existente
        corpo = {
            "type": "online", "processing_mode": "automatic",
            "total_amount": f"{valor:.2f}",
            "external_reference": f"chronotrade:{plano}:{periodo}:{email}"[:64],
            "description": descricao[:150],
            "payer": {"email": email},
            "transactions": {"payments": [{"amount": f"{valor:.2f}",
                                           "payment_method": {"id": "pix", "type": "bank_transfer"},
                                           "expiration_time": "P1D"}]},
        }
        resposta = self.requisitar("POST", API, corpo, self._cabecalhos())
        pagamento = (resposta.get("transactions", {}).get("payments") or [{}])[0]
        metodo = pagamento.get("payment_method", {})
        cobranca = Cobranca(str(resposta["id"]), email, plano, periodo, dias, valor,
                            metodo.get("qr_code", ""), metodo.get("qr_code_base64", ""),
                            resposta.get("status", "action_required"), datetime.now(), None)
        with self._con() as con:
            con.execute("INSERT INTO cobrancas VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)",
                        (cobranca.id, email, plano, periodo, dias, valor, cobranca.qr_texto, cobranca.qr_base64,
                         cobranca.status, cobranca.criado_em.isoformat(timespec="seconds")))
        return cobranca

    def consultar(self, id_: str) -> tuple[str, str]:
        resposta = self.requisitar("GET", f"{API}/{id_}", None, self._cabecalhos())
        return resposta.get("status", ""), resposta.get("status_detail", "")

    def pendentes(self) -> list[Cobranca]:
        with self._con() as con:
            linhas = con.execute("SELECT * FROM cobrancas WHERE liberado_em IS NULL").fetchall()
        return [self._linha(ln) for ln in linhas if ln["status"] not in ENCERRADO]

    def verificar(self, contas, so_email: str | None = None) -> list[Cobranca]:
        """Consulta as cobranças em aberto e libera as contas das que foram pagas. Devolve as liberadas."""
        liberadas = []
        for cob in self.pendentes():
            if so_email and cob.email != so_email:
                continue
            try:
                status, detalhe = self.consultar(cob.id)
            except Exception:
                continue  # sem internet ou erro momentâneo: tenta de novo no próximo ciclo
            with self._con() as con:
                con.execute("UPDATE cobrancas SET status = ? WHERE id = ?", (status, cob.id))
            if (status, detalhe) in PAGO:
                with self._con() as con:  # marca antes de liberar: uma cobrança nunca libera duas vezes
                    alterou = con.execute("UPDATE cobrancas SET liberado_em = ? WHERE id = ? AND liberado_em IS NULL",
                                          (datetime.now().isoformat(timespec="seconds"), cob.id)).rowcount
                if alterou:
                    contas.liberar(cob.email, cob.plano, cob.dias, valor=cob.valor, forma="PIX Mercado Pago",
                                   observacao=f"Liberado automaticamente (cobrança {cob.id})")
                    liberadas.append(cob)
        return liberadas

    def historico(self, email: str | None = None) -> list[Cobranca]:
        with self._con() as con:
            if email:
                linhas = con.execute("SELECT * FROM cobrancas WHERE email = ? ORDER BY criado_em DESC", (email,)).fetchall()
            else:
                linhas = con.execute("SELECT * FROM cobrancas ORDER BY criado_em DESC").fetchall()
        return [self._linha(ln) for ln in linhas]
