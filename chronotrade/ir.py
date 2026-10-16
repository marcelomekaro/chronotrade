"""Imposto de renda na bolsa: day trade e swing trade (operações comuns), mês a mês.

Regras em vigor em 2026 (a MP 1.303/2025, que unificaria tudo em 17,5%, caiu no Congresso):

- **Swing trade (operação comum)**: 15% sobre o lucro líquido do mês. Ações à vista têm isenção quando o total
  **vendido** em ações no mês fica em até R$ 20.000 (vale o valor das vendas, não o lucro). ETFs e BDRs não têm
  essa isenção. IRRF ("dedo-duro") de 0,005% sobre o valor das vendas.
- **Day trade**: 20% sobre o lucro líquido do mês, sem isenção. IRRF de 1% sobre o lucro de cada dia positivo.
- **Fundos imobiliários (FII)**: 20% sobre o lucro na venda de cotas, sem isenção (os rendimentos mensais seguem
  isentos para a pessoa física, nas condições da lei).
- **Prejuízos** ficam guardados e só abatem lucros da mesma modalidade: day trade com day trade, operação comum
  com operação comum, FII com FII.
- **DARF código 6015**, pago até o último dia útil do mês seguinte. Imposto abaixo de R$ 10 não se paga no mês:
  acumula até passar de R$ 10.

É uma calculadora de estudo e conferência. Confirme com um contador e com a Receita Federal antes de pagar.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

ALIQUOTA = {"comum": 0.15, "day": 0.20, "fii": 0.20}
NOMES = {"comum": "Swing trade (operações comuns)", "day": "Day trade", "fii": "Fundos imobiliários"}
ISENCAO_VENDAS_ACOES = 20_000.0
IRRF_COMUM = 0.00005
IRRF_DAY = 0.01
DARF_MINIMO = 10.0
CODIGO_DARF = "6015"


@dataclass
class Operacao:
    data: date
    ticker: str
    lado: str                  # "compra" ou "venda"
    quantidade: float
    preco: float
    classe: str = "Ação"       # Ação, FII, ETF, BDR
    taxas: float = 0.0         # corretagem + emolumentos dessa operação

    @property
    def valor(self) -> float:
        return self.quantidade * self.preco


@dataclass
class Resultado:
    """Um resultado realizado (venda ou day trade)."""
    data: date
    ticker: str
    classe: str
    modalidade: str            # comum, day, fii
    quantidade: float
    venda: float               # valor vendido
    custo: float               # custo do que foi vendido (com taxas)
    lucro: float


@dataclass
class Mes:
    mes: str                   # "2026-03"
    vendas_acoes: float = 0.0  # vendas comuns de ações (para a isenção de R$ 20 mil)
    isento: bool = False
    lucro: dict = field(default_factory=lambda: {"comum": 0.0, "day": 0.0, "fii": 0.0})
    lucro_isento: float = 0.0  # lucro de ações que ficou isento
    prejuizo_usado: dict = field(default_factory=lambda: {"comum": 0.0, "day": 0.0, "fii": 0.0})
    base: dict = field(default_factory=lambda: {"comum": 0.0, "day": 0.0, "fii": 0.0})
    imposto: dict = field(default_factory=lambda: {"comum": 0.0, "day": 0.0, "fii": 0.0})
    irrf: dict = field(default_factory=lambda: {"comum": 0.0, "day": 0.0, "fii": 0.0})
    prejuizo_acumulado: dict = field(default_factory=lambda: {"comum": 0.0, "day": 0.0, "fii": 0.0})
    devido: float = 0.0        # imposto do mês depois do IRRF
    acumulado_anterior: float = 0.0
    darf: float = 0.0          # o que pagar neste DARF (0 se abaixo de R$ 10)
    vencimento: date | None = None


@dataclass
class Apuracao:
    meses: list[Mes]
    resultados: list[Resultado]
    posicoes: dict[str, tuple[float, float]]   # ticker -> (quantidade, preço médio)
    avisos: list[str]

    @property
    def total_darf(self) -> float:
        return round(sum(m.darf for m in self.meses), 2)


def modalidade(classe: str, day_trade: bool) -> str:
    if classe == "FII":
        return "fii"
    return "day" if day_trade else "comum"


def ultimo_dia_util(ano: int, mes: int) -> date:
    """Último dia útil (segunda a sexta) do mês. Feriados não entram: confira no calendário da Receita."""
    proximo = date(ano + (mes == 12), mes % 12 + 1, 1)
    d = proximo - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def vencimento_darf(mes: str) -> date:
    ano, m = map(int, mes.split("-"))
    return ultimo_dia_util(ano + (m == 12), m % 12 + 1)


def apurar(operacoes: list[Operacao], prejuizos_iniciais: dict[str, float] | None = None,
           posicoes_iniciais: dict[str, tuple[float, float]] | None = None) -> Apuracao:
    """Calcula preço médio, separa day trade de operação comum e apura o imposto de cada mês."""
    posicoes: dict[str, list[float]] = {k: [q, pm] for k, (q, pm) in (posicoes_iniciais or {}).items()}
    resultados: list[Resultado] = []
    avisos: list[str] = []
    classe_de: dict[str, str] = {}
    irrf_por_mes: dict[str, dict[str, float]] = defaultdict(lambda: {"comum": 0.0, "day": 0.0, "fii": 0.0})
    vendas_acoes_mes: dict[str, float] = defaultdict(float)

    por_dia: dict[tuple[date, str], list[Operacao]] = defaultdict(list)
    for op in sorted(operacoes, key=lambda o: o.data):
        tk = op.ticker.upper().replace(".SA", "")
        classe_de[tk] = op.classe
        por_dia[(op.data, tk)].append(op)

    for (dia, tk), ops in sorted(por_dia.items()):
        classe = classe_de[tk]
        compras = [o for o in ops if o.lado == "compra"]
        vendas = [o for o in ops if o.lado == "venda"]
        qc, qv = sum(o.quantidade for o in compras), sum(o.quantidade for o in vendas)
        vc = sum(o.valor for o in compras) + sum(o.taxas for o in compras)   # custo inclui taxas
        vv = sum(o.valor for o in vendas) - sum(o.taxas for o in vendas)     # venda líquida de taxas
        pc = vc / qc if qc else 0.0
        pv = vv / qv if qv else 0.0
        mes = f"{dia:%Y-%m}"
        # 1. Day trade: a parte comprada e vendida no mesmo dia
        qdt = min(qc, qv)
        if qdt > 0:
            mod = modalidade(classe, True)
            lucro = qdt * (pv - pc)
            resultados.append(Resultado(dia, tk, classe, mod, qdt, qdt * pv, qdt * pc, lucro))
            if lucro > 0 and mod == "day":
                irrf_por_mes[mes]["day"] += lucro * IRRF_DAY
        # 2. Sobra de compra entra na posição; sobra de venda é operação comum contra o preço médio
        pos = posicoes.setdefault(tk, [0.0, 0.0])
        sobra_venda = qv - qdt
        if sobra_venda > 0:
            if pos[0] <= 0:
                avisos.append(f"{dia:%d/%m/%Y} {tk}: venda de {sobra_venda:g} sem posição anterior. "
                              "Informe a posição inicial (quantidade e preço médio) para o cálculo ficar certo.")
                custo_unit = pv  # sem custo conhecido: resultado zero
            else:
                custo_unit = pos[1]
            vendida = min(sobra_venda, pos[0]) if pos[0] > 0 else sobra_venda
            mod = modalidade(classe, False)
            lucro = sobra_venda * (pv - custo_unit)
            resultados.append(Resultado(dia, tk, classe, mod, sobra_venda, sobra_venda * pv, sobra_venda * custo_unit,
                                        lucro))
            if classe == "Ação":
                vendas_acoes_mes[mes] += sobra_venda * pv
            irrf_por_mes[mes][mod] += sobra_venda * pv * IRRF_COMUM
            pos[0] = max(0.0, pos[0] - vendida)
            if pos[0] == 0:
                pos[1] = 0.0
        sobra_compra = qc - qdt
        if sobra_compra > 0:
            total = pos[0] * pos[1] + sobra_compra * pc
            pos[0] += sobra_compra
            pos[1] = total / pos[0]

    # 3. Apuração mensal
    prejuizo = {"comum": 0.0, "day": 0.0, "fii": 0.0}
    for k, v in (prejuizos_iniciais or {}).items():
        prejuizo[k] = abs(float(v))
    meses_resultado: dict[str, list[Resultado]] = defaultdict(list)
    for r in resultados:
        meses_resultado[f"{r.data:%Y-%m}"].append(r)
    meses: list[Mes] = []
    acumulado = 0.0
    for mes in sorted(set(meses_resultado) | set(irrf_por_mes)):
        m = Mes(mes)
        m.vendas_acoes = round(vendas_acoes_mes.get(mes, 0.0), 2)
        m.isento = m.vendas_acoes <= ISENCAO_VENDAS_ACOES
        for r in meses_resultado.get(mes, []):
            if r.modalidade == "comum" and r.classe == "Ação" and m.isento and r.lucro > 0:
                m.lucro_isento += r.lucro
                continue
            m.lucro[r.modalidade] += r.lucro
        for k in ALIQUOTA:
            lucro = m.lucro[k]
            if lucro < 0:
                prejuizo[k] += -lucro
                continue
            usado = min(prejuizo[k], lucro)
            prejuizo[k] -= usado
            m.prejuizo_usado[k] = usado
            m.base[k] = lucro - usado
            m.imposto[k] = round(m.base[k] * ALIQUOTA[k], 2)
        irrf = irrf_por_mes.get(mes, {})
        for k in ALIQUOTA:
            m.irrf[k] = round(irrf.get(k, 0.0), 2) if m.imposto[k] > 0 or k == "day" else 0.0
        # IRRF de swing abaixo de R$ 1 é dispensado pela corretora
        if 0 < irrf.get("comum", 0) + irrf.get("fii", 0) < 1:
            m.irrf["comum"] = m.irrf["fii"] = 0.0
        m.prejuizo_acumulado = {k: round(v, 2) for k, v in prejuizo.items()}
        devido = sum(max(0.0, m.imposto[k] - m.irrf[k]) for k in ALIQUOTA)
        m.devido = round(devido, 2)
        m.acumulado_anterior = round(acumulado, 2)
        total = devido + acumulado
        if total >= DARF_MINIMO:
            m.darf, acumulado = round(total, 2), 0.0
        else:
            m.darf, acumulado = 0.0, total
        m.vencimento = vencimento_darf(mes)
        meses.append(m)
    return Apuracao(meses, resultados, {k: (round(v[0], 6), round(v[1], 6)) for k, v in posicoes.items() if v[0] > 0},
                    avisos)


def ler_planilha(df) -> list[Operacao]:
    """Lê operações de uma tabela (CSV/Excel da área do investidor da B3 ou do próprio app).

    Colunas aceitas (sem diferenciar maiúsculas): data / data do negócio; tipo / tipo de movimentação / lado
    (compra, venda, c, v); ticker / código de negociação / ativo; quantidade; preço; taxas (opcional);
    classe (opcional).
    """
    import pandas as pd

    def achar(*nomes):
        for col in df.columns:
            n = str(col).strip().lower()
            if any(n == x or n.startswith(x) for x in nomes):
                return col
        return None

    c_data = achar("data do negócio", "data do negocio", "data")
    c_lado = achar("tipo de movimentação", "tipo de movimentacao", "tipo", "lado", "operação", "operacao", "c/v")
    c_tk = achar("código de negociação", "codigo de negociacao", "ticker", "ativo", "código", "codigo", "papel")
    c_qtd = achar("quantidade", "qtd", "qtde")
    c_preco = achar("preço", "preco")
    c_taxas = achar("taxas", "custos")
    c_classe = achar("classe")
    if not all([c_data, c_lado, c_tk, c_qtd, c_preco]):
        raise ValueError("A planilha precisa das colunas: data, tipo (compra ou venda), ativo, quantidade e preço.")

    def numero(v) -> float:
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).replace("R$", "").strip()
        if "," in s:
            s = s.replace(".", "").replace(",", ".")
        return float(s or 0)

    ops = []
    for _, ln in df.iterrows():
        lado_txt = str(ln[c_lado]).strip().lower()
        if not lado_txt or lado_txt == "nan":
            continue
        lado = "venda" if lado_txt.startswith(("v", "s")) else "compra"
        tk = str(ln[c_tk]).strip().upper().replace(".SA", "")
        if tk.endswith("F") and len(tk) >= 6 and tk[-2].isdigit():   # mercado fracionário: PETR4F → PETR4
            tk = tk[:-1]
        data = pd.to_datetime(ln[c_data], dayfirst=True).date()
        classe = str(ln[c_classe]).strip() if c_classe and str(ln[c_classe]).strip() not in ("", "nan") else "Ação"
        ops.append(Operacao(data, tk, lado, numero(ln[c_qtd]), numero(ln[c_preco]), classe,
                            numero(ln[c_taxas]) if c_taxas else 0.0))
    return ops


# ---------------------------------------------------------------------------
# Lembretes do DARF (o agente Sentinela avisa perto do vencimento)
# ---------------------------------------------------------------------------


class Lembretes:
    def __init__(self, caminho):
        self.caminho = Path(caminho)
        with self._con() as con:
            con.execute("CREATE TABLE IF NOT EXISTS darf_lembretes (email TEXT NOT NULL, mes TEXT NOT NULL, "
                        "valor REAL NOT NULL, vencimento TEXT NOT NULL, avisado INTEGER NOT NULL DEFAULT 0, "
                        "PRIMARY KEY (email, mes))")

    @contextmanager
    def _con(self):
        con = sqlite3.connect(self.caminho, timeout=10)
        con.row_factory = sqlite3.Row
        try:
            yield con
            con.commit()
        finally:
            con.close()

    def guardar(self, email: str, apuracao: Apuracao) -> int:
        """Guarda os DARFs a pagar (valor > 0) para o agente lembrar. Devolve quantos."""
        n = 0
        with self._con() as con:
            for m in apuracao.meses:
                if m.darf > 0:
                    con.execute("INSERT INTO darf_lembretes (email, mes, valor, vencimento) VALUES (?, ?, ?, ?) "
                                "ON CONFLICT(email, mes) DO UPDATE SET valor = excluded.valor, "
                                "vencimento = excluded.vencimento", (email, m.mes, m.darf, m.vencimento.isoformat()))
                    n += 1
        return n

    def a_avisar(self, email: str, hoje: date, antecedencia: int = 5) -> list[tuple[str, float, date]]:
        with self._con() as con:
            linhas = con.execute("SELECT mes, valor, vencimento FROM darf_lembretes WHERE email = ? AND avisado = 0",
                                 (email,)).fetchall()
        saida = []
        for ln in linhas:
            venc = date.fromisoformat(ln["vencimento"])
            if hoje <= venc <= hoje + timedelta(days=antecedencia):
                saida.append((ln["mes"], ln["valor"], venc))
        return saida

    def marcar_avisado(self, email: str, mes: str) -> None:
        with self._con() as con:
            con.execute("UPDATE darf_lembretes SET avisado = 1 WHERE email = ? AND mes = ?", (email, mes))

    def listar(self, email: str) -> list[dict]:
        with self._con() as con:
            return [dict(x) for x in con.execute("SELECT * FROM darf_lembretes WHERE email = ? ORDER BY mes",
                                                 (email,)).fetchall()]

    def apagar_dados(self, email: str) -> None:
        with self._con() as con:
            con.execute("DELETE FROM darf_lembretes WHERE email = ?", (email,))
