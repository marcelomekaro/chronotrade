"""Avatares em pixel art para o Pregão: bonequinhos originais desenhados em SVG.

Cada avatar é uma grade de 12×16 "pixels" montada a partir de poucas escolhas
(pele, cabelo, roupa, acessório). Nada aqui copia personagens existentes.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

PELES = ["#F1C27D", "#E0AC69", "#C68642", "#8D5524", "#5C3A21", "#FFDBAC"]
CABELOS = ["curto", "longo", "careca", "coque", "bone", "cacheado"]
CORES_CABELO = ["#2B1B0E", "#5A3214", "#B5651D", "#E8C547", "#C0C0C0", "#7A3BE0"]
ROUPAS = ["#2B3BA0", "#F2C14E", "#5FD39A", "#F06A5D", "#A48BFF", "#E9E1C8", "#1C1C28", "#4FD1C5"]
ACESSORIOS = ["nenhum", "gravata", "oculos", "fone", "cracha"]
NOMES = {"curto": "Curto", "longo": "Longo", "careca": "Careca", "coque": "Coque", "bone": "Boné",
         "cacheado": "Cacheado", "nenhum": "Nenhum", "gravata": "Gravata", "oculos": "Óculos",
         "fone": "Fone", "cracha": "Crachá"}


@dataclass
class Avatar:
    pele: str = PELES[0]
    cabelo: str = "curto"
    cor_cabelo: str = CORES_CABELO[0]
    roupa: str = ROUPAS[0]
    acessorio: str = "gravata"

    def json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def de_json(cls, texto: str | None) -> Avatar | None:
        if not texto:
            return None
        try:
            dados = json.loads(texto)
            return cls(**{k: v for k, v in dados.items() if k in cls.__dataclass_fields__})
        except (ValueError, TypeError):
            return None


def sortear(semente: str) -> Avatar:
    """Um avatar estável a partir do e-mail, para quem ainda não personalizou o seu."""
    n = int(hashlib.sha256(semente.encode()).hexdigest(), 16)
    return Avatar(PELES[n % len(PELES)], CABELOS[(n >> 4) % len(CABELOS)],
                  CORES_CABELO[(n >> 8) % len(CORES_CABELO)], ROUPAS[(n >> 12) % len(ROUPAS)],
                  ACESSORIOS[(n >> 16) % len(ACESSORIOS)])


def _pixels(a: Avatar) -> list[tuple[int, int, str]]:
    """Lista de (x, y, cor) numa grade 12 de largura × 16 de altura."""
    px: list[tuple[int, int, str]] = []
    contorno = "#0A0E26"

    def ret(x0, y0, x1, y1, cor):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                px.append((x, y, cor))

    # cabeça
    ret(3, 2, 8, 7, a.pele)
    px += [(4, 4, contorno), (7, 4, contorno)]           # olhos
    ret(5, 6, 6, 6, "#B5533C")                           # boca
    # cabelo
    if a.cabelo == "curto":
        ret(3, 1, 8, 2, a.cor_cabelo)
        px += [(3, 3, a.cor_cabelo), (8, 3, a.cor_cabelo)]
    elif a.cabelo == "longo":
        ret(3, 1, 8, 2, a.cor_cabelo)
        ret(2, 2, 2, 8, a.cor_cabelo)
        ret(9, 2, 9, 8, a.cor_cabelo)
    elif a.cabelo == "coque":
        ret(5, 0, 6, 0, a.cor_cabelo)
        ret(3, 1, 8, 2, a.cor_cabelo)
    elif a.cabelo == "bone":
        ret(3, 1, 8, 2, a.roupa)
        ret(8, 2, 10, 2, a.roupa)
    elif a.cabelo == "cacheado":
        ret(2, 1, 9, 2, a.cor_cabelo)
        px += [(2, 3, a.cor_cabelo), (9, 3, a.cor_cabelo), (2, 5, a.cor_cabelo), (9, 5, a.cor_cabelo)]
    # corpo
    ret(2, 8, 9, 13, a.roupa)
    ret(0, 9, 1, 12, a.roupa)
    ret(10, 9, 11, 12, a.roupa)
    px += [(0, 13, a.pele), (1, 13, a.pele), (10, 13, a.pele), (11, 13, a.pele)]  # mãos
    ret(3, 14, 4, 15, "#1C1C28")
    ret(7, 14, 8, 15, "#1C1C28")
    # acessório
    if a.acessorio == "gravata":
        ret(5, 8, 6, 8, "#E9E1C8")
        ret(5, 9, 6, 12, "#F06A5D")
    elif a.acessorio == "oculos":
        ret(3, 4, 4, 4, contorno)
        ret(7, 4, 8, 4, contorno)
        px += [(5, 4, contorno), (6, 4, contorno)]
    elif a.acessorio == "fone":
        ret(2, 3, 2, 5, "#1C1C28")
        ret(9, 3, 9, 5, "#1C1C28")
        ret(3, 0, 8, 0, "#1C1C28")
    elif a.acessorio == "cracha":
        ret(6, 10, 7, 11, "#E9E1C8")
        px.append((6, 10, "#2B3BA0"))
    return px


def svg(a: Avatar, tamanho: int = 48, rotulo: str = "") -> str:
    """O avatar como SVG nítido (pixels quadrados), pronto para pôr no HTML."""
    escala = tamanho / 16
    rects = "".join(f'<rect x="{x}" y="{y}" width="1" height="1" fill="{c}"/>' for x, y, c in _pixels(a))
    titulo = f"<title>{rotulo}</title>" if rotulo else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 12 16" width="{12 * escala:.0f}" '
            f'height="{tamanho}" shape-rendering="crispEdges" role="img">{titulo}{rects}</svg>')


def img(a: Avatar, tamanho: int = 48, rotulo: str = "") -> str:
    """O avatar como <img> com SVG embutido (passa pelo filtro de HTML do Streamlit)."""
    import base64
    import html as _html

    dados = base64.b64encode(svg(a, tamanho, rotulo).encode()).decode()
    return (f'<img src="data:image/svg+xml;base64,{dados}" width="{12 * tamanho / 16:.0f}" height="{tamanho}" '
            f'alt="{_html.escape(rotulo)}" style="image-rendering:pixelated">')


def data_uri(a: Avatar, tamanho: int = 64) -> str:
    import base64

    return "data:image/svg+xml;base64," + base64.b64encode(svg(a, tamanho).encode()).decode()


def retrato(avatar_json: str | None, foto: str | None, semente: str, tamanho: int = 48, rotulo: str = "") -> str:
    """A foto da pessoa (redonda) ou, se não tiver, o bonequinho em pixel art."""
    import html as _html

    if foto:
        return (f'<img src="{_html.escape(foto)}" width="{tamanho}" height="{tamanho}" alt="{_html.escape(rotulo)}" '
                f'style="border-radius:50%;object-fit:cover;border:2px solid #E9E1C8;box-shadow:0 0 0 2px #0B1040">')
    return img(Avatar.de_json(avatar_json) or sortear(semente), tamanho, rotulo)


LADO_FOTO = 192


def processar_foto(dados: bytes, estilo_pixel: bool = False, lado: int = LADO_FOTO) -> str:
    """Recorta a foto em quadrado, reduz, tira metadados (EXIF com localização) e devolve um data URI pequeno."""
    import base64
    import io

    from PIL import Image, ImageOps

    try:
        imagem = Image.open(io.BytesIO(dados))
        imagem = ImageOps.exif_transpose(imagem).convert("RGB")
    except Exception as erro:
        raise ValueError("Não consegui abrir essa imagem. Use JPG ou PNG.") from erro
    imagem = ImageOps.fit(imagem, (lado, lado), Image.Resampling.LANCZOS)
    if estilo_pixel:
        imagem = imagem.resize((28, 28), Image.Resampling.BILINEAR).quantize(24).convert("RGB")
        imagem = imagem.resize((lado, lado), Image.Resampling.NEAREST)
    saida = io.BytesIO()
    if estilo_pixel:
        imagem.save(saida, "PNG", optimize=True)
        tipo = "png"
    else:
        imagem.save(saida, "JPEG", quality=82, optimize=True)
        tipo = "jpeg"
    return f"data:image/{tipo};base64," + base64.b64encode(saida.getvalue()).decode()
