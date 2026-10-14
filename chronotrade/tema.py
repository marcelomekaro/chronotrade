"""Visual do Chrono Trade: céu noturno, janelas de diálogo de RPG 16-bit e ouro.

Tudo aqui é original: cores, janelas e textos. Nenhum personagem, logotipo ou
arte de jogo existente é usado.
"""

from __future__ import annotations

import html

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

CORES = {
    "ceu": "#121838",
    "ceu_2": "#1A2150",
    "janela_topo": "#2B3BA0",
    "janela_base": "#17206A",
    "borda": "#E9E1C8",
    "ouro": "#F2C14E",
    "jade": "#5FD39A",
    "brasa": "#F06A5D",
    "portal": "#A48BFF",
    "texto": "#EDE6D2",
    "suave": "#A9B0D6",
}

CORES_CLASSE = {
    "Ação": "#5AB6F0",
    "FII": CORES["ouro"],
    "ETF": CORES["portal"],
    "BDR": CORES["jade"],
    "Outro": "#C9A36A",
}

_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:wght@400;700&family=Pixelify+Sans:wght@500;700&display=swap');

:root {{
  --ceu: {CORES['ceu']}; --ceu-2: {CORES['ceu_2']};
  --janela-topo: {CORES['janela_topo']}; --janela-base: {CORES['janela_base']};
  --borda: {CORES['borda']}; --ouro: {CORES['ouro']}; --jade: {CORES['jade']};
  --brasa: {CORES['brasa']}; --portal: {CORES['portal']};
  --texto: {CORES['texto']}; --suave: {CORES['suave']};
  --pixel: 'Pixelify Sans', 'Courier New', monospace;
  --corpo: 'Atkinson Hyperlegible', 'Segoe UI', sans-serif;
}}

html, body, [data-testid="stAppViewContainer"], [data-testid="stMarkdownContainer"],
button, input, textarea, select, label {{ font-family: var(--corpo); }}

