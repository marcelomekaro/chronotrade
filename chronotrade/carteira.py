"""A carteira do investidor: onde fica guardada e como vira uma tabela com números.

O arquivo fica em ``~/.chronotrade/carteira.json``, fora da pasta do projeto, para
nunca ir para o GitHub junto com o código.
"""

from __future__ import annotations

import io
import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

import pandas as pd

from chronotrade import calculos
from chronotrade.mercado import DadosAtivo, normalizar_ticker, parece_fii, ticker_curto

CLASSES = ["Ação", "FII", "ETF", "BDR", "Outro"]


def pasta_dados() -> Path:
    pasta = Path(os.environ.get("CHRONOTRADE_HOME") or Path.home() / ".chronotrade")
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


@dataclass
class Posicao:
    ticker: str
    quantidade: float
    preco_medio: float
    classe: str = "Ação"


@dataclass
class Carteira:
    posicoes: list[Posicao] = field(default_factory=list)
    caixa: float = 0.0
    aporte_mensal: float = 1000.0
    meta_renda_mensal: float = 3000.0
    taxa_bazin: float = 0.06
    margem_seguranca: float = 0.10
    metas_classe: dict[str, float] = field(
        default_factory=lambda: {"Ação": 50.0, "FII": 40.0, "ETF": 10.0, "BDR": 0.0, "Outro": 0.0})
    observar: list[str] = field(default_factory=list)  # ativos que você ainda não tem e quer acompanhar

    # -- persistência -------------------------------------------------------

    @classmethod
    def carregar(cls, caminho: Path | None = None) -> Carteira:
        caminho = caminho or pasta_dados() / "carteira.json"
        if not caminho.exists():
            return cls()
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        posicoes = [Posicao(**p) for p in dados.pop("posicoes", [])]
        conhecidos = {k: v for k, v in dados.items() if k in cls.__dataclass_fields__}
        return cls(posicoes=posicoes, **conhecidos)

    def salvar(self, caminho: Path | None = None) -> Path:
        caminho = caminho or pasta_dados() / "carteira.json"
        caminho.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
        return caminho

    # -- edição -------------------------------------------------------------

    def como_tabela_editavel(self) -> pd.DataFrame:
        linhas = [{"Ticker": ticker_curto(p.ticker), "Classe": p.classe,
                   "Quantidade": p.quantidade, "Preço médio": p.preco_medio} for p in self.posicoes]
        return pd.DataFrame(linhas, columns=["Ticker", "Classe", "Quantidade", "Preço médio"])

    def atualizar_de_tabela(self, tabela: pd.DataFrame) -> list[str]:
        """Substitui as posições pelas linhas editadas. Devolve os avisos encontrados."""
        avisos, novas, vistos = [], [], set()
        for _, linha in tabela.iterrows():
            bruto = str(linha.get("Ticker") or "").strip()
            if not bruto or bruto.lower() == "nan":
                continue
            ticker = normalizar_ticker(bruto)
            qtd = _float(linha.get("Quantidade"))
            pm = _float(linha.get("Preço médio"))
            if qtd is None or qtd <= 0:
                avisos.append(f"{bruto}: informe uma quantidade maior que zero.")
                continue
            if ticker in vistos:
                avisos.append(f"{bruto} aparece duas vezes; mantive só a primeira linha.")
                continue
            classe = linha.get("Classe") if linha.get("Classe") in CLASSES else (
                "FII" if parece_fii(ticker) else "Ação")
            vistos.add(ticker)
            novas.append(Posicao(ticker=ticker, quantidade=qtd, preco_medio=pm or 0.0, classe=classe))
        self.posicoes = novas
        return avisos

    def portfolio_context(self):
        """A carteira no formato que os agentes do TradingAgents entendem."""
        from tradingagents.portfolio import PortfolioContext

        return PortfolioContext.model_validate({
            "cash": self.caixa,
            "currency": "BRL",
            "positions": [{"ticker": p.ticker, "quantity": p.quantidade,
                           "average_price": p.preco_medio or None} for p in self.posicoes],
        })


def _float(valor) -> float | None:
    if valor is None:
        return None
    if isinstance(valor, str):
        valor = valor.strip().replace("R$", "").replace(" ", "")
        if "," in valor:
            valor = valor.replace(".", "").replace(",", ".")
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(v) else v


