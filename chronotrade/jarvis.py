"""Jarvis: comando de voz do Chrono Trade, com o OpenJarvis como cérebro local.

Como funciona:
1. A pessoa fala (microfone do navegador) ou digita.
2. A fala vira texto pelo OpenJarvis (``/v1/speech/transcribe``, Whisper local).
   Sem OpenJarvis, tenta o Gemini (se houver chave); sem nada, pede para digitar.
3. Um intérprete em português entende comandos do app: abrir telas, cotação,
   dica do aporte, proventos, patrimônio, notícias, ordem simulada, compartilhar.
4. O que não é comando vai para o modelo do OpenJarvis (``/v1/chat/completions``)
   com o contexto da carteira e a trava legal (sem recomendação).
5. A resposta volta em voz pelo OpenJarvis (``/v1/speech/synthesize``) ou pela
   voz do próprio navegador.

O OpenJarvis (github.com/open-jarvis/OpenJarvis) roda no seu PC: ``jarvis serve``
na porta 8000. Ele também pode usar as ferramentas do Chrono Trade pelo MCP
(``chronotrade-mcp``), veja GUIA_CHRONOTRADE.md.
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field

from chronotrade.legal import AVISO_CURTO

URL_PADRAO = "http://localhost:8000"

# ---------------------------------------------------------------------------
# Cliente do OpenJarvis
# ---------------------------------------------------------------------------


class Cliente:
    def __init__(self, url: str | None = None, chave: str | None = None, abrir=None, tempo: float = 30):
        self.url = (url or os.environ.get("OPENJARVIS_URL") or URL_PADRAO).rstrip("/")
        self.chave = chave if chave is not None else os.environ.get("OPENJARVIS_API_KEY", "")
        self._abrir = abrir or (lambda pedido, t: urllib.request.urlopen(pedido, timeout=t))
        self.tempo = tempo

    def _pedido(self, caminho: str, dados: bytes | None = None, tipo: str | None = None) -> urllib.request.Request:
        cab = {"Accept": "application/json"}
        if tipo:
            cab["Content-Type"] = tipo
        if self.chave:
            cab["Authorization"] = f"Bearer {self.chave}"
        return urllib.request.Request(self.url + caminho, data=dados, headers=cab, method="POST" if dados else "GET")

    def _ler(self, pedido, tempo: float | None = None) -> bytes:
        resposta = self._abrir(pedido, tempo or self.tempo)
        try:
            return resposta.read()
        finally:
            fechar = getattr(resposta, "close", None)
            if fechar:
                fechar()

    def saude(self) -> dict:
        """{"online": bool, "voz": bool, "detalhe": str}"""
        try:
            info = json.loads(self._ler(self._pedido("/health"), 3) or b"{}")
        except Exception as erro:
            return {"online": False, "voz": False, "detalhe": f"OpenJarvis fora do ar em {self.url} ({type(erro).__name__})."}
        try:
            voz = json.loads(self._ler(self._pedido("/v1/speech/health"), 3)).get("available", False)
        except Exception:
            voz = False
        nome = "Voz local do Chrono Trade" if isinstance(info, dict) and info.get("servico") == "chronotrade-voz" \
            else "OpenJarvis"
        return {"online": True, "voz": bool(voz), "nome": nome,
                "detalhe": f"{nome} conectado" + (" com voz." if voz else ", sem voz.")}

    def transcrever(self, audio: bytes, nome: str = "fala.wav", idioma: str = "pt") -> str:
        limite = uuid.uuid4().hex
        partes = [
            f'--{limite}\r\nContent-Disposition: form-data; name="language"\r\n\r\n{idioma}\r\n'.encode(),
            f'--{limite}\r\nContent-Disposition: form-data; name="file"; filename="{nome}"\r\n'
            "Content-Type: application/octet-stream\r\n\r\n".encode() + audio + b"\r\n",
            f"--{limite}--\r\n".encode(),
        ]
        pedido = self._pedido("/v1/speech/transcribe", b"".join(partes), f"multipart/form-data; boundary={limite}")
        return str(json.loads(self._ler(pedido)).get("text", "")).strip()

    def sintetizar(self, texto: str) -> bytes | None:
        try:
            pedido = self._pedido("/v1/speech/synthesize", json.dumps({"text": texto[:4000]}).encode(), "application/json")
            audio = self._ler(pedido, 60)
            return audio if audio[:4] == b"RIFF" else None
        except Exception:
            return None

    def conversar(self, mensagens: list[dict], modelo: str | None = None) -> str | None:
        corpo = {"messages": mensagens, "stream": False, "temperature": 0.3}
        modelo = modelo or os.environ.get("OPENJARVIS_MODELO")
        if modelo:
            corpo["model"] = modelo
        try:
            dados = json.loads(self._ler(self._pedido("/v1/chat/completions", json.dumps(corpo).encode(), "application/json"), 90))
            return dados["choices"][0]["message"]["content"].strip()
        except Exception:
            return None


def transcrever_gemini(audio: bytes, tipo: str = "audio/wav") -> str | None:
    """Plano B para a voz: o Gemini transcreve (usa a GOOGLE_API_KEY do .env)."""
    chave = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not chave:
        return None
    try:
        from google import genai
        from google.genai import types

        cliente = genai.Client(api_key=chave)
        resposta = cliente.models.generate_content(
            model=os.environ.get("CHRONOTRADE_MODELO_VOZ", "gemini-2.5-flash"),
            contents=["Transcreva exatamente esta fala em português do Brasil. Responda só com o texto.",
                      types.Part.from_bytes(data=audio, mime_type=tipo)])
        return (resposta.text or "").strip() or None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Intérprete de comandos em português
# ---------------------------------------------------------------------------

PAGINAS = {
    "portal": ("paginas/portal.py", ["portal", "inicio", "home", "painel"]),
    "inventario": ("paginas/inventario.py", ["inventario", "minha carteira", "carteira"]),
    "tesouro": ("paginas/tesouro.py", ["tesouro", "renda passiva", "dividendos recebidos"]),
    "agenda": ("paginas/agenda.py", ["agenda", "calendario", "datas com"]),
    "aporte": ("paginas/aporte.py", ["proximo aporte", "aporte"]),
    "linha": ("paginas/linha_do_tempo.py", ["linha do tempo", "projecao", "futuro"]),
    "oraculo": ("paginas/oraculo.py", ["oraculo", "analise com ia"]),
    "corretora": ("paginas/corretora.py", ["corretora", "ordens"]),
    "noticias": ("paginas/noticias.py", ["noticias", "jornal", "videos", "youtube"]),
    "pregao": ("paginas/pregao.py", ["pregao", "sala", "trading floor", "comunidade"]),
    "conexoes": ("paginas/conexoes.py", ["conexoes", "conexao", "metatrader", "profit"]),
    "avisos": ("paginas/avisos.py", ["avisos", "notificacoes"]),
    "conta": ("paginas/conta.py", ["minha conta", "assinatura", "plano"]),
}

EMPRESAS = {
    "petrobras": "PETR4", "itau": "ITUB4", "itausa": "ITSA4", "banco do brasil": "BBAS3", "bradesco": "BBDC4",
    "taesa": "TAEE11", "engie": "EGIE3", "weg": "WEGE3", "bb seguridade": "BBSE3", "ambev": "ABEV3",
    "cemig": "CMIG4", "sanepar": "SAPR11", "klabin": "KLBN11", "copel": "CPLE6", "isa energia": "ISAE4",
    "magazine luiza": "MGLU3", "magalu": "MGLU3", "santander": "SANB11", "eletrobras": "ELET3",
    "suzano": "SUZB3", "gerdau": "GGBR4", "mxrf": "MXRF11", "hglg": "HGLG11", "knri": "KNRI11",
    "ibovespa": "^BVSP", "bovespa": "^BVSP",
}
_VALE = re.compile(r"\b(da vale|acao da vale|acoes da vale|vale (3|tres))\b")

NUMEROS = {
    "um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5, "seis": 6, "sete": 7, "oito": 8,
    "nove": 9, "dez": 10, "onze": 11, "doze": 12, "quinze": 15, "vinte": 20, "trinta": 30, "quarenta": 40,
    "cinquenta": 50, "sessenta": 60, "setenta": 70, "oitenta": 80, "noventa": 90, "cem": 100, "cento": 100,
    "duzentos": 200, "duzentas": 200, "trezentos": 300, "trezentas": 300, "quatrocentos": 400,
    "quinhentos": 500, "quinhentas": 500, "mil": 1000,
}
_TICKER = re.compile(r"\b([a-z]{4})\s?(\d{1,2})\b")
_TICKER_FALADO = re.compile(r"\b([a-z]{4})\s+(" + "|".join(k for k in NUMEROS if NUMEROS[k] <= 12) + r")\b")
_PALAVRAS_COMUNS = {"para", "como", "qual", "quer", "tudo", "isso", "esta", "esse", "cota", "acao", "mais",
                    "meus", "minha", "quero", "agora", "hoje", "cada"}


def normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    sem_acento = re.sub(r"[^\w\s,.$]", " ", sem_acento.lower())
    return re.sub(r"\s+", " ", sem_acento).strip()


def achar_ticker(texto: str) -> str | None:
    t = normalizar(texto)
    for m in _TICKER.finditer(t):
        if m.group(1) not in _PALAVRAS_COMUNS:
            return (m.group(1) + m.group(2)).upper()
    for m in _TICKER_FALADO.finditer(t):
        if m.group(1) not in _PALAVRAS_COMUNS:
            return (m.group(1) + str(NUMEROS[m.group(2)])).upper()
    for nome in sorted(EMPRESAS, key=len, reverse=True):
        if re.search(rf"\b{nome}\b", t):
            return EMPRESAS[nome]
    if _VALE.search(t):
        return "VALE3"
    return None


def achar_quantidade(texto: str) -> int | None:
    t = normalizar(texto)
    m = re.search(r"\b(\d{1,6})\s*(acoes|acao|cotas|cota|papeis|unidades|lotes?)\b", t)
    if m:
        return int(m.group(1)) * (100 if m.group(2).startswith("lote") else 1)
    m = re.search(r"\b(\d{1,6})\s+(?:(?:acoes|cotas|papeis)\s+)?(?:(?:de|da|do)\s+)?[a-z]{4}\s?\d{1,2}\b", t)
    if m:
        return int(m.group(1))
    total, achou = 0, False
    m = re.search(r"\b((?:[a-z]+\s(?:e\s)?)+)(acoes|acao|cotas|cota)\b", t)
    if m:
        for palavra in m.group(1).split():
            if palavra == "mil":
                total, achou = (total or 1) * 1000, True
            elif palavra in NUMEROS:
                total, achou = total + NUMEROS[palavra], True
    return total if achou and total > 0 else None


def achar_preco(texto: str) -> float | None:
    t = normalizar(texto)
    m = re.search(r"\b(?:a|por|preco de|limite de|ate)\s+r?\$?\s*(\d+(?:[.,]\d{1,2})?)\s*(?:reais)?", t)
    if m and ("reais" in t or "r$" in t or "preco" in t or "limite" in t or "," in m.group(1) or "." in m.group(1)):
        return float(m.group(1).replace(",", "."))
    return None


@dataclass
class Comando:
    acao: str                     # navegar, cotacao, dica, proventos, patrimonio, noticias, ordem, compartilhar, ajuda, conversa
    texto: str
    ticker: str | None = None
    pagina: str | None = None
    lado: str | None = None
    quantidade: int | None = None
    preco: float | None = None


def entender(texto: str) -> Comando:
    t = normalizar(texto)
    if not t:
        return Comando("ajuda", texto)
    if re.search(r"\b(ajuda|o que voce faz|o que voce sabe|comandos)\b", t):
        return Comando("ajuda", texto)
    ticker = achar_ticker(t)
    venda = re.search(r"\b(vend[ae]r?|vendo|venda)\b", t)
    compra = re.search(r"\b(compr[ae]r?|compro|compra)\b", t)
    if re.search(r"\b(devo|deveria|vale a pena|recomenda|sugere|indica)\b", t):
        return Comando("conversa", texto, ticker)  # pedido de recomendação: o modelo explica, sem recomendar
    if (venda or compra) and ticker:
        return Comando("ordem", texto, ticker, lado="venda" if venda else "compra",
                       quantidade=achar_quantidade(t), preco=achar_preco(t))
    if re.search(r"\b(whats|whatsapp|zap|compartilh|mand[ae] pro|envi[ae] pr)\w*", t):
        return Comando("compartilhar", texto, ticker)
    if re.search(r"\b(abr[ae]|abrir|ir para|vai para|va para|mostr[ae]|leva|entra)\w*", t):
        for chave, (_, termos) in PAGINAS.items():
            if any(re.search(rf"\b{termo}\b", t) for termo in termos):
                return Comando("navegar", texto, ticker, pagina=chave)
    if re.search(r"\b(patrimonio|quanto (eu )?tenho|quanto vale (a |minha )?carteira|meu saldo|resumo da carteira)\b", t):
        return Comando("patrimonio", texto)
    if re.search(r"\b(dica|proximo aporte|onde aportar|o que comprar|aporte do mes)\b", t):
        return Comando("dica", texto)
    if re.search(r"\b(provento|proventos|dividendo|dividendos|data com|jcp|rendimento)\b", t):
        return Comando("proventos", texto, ticker)
    if re.search(r"\b(noticia|noticias|novidade|aconteceu)\b", t):
        return Comando("noticias", texto, ticker)
    if ticker and re.search(r"\b(cotacao|preco|quanto (esta|ta|custa)|como esta|como ta|subiu|caiu)\b", t):
        return Comando("cotacao", texto, ticker)
    if ticker and len(t.split()) <= 3:
        return Comando("cotacao", texto, ticker)
    return Comando("conversa", texto, ticker)


# ---------------------------------------------------------------------------
# Executar
# ---------------------------------------------------------------------------


@dataclass
class Resposta:
    texto: str
    pagina: str | None = None              # caminho de página para abrir
    ordem: dict | None = None              # ordem simulada aguardando confirmação
    compartilhar: str | None = None        # texto pronto para o WhatsApp
    dados: dict = field(default_factory=dict)


AJUDA = ("Posso abrir telas (\"abrir agenda\"), dar cotação (\"cotação da Petrobras\"), montar a dica do próximo "
         "aporte (\"qual a dica do aporte?\"), listar proventos, dizer o patrimônio, trazer notícias de um ativo, "
         "preparar uma ordem na carteira simulada (\"comprar 100 TAEE11\", você confirma antes) e compartilhar "
         "no WhatsApp. Outras perguntas eu respondo com o modelo do OpenJarvis.")

SISTEMA = ("Você é o Jarvis do Chrono Trade, assistente de voz de um app de carteira buy and hold na B3. "
           "Responda em português do Brasil, em até 4 frases curtas, próprias para serem faladas. "
           "Explique conceitos e use os dados da carteira quando ajudar. Nunca recomende comprar ou vender "
           "um ativo específico, nunca prometa retorno e lembre que a decisão é do investidor quando o assunto "
           "for comprar ou vender (regras da CVM). Se não souber, diga que não sabe.")


def _brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


@dataclass
class Contexto:
    """O que o Jarvis precisa do app. Funções para manter o intérprete testável."""
    carteira: object
    obter: Callable[[str], object]
    dica: Callable[[], object] | None = None
    noticias: Callable[[str | None], list] | None = None
    conversar: Callable[[list[dict]], str | None] | None = None
    resumo: Callable[[], dict] | None = None


def _resumo_texto(ctx: Contexto) -> str:
    if ctx.resumo is None:
        return ""
    r = ctx.resumo()
    return (f"Patrimônio {_brl(r.get('patrimonio', 0))}, {r.get('ativos', 0)} ativos, renda de proventos em 12 meses "
            f"{_brl(r.get('renda_12m', 0))}.")


def executar(cmd: Comando, ctx: Contexto, historico: list[dict] | None = None) -> Resposta:
    if cmd.acao == "ajuda":
        return Resposta(AJUDA)
    if cmd.acao == "navegar":
        caminho, termos = PAGINAS[cmd.pagina]
        return Resposta(f"Abrindo {termos[0]}.", pagina=caminho)
    if cmd.acao == "cotacao":
        d = ctx.obter(cmd.ticker if cmd.ticker.startswith("^") else cmd.ticker + ".SA")
        preco = getattr(d, "preco", None)
        if not preco:
            return Resposta(f"Não consegui a cotação de {cmd.ticker} agora.")
        var = d.variacao_dia() if callable(getattr(d, "variacao_dia", None)) else getattr(d, "variacao_dia", None)
        nome = "O Ibovespa" if cmd.ticker == "^BVSP" else cmd.ticker
        valor = f"{preco:,.0f} pontos".replace(",", ".") if cmd.ticker == "^BVSP" else _brl(preco)
        texto = f"{nome} está em {valor}"
        if var is not None:
            texto += f", {'alta' if var >= 0 else 'queda'} de {abs(var) * 100:.2f}% no dia".replace(".", ",")
        return Resposta(texto + ".", compartilhar=f"{nome}: {valor}.", dados={"ticker": cmd.ticker, "preco": preco})
    if cmd.acao == "patrimonio":
        texto = _resumo_texto(ctx) or "Cadastre a sua carteira no Inventário para eu calcular o patrimônio."
        return Resposta(texto, pagina=None, compartilhar=None)
    if cmd.acao == "dica":
        if ctx.dica is None:
            return Resposta("A dica do aporte precisa da carteira cadastrada.", pagina=PAGINAS["aporte"][0])
        dica = ctx.dica()
        texto = getattr(dica, "texto", str(dica))
        return Resposta(texto, compartilhar=texto)
    if cmd.acao == "proventos":
        eventos, previstos = [], []
        for p in getattr(ctx.carteira, "posicoes", []):
            if cmd.ticker and not p.ticker.upper().startswith(cmd.ticker.upper()):
                continue
            d = ctx.obter(p.ticker)
            prox = getattr(d, "proximo_provento", None)
            if prox:
                eventos.append((prox[0], p.ticker.replace(".SA", ""), prox[1] * p.quantidade))
                continue
            divs = getattr(d, "dividendos", None)
            if divs is not None and len(divs):
                from datetime import date as _date

                from chronotrade import agenda

                prev = agenda.prever(p.ticker, divs, p.quantidade, _date.today(), meses=2)
                if prev:
                    e = min(prev, key=lambda x: x.data)
                    previstos.append((e.data, p.ticker.replace(".SA", ""), e.total))
        if not (eventos or previstos):
            return Resposta("Não encontrei proventos anunciados nem previstos para os próximos 60 dias. "
                            "A Agenda mostra o ano inteiro.", pagina=PAGINAS["agenda"][0])
        partes = []
        if eventos:
            partes.append("Anunciadas: " + "; ".join(f"{t} em {d:%d/%m}, cerca de {_brl(v)}"
                                                     for d, t, v in sorted(eventos)[:5]))
        if previstos:
            partes.append("Previstas pelo histórico: " + "; ".join(f"{t} perto de {d:%d/%m}, uns {_brl(v)}"
                                                                    for d, t, v in sorted(previstos)[:4]))
        texto = ". ".join(partes) + "."
        return Resposta("Próximas datas com. " + texto, compartilhar=texto, pagina=PAGINAS["agenda"][0])
    if cmd.acao == "noticias":
        itens = ctx.noticias(cmd.ticker) if ctx.noticias else []
        if not itens:
            return Resposta("Não encontrei notícias agora.", pagina=PAGINAS["noticias"][0])
        manchetes = [i.titulo for i in itens[:3]]
        alvo = f" sobre {cmd.ticker}" if cmd.ticker else ""
        return Resposta(f"Manchetes{alvo}: " + ". ".join(manchetes) + ".", compartilhar="\n".join(
            f"• {i.titulo} {i.link}" for i in itens[:3]))
    if cmd.acao == "ordem":
        if not cmd.quantidade:
            return Resposta(f"Quantas {'cotas' if cmd.ticker.endswith('11') else 'ações'} de {cmd.ticker}? "
                            f"Diga, por exemplo: {'comprar' if cmd.lado == 'compra' else 'vender'} 100 {cmd.ticker}.")
        ordem = {"ticker": cmd.ticker, "lado": cmd.lado, "quantidade": cmd.quantidade, "preco": cmd.preco}
        verbo = "Compra" if cmd.lado == "compra" else "Venda"
        preco = f" a {_brl(cmd.preco)}" if cmd.preco else " a mercado"
        return Resposta(f"{verbo} de {cmd.quantidade} {cmd.ticker}{preco} na carteira simulada. Confirme na tela. "
                        "A decisão é sua.", ordem=ordem)
    if cmd.acao == "compartilhar":
        base = _resumo_texto(ctx) or "Estou acompanhando a minha carteira no Chrono Trade."
        if cmd.ticker:
            r = executar(Comando("cotacao", cmd.texto, cmd.ticker), ctx)
            base = r.compartilhar or r.texto
        return Resposta("Preparei a mensagem. Toque em enviar no WhatsApp e escolha o contato.", compartilhar=base)
    # conversa livre
    if ctx.conversar:
        mensagens = [{"role": "system", "content": SISTEMA + " Dados da carteira: " + (_resumo_texto(ctx) or "vazia")}]
        mensagens += (historico or [])[-6:]
        mensagens.append({"role": "user", "content": cmd.texto})
        resposta = ctx.conversar(mensagens)
        if resposta:
            if re.search(r"\b(compre|venda|comprar|vender)\b", normalizar(resposta)) and AVISO_CURTO not in resposta:
                resposta += " " + AVISO_CURTO
            return Resposta(resposta)
    if re.search(r"\b(devo|deveria|vale a pena|recomenda|sugere|indica)\b", normalizar(cmd.texto)):
        return Resposta("Não posso recomendar compra ou venda: isso é papel de um profissional registrado na CVM. "
                        "Posso mostrar o preço justo, o preço de entrada e o momento técnico pelas suas regras "
                        "na tela Próximo Aporte. A decisão é sua.", pagina=PAGINAS["aporte"][0])
    return Resposta("Não entendi como comando. " + AJUDA.split(". Outras")[0] + ". Ligue o OpenJarvis para conversas livres.")


_NUM_FALADO = {1: "um", 2: "dois", 3: "três", 4: "quatro", 5: "cinco", 6: "seis", 7: "sete", 8: "oito",
               9: "nove", 10: "dez", 11: "onze", 12: "doze"}


def para_fala(texto: str) -> str:
    """Deixa o texto bom de ouvir: tickers viram nomes, R$ vira reais, % vira por cento."""
    nomes = {v: k for k, v in EMPRESAS.items() if not v.startswith("^")}
    from chronotrade.noticias import NOMES_EMPRESAS

    def ticker(m):
        codigo = m.group(0).upper()
        if codigo in nomes or codigo[:4] in NOMES_EMPRESAS:
            nome = NOMES_EMPRESAS.get(codigo[:4]) or nomes[codigo].title()
            return f"{nome} {_NUM_FALADO.get(int(m.group(2)), m.group(2))}"
        return " ".join(m.group(1)) + " " + _NUM_FALADO.get(int(m.group(2)), m.group(2))

    def reais(m):
        inteiro, centavos = m.group(1).replace(".", ""), m.group(2) or "00"
        falado = f"{inteiro} {'real' if inteiro == '1' else 'reais'}"
        return falado + (f" e {int(centavos)} centavos" if int(centavos) else "")

    texto = re.sub(r"\bR\$\s?(\d{1,3}(?:\.\d{3})*|\d+)(?:,(\d{2}))?", reais, texto)
    texto = re.sub(r"\b([A-Z]{4})(\d{1,2})\b", ticker, texto)
    texto = re.sub(r"(\d),(\d+)\s?%", lambda m: f"{m.group(1)} vírgula {m.group(2).rstrip('0') or '0'} por cento", texto)
    texto = texto.replace("%", " por cento").replace("^BVSP", "Ibovespa")
    return re.sub(r"\s+", " ", texto).strip()


def falar_no_navegador(texto: str) -> str:
    """HTML que lê o texto com a voz do navegador (plano B quando o OpenJarvis não tem voz)."""
    seguro = json.dumps(texto[:1200]).replace("</", "<\\/")
    return ("<script>try{const u=new SpeechSynthesisUtterance(" + seguro + ");u.lang='pt-BR';u.rate=1.05;"
            "const v=speechSynthesis.getVoices().find(x=>x.lang&&x.lang.startsWith('pt'));if(v)u.voice=v;"
            "speechSynthesis.cancel();speechSynthesis.speak(u);}catch(e){}</script>")


def config_mcp(comando: str = "chronotrade-mcp") -> str:
    """Trecho para colar no ~/.openjarvis/config.toml e dar ao OpenJarvis as ferramentas do Chrono Trade."""
    servidores = json.dumps([{"name": "chronotrade", "command": comando, "args": []}])
    return f"[tools.mcp]\nenabled = true\nservers = '{servidores}'\n"
