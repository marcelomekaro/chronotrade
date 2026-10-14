"""Relatório da carteira para imprimir, salvar em PDF ou compartilhar.

Gera uma página HTML única, sem dependências, com versão para impressão em papel
branco. A opção ``ocultar_valores`` troca reais por porcentagens, para mostrar a
estratégia sem expor quanto dinheiro você tem.
"""

from __future__ import annotations

import html
from datetime import date

import pandas as pd

from chronotrade import calculos
from chronotrade.calculos import brl, pct
from chronotrade.carteira import Carteira, Resumo

_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:wght@400;700&family=Pixelify+Sans:wght@600&display=swap');
:root { --ceu:#121838; --janela:#1E2A86; --borda:#E9E1C8; --ouro:#F2C14E; --texto:#EDE6D2; --suave:#A9B0D6;
        --jade:#5FD39A; --brasa:#F06A5D; }
* { box-sizing: border-box; }
body { margin:0; background:var(--ceu); color:var(--texto); font-family:'Atkinson Hyperlegible','Segoe UI',sans-serif;
       font-size:15px; line-height:1.5; }
main { max-width: 860px; margin: 0 auto; padding: 28px 20px 40px; }
h1, h2 { font-family:'Pixelify Sans','Courier New',monospace; font-weight:600; }
h1 { color:var(--ouro); font-size:2rem; margin:0; }
h2 { font-size:1.25rem; margin:28px 0 10px; }
.data { color:var(--suave); margin:2px 0 18px; }
.cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:12px; }
.card { background:linear-gradient(180deg,#2B3BA0,#17206A); border:3px solid var(--borda); border-radius:8px;
        padding:12px 16px; box-shadow:4px 4px 0 #0A0E26; }
.card .r { color:var(--suave); font-size:.88rem; }
.card .v { font-family:'Pixelify Sans','Courier New',monospace; font-size:1.55rem; }
table { width:100%; border-collapse:collapse; font-size:.92rem; }
th, td { padding:6px 8px; border-bottom:1px solid rgba(233,225,200,.18); text-align:right; }
th:first-child, td:first-child, th:nth-child(2), td:nth-child(2) { text-align:left; }
th { color:var(--suave); font-weight:400; }
.sobe { color:var(--jade); } .desce { color:var(--brasa); }
.barra { height:14px; border:2px solid var(--borda); border-radius:3px; background:#0B1040; margin:8px 0 4px; }
.barra div { height:100%; background:var(--ouro); }
.nota { color:var(--suave); font-size:.85rem; margin-top:26px; }
.acoes { margin: 18px 0 0; }
button { font: inherit; font-family:'Pixelify Sans','Courier New',monospace; background:var(--ouro); color:#1B1606;
         border:3px solid var(--borda); border-radius:6px; padding:8px 16px; cursor:pointer; box-shadow:3px 3px 0 #0A0E26; }
button:focus-visible { outline:3px solid #A48BFF; outline-offset:2px; }
@media print {
  body { background:#fff; color:#1a1a1a; font-size:12px; }
  h1 { color:#1a1a1a; } .data, th, .nota, .card .r { color:#555; }
  .card { background:#fff; box-shadow:none; border:2px solid #1a1a1a; }
  .barra { background:#eee; border-color:#1a1a1a; } .barra div { background:#b8860b; }
  .sobe { color:#11703f; } .desce { color:#a32014; }
  th, td { border-bottom-color:#ccc; }
  .acoes { display:none; }
  main { padding:0; }
}
"""


def _cel(valor: float | None, texto: str) -> str:
    if valor is None or pd.isna(valor):
        return f"<td>{html.escape(texto)}</td>"
    classe = "sobe" if valor >= 0 else "desce"
    return f'<td class="{classe}">{html.escape(texto)}</td>'


def gerar(carteira: Carteira, tabela: pd.DataFrame, resumo: Resumo, ocultar_valores: bool = False,
          plano_aporte: dict | None = None, titulo: str = "Minha carteira") -> str:
    """O relatório completo, como texto HTML."""
    e = html.escape
    meta = carteira.meta_renda_mensal or 0
    progresso = min(resumo.renda_mensal_media / meta, 1.0) if meta else 0.0

    if ocultar_valores:
        cards = [("Resultado sobre o custo", pct(resumo.resultado_pct, sinal=True)),
                 ("Dividend yield", pct(resumo.dy)), ("Yield on cost", pct(resumo.yoc)),
                 ("Caminho até a meta de renda", pct(progresso, 0))]
    else:
        cards = [("Patrimônio", brl(resumo.patrimonio, 0)), ("Proventos em 12 meses", brl(resumo.renda_12m, 0)),
                 ("Dividend yield", pct(resumo.dy)), ("Resultado sobre o custo", pct(resumo.resultado_pct, sinal=True))]
    partes = [f'<div class="card"><div class="r">{e(r)}</div><div class="v">{e(v)}</div></div>' for r, v in cards]

    cab = ["Ativo", "Classe", "Peso", "Resultado", "DY 12m", "Yield on cost"]
    if not ocultar_valores:
        cab[2:2] = ["Quantidade", "Valor"]
    linhas = []
    for _, ln in tabela.iterrows():
        cel = [f"<td>{e(ln['ativo'])}</td>", f"<td>{e(ln['classe'])}</td>"]
        if not ocultar_valores:
            cel += [f"<td>{ln['quantidade']:,.0f}</td>".replace(",", "."), f"<td>{e(brl(ln['valor'], 0))}</td>"]
        cel += [f"<td>{e(pct(ln['peso']))}</td>", _cel(ln["resultado_pct"], pct(ln["resultado_pct"], sinal=True)),
                f"<td>{e(pct(ln['dy']))}</td>", f"<td>{e(pct(ln['yoc']))}</td>"]
        linhas.append("<tr>" + "".join(cel) + "</tr>")

    secao_aporte = ""
    if plano_aporte and not plano_aporte["compras"].empty:
        compras = plano_aporte["compras"]
        total = float(compras["valor_compra"].sum())
        corpo = "".join(
            f"<tr><td>{e(ln['ativo'])}</td><td>{e(ln['classe'])}</td><td>{int(ln['cotas'])}</td>"
            f"<td>{e(pct(ln['valor_compra'] / total) if ocultar_valores else brl(ln['valor_compra']))}</td></tr>"
            for _, ln in compras.iterrows())
        secao_aporte = (f"<h2>Plano do próximo aporte</h2><table><tr><th>Ativo</th><th>Classe</th><th>Cotas</th>"
                        f"<th>{'Parte do aporte' if ocultar_valores else 'Total'}</th></tr>{corpo}</table>")

    proj = calculos.projetar(calculos.Premissas(resumo.patrimonio, carteira.aporte_mensal, 0.03,
                                                resumo.dy or 0.06, 20, True), meta).tabela.set_index("mes")
    def _renda(a: int) -> str:
        renda = proj.loc[a * 12, "renda_mensal"]
        if ocultar_valores:
            return f"{pct(renda / meta, 0)} da meta" if meta else "—"
        return f"{brl(renda, 0)}/mês"

    linhas_proj = "".join(
        f"<tr><td>{a} anos</td><td></td><td>{e(_renda(a))}</td>"
        + ("" if ocultar_valores else f"<td>{e(brl(proj.loc[a * 12, 'patrimonio'], 0))}</td>") + "</tr>"
        for a in (5, 10, 20))
    cab_proj = "<tr><th>Prazo</th><th></th><th>Renda em proventos</th>" + \
               ("" if ocultar_valores else "<th>Patrimônio</th>") + "</tr>"

    meta_txt = "" if ocultar_valores else f" Meta: {e(brl(meta, 0))} por mês; hoje: {e(brl(resumo.renda_mensal_media, 0))}."
    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Chrono Trade: {e(titulo)}</title><style>{_CSS}</style></head>
<body><main>
<h1>{e(titulo)}</h1>
<p class="data">Chrono Trade, relatório de {date.today():%d/%m/%Y}</p>
<div class="cards">{''.join(partes)}</div>
<h2>Caminho até a meta de renda</h2>
<div class="barra" role="progressbar" aria-valuenow="{progresso * 100:.0f}"><div style="width:{progresso * 100:.1f}%"></div></div>
<p>{pct(progresso, 0)} da meta de renda mensal.{meta_txt}</p>
<h2>Posições</h2>
<table><tr>{''.join(f'<th>{c}</th>' for c in cab)}</tr>{''.join(linhas)}</table>
{secao_aporte}
<h2>Projeção com o aporte atual</h2>
<table>{cab_proj}{linhas_proj}</table>
<p class="nota">Projeção com valorização real de 3% ao ano e proventos reinvestidos, em reais de hoje.
Dados do Yahoo Finance; proventos estimados pela quantidade atual. Material de estudo, não é recomendação de investimento.</p>
<p class="acoes"><button onclick="window.print()">Imprimir ou salvar em PDF</button></p>
</main></body></html>"""


def resumo_texto(carteira: Carteira, tabela: pd.DataFrame, resumo: Resumo, ocultar_valores: bool = True) -> str:
    """Um resumo curto para colar no WhatsApp ou num grupo."""
    maiores = tabela.sort_values("peso", ascending=False).head(5)
    pesos = ", ".join(f"{ln['ativo']} {pct(ln['peso'], 0)}" for _, ln in maiores.iterrows())
    por_classe = tabela.groupby("classe")["peso"].sum().sort_values(ascending=False)
    classes = ", ".join(f"{k} {pct(v, 0)}" for k, v in por_classe.items())
    linhas = ["*Minha carteira no Chrono Trade*", f"Divisão: {classes}", f"Maiores posições: {pesos}",
              f"Dividend yield: {pct(resumo.dy)} | Yield on cost: {pct(resumo.yoc)}"]
    if not ocultar_valores:
        linhas.insert(1, f"Patrimônio: {brl(resumo.patrimonio, 0)} | Proventos em 12 meses: {brl(resumo.renda_12m, 0)}")
    meta = carteira.meta_renda_mensal or 0
    if meta:
        linhas.append(f"Caminho até a meta de renda: {pct(min(resumo.renda_mensal_media / meta, 1), 0)}")
    return "\n".join(linhas)