def ler_csv(conteudo: bytes) -> pd.DataFrame:
    """Lê uma planilha CSV de posições (ponto e vírgula ou vírgula; decimal com vírgula ou ponto)."""
    texto = conteudo.decode("utf-8-sig", errors="replace")
    sep = ";" if texto.count(";") >= texto.count(",") else ","
    df = pd.read_csv(io.StringIO(texto), sep=sep, dtype=str)
    nomes = {c: c.strip().lower() for c in df.columns}
    df = df.rename(columns=nomes)
    mapa = {}
    for c in df.columns:
        if c in ("ticker", "ativo", "código", "codigo", "papel"):
            mapa[c] = "Ticker"
        elif c.startswith("quant") or c == "qtd":
            mapa[c] = "Quantidade"
        elif "médio" in c or "medio" in c or c == "pm":
            mapa[c] = "Preço médio"
        elif c in ("classe", "tipo"):
            mapa[c] = "Classe"
    df = df.rename(columns=mapa)
    if "Ticker" not in df.columns or "Quantidade" not in df.columns:
        raise ValueError("A planilha precisa das colunas ticker e quantidade (preço médio e classe são opcionais).")
    for col in ("Preço médio", "Classe"):
        if col not in df.columns:
            df[col] = None
    return df[["Ticker", "Classe", "Quantidade", "Preço médio"]]


# ---------------------------------------------------------------------------
# Tabela com números
# ---------------------------------------------------------------------------


def montar_tabela(carteira: Carteira, dados: dict[str, DadosAtivo],
                  hoje: pd.Timestamp | None = None) -> pd.DataFrame:
    linhas = []
    for p in carteira.posicoes:
        d = dados.get(p.ticker)
        preco = d.preco if d and d.ok else None
        preco_uso = preco if preco is not None else p.preco_medio
        prov_12m = calculos.proventos_12m(d.dividendos, hoje) if d else 0.0
        media5 = calculos.media_anual_proventos(d.dividendos, 5, hoje) if d else 0.0
        custo = p.quantidade * p.preco_medio
        valor = p.quantidade * preco_uso
        linhas.append({
            "ticker": p.ticker,
            "ativo": ticker_curto(p.ticker),
            "nome": d.nome if d else "",
            "classe": p.classe,
            "quantidade": p.quantidade,
            "preco_medio": p.preco_medio,
            "preco": preco,
            "variacao_dia": d.variacao_dia if d else None,
            "custo": custo,
            "valor": valor,
            "resultado": valor - custo,
            "resultado_pct": (valor / custo - 1) if custo else None,
            "prov_12m_acao": prov_12m,
            "renda_12m": prov_12m * p.quantidade,
            "dy": calculos.dividend_yield(prov_12m, preco),
            "yoc": calculos.yield_on_cost(prov_12m, p.preco_medio),
            "media_prov_5a": media5,
            "teto_bazin": calculos.preco_teto_bazin(media5, carteira.taxa_bazin),
            "graham": calculos.preco_justo_graham(d.lpa, d.vpa) if d else None,
            "numero_magico": calculos.numero_magico(preco, prov_12m),
            "fonte": d.fonte if d else "indisponivel",
        })
    tabela = pd.DataFrame(linhas)
    if not tabela.empty:
        total = tabela["valor"].sum()
        tabela["peso"] = tabela["valor"] / total if total else 0.0
        tabela = tabela.sort_values("valor", ascending=False).reset_index(drop=True)
    return tabela


@dataclass
class Resumo:
    patrimonio: float
    custo: float
    resultado: float
    resultado_pct: float | None
    renda_12m: float
    renda_mensal_media: float
    dy: float | None
    yoc: float | None
    caixa: float


def resumir(tabela: pd.DataFrame, caixa: float = 0.0) -> Resumo:
    if tabela.empty:
        return Resumo(caixa, 0.0, 0.0, None, 0.0, 0.0, None, None, caixa)
    valor = float(tabela["valor"].sum())
    custo = float(tabela["custo"].sum())
    renda = float(tabela["renda_12m"].sum())
    return Resumo(
        patrimonio=valor + caixa,
        custo=custo,
        resultado=valor - custo,
        resultado_pct=(valor / custo - 1) if custo else None,
        renda_12m=renda,
        renda_mensal_media=renda / 12,
        dy=renda / valor if valor else None,
        yoc=renda / custo if custo else None,
        caixa=caixa,
    )


EXEMPLO = Carteira(
    posicoes=[
        Posicao("TAEE11.SA", 120, 33.10, "Ação"),
        Posicao("BBAS3.SA", 150, 24.80, "Ação"),
        Posicao("ITUB4.SA", 100, 31.40, "Ação"),
        Posicao("EGIE3.SA", 60, 40.20, "Ação"),
        Posicao("WEGE3.SA", 40, 44.00, "Ação"),
        Posicao("HGLG11.SA", 30, 158.00, "FII"),
        Posicao("MXRF11.SA", 400, 9.85, "FII"),
        Posicao("BOVA11.SA", 25, 118.00, "ETF"),
    ],
    caixa=850.0,
    aporte_mensal=1500.0,
    meta_renda_mensal=5000.0,
    observar=["BBSE3.SA", "KNRI11.SA", "VALE3.SA"],
)
