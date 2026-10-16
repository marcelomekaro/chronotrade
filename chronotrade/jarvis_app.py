"""O Jarvis dentro do app: comandos que mexem nas telas e o modo mãos livres (em todas as telas).

A tela Jarvis e o botão flutuante usam as mesmas funções daqui, então a conversa é uma só.
"""

from __future__ import annotations

import base64
import os
import time
from pathlib import Path

import streamlit as st

from chronotrade import estado, jarvis, noticias
from chronotrade.carteira import pasta_dados

_PASTA = Path(__file__).parent / "componentes" / "jarvis"
_componente = None
JANELA_CONVERSA = 20      # segundos em que dá para falar de novo sem dizer "Jarvis"


def url() -> str:
    return (st.session_state.get("openjarvis_url") or estado.config_loja().get("openjarvis_url")
            or os.environ.get("OPENJARVIS_URL") or jarvis.URL_PADRAO)


@st.cache_data(ttl=45, show_spinner=False)
def _saude(endereco: str) -> dict:
    return jarvis.Cliente(endereco).saude()


def saude(atualizar: bool = False) -> dict:
    if atualizar:
        _saude.clear()
    return _saude(url())


def cliente() -> jarvis.Cliente:
    return jarvis.Cliente(url())


def historico() -> list[dict]:
    return st.session_state.setdefault("jarvis_hist", [])


def ouvir(dados: bytes) -> str | None:
    s = saude()
    if s["online"] and s["voz"]:
        try:
            return cliente().transcrever(dados, "fala.wav")
        except Exception:
            pass
    return jarvis.transcrever_gemini(dados)


def sintetizar(texto: str) -> bytes | None:
    s = saude()
    if s["online"] and s["voz"] and texto:
        return cliente().sintetizar(jarvis.para_fala(texto.split("\n")[0][:600]))
    return None


# ---------------------------------------------------------------------------
# Comandos do app
# ---------------------------------------------------------------------------


def _eu() -> str:
    return estado.identidade()[0]


def _precisa_conta() -> str | None:
    if estado.visitante() or not estado.pode_conversar():
        return "Isso precisa da sua conta. Crie a sua na tela de entrada."
    return None


def _checkin(_cmd) -> str:
    if (erro := _precisa_conta()):
        return erro
    j = estado.jogo()
    r = j.checkin(_eu())
    estado.trilha("felicidade")
    if r is None:
        return f"Você já fez o check-in hoje. Seu saldo é de {j.saldo(_eu())} pontos. Volte amanhã para manter a sequência."
    return f"Check-in feito: mais {r[0]} pontos. Sequência de {r[1]} {'dia' if r[1] == 1 else 'dias'}."


def _estresse(cmd) -> jarvis.Resposta:
    from chronotrade import simulacao_app as sa, simulador

    if not estado.permite("estresse"):
        return jarvis.Resposta("O teste de estresse faz parte do plano Médio.", pagina="paginas/conta.py")
    c = estado.carteira()
    if not c.posicoes:
        return jarvis.Resposta("Cadastre a sua carteira no Inventário para eu simular uma crise.",
                               pagina="paginas/inventario.py", abrir=True)
    chave = cmd.extra or "covid"
    r = simulador.estresse(sa.posicoes_estresse(), sa.cenario(chave), c.caixa, c.aporte_mensal)
    st.session_state.sim_cenario = chave
    st.session_state.sim_aba = "estresse"
    estado.conquistar("estresse")
    return jarvis.Resposta(sa.frase_estresse(r, c.aporte_mensal), pagina="paginas/simulador.py", abrir=True)


def _intencao(cmd) -> jarvis.Resposta:
    from chronotrade import simulacao_app as sa, simulador

    if not estado.permite("estresse"):
        return jarvis.Resposta("A simulação de intenções faz parte do plano Médio.", pagina="paginas/conta.py")
    if not cmd.quantidade:
        return jarvis.Resposta(f"Quantas de {cmd.ticker}? Diga, por exemplo: simular compra de 100 {cmd.ticker}.")
    it = simulador.Intencao(cmd.ticker, cmd.lado or "compra", cmd.quantidade, cmd.preco, sa.classe_provavel(cmd.ticker))
    r = sa.simular([it])
    st.session_state.sim_intencoes = [{"ticker": it.ticker, "lado": it.lado, "quantidade": it.quantidade,
                                       "preco": it.preco, "classe": it.classe}]
    st.session_state.sim_aba = "intencoes"
    ordem = None
    texto = sa.frase_intencao(it, r)
    if estado.permite("simulador"):
        ordem = {"ticker": it.ticker, "lado": it.lado, "quantidade": int(it.quantidade), "preco": it.preco}
    return jarvis.Resposta(texto, pagina="paginas/simulador.py", abrir=True, ordem=ordem)


