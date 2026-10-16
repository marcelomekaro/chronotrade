"""Meu perfil: foto, apelido, bio e o bonequinho do Pregão."""

import dataclasses
import html

import streamlit as st

from chronotrade import avatar as av, estado, pregao as pg, tema

st.title("Meu perfil")
tema.subtitulo("Como você aparece no Pregão e as cores do seu app.")
db = estado.pregao()
eu, nome = estado.identidade()
p = db.perfil_completo(eu, nome)
pode = estado.pode_conversar()
if not pode:
    tema.aviso("No modo visitante dá para experimentar, mas nada é salvo. Crie a sua conta para ter o seu perfil.")

atual = av.Avatar.de_json(p.avatar) or av.sortear(eu)
st.session_state.setdefault("foto_nova", None)

col_prev, col_form = st.columns([1, 2], gap="large")

with col_form:
    apelido = st.text_input("Apelido (como você aparece no Pregão)", value=p.apelido, max_chars=18,
                            help="De 2 a 18 letras. Precisa ser único: se alguém já usa, coloque um número ou sobrenome.")
    bio = st.text_area("Sobre você (opcional)", value=p.bio, max_chars=140, height=80,
                       placeholder="Ex.: Investidor de dividendos desde 2019, foco em elétricas e FIIs de papel.")

    st.subheader("Foto")
    envio, camera = st.tabs(["📁 Enviar foto", "📷 Tirar foto"])
    with envio:
        arquivo = st.file_uploader("Foto do rosto (JPG ou PNG)", type=["jpg", "jpeg", "png", "webp"],
                                   accept_multiple_files=False, disabled=not pode)
    with camera:
        tirada = st.camera_input("Sorria!", disabled=not pode) if st.toggle("Abrir a câmera", disabled=not pode) else None
    pixel = st.toggle("Estilo pixel (combina com o salão)", value=False)
    origem = tirada or arquivo
    if origem is not None:
        if origem.size > 8 * 1024 * 1024:
            st.error("Foto grande demais. Use uma de até 8 MB.")
        else:
            import hashlib

            marca = hashlib.sha1(origem.getvalue()).hexdigest() + str(pixel)
            if marca != st.session_state.get("foto_salva_marca"):
                try:
                    st.session_state.foto_nova = av.processar_foto(origem.getvalue(), pixel)
                    st.session_state.foto_marca = marca
                except ValueError as erro:
                    st.error(str(erro))
    tema.legenda("A foto aparece para todos no Pregão. Use uma foto sua; o app recorta em quadrado, reduz e apaga "
                 "os dados escondidos da imagem (como a localização).")

    with st.expander("Bonequinho em pixel art (aparece quando não há foto)", expanded=not p.foto):
        c1, c2 = st.columns(2)
        pele = c1.select_slider("Pele", options=av.PELES, value=atual.pele, format_func=lambda c: str(av.PELES.index(c) + 1))
        roupa = c2.select_slider("Roupa", options=av.ROUPAS, value=atual.roupa,
                                 format_func=lambda c: str(av.ROUPAS.index(c) + 1))
        cabelo = c1.selectbox("Cabelo", av.CABELOS, index=av.CABELOS.index(atual.cabelo), format_func=av.NOMES.get)
        cor = c2.select_slider("Cor do cabelo", options=av.CORES_CABELO, value=atual.cor_cabelo,
                               format_func=lambda c: str(av.CORES_CABELO.index(c) + 1))
        acessorio = st.selectbox("Acessório", av.ACESSORIOS, index=av.ACESSORIOS.index(atual.acessorio),
                                 format_func=av.NOMES.get)
    boneco = dataclasses.replace(atual, pele=pele, cabelo=cabelo, cor_cabelo=cor, roupa=roupa, acessorio=acessorio)

    foto_final = st.session_state.foto_nova or p.foto
    b1, b2 = st.columns(2)
    if b1.button("Salvar perfil", type="primary", disabled=not pode, width="stretch"):
        try:
            db.salvar_perfil(eu, apelido, boneco.json(), foto=st.session_state.foto_nova or False, bio=bio)
            if st.session_state.foto_nova:
                estado.conquistar("perfil_foto")
            st.session_state.foto_nova = None
            st.session_state.foto_salva_marca = st.session_state.get("foto_marca")
            st.toast("Perfil salvo. É assim que o Pregão te vê agora.", icon="✅")
            st.rerun()
        except pg.ErroPregao as erro:
            st.error(str(erro))
    if p.foto and b2.button("Remover foto", disabled=not pode, width="stretch"):
        db.remover_foto(eu)
        st.session_state.foto_nova = None
        st.rerun()

