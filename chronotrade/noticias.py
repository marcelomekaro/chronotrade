"""Notícias e vídeos: feeds RSS de sites de mercado, busca por ativo e canais do YouTube.

Tudo por RSS (gratuito, sem chave): cada fonte é só um endereço. O administrador
edita a lista no painel; cada pessoa pode adicionar canais do YouTube.
"""

from __future__ import annotations

import html
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import quote

FONTES_PADRAO = [
    ("B3 e Ibovespa", "google:B3 Ibovespa ações"),
    ("Mercado financeiro", "google:mercado financeiro dividendos"),
    ("InfoMoney", "https://www.infomoney.com.br/feed/"),
    ("Money Times", "https://www.moneytimes.com.br/feed/"),
    ("Negócios", "google:economia negócios Brasil"),
]

NOMES_EMPRESAS = {
    "PETR": "Petrobras", "VALE": "Vale", "ITUB": "Itaú", "BBAS": "Banco do Brasil", "BBDC": "Bradesco",
    "TAEE": "Taesa", "EGIE": "Engie Brasil", "WEGE": "WEG", "BBSE": "BB Seguridade", "ABEV": "Ambev",
    "ITSA": "Itaúsa", "CMIG": "Cemig", "SAPR": "Sanepar", "KLBN": "Klabin", "CPLE": "Copel",
}

_YT_ID = re.compile(r"(?:v=|youtu\.be/|/live/|/shorts/|/embed/)([A-Za-z0-9_-]{11})")
_YT_CANAL = re.compile(r"(UC[A-Za-z0-9_-]{22})")


@dataclass
class Item:
    titulo: str
    link: str
    fonte: str
    data: datetime | None
    resumo: str = ""
    video_id: str = ""


def url_google_news(busca: str) -> str:
    return f"https://news.google.com/rss/search?q={quote(busca)}&hl=pt-BR&gl=BR&ceid=BR:pt-419"


def busca_do_ativo(ticker: str) -> str:
    curto = ticker.replace(".SA", "").upper()
    nome = NOMES_EMPRESAS.get(curto[:4], "")
    return f'"{curto}" OR "{nome}"' if nome else f'"{curto}"'


def resolver(endereco: str) -> str:
    """'google:termo' vira o RSS do Google Notícias; 'UC…' vira o RSS do canal do YouTube."""
    endereco = endereco.strip()
    if endereco.startswith("google:"):
        return url_google_news(endereco[7:])
    canal = _YT_CANAL.search(endereco)
    if canal and ("youtube" in endereco or endereco.startswith("UC")):
        return f"https://www.youtube.com/feeds/videos.xml?channel_id={canal.group(1)}"
    return endereco


def ler_fontes(texto: str | None) -> list[tuple[str, str]]:
    """Lista de fontes escrita pelo admin: JSON [[nome, url], ...] ou linhas "Nome | endereço"."""
    texto = (texto or "").strip()
    if not texto:
        return list(FONTES_PADRAO)
    if texto.startswith("["):
        try:
            return [(str(n), str(u)) for n, u in json.loads(texto)] or list(FONTES_PADRAO)
        except (ValueError, TypeError):
            return list(FONTES_PADRAO)
    fontes = []
    for linha in texto.splitlines():
        if not linha.strip():
            continue
        nome, _, endereco = linha.partition("|")
        if not endereco.strip():
            nome, endereco = linha.strip()[:30], linha.strip()
        fontes.append((nome.strip(), endereco.strip()))
    return fontes or list(FONTES_PADRAO)


def ler_canais(texto: str | None) -> list[str]:
    """Canais do YouTube, um por linha ("Nome | link" ou só o link): devolve os endereços."""
    return [(ln.partition("|")[2] or ln).strip() for ln in (texto or "").splitlines() if ln.strip()]


def id_video(url: str) -> str:
    m = _YT_ID.search(url or "")
    return m.group(1) if m else ""


def _limpar(texto: str) -> str:
    sem_tags = re.sub(r"<[^>]+>", " ", texto or "")
    return re.sub(r"\s+", " ", html.unescape(sem_tags)).strip()


def _data(texto: str | None) -> datetime | None:
    if not texto:
        return None
    try:
        return parsedate_to_datetime(texto).replace(tzinfo=None)
    except (TypeError, ValueError):
        try:
            return datetime.fromisoformat(texto.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return None


def interpretar(xml_texto: str | bytes, fonte: str) -> list[Item]:
    """Lê RSS 2.0 (sites, Google Notícias) e Atom (YouTube)."""
    raiz = ET.fromstring(xml_texto)
    itens: list[Item] = []
    for item in raiz.iter("item"):
        titulo = _limpar(item.findtext("title"))
        origem = item.find("source")
        nome_fonte = origem.text.strip() if origem is not None and origem.text else fonte
        if nome_fonte and titulo.endswith(f" - {nome_fonte}"):
            titulo = titulo[: -len(nome_fonte) - 3]
        itens.append(Item(titulo, (item.findtext("link") or "").strip(), nome_fonte, _data(item.findtext("pubDate")),
                          _limpar(item.findtext("description"))[:280]))
    atom = "{http://www.w3.org/2005/Atom}"
    yt = "{http://www.youtube.com/xml/schemas/2015}"
    for entrada in raiz.iter(f"{atom}entry"):
        link = entrada.find(f"{atom}link")
        autor = entrada.find(f"{atom}author/{atom}name")
        itens.append(Item(_limpar(entrada.findtext(f"{atom}title")), link.get("href", "") if link is not None else "",
                          autor.text if autor is not None and autor.text else fonte,
                          _data(entrada.findtext(f"{atom}published")), "",
                          entrada.findtext(f"{yt}videoId") or ""))
    return itens


def buscar(endereco: str, fonte: str, baixar=None, limite: int = 12) -> list[Item]:
    """Baixa e lê um feed. Em caso de erro devolve lista vazia (a tela avisa)."""
    url = resolver(endereco)
    pedido = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 ChronoTrade/1.0"})
    try:
        dados = (baixar or (lambda r: urllib.request.urlopen(r, timeout=12).read()))(pedido)
        return interpretar(dados, fonte)[:limite]
    except Exception:
        return []


def demo(tickers: list[str]) -> list[Item]:
    """Manchetes fictícias para o modo demonstração (marcadas como exemplo)."""
    agora = datetime.now()
    base = [
        ("Ibovespa fecha em alta puxado por bancos e mineração", "Exemplo B3"),
        ("Empresas elétricas anunciam calendário de dividendos do trimestre", "Exemplo Mercado"),
        ("Fundos imobiliários de logística seguem com vacância baixa", "Exemplo FIIs"),
    ]
    base += [(f"{t.replace('.SA', '')}: conselho aprova pagamento de proventos", "Exemplo Empresa") for t in tickers[:4]]
    return [Item(t, "https://www.b3.com.br", f, agora - timedelta(hours=3 * i), "Notícia de exemplo do modo demonstração.")
            for i, (t, f) in enumerate(base)]
