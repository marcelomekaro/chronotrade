"""Jarvis: fale com o Chrono Trade. Mãos livres em todas as telas, ou por aqui com voz e texto."""

import hashlib

import streamlit as st
import streamlit.components.v1 as components

from chronotrade import compartilhar_whats, estado, jarvis, jarvis_app, tema

st.title("Jarvis")
tema.subtitulo("Seu assistente de voz: comanda o app inteiro sem tirar as mãos do que você está fazendo.")
estado.exigir("jarvis")

saude = jarvis_app.saude()
historico = jarvis_app.historico()

col_status, col_voz = st.columns([3, 1], vertical_alignment="center")
with col_status:
    if saude["online"]:
        st.markdown(f"🟢 **{saude.get('nome', 'OpenJarvis')} conectado** em `{jarvis_app.url()}`"
                    + (", ouvindo e falando." if saude["voz"] else ", sem voz."))
    else:
        st.markdown("🟡 **Voz local desligada.** Os comandos funcionam e a resposta sai pela voz do navegador. Para "
                    "ouvir sem internet, ligue o `chronotrade-voz` ou o OpenJarvis (veja Conexões).")
with col_voz:
    falar = st.toggle("Responder falando", value=True)
    if st.button("Testar de novo", width="stretch"):
        jarvis_app.saude(atualizar=True)
        st.rerun()

st.markdown(
    '<div class="ct-cartoes">'
    '<div class="ct-cartao"><div class="ct-cartao-ico">🎙️</div><b>Mãos livres</b><span>Toque no botão verde no canto '
    'da tela (ou <kbd>Alt</kbd>+<kbd>J</kbd>) e escolha <i>Sempre ouvindo</i>. Depois é só dizer '
    '“<b>Jarvis</b>, …” de qualquer tela.</span></div>'
    '<div class="ct-cartao"><div class="ct-cartao-ico">💬</div><b>Conversa contínua</b><span>Depois de uma resposta, '
    'por 20 segundos dá para continuar sem repetir “Jarvis”. Diga <i>“para de ouvir”</i> para desligar.</span></div>'
    '<div class="ct-cartao"><div class="ct-cartao-ico">✅</div><b>Confirma por voz</b><span>Ordens vão só para a '
    'carteira simulada: o Jarvis pergunta e você diz <i>“confirmar”</i> ou <i>“cancelar”</i>.</span></div>'
    '</div>', unsafe_allow_html=True)

with st.expander("Tudo o que dá para pedir"):
    st.markdown(
        "| Para | Diga |\n|---|---|\n"
        "| Navegar | “Jarvis, abrir a agenda”, “abrir o simulador”, “abrir o pregão” |\n"
        "| Carteira | “quanto vale minha carteira?”, “próximos proventos”, “qual a dica do aporte?” |\n"
        "| Mercado | “cotação da Taesa”, “notícias da Petrobras”, “como está o Ibovespa?” |\n"
        "| Simulações | “e se vier uma crise como a de 2008?”, “e se o mercado cair 30%?”, “simular compra de 100 TAEE11” |\n"
        "| Pregão | “aplausos no pregão”, “soltar um foguete no salão”, “falar a minha frase 2” |\n"
        "| Pontos | “faz o meu check-in”, “abrir a loja” |\n"
        "| Avisos | “tenho avisos novos?”, “me avise quando a Taesa ficar abaixo de 34 reais” |\n"
        "| App | “mudar o tema para verde”, “repete”, “para de ouvir” |\n"
        "| Ordens (simuladas) | “comprar 100 TAEE11” e depois “confirmar” |")


def _ouvir(audio) -> str | None:
    texto = jarvis_app.ouvir(audio.getvalue())
    if texto:
        return jarvis.corrigir(texto)
    st.warning("Não consegui transformar a fala em texto. Ligue a voz local ou digite o comando abaixo.")
    return None


def _processar(texto: str) -> None:
    with st.spinner("Jarvis pensando…"):
        _, resposta = jarvis_app.processar(texto, "texto")
    if resposta.abrir and resposta.pagina:
        st.session_state.jv_abrir = resposta.pagina


audio = st.audio_input("Ou grave aqui um comando", key="jarvis_audio")
if audio is not None:
    marca = hashlib.sha1(audio.getvalue()).hexdigest()
    if st.session_state.get("jarvis_ultimo_audio") != marca:
        st.session_state.jarvis_ultimo_audio = marca
        ouvido = _ouvir(audio)
        if ouvido:
            _processar(jarvis.tirar_ativacao(ouvido)[1] or ouvido)

sugestoes = ["Faz o meu check-in", "E se vier uma crise como a de 2008?", "Simular compra de 100 TAEE11",
             "Qual a dica do aporte?", "Próximos proventos", "Aplausos no pregão"]
cols = st.columns(3)
for i, s in enumerate(sugestoes):
    if cols[i % 3].button(s, key=f"sug{i}", width="stretch"):
        _processar(s)

digitado = st.chat_input("Ou digite um comando para o Jarvis")
if digitado:
    _processar(digitado)

# --- Conversa ------------------------------------------------------------------------------
if not historico:
    st.caption("A conversa aparece aqui, inclusive o que você falar no modo mãos livres em outras telas.")
for i, m in enumerate(historico):
    eu_falei = m["role"] == "user"
    with st.chat_message("user" if eu_falei else "assistant", avatar=("🗣️" if m.get("voz") else "🧑") if eu_falei else "🎙️"):
        st.markdown(m["content"].replace("$", "\\$"))
        if eu_falei:
            continue
        if m.get("pagina"):
            st.page_link(m["pagina"], label="Abrir a tela", icon="➡️")
        if m.get("ordem") and not m.get("feita"):
            o = m["ordem"]
            if not estado.permite("simulador"):
                st.caption("A carteira simulada faz parte do plano Médio.")
            elif st.button(f"Confirmar {o['lado']} de {o['quantidade']} {o['ticker']} (simulada)", key=f"ord{i}",
                           type="primary"):
                m["feita"] = True
                st.session_state.pop("jv_ordem", None)
                m["content"] += "\n\n**Resultado:** " + jarvis_app.executar_ordem(o)
                st.rerun()
        if m.get("compartilhar"):
            compartilhar_whats.botao(m["compartilhar"], f"jv{i}", estado.pasta_social(), "Mandar no WhatsApp")

# --- Falar a última resposta (o que foi digitado aqui; o mãos livres fala sozinho) --------------
ultima = historico[-1] if historico else None
if falar and ultima and ultima.get("nova"):
    ultima["nova"] = False
    som = jarvis_app.sintetizar(ultima["content"])
    if som:
        st.audio(som, format="audio/wav", autoplay=True)
    else:
        components.html(jarvis.falar_no_navegador(jarvis.para_fala(ultima["content"].split("\n")[0][:600])), height=0)

if st.session_state.get("jv_abrir"):
    st.page_link(st.session_state.pop("jv_abrir"), label="Abrir o resultado", icon="➡️")

if historico and st.button("Limpar conversa"):
    st.session_state.jarvis_hist = []
    st.rerun()
tema.legenda("O Jarvis executa comandos do app e explica conceitos. Ele não recomenda compra ou venda: as dicas "
             "vêm das regras que você configurou, e a decisão é sempre sua. Ordens por voz vão só para a carteira "
             "simulada e pedem confirmação. No modo “sempre ouvindo”, o áudio só é transcrito pela sua voz local "
             "(ou pelo Gemini, se configurado) e nada é guardado.")
