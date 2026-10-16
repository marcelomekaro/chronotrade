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
@import url('https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:wght@400;700&family=Pixelify+Sans:wght@500;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

:root {{
  --ceu: {CORES['ceu']}; --ceu-2: {CORES['ceu_2']};
  --janela-topo: {CORES['janela_topo']}; --janela-base: {CORES['janela_base']};
  --borda: {CORES['borda']}; --ouro: {CORES['ouro']}; --jade: {CORES['jade']};
  --brasa: {CORES['brasa']}; --portal: {CORES['portal']};
  --texto: {CORES['texto']}; --suave: {CORES['suave']};
  --tinta: #0A0E26; --tinta-2: #0B1040;
  --pixel: 'Pixelify Sans', 'Courier New', monospace;
  --corpo: 'Atkinson Hyperlegible', 'Segoe UI', sans-serif;
  --moderna: 'Plus Jakarta Sans', 'Atkinson Hyperlegible', 'Segoe UI', system-ui, sans-serif;
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
[data-testid="stPlotlyChart"], [data-testid="stPlotlyChart"] > div, .js-plotly-plot .plotly .main-svg {{
  background: transparent !important; }}
.js-plotly-plot .plotly rect.bg {{ fill: var(--tinta-2) !important; fill-opacity: .55 !important; }}
[data-testid="stAppDeployButton"] {{ display: none; }}
[data-testid="stSidebar"] {{ background: var(--ceu-2); border-right: 2px solid rgba(233,225,200,.18); }}

h1 {{ font-family: var(--pixel) !important; letter-spacing: .5px; }}
h2, h3 {{ font-family: var(--corpo) !important; font-weight: 700 !important; color: var(--texto); }}
h1 {{ font-size: 2.2rem !important; color: var(--ouro); text-shadow: 3px 3px 0 var(--tinta); }}
h2 {{ font-size: 1.45rem !important; }}
h3 {{ font-size: 1.15rem !important; }}
p, li {{ max-width: 75ch; }}

.ct-janela {{
  background: linear-gradient(180deg, var(--janela-topo) 0%, var(--janela-base) 100%);
  border: 3px solid var(--borda);
  border-radius: 8px;
  box-shadow: inset 0 0 0 3px var(--tinta-2), 4px 4px 0 var(--tinta);
  padding: 18px 22px;
  color: var(--texto);
  margin-bottom: 14px;
}}
.ct-janela .rotulo {{ color: var(--suave); font-size: .95rem; }}
.ct-janela .valor {{ font-family: var(--corpo); font-weight: 800; font-size: clamp(1.35rem, 1.9vw, 2.1rem); color: var(--texto);
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
  background: repeating-linear-gradient(90deg, var(--tinta-2) 0 22px, var(--ceu-2) 22px 24px);
  box-shadow: 4px 4px 0 var(--tinta); overflow: hidden;
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

[data-testid="stMetric"] {{ background: var(--tinta-2); border: 2px solid rgba(233,225,200,.35);
  border-radius: 6px; padding: 10px 14px; }}
[data-testid="stMetricValue"] {{ font-family: var(--corpo); font-weight: 800; }}

.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {{
  background: var(--ouro); color: #1B1606; border: 3px solid var(--borda); font-family: var(--pixel);
  box-shadow: 3px 3px 0 var(--tinta); border-radius: 6px;
}}
.stButton > button[kind="primary"]:hover {{ filter: brightness(1.08); }}
button:focus-visible, a:focus-visible, input:focus-visible {{ outline: 3px solid var(--portal) !important; outline-offset: 2px; }}

[data-testid="stSidebar"] [data-testid="stPageLink"] p {{ font-family: var(--corpo); font-weight: 600; font-size: 1rem; }}
.ct-marca {{ font-family: var(--pixel); font-size: 1.6rem; color: var(--ouro); text-shadow: 3px 3px 0 var(--tinta); line-height: 1.1; margin-bottom: 14px; }}
.ct-secao {{ font-family: var(--pixel); font-size: .8rem; letter-spacing: .08em; text-transform: uppercase; color: var(--suave); margin: 12px 0 2px; }}
.ct-marca small {{ display: block; font-family: var(--corpo); font-size: .85rem; color: var(--suave); text-shadow: none; margin-top: 4px; }}

/* Portaria (tela de entrada) */
.ct-heroi {{ margin: 8px 0 6px; }}
.ct-subtitulo {{ color: var(--suave); font-size: 1.05rem; margin: -6px 0 14px; }}
.ct-slogan {{ font-family: var(--pixel); font-size: clamp(1.2rem, 2.8vw, 1.7rem); color: var(--texto); margin-top: 10px; text-shadow: 2px 2px 0 var(--tinta); }}
.ct-heroi-titulo {{ font-family: var(--pixel); font-size: clamp(2.6rem, 7vw, 4.6rem); color: var(--ouro);
  line-height: 1; text-shadow: 4px 4px 0 var(--tinta); }}
.ct-heroi p {{ font-size: clamp(1.05rem, 2.2vw, 1.35rem); color: var(--texto); margin: 14px 0 8px; max-width: 40ch; }}

/* ---------- Efeitos para todos os temas: entrada suave, atalhos e cartões ---------- */
[data-testid="stMainBlockContainer"] [data-testid="stVerticalBlock"] > [data-testid="stElementContainer"],
[data-testid="stMainBlockContainer"] [data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"],
[data-testid="stMainBlockContainer"] [data-testid="stVerticalBlock"] > [data-testid="stVerticalBlockBorderWrapper"] {{
  animation: ct-subir .5s cubic-bezier(.2,.8,.2,1) backwards; }}
[data-testid="stMainBlockContainer"] [data-testid="stVerticalBlock"] > :nth-child(2) {{ animation-delay: .04s; }}
[data-testid="stMainBlockContainer"] [data-testid="stVerticalBlock"] > :nth-child(3) {{ animation-delay: .08s; }}
[data-testid="stMainBlockContainer"] [data-testid="stVerticalBlock"] > :nth-child(4) {{ animation-delay: .12s; }}
[data-testid="stMainBlockContainer"] [data-testid="stVerticalBlock"] > :nth-child(5) {{ animation-delay: .16s; }}
[data-testid="stMainBlockContainer"] [data-testid="stVerticalBlock"] > :nth-child(n+6) {{ animation-delay: .2s; }}
@keyframes ct-subir {{ from {{ opacity: 0; transform: translateY(10px); }} }}
[data-testid="stMainBlockContainer"] [data-testid="stPageLink"] a {{
  border: 1px solid color-mix(in srgb, var(--borda) 70%, transparent); border-radius: 12px; padding: 6px 12px;
  background: rgba(255,255,255,.03); transition: transform .15s ease, border-color .15s ease, background .15s ease; }}
[data-testid="stMainBlockContainer"] [data-testid="stPageLink"] a:hover {{ transform: translateY(-2px);
  border-color: var(--ouro); background: color-mix(in srgb, var(--ouro) 10%, transparent); }}
.ct-cartoes {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; margin: 6px 0 16px; }}
.ct-cartao {{ border: 1px solid color-mix(in srgb, var(--borda) 75%, transparent); border-radius: 16px; padding: 14px 16px;
  background: linear-gradient(180deg, rgba(255,255,255,.05), rgba(255,255,255,.01)); display: flex; flex-direction: column; gap: 4px;
  transition: transform .2s ease, border-color .2s ease; }}
.ct-cartao:hover {{ transform: translateY(-3px); border-color: var(--ouro); }}
.ct-cartao span {{ color: var(--suave); font-size: .93rem; line-height: 1.45; }}
.ct-cartao-ico {{ font-size: 1.5rem; }}
.ct-credito {{ font-size: .8rem; color: var(--suave); line-height: 1.5; margin-top: 6px; padding-top: 8px;
  border-top: 1px solid color-mix(in srgb, var(--borda) 60%, transparent); }}
.ct-credito a {{ color: var(--ouro); text-decoration: none; }}
.ct-credito a:hover {{ text-decoration: underline; }}
kbd {{ background: rgba(255,255,255,.1); border: 1px solid rgba(255,255,255,.2); border-bottom-width: 2px; border-radius: 6px;
  padding: 0 6px; font-size: .85em; font-family: var(--corpo); }}
::-webkit-scrollbar {{ width: 10px; height: 10px; }}
::-webkit-scrollbar-thumb {{ background: color-mix(in srgb, var(--suave) 35%, transparent); border-radius: 10px; border: 2px solid transparent; background-clip: padding-box; }}
::-webkit-scrollbar-track {{ background: transparent; }}
@media (prefers-reduced-motion: reduce) {{ [data-testid="stMainBlockContainer"] [data-testid="stVerticalBlock"] > * {{ animation: none !important; }} }}

/* Celular: menos margem, números menores, nada estoura a largura da tela */
@media (max-width: 640px) {{
  [data-testid="stMainBlockContainer"], .block-container {{ padding: 2.6rem 0.9rem 3rem !important; }}
  h1 {{ font-size: 1.65rem !important; }}
  h2 {{ font-size: 1.2rem !important; }}
  h3 {{ font-size: 1.02rem !important; }}
  .ct-janela {{ padding: 12px 14px; margin-bottom: 10px; box-shadow: inset 0 0 0 2px var(--tinta-2), 3px 3px 0 var(--tinta); }}
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


# ---------------------------------------------------------------------------
# Temas de cores: cada pessoa escolhe em Meu perfil; o administrador define o padrão
# ---------------------------------------------------------------------------

TEMAS = {
    "moderno": {"nome": "Esmeralda moderno", "descricao": "Grafite com verde esmeralda. Limpo, leve e direto ao ponto.",
                "ceu": "#0B1017", "ceu_2": "#0F1620", "janela_topo": "#16202C", "janela_base": "#121A24",
                "borda": "#2A3646", "ouro": "#34D399", "jade": "#4ADE80", "brasa": "#F87171", "portal": "#60A5FA",
                "texto": "#E8EDF3", "suave": "#93A1B3", "tinta": "#05080C", "tinta_2": "#111823",
                "estrelas": False, "titulo": "moderno", "estilo": "moderno"},
    "oceano": {"nome": "Oceano moderno", "descricao": "Azul profundo com ciano. Cara de banco digital.",
               "ceu": "#0A1020", "ceu_2": "#0E1529", "janela_topo": "#15203A", "janela_base": "#111A30",
               "borda": "#273556", "ouro": "#38BDF8", "jade": "#4ADE80", "brasa": "#FB7185", "portal": "#A78BFA",
               "texto": "#E6ECF7", "suave": "#94A3B8", "tinta": "#050913", "tinta_2": "#0F1730",
               "estrelas": False, "titulo": "moderno", "estilo": "moderno"},
    "retro": {"nome": "Retrô noite", "descricao": "O original: céu estrelado, janelas de RPG e ouro.",
              "ceu": "#121838", "ceu_2": "#1A2150", "janela_topo": "#2B3BA0", "janela_base": "#17206A",
              "borda": "#E9E1C8", "ouro": "#F2C14E", "jade": "#5FD39A", "brasa": "#F06A5D", "portal": "#A48BFF",
              "texto": "#EDE6D2", "suave": "#A9B0D6", "tinta": "#0A0E26", "tinta_2": "#0B1040",
              "estrelas": True, "titulo": "pixel", "estilo": "retro"},
    "verde": {"nome": "Verde investidor", "descricao": "Verde de mercado com detalhes dourados. Sóbrio e comercial.",
              "ceu": "#0C1F17", "ceu_2": "#10291F", "janela_topo": "#1E6B4B", "janela_base": "#124532",
              "borda": "#D9EBDD", "ouro": "#F2C14E", "jade": "#7BE0A6", "brasa": "#F06A5D", "portal": "#8FD3FF",
              "texto": "#EAF4EC", "suave": "#A3C7B2", "tinta": "#06140E", "tinta_2": "#0A1C14",
              "estrelas": False, "titulo": "moderno", "estilo": "moderno"},
    "laranja": {"nome": "Laranja energia", "descricao": "Grafite com laranja vibrante, cara de corretora moderna.",
                "ceu": "#1A1410", "ceu_2": "#231A14", "janela_topo": "#B4561C", "janela_base": "#7A3410",
                "borda": "#F3E2CF", "ouro": "#FFB347", "jade": "#5FD39A", "brasa": "#FF6B5B", "portal": "#FFD08A",
                "texto": "#F7EDE2", "suave": "#CDB6A0", "tinta": "#120B06", "tinta_2": "#1C120A",
                "estrelas": False, "titulo": "moderno", "estilo": "moderno"},
    "classico": {"nome": "Clássico", "descricao": "Azul-marinho e dourado, títulos com serifa. Cara de private bank.",
                 "ceu": "#0B1B2E", "ceu_2": "#0F2440", "janela_topo": "#173A63", "janela_base": "#102A4A",
                 "borda": "#C9A227", "ouro": "#D4AF37", "jade": "#4CC38A", "brasa": "#E5675A", "portal": "#9DB7D9",
                 "texto": "#F1F4F8", "suave": "#A7B4C6", "tinta": "#06101C", "tinta_2": "#0A1830",
                 "estrelas": False, "titulo": "serifa", "estilo": "moderno"},
}
TEMA_PADRAO = "moderno"


def paleta() -> dict:
    """As cores do tema em uso (para gráficos e componentes)."""
    return st.session_state.get("_paleta") or TEMAS[TEMA_PADRAO]


def cor(chave: str) -> str:
    return paleta().get(chave, CORES.get(chave, "#FFFFFF"))


def aplicar_paleta(nome: str | None) -> None:
    """Troca as cores do app pelo tema escolhido (vem depois do CSS base, então vence)."""
    t = TEMAS.get(nome or "", TEMAS[TEMA_PADRAO])
    st.session_state["_paleta"] = t
    _registrar_plotly(t)
    if t is TEMAS["retro"]:
        return
    titulo = {"serifa": "Georgia, 'Times New Roman', serif", "pixel": "var(--pixel)"}.get(t["titulo"], "var(--moderna)")
    fundo = (f"linear-gradient(180deg, {t['tinta_2']} 0%, {t['ceu']} 45%, {t['ceu_2']} 100%)")
    st.markdown(f"""<style>
:root {{
  --ceu: {t['ceu']}; --ceu-2: {t['ceu_2']}; --janela-topo: {t['janela_topo']}; --janela-base: {t['janela_base']};
  --borda: {t['borda']}; --ouro: {t['ouro']}; --jade: {t['jade']}; --brasa: {t['brasa']}; --portal: {t['portal']};
  --texto: {t['texto']}; --suave: {t['suave']}; --tinta: {t['tinta']}; --tinta-2: {t['tinta_2']};
  --primary-color: {t['ouro']};
}}
[data-testid="stAppViewContainer"] {{ background: {fundo} !important; background-attachment: fixed !important; }}
[data-testid="stSidebar"] {{ background: {t['ceu_2']} !important; }}
[data-testid="stBottomBlockContainer"], [data-testid="stBottom"] > div {{ background: {t['ceu']} !important; }}
[data-baseweb="input"] > div, [data-baseweb="select"] > div, [data-baseweb="textarea"], [data-baseweb="base-input"],
[data-testid="stChatInput"] > div, [data-testid="stFileUploaderDropzone"], [data-testid="stNumberInputContainer"] {{
  background-color: {t['tinta_2']} !important; }}
[data-testid="stExpander"] details, [data-testid="stPopoverBody"] {{ background-color: {t['ceu_2']} !important; }}
h1, .ct-marca, .ct-heroi-titulo, .ct-slogan {{ font-family: {titulo} !important; }}
h1 {{ color: var(--ouro) !important; }}
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"],
[data-testid="stBaseButton-primary"] {{ background: var(--ouro) !important; color: {t['tinta']} !important; }}
[data-testid="stSidebar"] [data-testid="stPageLink"] a[aria-current="page"] {{ background: {t['janela_base']} !important; }}
</style>""", unsafe_allow_html=True)
    if t.get("estilo") == "moderno":
        st.markdown(_MODERNO, unsafe_allow_html=True)


_MODERNO = """<style>
/* ---------- Estilo moderno: cartões de vidro, cantos suaves, brilho discreto ---------- */
html, body, [data-testid="stAppViewContainer"], [data-testid="stMarkdownContainer"], button, input, textarea, select, label {
  font-family: var(--moderna) !important; }
[data-testid="stAppViewContainer"]::before {
  content: ""; position: fixed; inset: -20%; z-index: 0; pointer-events: none;
  background:
    radial-gradient(38% 30% at 82% 8%, color-mix(in srgb, var(--ouro) 16%, transparent), transparent 70%),
    radial-gradient(30% 28% at 8% 92%, color-mix(in srgb, var(--portal) 12%, transparent), transparent 70%),
    radial-gradient(26% 22% at 50% 50%, color-mix(in srgb, var(--jade) 5%, transparent), transparent 70%);
  animation: ct-aurora 28s ease-in-out infinite alternate; }
@keyframes ct-aurora { to { transform: translate3d(-4%, 3%, 0) scale(1.06); } }
[data-testid="stMain"], [data-testid="stSidebar"] { position: relative; z-index: 1; }
h1 { font-weight: 800 !important; letter-spacing: -.025em !important; text-shadow: none !important; font-size: 2.15rem !important;
  background: linear-gradient(92deg, var(--texto) 0%, var(--ouro) 120%); -webkit-background-clip: text; background-clip: text;
  -webkit-text-fill-color: transparent; }
h2, h3 { letter-spacing: -.01em; font-family: var(--moderna) !important; }
.ct-subtitulo { font-size: 1.02rem; margin-top: -10px; }
.ct-janela, [data-testid="stMetric"] {
  background: linear-gradient(180deg, rgba(255,255,255,.055), rgba(255,255,255,.015)), var(--tinta-2) !important;
  border: 1px solid color-mix(in srgb, var(--borda) 80%, transparent) !important; border-radius: 16px !important;
  box-shadow: 0 1px 0 rgba(255,255,255,.05) inset, 0 12px 32px -12px rgba(0,0,0,.55) !important;
  transition: transform .25s cubic-bezier(.2,.8,.2,1), box-shadow .25s ease, border-color .25s ease; position: relative; }
.ct-janela:hover, [data-testid="stMetric"]:hover { transform: translateY(-3px);
  border-color: color-mix(in srgb, var(--ouro) 45%, var(--borda)) !important;
  box-shadow: 0 1px 0 rgba(255,255,255,.06) inset, 0 18px 40px -14px color-mix(in srgb, var(--ouro) 35%, rgba(0,0,0,.6)) !important; }
.ct-janela .rotulo { font-size: .82rem; text-transform: uppercase; letter-spacing: .06em; font-weight: 600; }
.ct-janela .valor { font-weight: 800; letter-spacing: -.02em; font-variant-numeric: tabular-nums; }
.ct-janela.ct-fala { border-left: 3px solid var(--ouro) !important; }
.ct-janela.ct-fala:hover { transform: none; }
.ct-fala b { color: var(--ouro); }
.stButton > button, .stFormSubmitButton > button, [data-testid="stPopover"] button, .stDownloadButton > button,
[data-testid="stBaseButton-secondary"] {
  border-radius: 12px !important; font-weight: 600; transition: transform .15s ease, box-shadow .2s ease, background .2s ease, border-color .2s ease; }
.stButton > button:hover, .stFormSubmitButton > button:hover { transform: translateY(-1px); }
.stButton > button:active, .stFormSubmitButton > button:active { transform: translateY(0) scale(.98); }
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"], [data-testid="stBaseButton-primary"] {
  font-family: var(--moderna) !important; font-weight: 700 !important; border: 0 !important;
  background: linear-gradient(135deg, color-mix(in srgb, var(--ouro) 92%, white), color-mix(in srgb, var(--ouro) 80%, black)) !important;
  box-shadow: 0 8px 22px -8px color-mix(in srgb, var(--ouro) 70%, transparent) !important; }
.stButton > button[kind="primary"]:hover { box-shadow: 0 12px 28px -8px color-mix(in srgb, var(--ouro) 85%, transparent) !important; filter: none; }
[data-baseweb="input"] > div, [data-baseweb="select"] > div, [data-baseweb="textarea"], [data-testid="stNumberInputContainer"],
[data-testid="stChatInput"] > div { border-radius: 12px !important; }
[data-testid="stExpander"] details { border-radius: 14px !important; border-color: color-mix(in srgb, var(--borda) 80%, transparent) !important; }
[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 16px !important; }
[data-testid="stChatMessage"] { border-radius: 16px; background: rgba(255,255,255,.025); }
[data-testid="stDataFrame"], [data-testid="stTable"] { border-radius: 14px; overflow: hidden; }
[data-testid="stTabs"] [role="tab"] { font-weight: 600; }
[data-testid="stTabs"] [role="tab"][aria-selected="true"] { color: var(--ouro); }
[data-testid="stSidebar"] { background: color-mix(in srgb, var(--ceu-2) 88%, transparent) !important; backdrop-filter: blur(10px);
  border-right: 1px solid color-mix(in srgb, var(--borda) 70%, transparent) !important; }
[data-testid="stSidebar"] [data-testid="stPageLink"] a { border-radius: 10px; transition: background .15s ease, transform .15s ease; }
[data-testid="stSidebar"] [data-testid="stPageLink"] a:hover { background: rgba(255,255,255,.05); transform: translateX(2px); }
[data-testid="stSidebar"] [data-testid="stPageLink"] a[aria-current="page"] {
  background: color-mix(in srgb, var(--ouro) 14%, transparent) !important; box-shadow: inset 3px 0 0 var(--ouro); }
.ct-marca { font-family: var(--moderna) !important; font-weight: 800; letter-spacing: -.03em; text-shadow: none !important;
  background: linear-gradient(92deg, var(--texto), var(--ouro)); -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; }
.ct-marca small { -webkit-text-fill-color: var(--suave); font-weight: 500; letter-spacing: 0; font-size: .82rem; line-height: 1.35; }
[data-testid="stMainBlockContainer"] { padding-top: 3.4rem !important; }
.ct-heroi-titulo { font-weight: 800; letter-spacing: -.035em; text-shadow: none !important;
  background: linear-gradient(92deg, var(--texto) 0%, var(--ouro) 70%); -webkit-background-clip: text; background-clip: text;
  -webkit-text-fill-color: transparent; }
.ct-slogan { font-weight: 600; text-shadow: none !important; }
.ct-secao { font-family: var(--moderna) !important; font-weight: 700; font-size: .72rem; letter-spacing: .12em; }
.ct-tempo .trilho { border: 1px solid color-mix(in srgb, var(--borda) 90%, transparent) !important; border-radius: 999px !important;
  height: 16px !important; background: rgba(255,255,255,.06) !important; box-shadow: inset 0 1px 3px rgba(0,0,0,.4) !important; }
.ct-tempo .preenchido { border-radius: 999px; position: relative; overflow: hidden;
  background: linear-gradient(90deg, color-mix(in srgb, var(--ouro) 65%, var(--portal)), var(--ouro)) !important;
  animation: ct-encher-suave 1.4s cubic-bezier(.2,.8,.2,1) both !important; box-shadow: 0 0 18px color-mix(in srgb, var(--ouro) 55%, transparent); }
.ct-tempo .preenchido::after { content: ""; position: absolute; inset: 0;
  background: linear-gradient(100deg, transparent 20%, rgba(255,255,255,.45) 50%, transparent 80%);
  transform: translateX(-100%); animation: ct-brilho 3.2s ease-in-out 1.4s infinite; }
@keyframes ct-encher-suave { from { width: 0; } }
@keyframes ct-brilho { 60%, 100% { transform: translateX(100%); } }
.ct-aviso { border-radius: 12px; border-style: solid; border-width: 1px; background: color-mix(in srgb, var(--ouro) 8%, transparent); }
.ct-selo { font-family: var(--moderna); font-weight: 700; border-radius: 999px; border-width: 1.5px; }
.ct-era .quando { font-family: var(--moderna); font-weight: 700; }
@media (prefers-reduced-motion: reduce) {
  [data-testid="stAppViewContainer"]::before, .ct-tempo .preenchido::after { animation: none !important; }
  .ct-janela:hover, [data-testid="stMetric"]:hover { transform: none; } }
</style>"""


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


def _modelo(t: dict) -> go.layout.Template:
    """O visual dos gráficos para um tema (montado na hora: cada pessoa pode usar um tema diferente)."""
    moderno = t.get("estilo") == "moderno"
    grade = "rgba(255,255,255,.07)" if moderno else "rgba(233,225,200,.08)"
    linha = "rgba(255,255,255,.18)" if moderno else "rgba(233,225,200,.25)"
    modelo = go.layout.Template()
    modelo.layout = go.Layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=("Plus Jakarta Sans, " if moderno else "") + "Atkinson Hyperlegible, Segoe UI, sans-serif",
                  color=t["texto"], size=14),
        colorway=[t["ouro"], "#5AB6F0", t["portal"], t["jade"], "#F08FB0", "#C9A36A",
                  "#FF9F6B", "#4FD1C5", "#D6C9FF", "#B8E05B", "#E9E1C8", "#7C8CF0"],
        xaxis=dict(gridcolor=grade, zerolinecolor=linha, linecolor=linha, showgrid=not moderno),
        yaxis=dict(gridcolor=grade, zerolinecolor=linha, linecolor=linha),
        hoverlabel=dict(bgcolor=t["tinta_2"] if moderno else t["janela_base"], bordercolor=t["ouro"] if moderno else t["borda"],
                        font=dict(color=t["texto"])),
        legend=dict(bgcolor="rgba(0,0,0,0)", orientation="h", x=0, y=1.02, yanchor="bottom"),
        margin=dict(l=8, r=40, t=36, b=8),
        separators=",.",
        bargap=0.28,
    )
    return modelo


def _registrar_plotly(t: dict | None = None) -> None:
    if t is None:
        pio.templates["chrono"] = _modelo(TEMAS["retro"])
        pio.templates.default = "chrono"


def janela(rotulo: str, valor: str, detalhe: str = "", ouro: bool = False) -> None:
    """Uma janela de diálogo com um número em destaque."""
    st.markdown(
        f'<div class="ct-janela"><div class="rotulo">{html.escape(rotulo)}</div>'
        f'<div class="valor{" ouro" if ouro else ""}">{html.escape(valor)}</div>'
        f'<div class="detalhe">{detalhe}</div></div>',
        unsafe_allow_html=True,
    )


def subtitulo(texto: str) -> None:
    """Uma linha logo abaixo do título dizendo para que serve a tela."""
    st.markdown(f'<p class="ct-subtitulo">{html.escape(texto)}</p>', unsafe_allow_html=True)


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
    fig.update_layout(template=_modelo(paleta()))
    fig.update_xaxes(automargin=True)
    fig.update_yaxes(automargin=True)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, theme=None)


def legenda(texto: str) -> None:
    """Legenda pequena sob um gráfico ou tabela. Escapa o $ para o Streamlit não ler como fórmula."""
    st.caption(texto.replace("$", "\\$"))


from chronotrade.legal import AVISO_LEGAL  # noqa: E402


def aviso_legal() -> None:
    """O aviso legal em letra pequena, no fim das telas que mostram números de investimento."""
    legenda(AVISO_LEGAL)