def _sala() -> str:
    return st.session_state.get("sala_pregao") or "geral"


def _emoji(cmd) -> str:
    from chronotrade import pregao as pg

    if (erro := _precisa_conta()):
        return erro
    try:
        estado.pregao().emote(_sala(), _eu(), cmd.extra or "👏")
    except pg.ErroPregao as erro:
        return str(erro)
    estado.conquistar("primeiro_emoji")
    return f"Soltei {pg.EMOJI_NOMES.get(cmd.extra, 'o emoji')} no salão."


def _frase(cmd) -> jarvis.Resposta | str:
    from chronotrade import pregao as pg

    if (erro := _precisa_conta()):
        return erro
    db = estado.pregao()
    frases = db.frases(_eu())
    if not frases:
        return jarvis.Resposta("Você ainda não tem frases. Grave a primeira em Meu perfil.", pagina="paginas/perfil.py")
    indice = int(cmd.extra or 1)
    if not 1 <= indice <= len(frases):
        return f"Você tem {len(frases)} {'frase' if len(frases) == 1 else 'frases'}. Diga, por exemplo: falar a frase 1."
    try:
        db.tocar_frase(_sala(), _eu(), frases[indice - 1].id)
    except pg.ErroPregao as erro:
        return str(erro)
    return jarvis.Resposta("Pronto, seu avatar falou no salão.", dados={"curta": True})


def _tema(cmd) -> str:
    from chronotrade.tema import TEMAS

    chave = cmd.extra if cmd.extra in TEMAS else None
    if not chave:
        return "Os temas são: " + ", ".join(t["nome"] for t in TEMAS.values()) + "."
    if estado.visitante():
        st.session_state.tema_visitante = chave
    else:
        estado.pregao().salvar_tema(_eu(), chave, estado.identidade()[1])
    return f"Tema {TEMAS[chave]['nome']} aplicado."


def _avisos(_cmd) -> jarvis.Resposta:
    caixa = estado.caixa_avisos()
    email = estado.email_avisos()
    novos = [a for a in caixa.listar(email, 20) if not a.lido]
    if not novos:
        return jarvis.Resposta("Nenhum aviso novo. Está tudo em dia.")
    partes = [f"{a.titulo}. {a.texto[:160]}" for a in novos[:3]]
    caixa.marcar_lidos(email)
    inicio = "Você tem um aviso novo. " if len(novos) == 1 else f"Você tem {len(novos)} avisos novos. "
    return jarvis.Resposta(inicio + " ".join(partes), pagina="paginas/avisos.py")


def executar_ordem(o: dict) -> str:
    from chronotrade.corretoras import ErroCorretora, Ordem, abrir

    pasta = estado.pasta() or (pasta_dados() / "visitantes" / estado.email_avisos().split(":")[-1])
    sim = abrir("simulada", pasta, preco=lambda t: estado.ativo(t).preco)
    try:
        r = sim.enviar(Ordem(o["ticker"], o["lado"], int(o["quantidade"]),
                             "limitada" if o.get("preco") else "mercado", o.get("preco")))
        return f"Feito na carteira simulada: {r.situacao}. {r.mensagem}"
    except ErroCorretora as erro:
        return f"Não deu: {erro}"


def _confirmar(_cmd) -> str:
    o = st.session_state.pop("jv_ordem", None)
    if not o:
        return "Não tenho nada esperando confirmação."
    if not estado.permite("simulador"):
        return "A carteira simulada faz parte do plano Médio."
    for m in reversed(historico()):
        if m.get("ordem") == o:
            m["feita"] = True
            break
    return executar_ordem(o)


def _cancelar(_cmd) -> str:
    return "Cancelado. Nada foi feito." if st.session_state.pop("jv_ordem", None) else "Tudo bem."


def _parar(_cmd) -> jarvis.Resposta:
    return jarvis.Resposta("Tudo bem, parei de ouvir. Toque no microfone quando precisar.", dados={"parar": True})


def _repetir(_cmd) -> jarvis.Resposta:
    for m in reversed(historico()):
        if m["role"] == "assistant":
            return jarvis.Resposta(m["content"], dados={"repetida": True})
    return jarvis.Resposta("Ainda não falei nada.")


def _musica(cmd) -> str:
    humor = cmd.extra or "incentivo"
    estado.trilha(humor, forcar=True)
    if humor == "parar":
        return "Música pausada."
    nomes = {"incentivo": "incentivo", "tensao": "tensão", "euforia": "euforia", "felicidade": "felicidade"}
    return f"Tocando a trilha de {nomes.get(humor, humor)}. Ajuste o volume no botão de música."


