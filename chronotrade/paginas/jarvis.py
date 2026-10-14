"""Jarvis: fale com o Chrono Trade. Comandos de voz com o OpenJarvis rodando no seu PC."""

import hashlib
import os

import streamlit as st
import streamlit.components.v1 as components

from chronotrade import compartilhar_whats, estado, jarvis, noticias, tema
from chronotrade.carteira import pasta_dados
from chronotrade.corretoras import ErroCorretora, Ordem, abrir

st.title("Jarvis")
estado.exigir("jarvis")

url = st.session_state.get("openjarvis_url") or estado.config_loja().get("openjarvis_url") \
    or os.environ.get("OPENJARVIS_URL") or jarvis.URL_PADRAO
cliente = jarvis.Cliente(url)
if "saude_oj" not in st.session_state:
    st.session_state.saude_oj = cliente.saude()
saude = st.session_state.saude_oj
historico: list[dict] = st.session_state.setdefault("jarvis_hist", [])

col_status, col_voz = st.columns([3, 1], vertical_alignment="center")
with col_status:
    if saude["online"]:
        st.markdown(f"🟢 **OpenJarvis conectado** em `{url}`" + (" com voz local." if saude["voz"] else "."))
    else:
        st.markdown("🟡 **OpenJarvis desligado.** Os comandos do app funcionam; para voz local e conversa livre, "
                    "ligue o OpenJarvis (veja Conexões → OpenJarvis).")
with col_voz:
    falar = st.toggle("Responder falando", value=True)
    if st.button("Testar de novo", width="stretch"):
        st.session_state.saude_oj = cliente.saude()
        st.rerun()

c = estado.carteira()


def _resumo() -> dict:
    if not c.posicoes:
        return {}
    _, r, _ = estado.tabela_e_resumo()
    return {"patrimonio": r.patrimonio, "ativos": len(c.posicoes), "renda_12m": r.renda_12m}


def _dica():
    from chronotrade.agentes import sentinela

    return sentinela.montar_dica(c, estado.ativo, usar_tecnica=estado.permite("tecnica"))


def _noticias(ticker):
    if estado.modo_demo():
        return noticias.demo([ticker] if ticker else [p.ticker for p in c.posicoes])
    busca = noticias.busca_do_ativo(ticker) if ticker else "B3 Ibovespa"
    return noticias.buscar("google:" + busca, "Google Notícias", limite=5)


contexto = jarvis.Contexto(carteira=c, obter=estado.ativo, dica=_dica if (c.posicoes or c.observar) else None,
                           noticias=_noticias, conversar=cliente.conversar if saude["online"] else None,
                           resumo=_resumo)


def _ouvir(audio) -> str | None:
    dados = audio.getvalue()
    if saude["online"] and saude["voz"]:
        try:
            return cliente.transcrever(dados, "fala.wav")
        except Exception as erro:
            st.toast(f"OpenJarvis não transcreveu: {erro}", icon="⚠️")
    texto = jarvis.transcrever_gemini(dados)
    if texto:
        return texto
    st.warning("Não consegui transformar a fala em texto. Ligue o OpenJarvis com voz ou digite o comando abaixo.")
    return None


def _processar(texto: str) -> None:
    cmd = jarvis.entender(texto)
    passado = [{"role": m["role"], "content": m["content"]} for m in historico]
    with st.spinner("Jarvis pensando…"):
        resposta = jarvis.executar(cmd, contexto, passado)
    historico.append({"role": "user", "content": texto})
    historico.append({"role": "assistant", "content": resposta.texto, "pagina": resposta.pagina,
                      "ordem": resposta.ordem, "compartilhar": resposta.compartilhar, "nova": True})


# --- Entrada: voz, sugestões e texto ----------------------------------------------------
tema.fala("Toque no microfone e fale, por exemplo: <i>“cotação da Taesa”</i>, <i>“qual a dica do aporte?”</i>, "
          "<i>“próximos dividendos”</i>, <i>“abrir o pregão”</i>, <i>“comprar 100 TAEE11”</i> (carteira simulada).")
audio = st.audio_input("Falar com o Jarvis", key="jarvis_audio")
if audio is not None:
    marca = hashlib.sha1(audio.getvalue()).hexdigest()
    if st.session_state.get("jarvis_ultimo_audio") != marca:
        st.session_state.jarvis_ultimo_audio = marca
        ouvido = _ouvir(audio)
        if ouvido:
            _processar(ouvido)

sugestoes = ["Cotação do Ibovespa", "Qual a dica do aporte?", "Próximos proventos", "Quanto vale minha carteira?",
             "Notícias da Taesa", "Comprar 100 TAEE11"]
cols = st.columns(3)
for i, s in enumerate(sugestoes):
    if cols[i % 3].button(s, key=f"sug{i}", width="stretch"):
        _processar(s)

digitado = st.chat_input("Ou digite um comando para o Jarvis")
if digitado:
    _processar(digitado)

# --- Conversa ------------------------------------------------------------------------------
if not historico:
    st.caption("A conversa aparece aqui.")
for i, m in enumerate(historico):
    with st.chat_message("user" if m["role"] == "user" else "assistant", avatar="🧑" if m["role"] == "user" else "🎙️"):
        st.markdown(m["content"].replace("$", "\\$"))
        if m["role"] != "assistant":
            continue
        if m.get("pagina"):
            st.page_link(m["pagina"], label="Abrir a tela", icon="➡️")
        if m.get("ordem") and not m.get("feita"):
            o = m["ordem"]
            if not estado.permite("simulador"):
                st.caption("A carteira simulada faz parte do plano Médio.")
            elif st.button(f"Confirmar {o['lado']} de {o['quantidade']} {o['ticker']} (simulada)", key=f"ord{i}",
                           type="primary"):
                pasta = estado.pasta() or (pasta_dados() / "visitantes" / estado.email_avisos().split(":")[-1])
                sim = abrir("simulada", pasta, preco=lambda t: estado.ativo(t).preco)
                try:
                    r = sim.enviar(Ordem(o["ticker"], o["lado"], int(o["quantidade"]),
                                         "limitada" if o.get("preco") else "mercado", o.get("preco")))
                    m["feita"] = True
                    m["content"] += f"\n\n**Resultado:** {r.situacao}. {r.mensagem}"
                except ErroCorretora as erro:
                    m["content"] += f"\n\n**Não deu:** {erro}"
                st.rerun()
        if m.get("compartilhar"):
            compartilhar_whats.botao(m["compartilhar"], f"jv{i}", estado.pasta_social(), "Mandar no WhatsApp")

# --- Falar a última resposta ---------------------------------------------------------------
ultima = historico[-1] if historico else None
if falar and ultima and ultima.get("nova"):
    ultima["nova"] = False
    texto_falado = ultima["content"].split("\n")[0][:600]
    som = cliente.sintetizar(texto_falado) if saude["online"] and saude["voz"] else None
    if som:
        st.audio(som, format="audio/wav", autoplay=True)
    else:
        components.html(jarvis.falar_no_navegador(texto_falado), height=0)

col1, col2 = st.columns(2)
if historico and col1.button("Limpar conversa"):
    st.session_state.jarvis_hist = []
    st.rerun()
tema.legenda("O Jarvis executa comandos do app e explica conceitos. Ele não recomenda compra ou venda: as dicas "
             "vêm das regras que você configurou, e a decisão é sempre sua. Ordens por voz vão só para a carteira "
             "simulada e pedem confirmação.")
