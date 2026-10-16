"""Simulador de mercado: testes de estresse, simulação de intenções e futuros possíveis.

Três perguntas que o investidor de buy and hold faz:

1. **Estresse:** "e se vier uma crise como a de 2008 ou a da Covid?" Aplica à carteira de hoje
   as quedas aproximadas de crises que a B3 já viveu, ajustadas pela sensibilidade (beta) de cada
   ação ao Ibovespa, e mostra o que acontece com quem continua aportando.
2. **Intenções:** "e se eu comprar 100 TAEE11 e vender 50 BBAS3?" Mostra a carteira antes e depois:
   peso de cada ativo, concentração, renda de proventos e o impacto numa crise.
3. **Futuros possíveis:** milhares de caminhos sorteados a partir dos retornos reais da carteira
   (bootstrap), com a faixa do provável e a chance de terminar no prejuízo.

Os números das crises são aproximações de quedas do topo ao fundo, para estudo. Não são previsão
e não são recomendação de investimento.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

CLASSES = ("Ação", "FII", "ETF", "BDR", "Outro")


@dataclass(frozen=True)
class Cenario:
    nome: str
    quando: str
    historia: str
    choques: dict[str, float]          # queda (negativo) ou alta por classe, do topo ao fundo
    corte_proventos: float = 0.0       # quanto os proventos caíram no período (0,25 = 25% menos)
    meses_queda: int = 1               # quanto tempo levou até o fundo
    meses_recuperacao: int = 6         # quanto tempo o Ibovespa levou para voltar ao topo
    usar_beta: bool = True             # ajustar ações e ETFs pela sensibilidade ao Ibovespa


CENARIOS: dict[str, Cenario] = {
    "covid": Cenario(
        "Covid-19", "fevereiro a março de 2020",
        "O mundo parou. O Ibovespa caiu quase 47% em cinco semanas, com seis circuit breakers em março. "
        "Em dez meses ele já tinha voltado ao topo.",
        {"Ação": -0.47, "FII": -0.32, "ETF": -0.47, "BDR": -0.16, "Outro": -0.30},
        corte_proventos=0.25, meses_queda=1, meses_recuperacao=10),
    "crise_2008": Cenario(
        "Crise financeira global", "maio a outubro de 2008",
        "A quebra do Lehman Brothers travou o crédito no mundo. O Ibovespa foi de 73 mil para 29 mil pontos "
        "(-60%) e o dólar saltou 45%. A volta ao topo levou cerca de dois anos.",
        {"Ação": -0.60, "FII": -0.30, "ETF": -0.60, "BDR": -0.13, "Outro": -0.40},
        corte_proventos=0.20, meses_queda=5, meses_recuperacao=25),
    "recessao_2015": Cenario(
        "Recessão e crise fiscal", "2015 a janeiro de 2016",
        "PIB encolhendo, Selic a 14,25% e perda do grau de investimento. O Ibovespa caiu cerca de 40% "
        "e o dólar passou de R$ 4, o que fez os BDRs subirem em reais.",
        {"Ação": -0.40, "FII": -0.20, "ETF": -0.40, "BDR": 0.30, "Outro": -0.25},
        corte_proventos=0.30, meses_queda=16, meses_recuperacao=13),
    "juros_2022": Cenario(
        "Choque de juros", "2021 a 2022",
        "A Selic subiu de 2% para 13,75%. A renda fixa ficou mais atraente, o Ibovespa caiu cerca de 25% "
        "do topo e os fundos imobiliários de tijolo sofreram.",
        {"Ação": -0.25, "FII": -0.15, "ETF": -0.25, "BDR": -0.22, "Outro": -0.10},
        corte_proventos=0.05, meses_queda=13, meses_recuperacao=16),
    "greve_2018": Cenario(
        "Greve dos caminhoneiros", "maio a junho de 2018",
        "Dez dias de estradas paradas e incerteza eleitoral. O Ibovespa caiu cerca de 19% em seis semanas "
        "e o dólar subiu.",
        {"Ação": -0.19, "FII": -0.10, "ETF": -0.19, "BDR": 0.08, "Outro": -0.08},
        corte_proventos=0.0, meses_queda=2, meses_recuperacao=5),
    "joesley": Cenario(
        "Joesley Day", "18 de maio de 2017",
        "A divulgação de uma gravação envolvendo o presidente derrubou o Ibovespa 8,8% num só dia, com "
        "circuit breaker. Em cerca de dois meses o índice voltou.",
        {"Ação": -0.09, "FII": -0.03, "ETF": -0.09, "BDR": 0.07, "Outro": -0.04},
        corte_proventos=0.0, meses_queda=0, meses_recuperacao=2),
}


def cenario_livre(acoes: float, fiis: float, exterior: float, corte_proventos: float = 0.0,
                  meses_queda: int = 3, meses_recuperacao: int = 12) -> Cenario:
    """Monte a sua própria crise: quedas por tipo de ativo (em fração, -0,3 = -30%)."""
    return Cenario("Cenário próprio", "você escolheu", "Quedas definidas por você.",
                   {"Ação": acoes, "FII": fiis, "ETF": acoes, "BDR": exterior, "Outro": (acoes + fiis) / 2},
                   corte_proventos=corte_proventos, meses_queda=meses_queda,
                   meses_recuperacao=meses_recuperacao)


# ---------------------------------------------------------------------------
# Sensibilidade ao Ibovespa
# ---------------------------------------------------------------------------


def beta(historico: pd.Series | None, indice: pd.Series | None, minimo_pontos: int = 120,
         limites: tuple[float, float] = (0.4, 1.6)) -> float:
    """Quanto o ativo costuma andar quando o Ibovespa anda 1%. Sem dados suficientes, 1."""
    if historico is None or indice is None or len(historico) < minimo_pontos or len(indice) < minimo_pontos:
        return 1.0
    a = _sem_fuso(historico).pct_change()
    b = _sem_fuso(indice).pct_change()
    juntos = pd.concat([a, b], axis=1, join="inner").dropna().tail(252)
    if len(juntos) < minimo_pontos or juntos.iloc[:, 1].var() == 0:
        return 1.0
    valor = float(juntos.cov().iloc[0, 1] / juntos.iloc[:, 1].var())
    if not np.isfinite(valor):
        return 1.0
    return round(min(limites[1], max(limites[0], valor)), 2)


def _sem_fuso(s: pd.Series) -> pd.Series:
    s = s.dropna()
    idx = pd.to_datetime(s.index)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)
    return pd.Series(s.values, index=idx.normalize()).groupby(level=0).last()


# ---------------------------------------------------------------------------
# Estresse
# ---------------------------------------------------------------------------


@dataclass
class ResultadoEstresse:
    cenario: Cenario
    por_ativo: pd.DataFrame        # ativo, classe, valor, beta, choque, valor_depois, perda
    antes: float
    depois: float
    caixa: float
    renda_antes: float             # proventos em 12 meses, hoje
    renda_depois: float            # com o corte do cenário
    caminho: pd.DataFrame          # mes, sem_aporte, com_aporte, aportado
    ganho_aportando: float         # quanto a mais quem aportou na crise tem na volta, comparado a sem crise
    desconto_medio: float          # quão mais barato, em média, saíram as compras na crise

    @property
    def perda(self) -> float:
        return self.depois - self.antes

    @property
    def queda(self) -> float:
        investido = self.antes - self.caixa
        return (self.depois - self.antes) / investido if investido else 0.0


def choque_do_ativo(classe: str, b: float, cenario: Cenario) -> float:
    base = cenario.choques.get(classe, cenario.choques.get("Outro", 0.0))
    if cenario.usar_beta and classe in ("Ação", "ETF") and base < 0:
        return max(-0.95, base * b)
    return base


def trajetoria(choque: float, meses_queda: int, meses_recuperacao: int, depois: int = 12,
               alta_mensal: float = 0.005) -> np.ndarray:
    """Nível do mercado mês a mês (1 = hoje): desce até o fundo, volta ao topo e segue crescendo."""
    fundo = max(0.05, 1 + choque)
    pontos = [1.0]
    q = max(meses_queda, 0)
    for m in range(1, q + 1):
        pontos.append(float(np.exp(np.log(fundo) * m / q)))
    if q == 0:
        pontos.append(fundo)  # queda num dia só: o mês seguinte já começa no fundo
    r = max(meses_recuperacao, 1)
    for m in range(1, r + 1):
        pontos.append(float(np.exp(np.log(fundo) * (1 - m / r))))
    for _ in range(depois):
        pontos.append(pontos[-1] * (1 + alta_mensal))
    return np.array(pontos)


def estresse(posicoes: list[dict], cenario: Cenario, caixa: float = 0.0, aporte_mensal: float = 0.0) -> ResultadoEstresse:
    """posicoes: [{ativo, classe, valor, renda_12m, beta}]."""
    linhas = []
    for p in posicoes:
        b = float(p.get("beta") or 1.0)
        ch = choque_do_ativo(p.get("classe") or "Outro", b, cenario)
        valor = float(p.get("valor") or 0.0)
        linhas.append({"ativo": p["ativo"], "classe": p.get("classe") or "Outro", "valor": valor, "beta": b,
                       "choque": ch, "valor_depois": valor * (1 + ch), "perda": valor * ch,
                       "renda_12m": float(p.get("renda_12m") or 0.0)})
    tabela = pd.DataFrame(linhas, columns=["ativo", "classe", "valor", "beta", "choque", "valor_depois", "perda",
                                           "renda_12m"])
    investido = float(tabela["valor"].sum()) if not tabela.empty else 0.0
    depois_inv = float(tabela["valor_depois"].sum()) if not tabela.empty else 0.0
    queda_total = (depois_inv / investido - 1) if investido else 0.0
    renda = float(tabela["renda_12m"].sum()) if not tabela.empty else 0.0

    nivel = trajetoria(queda_total, cenario.meses_queda, cenario.meses_recuperacao)
    unidades = investido  # 1 unidade = R$ 1 no nível de hoje
    sem, com, aportado = [], [], []
    total_aportado = 0.0
    precos_pagos = []
    for mes, n in enumerate(nivel):
        if mes > 0 and aporte_mensal > 0:
            unidades += aporte_mensal / n
            total_aportado += aporte_mensal
            precos_pagos.append(n)
        sem.append(investido * n + caixa)
        com.append(unidades * n + caixa)
        aportado.append(investido + total_aportado + caixa)
    caminho = pd.DataFrame({"mes": range(len(nivel)), "sem_aporte": sem, "com_aporte": com, "aportado": aportado})
    volta = max(cenario.meses_queda, 1) + max(cenario.meses_recuperacao, 1)
    ganho = (unidades_ate(nivel, investido, aporte_mensal, volta) - (investido + aporte_mensal * volta)) if aporte_mensal else 0.0
    desconto = 1 - float(np.mean(precos_pagos[:volta])) if precos_pagos else 0.0
    return ResultadoEstresse(cenario, tabela, investido + caixa, depois_inv + caixa, caixa, renda,
                             renda * (1 - cenario.corte_proventos), caminho, max(ganho, 0.0), max(desconto, 0.0))


def unidades_ate(nivel: np.ndarray, inicial: float, aporte: float, ate_mes: int) -> float:
    """Valor da carteira no mês da volta ao topo (nível 1) para quem aportou todo mês."""
    unidades = inicial
    for mes in range(1, min(ate_mes, len(nivel) - 1) + 1):
        unidades += aporte / nivel[mes]
    return unidades * nivel[min(ate_mes, len(nivel) - 1)]


def todos_os_cenarios(posicoes: list[dict], caixa: float = 0.0) -> pd.DataFrame:
    """Um resumo por cenário, para comparar as crises lado a lado."""
    linhas = []
    for chave, c in CENARIOS.items():
        r = estresse(posicoes, c, caixa)
        linhas.append({"chave": chave, "cenario": c.nome, "quando": c.quando, "queda": r.queda, "perda": r.perda,
                       "renda_depois": r.renda_depois, "meses_volta": c.meses_queda + c.meses_recuperacao})
    return pd.DataFrame(linhas)


# ---------------------------------------------------------------------------
# Intenções: e se eu comprar ou vender?
# ---------------------------------------------------------------------------


@dataclass
class Intencao:
    ticker: str           # código curto, ex.: TAEE11
    lado: str             # "compra" ou "venda"
    quantidade: float
    preco: float | None = None  # None = preço de agora
    classe: str = "Ação"


@dataclass
class ResultadoIntencao:
    antes: pd.DataFrame          # ativo, classe, quantidade, preco_medio, preco, valor, peso, renda_12m
    depois: pd.DataFrame
    custo: float                 # dinheiro que sai (compra) ou entra (venda, negativo)
    caixa_antes: float
    caixa_depois: float
    avisos: list[str] = field(default_factory=list)

    def resumo(self, momento: str) -> dict:
        t = self.antes if momento == "antes" else self.depois
        caixa = self.caixa_antes if momento == "antes" else self.caixa_depois
        valor = float(t["valor"].sum()) if not t.empty else 0.0
        renda = float(t["renda_12m"].sum()) if not t.empty else 0.0
        pesos = t["valor"] / valor if valor else pd.Series(dtype=float)
        maior = t.loc[pesos.idxmax()] if len(pesos) else None
        return {"investido": valor, "caixa": caixa, "patrimonio": valor + caixa, "renda_12m": renda,
                "renda_mes": renda / 12, "dy": renda / valor if valor else None, "ativos": int((t["quantidade"] > 0).sum()),
                "maior_ativo": maior["ativo"] if maior is not None else "",
                "maior_peso": float(pesos.max()) if len(pesos) else 0.0,
                "concentracao": float((pesos ** 2).sum()) if len(pesos) else 0.0,
                "por_classe": (t.groupby("classe")["valor"].sum() / valor).to_dict() if valor else {}}


def simular_intencoes(carteira_atual: list[dict], intencoes: list[Intencao], precos: dict[str, float],
                      proventos_acao: dict[str, float], caixa: float = 0.0) -> ResultadoIntencao:
    """carteira_atual: [{ativo, classe, quantidade, preco_medio}]; precos e proventos_acao por código curto."""
    pos = {p["ativo"]: dict(p) for p in carteira_atual}
    avisos: list[str] = []
    custo = 0.0
    for it in intencoes:
        tk = it.ticker.upper().replace(".SA", "")
        preco = it.preco or precos.get(tk)
        if not preco or it.quantidade <= 0:
            avisos.append(f"{tk}: sem preço ou quantidade, ficou de fora.")
            continue
        atual = pos.get(tk) or {"ativo": tk, "classe": it.classe, "quantidade": 0.0, "preco_medio": 0.0}
        if it.lado == "venda":
            qtd = min(it.quantidade, atual["quantidade"])
            if qtd < it.quantidade:
                avisos.append(f"{tk}: você tem {atual['quantidade']:g}, a venda foi limitada a isso.")
            atual["quantidade"] -= qtd
            custo -= qtd * preco
        else:
            total = atual["quantidade"] * atual["preco_medio"] + it.quantidade * preco
            atual["quantidade"] += it.quantidade
            atual["preco_medio"] = total / atual["quantidade"]
            custo += it.quantidade * preco
        pos[tk] = atual
        precos.setdefault(tk, preco)

    def tabela(posicoes) -> pd.DataFrame:
        linhas = []
        for p in posicoes:
            if p["quantidade"] <= 0:
                continue
            preco = precos.get(p["ativo"]) or p["preco_medio"]
            linhas.append({"ativo": p["ativo"], "classe": p["classe"], "quantidade": p["quantidade"],
                           "preco_medio": p["preco_medio"], "preco": preco, "valor": p["quantidade"] * preco,
                           "renda_12m": p["quantidade"] * proventos_acao.get(p["ativo"], 0.0)})
        t = pd.DataFrame(linhas, columns=["ativo", "classe", "quantidade", "preco_medio", "preco", "valor", "renda_12m"])
        total = t["valor"].sum() if not t.empty else 0
        t["peso"] = t["valor"] / total if total else 0.0
        return t.sort_values("valor", ascending=False).reset_index(drop=True)

    caixa_depois = caixa - custo
    if caixa_depois < 0:
        avisos.append("O caixa não cobre tudo: faltariam " + _brl(-caixa_depois) + ". Considere o aporte do mês.")
    return ResultadoIntencao(tabela(carteira_atual), tabela(pos.values()), custo, caixa, caixa_depois, avisos)


def _brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ---------------------------------------------------------------------------
# Futuros possíveis (Monte Carlo por blocos)
# ---------------------------------------------------------------------------


@dataclass
class Futuros:
    meses: list[int]
    faixas: pd.DataFrame           # mes, p5, p25, p50, p75, p95
    chance_prejuizo: float         # chance de terminar abaixo do que foi investido
    pior_mes_95: float             # perda de um mês ruim (1 em 20)
    aportado: float


def retornos_carteira(historicos: dict[str, pd.Series], pesos: dict[str, float], dias: int = 504) -> pd.Series:
    """Retorno diário da carteira com os pesos de hoje, usando os históricos de cada ativo."""
    series = []
    for ativo, peso in pesos.items():
        h = historicos.get(ativo)
        if h is None or len(h) < 30 or not peso:
            continue
        series.append(_sem_fuso(h).pct_change().rename(ativo) * peso)
    if not series:
        return pd.Series(dtype=float)
    df = pd.concat(series, axis=1).tail(dias).dropna(how="all").fillna(0.0)
    total = sum(p for a, p in pesos.items() if a in df.columns)
    return (df.sum(axis=1) / total).dropna() if total else pd.Series(dtype=float)


def simular_futuros(retornos: pd.Series, valor: float, meses: int = 12, aporte_mensal: float = 0.0,
                    caminhos: int = 2000, semente: int = 7) -> Futuros | None:
    r = retornos.dropna().to_numpy()
    if len(r) < 60 or valor <= 0:
        return None
    gerador = np.random.default_rng(semente)
    bloco = 21
    inicios = gerador.integers(0, len(r) - bloco, size=(caminhos, meses))
    mensal = np.prod(1 + r[inicios[..., None] + np.arange(bloco)], axis=2) - 1  # caminhos x meses
    valores = np.empty((caminhos, meses + 1))
    valores[:, 0] = valor
    for m in range(meses):
        valores[:, m + 1] = valores[:, m] * (1 + mensal[:, m]) + aporte_mensal
    q = np.percentile(valores, [5, 25, 50, 75, 95], axis=0)
    faixas = pd.DataFrame({"mes": range(meses + 1), "p5": q[0], "p25": q[1], "p50": q[2], "p75": q[3], "p95": q[4]})
    aportado = valor + aporte_mensal * meses
    return Futuros(list(range(meses + 1)), faixas, float((valores[:, -1] < aportado).mean()),
                   float(np.percentile(mensal[:, 0], 5)), aportado)