with col_prev:
    st.markdown("**Assim você aparece**")
    st.html(f'<div class="ct-janela" style="display:flex;flex-direction:column;align-items:center;gap:10px;padding:22px">'
            f'{av.retrato(boneco.json(), foto_final, eu, 128, apelido)}'
            f'<div style="color:var(--ouro);font-size:1.3rem;font-weight:800">{html.escape(apelido or "?")}</div>'
            f'<div style="color:var(--suave);font-size:.9rem;text-align:center">{html.escape(bio or "")}</div></div>')
    if st.session_state.foto_nova:
        st.caption("Foto nova ainda não salva.")
    st.page_link("paginas/pregao.py", label="Ir para o Pregão", icon="🏛️")

st.divider()
st.subheader("Frases do avatar")
st.markdown("Frases curtas que o seu avatar fala no salão do Pregão: com a **sua voz** gravada, com a **voz do Jarvis** "
            "ou com a voz do navegador. No salão, toque em **🗣️ Frases** ou diga *“Jarvis, falar a minha frase 1”*.")
frases = db.frases(eu) if pode else []
for i, f in enumerate(frases, start=1):
    with st.container(border=True):
        c1, c2, c3 = st.columns([0.62, 0.26, 0.12], vertical_alignment="center")
        origem_txt = {"gravada": "🎙️ sua voz", "voz": "🤖 voz do Jarvis", "texto": "🗣️ voz do navegador"}[f.origem]
        c1.markdown(f"**{i}. {html.escape(f.texto)}**  \n<span style='color:var(--suave);font-size:.85rem'>{origem_txt}</span>",
                    unsafe_allow_html=True)
        with c2:
            achada = db.frase(f.id)
            if achada and achada[1]:
                st.audio(achada[1], format="audio/wav")
            elif st.button("▶ Ouvir", key=f"ouvir_frase{f.id}"):
                import streamlit.components.v1 as components

                from chronotrade import jarvis

                components.html(jarvis.falar_no_navegador(f.texto), height=0)
        if c3.button("🗑️", key=f"apagar_frase{f.id}", help="Apagar esta frase"):
            db.apagar_frase(f.id, eu)
            st.rerun()

if pode and len(frases) < pg.FRASES_MAXIMO:
    with st.expander("➕ Nova frase", expanded=not frases):
        sugestoes = ["Bom dia, pregão!", "Buy and hold diário!", "Mais um aporte feito!", "Data com chegando!",
                     "Dividendo caiu na conta!", "Paciência também rende."]
        escolhida = st.pills("Ideias", sugestoes, key="frase_ideia")
        texto_frase = st.text_input("Texto da frase (aparece no balão)", value=escolhida or "", max_chars=pg.FRASE_TEXTO_MAXIMO,
                                    key=f"frase_texto_{escolhida or ''}")
        from chronotrade import jarvis_app

        voz_ok = jarvis_app.saude()["online"] and jarvis_app.saude()["voz"]
        modos = {"gravada": "🎙️ Gravar com a minha voz", "voz": "🤖 Voz do Jarvis", "texto": "🗣️ Voz do navegador"}
        if not voz_ok:
            modos.pop("voz")
        modo = st.radio("Como o avatar fala", list(modos), format_func=modos.get, horizontal=True, key="frase_modo")
        gravacao = st.audio_input("Grave a frase (até 8 segundos)", key="frase_audio") if modo == "gravada" else None
        if st.button("Salvar frase", type="primary", disabled=not texto_frase.strip()):
            from chronotrade import audio as au

            try:
                som = None
                if modo == "gravada":
                    if gravacao is None:
                        raise pg.ErroPregao("Grave a frase antes de salvar.")
                    som, _ = au.preparar_frase(gravacao.getvalue())
                elif modo == "voz":
                    bruto = jarvis_app.cliente().sintetizar(texto_frase)
                    som = au.preparar_frase(bruto, 10)[0] if bruto else None
                db.salvar_frase(eu, texto_frase, som, modo if som or modo == "texto" else "texto")
                estado.conquistar("primeira_frase")
                st.toast("Frase salva. Use no salão do Pregão!", icon="🗣️")
                st.rerun()
            except (pg.ErroPregao, au.ErroAudio) as erro:
                st.error(str(erro))
        tema.legenda("Frases são públicas no salão e passam pelas regras do Pregão: nada de promessas de ganho, "
                     "links ou ofensas. Quem ouvir algo errado pode denunciar.")