def _carteira_virtual(cmd) -> jarvis.Resposta:
    from chronotrade import carteiras_virtuais as cv

    capital = float(cmd.extra) if cmd.extra else 10_000.0
    db = estado.carteiras_virtuais()
    try:
        nova = db.criar(_eu(), f"Carteira por voz {len(db.listar(_eu())) + 1}", capital)
    except cv.ErroCarteira as erro:
        return jarvis.Resposta(str(erro))
    st.session_state.cv_sel = nova.id
    estado.trilha("incentivo")
    return jarvis.Resposta(f"Criei a {nova.nome} com {jarvis._brl(capital)}. Agora é só comprar e acompanhar ao vivo.",
                           pagina="paginas/virtuais.py", abrir=True)


def _crescimento(_cmd) -> jarvis.Resposta:
    from datetime import date, timedelta

    from chronotrade import patrimonio as pt

    cres = pt.crescimento(estado.patrimonio().serie(_eu(), date.today() - timedelta(days=31)))
    if cres is None:
        return jarvis.Resposta("Ainda estou juntando as fotos diárias do patrimônio. Em poucos dias eu consigo dizer "
                               "quanto veio dos aportes e quanto o dinheiro rendeu.", pagina="paginas/crescimento.py",
                               abrir=True)
    sinal = "cresceu" if cres.fim >= cres.inicio else "recuou"
    return jarvis.Resposta(f"Nos últimos 30 dias o patrimônio {sinal} {jarvis._brl(abs(cres.fim - cres.inicio))} e está em "
                           f"{jarvis._brl(cres.fim)}. Seus aportes foram {jarvis._brl(cres.aportes)} e o dinheiro "
                           f"trabalhando rendeu {jarvis._brl(cres.trabalho)}.", pagina="paginas/crescimento.py", abrir=True)


def _imposto(_cmd) -> jarvis.Resposta:
    from datetime import date

    from chronotrade import ir

    pendentes = [x for x in ir.Lembretes(pasta_dados() / "contas.db").listar(_eu())
                 if date.fromisoformat(x["vencimento"]) >= date.today()]
    if pendentes:
        x = pendentes[0]
        return jarvis.Resposta(f"O próximo DARF é de {jarvis._brl(x['valor'])}, código {ir.CODIGO_DARF}, e vence em "
                               f"{date.fromisoformat(x['vencimento']):%d/%m}. Confira na calculadora.",
                               pagina="paginas/impostos.py", abrir=True)
    return jarvis.Resposta("Abri a calculadora de imposto: digite as operações ou importe a planilha da B3, e eu mostro "
                           "o DARF e o vencimento.", pagina="paginas/impostos.py", abrir=True)


def contexto() -> jarvis.Contexto:
    c = estado.carteira()
    saude_ = saude()

    def resumo() -> dict:
        if not c.posicoes:
            return {}
        _, r, _ = estado.tabela_e_resumo()
        return {"patrimonio": r.patrimonio, "ativos": len(c.posicoes), "renda_12m": r.renda_12m}

    def dica():
        from chronotrade.agentes import sentinela

        return sentinela.montar_dica(c, estado.ativo, usar_tecnica=estado.permite("tecnica"))

    def manchetes(ticker):
        if estado.modo_demo():
            return noticias.demo([ticker] if ticker else [p.ticker for p in c.posicoes])
        busca = noticias.busca_do_ativo(ticker) if ticker else "B3 Ibovespa"
        return noticias.buscar("google:" + busca, "Google Notícias", limite=5)

    def criar_alerta(ticker: str, tipo: str, preco: float):
        from chronotrade import alertas

        try:
            criado = alertas.Alertas(pasta_dados() / "contas.db").criar(estado.email_avisos(), ticker, tipo, preco)
        except alertas.ErroAlerta as erro:
            raise ValueError(str(erro)) from erro
        estado.conquistar("primeiro_alerta")
        return criado

    acoes = {"checkin": _checkin, "estresse": _estresse, "intencao": _intencao, "emoji": _emoji, "frase": _frase,
             "tema": _tema, "avisos": _avisos, "confirmar": _confirmar, "cancelar": _cancelar, "parar": _parar,
             "repetir": _repetir, "musica": _musica, "carteira_virtual": _carteira_virtual,
             "crescimento": _crescimento, "imposto": _imposto}
    return jarvis.Contexto(carteira=c, obter=estado.ativo, dica=dica if (c.posicoes or c.observar) else None,
                           noticias=manchetes, conversar=cliente().conversar if saude_["online"] else None,
                           resumo=resumo, criar_alerta=criar_alerta if estado.permite("alertas") else None,
                           acoes=acoes)


