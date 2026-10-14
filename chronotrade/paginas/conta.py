"""Minha conta: situação da assinatura, pagamento, troca de senha e dados pessoais."""

import json
import shutil

import streamlit as st

from chronotrade import contas, estado, loja, planos, tema
from chronotrade.calculos import brl
from chronotrade.carteira import pasta_dados

st.title("Minha conta")
u = estado.usuario()
if u is None:
    tema.fala("Você está no modo visitante, com dados fictícios. Para guardar a sua carteira, "
              "saia e crie a sua conta na tela de entrada.")
    if st.button("Sair do modo visitante", type="primary"):
        estado.sair()
        st.rerun()
    st.stop()

if u.senha_temporaria:
    tema.aviso("Você entrou com uma senha temporária. Crie a sua senha definitiva no fim desta página.")

dias = u.dias_restantes()
col1, col2, col3 = st.columns(3)
with col1:
    nome_plano = "Administrador" if u.admin else ("A escolher" if u.status == "pendente" else contas.PLANOS[u.plano_efetivo])
    tema.janela("Plano", nome_plano, u.email, ouro=True)
with col2:
    curto = {"pendente": "Pendente", "ativo": "Ativo", "bloqueado": "Bloqueado"}
    situacao = "Vencido" if u.status == "ativo" and u.vencido() else curto[u.status]
    detalhe = "Aguardando liberação" if u.status == "pendente" else f"Cliente desde {u.criado_em:%d/%m/%Y}"
    tema.janela("Situação", situacao, detalhe)
with col3:
    if u.admin:
        tema.janela("Validade", "Sem prazo", "Conta do administrador")
    elif u.validade:
        tema.janela("Validade", f"{u.validade:%d/%m/%Y}",
                    tema.variacao(dias, f"{dias} dias restantes") if dias >= 0 else "Renove para continuar")
    else:
        tema.janela("Validade", "—", "Aguardando a primeira liberação")

# --- Plano e pagamento ---------------------------------------------------------------
if not u.admin:
    if u.status == "pendente":
        st.subheader("Falta pouco")
        tema.fala(f"Recebemos o seu cadastro, {u.nome.split()[0]}. Escolha o plano e pague pelo PIX: "
                  "a conta é liberada assim que o pagamento for confirmado.")
        loja.painel_pagamento(u.email, u.nome)
    elif u.status == "bloqueado":
        tema.fala("Esta conta está bloqueada. Fale com o suporte para entender o motivo.")
    elif u.vencido():
        st.subheader("Renovar a assinatura")
        loja.painel_pagamento(u.email, u.nome, u.plano)
    else:
        with st.expander("Mudar de plano ou renovar antes de vencer"):
            st.caption("Os dias novos são somados à validade atual. Ao mudar de plano, o novo vale a partir do pagamento.")
            loja.painel_pagamento(u.email, u.nome, u.plano)
    with st.expander("O que cada plano inclui"):
        loja.comparativo()
    pagos = estado.banco().pagamentos(u.email)
    if pagos:
        with st.expander("Meus pagamentos"):
            for p in pagos:
                st.markdown(f"{p['registrado_em'][:10]}: {brl(p['valor'])}, {p['dias']} dias, plano "
                            f"{contas.PLANOS.get(planos.normalizar(p['plano']), p['plano'])}".replace("$", "\\$"))

# --- Avisos do agente Sentinela ----------------------------------------------------------
if u.pode_usar():
    st.subheader("Avisos do agente Sentinela")
    lim = u.limites
    st.markdown(f"Frequência no seu plano: **{'todo dia' if lim.sentinela == 'diario' else 'toda semana'}**. "
                "A dica sempre aparece aqui no app; escolha também onde mais quer receber.")
    with st.form("avisos"):
        por_email = st.checkbox("Receber por e-mail", value=u.aviso_email, disabled=not u.libera("avisos_email"),
                                help=None if u.libera("avisos_email") else "Disponível a partir do plano Médio.")
        por_whats = st.checkbox("Receber por WhatsApp", value=u.aviso_whatsapp, disabled=not u.libera("avisos_whatsapp"),
                                help=None if u.libera("avisos_whatsapp") else "Disponível no plano Premium.")
        numero = st.text_input("Número do WhatsApp com DDD", value=u.whatsapp)
        if st.form_submit_button("Salvar preferências"):
            estado.banco().preferencias(u.email, True, por_email and u.libera("avisos_email"),
                                        por_whats and u.libera("avisos_whatsapp"), numero)
            st.success("Preferências salvas.")
    if lim.analises_ia_mes:
        usadas = estado.banco().uso_mes(u.email, "oraculo")
        st.caption(f"Análises do Oráculo de IA neste mês: {usadas} de {lim.analises_ia_mes}.")

# --- Senha ---------------------------------------------------------------------------
st.subheader("Trocar a senha")
with st.form("senha"):
    atual = st.text_input("Senha atual", type="password", autocomplete="current-password")
    nova = st.text_input("Senha nova", type="password", autocomplete="new-password",
                         help="Pelo menos 8 caracteres, misturando letras e números.")
    repetir = st.text_input("Repita a senha nova", type="password", autocomplete="new-password")
    if st.form_submit_button("Trocar a senha"):
        if nova != repetir:
            st.error("As duas senhas novas estão diferentes.")
        else:
            try:
                estado.banco().trocar_senha(u.email, atual, nova)
                st.success("Senha trocada.")
            except contas.ErroConta as erro:
                st.error(str(erro))

# --- Dados pessoais (LGPD) -------------------------------------------------------------------
st.subheader("Meus dados")
# A pasta é calculada direto da conta: assim os dados aparecem (e podem ser apagados) mesmo com a assinatura vencida.
pasta = pasta_dados() / "usuarios" / u.id_pasta if estado.servidor() else None
arquivo = pasta / "carteira.json" if pasta else None
carteira_json = arquivo.read_text(encoding="utf-8") if arquivo and arquivo.exists() else "{}"
meus_dados = {
    "conta": {"nome": u.nome, "email": u.email, "whatsapp": u.whatsapp, "plano": u.plano,
              "situacao": u.status, "validade": u.validade.isoformat() if u.validade else None,
              "criado_em": u.criado_em.isoformat()},
    "pagamentos": estado.banco().pagamentos(u.email),
    "carteira": json.loads(carteira_json),
}
st.download_button("Baixar meus dados", json.dumps(meus_dados, ensure_ascii=False, indent=2).encode("utf-8"),
                   file_name="meus_dados_chronotrade.json", mime="application/json")

if not u.admin:
    with st.expander("Excluir minha conta"):
        st.markdown("Apaga a conta, a carteira e as análises guardadas. Não dá para desfazer.")
        confirma = st.text_input("Para confirmar, escreva o seu e-mail")
        if st.button("Excluir conta e dados", disabled=confirma.strip().lower() != u.email):
            if pasta and pasta.exists():
                shutil.rmtree(pasta, ignore_errors=True)
            estado.banco().excluir(u.email)
            estado.sair()
            st.rerun()

st.divider()
if st.button("Sair"):
    estado.sair()
    st.rerun()
