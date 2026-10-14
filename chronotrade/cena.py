"""A cena do Pregão: o salão de negociação em pixel art, com mesas, telão, letreiro e avatares.

Gera HTML e CSS puros (sem imagens externas). Cada pessoa online ocupa uma
mesa; quem falou há pouco ganha um balão com a mensagem.
"""

from __future__ import annotations

import html

from chronotrade import avatar as av

_CSS = """
<style>
.ct-salao { position: relative; border: 3px solid #E9E1C8; border-radius: 8px; overflow: hidden;
  box-shadow: inset 0 0 0 3px #0B1040, 4px 4px 0 #0A0E26;
  background:
    repeating-linear-gradient(0deg, rgba(0,0,0,.18) 0 2px, transparent 2px 32px),
    repeating-linear-gradient(90deg, rgba(0,0,0,.18) 0 2px, transparent 2px 32px),
    linear-gradient(180deg, #3A2F5B 0%, #2B2550 38%, #24305E 100%);
  font-family: 'Atkinson Hyperlegible', 'Segoe UI', sans-serif; color: #EDE6D2; }
.ct-letreiro { background: #05071A; border-bottom: 3px solid #E9E1C8; white-space: nowrap; overflow: hidden;
  font-family: 'Pixelify Sans', 'Courier New', monospace; font-size: 15px; padding: 6px 0; }
.ct-letreiro span { display: inline-block; padding-left: 100%; animation: ct-rolar 38s linear infinite; }
.ct-letreiro b { margin: 0 18px; } .ct-letreiro .s { color: #5FD39A; } .ct-letreiro .d { color: #F06A5D; }
@keyframes ct-rolar { to { transform: translateX(-100%); } }
.ct-telao { margin: 14px auto 6px; width: min(78%, 560px); background: #0B1040; border: 3px solid #E9E1C8;
  border-radius: 4px; padding: 8px 14px; text-align: center; box-shadow: 0 0 18px rgba(164,139,255,.35); }
.ct-telao .t { font-family: 'Pixelify Sans', 'Courier New', monospace; color: #F2C14E; font-size: 20px; }
.ct-telao .s { color: #A9B0D6; font-size: 13px; }
.ct-mesas { display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 18px 10px;
  padding: 26px 16px 18px; }
.ct-lugar { position: relative; display: flex; flex-direction: column; align-items: center; min-height: 205px;
  justify-content: flex-end; }
.ct-lugar .mesa { width: 92px; height: 18px; background: #6B4A2B; border: 2px solid #0A0E26; border-radius: 2px;
  box-shadow: 0 4px 0 #3D2A17; margin-top: -6px; position: relative; z-index: 1; }
.ct-lugar .tela { position: absolute; bottom: 14px; left: 50%; transform: translateX(8px); width: 26px; height: 18px;
  background: #121838; border: 2px solid #0A0E26; z-index: 2; }
.ct-lugar .tela::after { content: ""; position: absolute; left: 3px; right: 3px; top: 7px; height: 2px; background: #5FD39A; }
.ct-lugar .nome { margin-top: 8px; font-size: 13px; background: rgba(5,7,26,.75); padding: 1px 8px; border-radius: 3px;
  max-width: 116px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ct-lugar .eu { color: #F2C14E; }
.ct-lugar.vazio { opacity: .35; }
.ct-balao { position: absolute; bottom: 118px; left: 50%; transform: translateX(-50%); width: 150px;
  background: #E9E1C8; color: #1B1606; border: 2px solid #0A0E26; border-radius: 6px; padding: 5px 7px;
  font-size: 12px; line-height: 1.3; z-index: 3; box-shadow: 3px 3px 0 #0A0E26;
  display: -webkit-box; -webkit-line-clamp: 4; -webkit-box-orient: vertical; overflow: hidden; }
.ct-balao::after { content: ""; position: absolute; left: 50%; bottom: -8px; margin-left: -5px;
  border: 5px solid transparent; border-top-color: #E9E1C8; }
@media (prefers-reduced-motion: reduce) { .ct-letreiro span { animation: none; padding-left: 12px; } }
@media (max-width: 640px) { .ct-mesas { grid-template-columns: repeat(2, 1fr); padding-top: 8px; } .ct-balao { width: 140px; } }
</style>
"""


def letreiro(cotacoes: list[tuple[str, float | None, float | None]]) -> str:
    """Faixa de cotações que corre no alto do salão: (ativo, preço, variação do dia)."""
    itens = []
    for ativo, preco, var in cotacoes:
        if preco is None:
            continue
        classe = "s" if (var or 0) >= 0 else "d"
        seta = "▲" if (var or 0) >= 0 else "▼"
        texto_var = f"{(var or 0) * 100:+.2f}%".replace(".", ",")
        itens.append(f'<b>{html.escape(ativo)} {preco:,.2f}'.replace(",", "X").replace(".", ",").replace("X", ".")
                     + f' <span class="{classe}">{seta} {texto_var}</span></b>')
    return f'<div class="ct-letreiro"><span>{"".join(itens) or "<b>Mercado</b>"}</span></div>'


def salao(participantes: list[tuple[str, str, str | None]], falas: dict[str, str], eu: str = "",
          titulo: str = "Pregão geral", subtitulo: str = "", cotacoes=None, lugares_minimos: int = 8) -> str:
    """O HTML do salão. ``participantes`` = [(email, apelido, avatar_json)]."""
    blocos = []
    for email, apelido, avatar_json in participantes:
        a = av.Avatar.de_json(avatar_json) or av.sortear(email)
        balao = ""
        if email in falas:
            balao = f'<div class="ct-balao">{html.escape(falas[email][:160])}</div>'
        classe_nome = "nome eu" if email == eu else "nome"
        blocos.append(f'<div class="ct-lugar">{balao}{av.img(a, 64, apelido)}<div class="tela"></div>'
                      f'<div class="mesa"></div><div class="{classe_nome}">{html.escape(apelido)}</div></div>')
    for _ in range(max(0, lugares_minimos - len(participantes))):
        blocos.append('<div class="ct-lugar vazio"><div class="tela"></div><div class="mesa"></div>'
                      '<div class="nome">livre</div></div>')
    gente = len(participantes)
    return (_CSS + '<div class="ct-salao" role="img" aria-label="Salão do pregão com '
            f'{gente} pessoa{"s" if gente != 1 else ""} online">'
            + (letreiro(cotacoes) if cotacoes else "")
            + f'<div class="ct-telao"><div class="t">{html.escape(titulo)}</div>'
              f'<div class="s">{html.escape(subtitulo)}, {gente} online agora</div></div>'
            + f'<div class="ct-mesas">{"".join(blocos)}</div></div>')
