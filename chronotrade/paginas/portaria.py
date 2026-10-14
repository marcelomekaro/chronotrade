"""Portaria: a primeira tela de quem não entrou. Apresenta o app, entra, cadastra e mostra os planos."""

import streamlit as st

from chronotrade import contas, estado, loja, tema

cfg = estado.config_loja()

st.markdown('<div class="ct-heroi"><div class="ct-heroi-titulo">Chrono Trade</div>'
            '<p>Sua carteira de dividendos, do primeiro aporte até a renda que paga as contas.</p></div>',
            unsafe_allow_html=True)
tema.linha_do_tempo(0.38, "Hoje: R$ 1.140/mês em proventos", "Meta: R$ 3.000/mês")
tema.legenda("Exemplo da linha do tempo que o app monta com a sua carteira.")

dir_, esq = st.columns([1, 1.15], gap="large")

with dir_:
    entrar, criar = st.tabs(["Entrar", "Criar conta"])
    with entrar, st.form("entrar"):
        email = st.text_input("E-mail", autocomplete="email")
        senha = st.text_input("Senha", type="password", autocomplete="current-password")
        lembrar = st.checkbox("Manter conectado neste aparelho", value=True,
                              help="Não marque em computadores de uso público.")
        if st.form_submit_button("Entrar", type="primary", width="stretch"):
            try:
                u = estado.banco().entrar(email, senha)
                if u.status == "bloqueado":
                    st.error("Esta conta está bloqueada. Fale com o suporte.")
                else:
                    estado.conectar(u, lembrar)
                    st.rerun()
            except contas.ErroConta as erro:
                st.error(str(erro))
        st.caption("Esqueceu a senha? Peça uma senha temporária ao suporte pelo WhatsApp.")
    with criar, st.form("cadastro"):
        nome = st.text_input("Nome")
        novo_email = st.text_input("E-mail", key="cad_email", autocomplete="email")
        whatsapp = st.text_input("WhatsApp com DDD (opcional)", placeholder="(11) 98765-4321")
        nova = st.text_input("Senha", type="password", key="cad_senha", autocomplete="new-password",
                             help="Pelo menos 8 caracteres, misturando letras e números.")
        aceito = st.checkbox("Li e aceito os termos de uso e a política de privacidade")
        if st.form_submit_button("Criar conta", type="primary", width="stretch"):
            if not aceito:
                st.error("Para criar a conta, aceite os termos de uso.")
            else:
                try:
                    u = estado.banco().cadastrar(nome, novo_email, nova, whatsapp)
                    estado.conectar(u, lembrar=True)
                    st.rerun()
                except contas.ErroConta as erro:
                    st.error(str(erro))
    with st.expander("Termos de uso e privacidade"):
        from chronotrade.termos import texto_termos

        st.markdown(texto_termos(cfg))
    if st.button("Experimentar com dados fictícios", width="stretch",
                 help="Veja todas as telas com uma carteira de exemplo, sem cadastro."):
        estado.sair()
        st.session_state.visitante = True
        estado.usar_exemplo()
        st.rerun()

with esq:
    st.subheader("O que você acompanha")
    st.markdown(
        "- **Quanto a carteira paga por mês** em dividendos e quanto falta para a sua meta\n"
        "- **Preço de entrada e preço justo** de cada ação, pelos métodos Bazin e Graham\n"
        "- **Onde colocar o próximo aporte**, respeitando as metas de ações, FIIs e ETFs\n"
        "- **Projeção do patrimônio** em anos, com reinvestimento dos proventos\n"
        "- **Agentes de IA** que debatem uma ação e dão um parecer\n"
        "- **Relatório** para imprimir, salvar em PDF ou mandar no WhatsApp"
    )
    st.subheader("Planos")
    loja.mostrar_planos()

tema.legenda("Ferramenta de estudo e organização. Não é recomendação de investimento.")