def processar(texto: str, origem: str = "texto") -> tuple[jarvis.Comando, jarvis.Resposta]:
    """Entende, executa e guarda na conversa. origem: "texto" (tela) ou "voz" (mãos livres)."""
    cmd = jarvis.entender(texto)
    hist = historico()
    passado = [{"role": m["role"], "content": m["content"]} for m in hist]
    resposta = jarvis.executar(cmd, contexto(), passado)
    if resposta.ordem:
        st.session_state.jv_ordem = resposta.ordem
        if origem == "voz":
            resposta.texto += " Para fazer na carteira simulada, diga: confirmar. Ou diga: cancelar."
    if not resposta.dados.get("repetida"):
        hist.append({"role": "user", "content": texto, "voz": origem == "voz"})
        hist.append({"role": "assistant", "content": resposta.texto, "pagina": resposta.pagina,
                     "ordem": resposta.ordem, "compartilhar": resposta.compartilhar, "nova": origem != "voz"})
        del hist[:-40]
    if origem == "voz":
        estado.conquistar("maos_livres")
    return cmd, resposta


# ---------------------------------------------------------------------------
# Mãos livres: o botão flutuante em todas as telas
# ---------------------------------------------------------------------------


def _comp():
    global _componente
    if _componente is None:
        import streamlit.components.v1 as components

        _componente = components.declare_component("jarvis_maos_livres", path=str(_PASTA))
    return _componente


# Comandos que mudam o que aparece na tela inteira (os outros só atualizam o botão)
_RECARREGAR_TUDO = {"tema", "checkin", "confirmar", "cancelar", "avisos", "ordem", "alerta", "musica"}


def _responder(n: int, ouvido: str = "", texto: str = "", silencioso: bool = False, parar: bool = False) -> None:
    som = sintetizar(texto) if texto and not silencioso else None
    st.session_state.jv_resposta = {
        "n": n, "ouvido": ouvido, "texto": texto, "fala": jarvis.para_fala(texto.split("\n")[0][:600]) if texto else "",
        "audio": "data:audio/wav;base64," + base64.b64encode(som).decode() if som else None,
        "silencioso": silencioso, "parar": parar}


def tratar_fala(wav: bytes, modo: str) -> tuple[jarvis.Comando | None, jarvis.Resposta | None]:
    """Do áudio à resposta, com a regra da palavra de ativação no modo "sempre ouvindo"."""
    n = int(time.time() * 1000)
    texto = jarvis.corrigir((ouvir(wav) or "").strip())
    if not texto or jarvis.ruido(texto):
        if modo == "toque":
            _responder(n, texto, "Não ouvi direito. Pode repetir?")
        else:
            _responder(n, silencioso=True)
        return None, None
    chamou, resto = jarvis.tirar_ativacao(texto)
    conversa_aberta = time.time() < st.session_state.get("jv_janela", 0)
    if modo == "palavra" and not chamou and not conversa_aberta:
        _responder(n, silencioso=True)   # conversa do ambiente: não é com o Jarvis
        return None, None
    comando = resto if chamou else texto
    st.session_state.jv_janela = time.time() + JANELA_CONVERSA
    if chamou and not comando.strip(" ,.!?"):
        _responder(n, texto, "Pois não?")
        return None, None
    cmd, resposta = processar(comando, "voz")
    ouvido = f"Jarvis, {comando}" if chamou else texto   # mostra o comando limpo, sem o "Javis/Já vi" do reconhecimento
    _responder(n, ouvido, resposta.texto, parar=bool(resposta.dados.get("parar")))
    return cmd, resposta


@st.fragment
def _painel() -> None:
    valor = _comp()(resposta=st.session_state.get("jv_resposta"), permitido=True, key="jarvis_maos_livres", default=None)
    if not valor or valor.get("n") == st.session_state.get("jv_n"):
        return
    st.session_state.jv_n = valor.get("n")
    if valor.get("acao") != "fala" or not valor.get("audio"):
        return
    try:
        wav = base64.b64decode(valor["audio"])
    except ValueError:
        return
    cmd, resposta = tratar_fala(wav, valor.get("modo") or "palavra")
    if resposta is not None and resposta.abrir and resposta.pagina:
        st.switch_page(resposta.pagina)
    if cmd is not None and (cmd.acao in _RECARREGAR_TUDO or st.session_state.get("pagina_atual") == "jarvis"):
        st.rerun()
    st.rerun(scope="fragment")


def botao_flutuante() -> None:
    """Desenha o Jarvis mãos livres no canto da tela. Chame antes de rodar a página."""
    if estado.permite("jarvis"):
        _painel()