elif not pode:
    st.caption("Crie a sua conta para gravar frases.")

st.divider()
st.subheader("Aparência do app")
from chronotrade import tema as _tema  # noqa: E402

atual_tema = estado.tema_atual()
opcoes = list(_tema.TEMAS)
for inicio in range(0, len(opcoes), 3):
    cols = st.columns(3)
    for col, chave in zip(cols, opcoes[inicio:inicio + 3], strict=False):
        t = _tema.TEMAS[chave]
        with col:
            st.html(f'<div class="ct-amostra" style="border:1px solid {t["borda"]};border-radius:16px;overflow:hidden;'
                    f'box-shadow:0 0 0 {"2px " + t["ouro"] if chave == atual_tema else "0"};background:{t["ceu"]}">'
                    f'<div style="padding:12px 14px;color:{t["texto"]};font-weight:700;display:flex;align-items:center;gap:8px">'
                    f'<span style="width:12px;height:12px;border-radius:50%;background:{t["ouro"]};display:inline-block"></span>'
                    f'{t["nome"]}</div>'
                    f'<div style="display:flex;gap:6px;padding:0 14px 10px">'
                    f'<span style="flex:2;height:30px;border-radius:8px;background:linear-gradient(135deg,{t["janela_topo"]},{t["janela_base"]})"></span>'
                    f'<span style="flex:1;height:30px;border-radius:8px;background:{t["ouro"]}"></span>'
                    f'<span style="flex:1;height:30px;border-radius:8px;background:{t["jade"]}"></span></div>'
                    f'<div style="background:{t["ceu_2"]};color:{t["suave"]};padding:8px 14px;font-size:.85rem;min-height:54px">'
                    f'{t["descricao"]}</div></div>')
            if st.button("Em uso" if chave == atual_tema else "Usar este", key=f"tema_{chave}", width="stretch",
                         disabled=chave == atual_tema, type="secondary" if chave == atual_tema else "primary"):
                if estado.visitante():
                    st.session_state.tema_visitante = chave
                else:
                    db.salvar_tema(eu, chave, nome)
                st.rerun()
tema.legenda("O tema vale para você, em todos os aparelhos. Dá para trocar por voz: “Jarvis, mudar o tema para verde”. "
             "O salão do Pregão mantém o visual de jogo.")

st.subheader("Trilha sonora")
st.markdown("O botão **♪** no canto da tela toca música gerada pelo app em quatro climas: 💪 Incentivo, ⚡ Tensão, "
            "🚀 Euforia e 😊 Felicidade. Ligue a **trilha automática** para a música mudar com o que acontece (euforia "
            "quando a carteira sobe forte, tensão no teste de estresse, felicidade no check-in). Você também pode "
            "colocar uma música sua:")
musica_atual, musica_nome = db.musica_de(eu)
m1, m2 = st.columns([2, 1], vertical_alignment="bottom")
enviada = m1.file_uploader("Minha música (MP3, OGG, WAV ou M4A, até 12 MB)", type=["mp3", "ogg", "wav", "m4a"],
                           disabled=not pode, key="musica_up")
if enviada is not None and pode and st.session_state.get("musica_marca") != enviada.file_id:
    from chronotrade import trilha

    try:
        url = trilha.guardar_musica(enviada.getvalue(), enviada.name)
        db.salvar_musica(eu, url, enviada.name.rsplit(".", 1)[0], nome)
        st.session_state.musica_marca = enviada.file_id
        st.toast("Música salva. Escolha 🎵 no botão ♪.", icon="🎵")
        st.rerun()
    except (ValueError, OSError) as erro:
        st.error(f"Não consegui guardar a música: {erro}")
if musica_atual:
    m1.audio(musica_atual)
    if m2.button("Remover minha música", width="stretch"):
        db.salvar_musica(eu, None)
        st.rerun()
tema.legenda("Use só músicas que você tem direito de usar. A trilha gerada pelo app é livre para usar.")

