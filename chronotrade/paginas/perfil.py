"""Meu perfil: foto, apelido, bio e o bonequinho do Pregão."""

import html

import streamlit as st

from chronotrade import avatar as av, estado, pregao as pg, tema

st.title("Meu perfil")
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
    boneco = av.Avatar(pele, cabelo, cor, roupa, acessorio)

    foto_final = st.session_state.foto_nova or p.foto
    b1, b2 = st.columns(2)
    if b1.button("Salvar perfil", type="primary", disabled=not pode, width="stretch"):
        try:
            db.salvar_perfil(eu, apelido, boneco.json(), foto=st.session_state.foto_nova or False, bio=bio)
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
    st.html(f'<div style="display:flex;flex-direction:column;align-items:center;gap:10px;padding:18px;'
            f'border:3px solid var(--creme,#E9E1C8);border-radius:8px;background:#121838">'
            f'{av.retrato(boneco.json(), foto_final, eu, 128, apelido)}'
            f'<div style="font-family:Pixelify Sans,monospace;color:#F2C14E;font-size:1.3rem">{html.escape(apelido or "?")}</div>'
            f'<div style="color:#A9B0D6;font-size:.9rem;text-align:center">{html.escape(bio or "")}</div></div>')
    if st.session_state.foto_nova:
        st.caption("Foto nova ainda não salva.")
    st.page_link("paginas/pregao.py", label="Ir para o Pregão", icon="🏛️")
