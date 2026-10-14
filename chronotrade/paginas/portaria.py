"""Portaria: a vitrine de quem ainda não entrou. Apresenta, convence, cadastra e entra."""

import streamlit as st

from chronotrade import contas, estado, loja, tema
from chronotrade.calculos import brl
from chronotrade.legal import AVISO_LEGAL

cfg = estado.config_loja()

st.markdown('<div class="ct-heroi"><div class="ct-heroi-titulo">Chrono Trade</div>'
            '<p>Sua carteira de dividendos, do primeiro aporte até a renda que paga as contas.</p></div>',
            unsafe_allow_html=True)
tema.linha_do_tempo(0.38, "Hoje: R$ 1.140/mês em proventos", "Meta: R$ 3.000/mês")
tema.legenda("Exemplo da linha do tempo que o app monta com a sua carteira.")

form, vitrine = st.columns([1, 1.25], gap="large")

with form:
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
        whatsapp = st.text_input("WhatsApp com DDD", placeholder="(19) 98765-4321",
                                 help="Para receber os avisos do agente Sentinela (planos Premium) e falar com o suporte.")
        nova = st.text_input("Senha", type="password", key="cad_senha", autocomplete="new-password",
                             help="Pelo menos 8 caracteres, misturando letras e números.")
        aceito = st.checkbox("Li e aceito os termos de uso e a política de privacidade")
        ciente = st.checkbox("Entendo que o Chrono Trade não faz recomendação de investimento e que "
                             "as decisões e os riscos dos meus aportes são meus")
        if st.form_submit_button("Criar conta", type="primary", width="stretch"):
            if not (aceito and ciente):
                st.error("Para criar a conta, marque as duas confirmações.")
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
                 help="Veja as telas com uma carteira de exemplo, sem cadastro."):
        estado.sair()
        st.session_state.visitante = True
        estado.usar_exemplo()
        st.rerun()
    if cfg.get("whatsapp_admin"):
        from chronotrade import pix

        st.link_button("Tirar dúvidas pelo WhatsApp",
                       pix.link_whatsapp(cfg["whatsapp_admin"], "Olá! Quero saber mais sobre o Chrono Trade."),
                       width="stretch")

with vitrine:
    st.subheader("Por que investidores usam o Chrono Trade")
    st.markdown(
        "- 🧭 **Sabe onde colocar cada real do aporte**: o app cruza preço justo (Bazin e Graham), "
        "gráfico (tendência e IFR) e as suas metas por classe, e mostra quantas cotas de cada ativo.\n"
        "- 🛡️ **O agente Sentinela trabalha por você**: toda semana (ou todo dia, no Premium) ele vigia a "
        "carteira e manda a dica do próximo aporte no app, por e-mail ou WhatsApp.\n"
        "- 📅 **Agenda dos dividendos**: as próximas datas com e quanto deve cair na conta.\n"
        "- ⏳ **Linha do tempo até a sua renda**: em quantos anos os proventos pagam as suas contas.\n"
        "- 🔮 **Agentes de IA que debatem uma ação** (otimista, pessimista, risco) antes de você decidir.\n"
        "- 🔌 **Pronto para a corretora**: carteira simulada para treinar e conexão com MetaTrader 5."
    )
    st.subheader("Quanto vale comprar com desconto")
    col1, col2 = st.columns(2)
    aporte = col1.number_input("Seu aporte mensal (R$)", 100.0, 100_000.0, 1500.0, 100.0, format="%.0f")
    desconto = col2.slider("Desconto médio sobre o preço justo", 5, 25, 10, format="%d%%")
    economia = aporte * 12 / (1 - desconto / 100) - aporte * 12  # o mesmo dinheiro compra mais ações
    tema.fala(f"Comprando sempre {desconto}% abaixo do preço justo, em um ano seus <b>{brl(aporte * 12, 0)}</b> "
              f"de aportes compram o equivalente a <b>{brl(aporte * 12 + economia, 0)}</b>: "
              f"<b>{brl(economia, 0)}</b> a mais em ações, que seguem pagando dividendos.")
    tema.legenda("Exemplo ilustrativo de como funciona a margem de segurança. Não é promessa de resultado.")

st.subheader("Planos")
loja.mostrar_planos()
with st.expander("Comparar tudo o que cada plano inclui"):
    loja.comparativo()
st.caption(AVISO_LEGAL)