[data-testid="stAppViewContainer"] {{
  background-color: var(--ceu);
  background-image:
    radial-gradient(1.5px 1.5px at 12% 18%, rgba(233,225,200,.55) 50%, transparent 51%),
    radial-gradient(1px 1px at 72% 9%, rgba(233,225,200,.45) 50%, transparent 51%),
    radial-gradient(1.5px 1.5px at 41% 63%, rgba(164,139,255,.5) 50%, transparent 51%),
    radial-gradient(1px 1px at 88% 47%, rgba(233,225,200,.35) 50%, transparent 51%),
    radial-gradient(1px 1px at 23% 86%, rgba(242,193,78,.4) 50%, transparent 51%),
    linear-gradient(180deg, #0E1330 0%, var(--ceu) 40%, #161C46 100%);
  background-size: 420px 420px, 380px 380px, 520px 520px, 300px 300px, 460px 460px, 100% 100%;
  background-attachment: fixed;
}}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stAppDeployButton"] {{ display: none; }}
[data-testid="stSidebar"] {{ background: var(--ceu-2); border-right: 2px solid rgba(233,225,200,.18); }}

h1, h2, h3 {{ font-family: var(--pixel) !important; color: var(--texto); letter-spacing: .5px; }}
h1 {{ font-size: 2.2rem !important; color: var(--ouro); text-shadow: 3px 3px 0 #0A0E26; }}
h2 {{ font-size: 1.45rem !important; }}
h3 {{ font-size: 1.15rem !important; }}
p, li {{ max-width: 75ch; }}

.ct-janela {{
  background: linear-gradient(180deg, var(--janela-topo) 0%, var(--janela-base) 100%);
  border: 3px solid var(--borda);
  border-radius: 8px;
  box-shadow: inset 0 0 0 3px #0B1040, 4px 4px 0 #0A0E26;
  padding: 18px 22px;
  color: var(--texto);
  margin-bottom: 14px;
}}
.ct-janela .rotulo {{ color: var(--suave); font-size: .95rem; }}
.ct-janela .valor {{ font-family: var(--pixel); font-size: clamp(1.35rem, 1.9vw, 2.1rem); color: var(--texto);
  line-height: 1.2; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.ct-janela .valor.ouro {{ color: var(--ouro); }}
.ct-janela .detalhe {{ font-size: .95rem; margin-top: 4px; }}
.ct-sobe {{ color: var(--jade); }}
.ct-desce {{ color: var(--brasa); }}

.ct-fala {{ font-size: 1.12rem; line-height: 1.55; }}
.ct-fala b {{ color: var(--ouro); }}

/* A linha do tempo até a meta: o elemento central do Portal */
.ct-tempo {{ margin: 6px 0 4px; }}
.ct-tempo .trilho {{
  position: relative; height: 26px; border: 3px solid var(--borda); border-radius: 4px;
  background: repeating-linear-gradient(90deg, #0B1040 0 22px, #10165A 22px 24px);
  box-shadow: 4px 4px 0 #0A0E26; overflow: hidden;
}}
.ct-tempo .preenchido {{
  height: 100%;
  background: repeating-linear-gradient(90deg, var(--ouro) 0 22px, #D9A632 22px 24px);
  animation: ct-encher 1.4s steps(14, end) both;
}}
.ct-tempo .marcas {{ display: flex; justify-content: space-between; color: var(--suave);
  font-size: .9rem; margin-top: 6px; }}
@keyframes ct-encher {{ from {{ width: 0; }} }}
@media (prefers-reduced-motion: reduce) {{ .ct-tempo .preenchido {{ animation: none; }} }}

.ct-era {{ border-left: 3px solid var(--portal); padding: 2px 0 10px 14px; margin-left: 6px; }}
.ct-era .quando {{ font-family: var(--pixel); color: var(--portal); }}
.ct-era .titulo {{ font-weight: 700; color: var(--texto); }}
.ct-era .texto {{ color: var(--suave); }}

.ct-selo {{ display: inline-block; font-family: var(--pixel); padding: 4px 12px; border: 2px solid currentColor;
  border-radius: 4px; font-size: 1.05rem; }}

.ct-aviso {{ border: 2px dashed var(--ouro); border-radius: 6px; padding: 8px 12px; color: var(--ouro);
  background: rgba(242,193,78,.06); margin-bottom: 12px; }}

[data-testid="stMetric"] {{ background: rgba(11,16,64,.55); border: 2px solid rgba(233,225,200,.35);
  border-radius: 6px; padding: 10px 14px; }}
[data-testid="stMetricValue"] {{ font-family: var(--pixel); }}

.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {{
  background: var(--ouro); color: #1B1606; border: 3px solid var(--borda); font-family: var(--pixel);
  box-shadow: 3px 3px 0 #0A0E26; border-radius: 6px;
}}
.stButton > button[kind="primary"]:hover {{ filter: brightness(1.08); }}
button:focus-visible, a:focus-visible, input:focus-visible {{ outline: 3px solid var(--portal) !important; outline-offset: 2px; }}

[data-testid="stSidebar"] [data-testid="stPageLink"] p {{ font-family: var(--pixel); font-size: 1.02rem; }}
.ct-marca {{ font-family: var(--pixel); font-size: 1.6rem; color: var(--ouro); text-shadow: 3px 3px 0 #0A0E26; line-height: 1.1; margin-bottom: 14px; }}
.ct-marca small {{ display: block; font-family: var(--corpo); font-size: .85rem; color: var(--suave); text-shadow: none; margin-top: 4px; }}

/* Portaria (tela de entrada) */
.ct-heroi {{ margin: 8px 0 6px; }}
.ct-heroi-titulo {{ font-family: var(--pixel); font-size: clamp(2.6rem, 7vw, 4.6rem); color: var(--ouro);
  line-height: 1; text-shadow: 4px 4px 0 #0A0E26; }}
.ct-heroi p {{ font-size: clamp(1.05rem, 2.2vw, 1.35rem); color: var(--texto); margin: 14px 0 8px; max-width: 40ch; }}

/* Celular: menos margem, números menores, nada estoura a largura da tela */
@media (max-width: 640px) {{
  [data-testid="stMainBlockContainer"], .block-container {{ padding: 2.6rem 0.9rem 3rem !important; }}
  h1 {{ font-size: 1.65rem !important; }}
  h2 {{ font-size: 1.2rem !important; }}
  h3 {{ font-size: 1.02rem !important; }}
  .ct-janela {{ padding: 12px 14px; margin-bottom: 10px; box-shadow: inset 0 0 0 2px #0B1040, 3px 3px 0 #0A0E26; }}
  .ct-janela .valor {{ font-size: 1.6rem; }}
  .ct-fala {{ font-size: 1rem; line-height: 1.5; }}
  .ct-tempo .marcas {{ font-size: .8rem; }}
  [data-testid="stHorizontalBlock"] {{ gap: .5rem; }}
}}
</style>
"""


def aplicar() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
    _registrar_plotly()
    _instalavel()


_CABECALHO = """
<script>
(function () {
  const doc = window.parent.document;
  if (doc.getElementById("ct-manifest")) return;
  const add = (tag, attrs) => { const el = doc.createElement(tag);
    Object.entries(attrs).forEach(([k, v]) => el.setAttribute(k, v)); doc.head.appendChild(el); };
  add("link", {id: "ct-manifest", rel: "manifest", href: "app/static/manifest.json"});
  add("meta", {name: "theme-color", content: "#121838"});
  add("meta", {name: "mobile-web-app-capable", content: "yes"});
  add("meta", {name: "apple-mobile-web-app-capable", content: "yes"});
  add("meta", {name: "apple-mobile-web-app-title", content: "Chrono Trade"});
  add("link", {rel: "apple-touch-icon", href: "app/static/icone-192.png"});
})();
</script>
"""


def _instalavel() -> None:
    """Liga o manifesto e o ícone, para o celular oferecer "Adicionar à tela inicial"."""
    import streamlit.components.v1 as componentes

    componentes.html(_CABECALHO, height=0)


def _registrar_plotly() -> None:
    modelo = go.layout.Template()
    modelo.layout = go.Layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Atkinson Hyperlegible, Segoe UI, sans-serif", color=CORES["texto"], size=14),
        colorway=[CORES["ouro"], "#5AB6F0", CORES["portal"], CORES["jade"], "#F08FB0", "#C9A36A",
                  "#FF9F6B", "#4FD1C5", "#D6C9FF", "#B8E05B", "#E9E1C8", "#7C8CF0"],
        xaxis=dict(gridcolor="rgba(233,225,200,.08)", zerolinecolor="rgba(233,225,200,.2)",
                   linecolor="rgba(233,225,200,.25)"),
        yaxis=dict(gridcolor="rgba(233,225,200,.08)", zerolinecolor="rgba(233,225,200,.2)",
                   linecolor="rgba(233,225,200,.25)"),
        hoverlabel=dict(bgcolor=CORES["janela_base"], bordercolor=CORES["borda"],
                        font=dict(color=CORES["texto"])),
        legend=dict(bgcolor="rgba(0,0,0,0)", orientation="h", x=0, y=1.02, yanchor="bottom"),
        margin=dict(l=8, r=40, t=36, b=8),
        separators=",.",
    )
    pio.templates["chrono"] = modelo
    pio.templates.default = "chrono"


def janela(rotulo: str, valor: str, detalhe: str = "", ouro: bool = False) -> None:
    """Uma janela de diálogo com um número em destaque."""
    st.markdown(
        f'<div class="ct-janela"><div class="rotulo">{html.escape(rotulo)}</div>'
        f'<div class="valor{" ouro" if ouro else ""}">{html.escape(valor)}</div>'
        f'<div class="detalhe">{detalhe}</div></div>',
        unsafe_allow_html=True,
    )


def fala(texto_html: str) -> None:
    """Uma janela de diálogo com texto corrido, como a fala de um personagem."""
    st.markdown(f'<div class="ct-janela ct-fala">{texto_html}</div>', unsafe_allow_html=True)


def variacao(valor: float | None, texto: str) -> str:
    if valor is None:
        return html.escape(texto)
    classe = "ct-sobe" if valor >= 0 else "ct-desce"
    seta = "▲" if valor >= 0 else "▼"
    return f'<span class="{classe}">{seta} {html.escape(texto)}</span>'


def linha_do_tempo(fracao: float, inicio: str, fim: str) -> None:
    fracao = max(0.0, min(1.0, fracao))
    st.markdown(
        f'<div class="ct-tempo"><div class="trilho" role="progressbar" aria-valuemin="0" '
        f'aria-valuemax="100" aria-valuenow="{fracao * 100:.0f}">'
        f'<div class="preenchido" style="width:{fracao * 100:.1f}%"></div></div>'
        f'<div class="marcas"><span>{html.escape(inicio)}</span><span>{html.escape(fim)}</span></div></div>',
        unsafe_allow_html=True,
    )


def era(quando: str, titulo: str, texto: str) -> None:
    st.markdown(
        f'<div class="ct-era"><div class="quando">{html.escape(quando)}</div>'
        f'<div class="titulo">{html.escape(titulo)}</div><div class="texto">{html.escape(texto)}</div></div>',
        unsafe_allow_html=True,
    )


def aviso(texto: str) -> None:
    st.markdown(f'<div class="ct-aviso">{html.escape(texto)}</div>', unsafe_allow_html=True)


def selo(texto: str, cor: str) -> str:
    return f'<span class="ct-selo" style="color:{cor}">{html.escape(texto)}</span>'


def mostrar(fig: go.Figure) -> None:
    """Desenha um gráfico Plotly com o visual do Chrono Trade."""
    fig.update_layout(template=pio.templates["chrono"])
    fig.update_xaxes(automargin=True)
    fig.update_yaxes(automargin=True)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, theme=None)


def legenda(texto: str) -> None:
    """Legenda pequena sob um gráfico ou tabela. Escapa o $ para o Streamlit não ler como fórmula."""
    st.caption(texto.replace("$", "\\$"))
