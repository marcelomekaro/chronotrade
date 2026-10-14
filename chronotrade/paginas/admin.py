"""Painel do administrador: liberar contas, renovar, cobrar e configurar a loja."""

import shutil
from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from chronotrade import contas, estado, loja, pix, tema
from chronotrade.calculos import brl, mes_ano
from chronotrade.carteira import pasta_dados

u = estado.usuario()
if u is None or not u.admin:
    st.error("Página só para o administrador.")
    st.stop()

banco = estado.banco()
cfg = banco.config()
st.title("Painel do administrador")
ind = banco.indicadores()

col1, col2, col3, col4 = st.columns(4)
with col1:
    tema.janela("Assinantes ativos", str(ind["ativos"]), f"{ind['completos']} no plano Completo", ouro=True)
with col2:
    tema.janela("Aguardando liberação", str(ind["pendentes"]), "Na aba Pendentes")
with col3:
    tema.janela("Vencem em 7 dias", str(len(ind["vencendo"])), f"{len(ind['vencidos'])} já vencidos")
with col4:
    tema.janela("Receita no mês", brl(ind["receita_mes"], 0), "Pagamentos registrados")

OPCOES_DIAS = {30: "30 dias", 90: "90 dias", 180: "180 dias", 365: "1 ano", 7: "7 dias (teste)"}
FORMAS = ["PIX", "Cartão", "Dinheiro", "Cortesia"]


def _valor_padrao(dias: int) -> float:
    o = loja.ofertas()
    if dias == 365 and "anual" in o:
        return o["anual"]["valor"]
    if "mensal" in o:
        return round(o["mensal"]["valor"] * max(dias, 30) / 30, 2)
    return 0.0


def _formulario_liberar(email: str, chave: str, rotulo: str) -> None:
    """Plano, dias e valor pago; ao confirmar, ativa ou renova a conta e registra o pagamento."""
    with st.form(f"liberar_{chave}"):
        c1, c2, c3, c4 = st.columns(4)
        plano = c1.selectbox("Plano", list(contas.PLANOS), index=1, format_func=contas.PLANOS.get)
        dias = c2.selectbox("Acesso", list(OPCOES_DIAS), format_func=OPCOES_DIAS.get)
        forma = c3.selectbox("Forma", FORMAS)
        valor = c4.number_input("Valor recebido (R$)", min_value=0.0, step=1.0, format="%.2f",
                                value=_valor_padrao(30), help="Use 0 para cortesia.")
        if st.form_submit_button(rotulo, type="primary"):
            novo = banco.liberar(email, plano, dias, valor=0.0 if forma == "Cortesia" else valor, forma=forma)
            st.success(f"{novo.nome}: plano {contas.PLANOS[novo.plano]} até {novo.validade:%d/%m/%Y}.")
            st.rerun()


pendentes, assinantes, cobranca, pagamentos, config = st.tabs(
    ["Pendentes", "Assinantes", "Cobrança", "Pagamentos", "Loja"])

# --- Pendentes ------------------------------------------------------------------------
with pendentes:
    fila = [x for x in banco.listar() if x.status == "pendente"]
    if not fila:
        st.info("Ninguém aguardando liberação.")
    for p in fila:
        with st.container(border=True):
            contato = f", WhatsApp {p.whatsapp}" if p.whatsapp else ""
            st.markdown(f"**{p.nome}**, {p.email}{contato}  \nCadastro em {p.criado_em:%d/%m/%Y %H:%M}")
            _formulario_liberar(p.email, f"p_{p.id_pasta}", "Liberar acesso")
            if st.button("Recusar cadastro", key=f"recusar_{p.id_pasta}"):
                banco.mudar_status(p.email, "bloqueado")
                st.rerun()

# --- Assinantes -------------------------------------------------------------------------
with assinantes:
    todos = [x for x in banco.listar() if not x.admin]
    if not todos:
        st.info("Ainda não há contas cadastradas.")
    else:
        tabela = pd.DataFrame([{
            "Nome": x.nome, "E-mail": x.email, "WhatsApp": x.whatsapp,
            "Situação": "Vencido" if x.status == "ativo" and x.vencido() else contas.STATUS[x.status],
            "Plano": contas.PLANOS[x.plano],
            "Validade": f"{x.validade:%d/%m/%Y}" if x.validade else "",
            "Dias": x.dias_restantes() if x.validade else None,
            "Último acesso": f"{x.ultimo_acesso:%d/%m %H:%M}" if x.ultimo_acesso else "",
        } for x in todos])
        st.dataframe(tabela, hide_index=True, width="stretch")
        st.download_button("Baixar lista em CSV", tabela.to_csv(sep=";", index=False).encode("utf-8-sig"),
                           file_name=f"assinantes_{date.today():%Y-%m-%d}.csv", mime="text/csv")

        st.subheader("Gerenciar uma conta")
        escolhido = st.selectbox("Conta", [x.email for x in todos],
                                 format_func=lambda e: next(f"{x.nome} ({x.email})" for x in todos if x.email == e))
        alvo = banco.buscar(escolhido)
        st.markdown(f"**{contas.STATUS[alvo.status]}**, plano {contas.PLANOS[alvo.plano]}"
                    + (f", válido até {alvo.validade:%d/%m/%Y}" if alvo.validade else ""))
        st.markdown("**Renovar ou mudar o plano** (os dias são somados à validade atual)")
        _formulario_liberar(alvo.email, f"a_{alvo.id_pasta}", "Registrar e liberar")

        c1, c2, c3 = st.columns(3)
        if alvo.status == "bloqueado":
            if c1.button("Reativar a conta"):
                banco.mudar_status(alvo.email, "ativo")
                st.rerun()
        elif c1.button("Bloquear a conta"):
            banco.mudar_status(alvo.email, "bloqueado")
            st.rerun()
        if c2.button("Gerar senha temporária"):
            st.session_state.senha_gerada = (alvo.email, banco.redefinir_senha(alvo.email))
        with c3.popover("Excluir a conta"):
            st.markdown("Apaga a conta, a carteira e as análises guardadas. Não dá para desfazer.")
            if st.button("Confirmar exclusão", type="primary"):
                shutil.rmtree(pasta_dados() / "usuarios" / alvo.id_pasta, ignore_errors=True)
                banco.excluir(alvo.email)
                st.rerun()

        gerada = st.session_state.get("senha_gerada")
        if gerada and gerada[0] == alvo.email:
            st.success(f"Senha temporária de {alvo.email}:")
            st.code(gerada[1], language=None)
            if alvo.whatsapp:
                msg = (f"Olá, {alvo.nome.split()[0]}! Sua senha temporária do Chrono Trade é {gerada[1]} . "
                       "Entre com ela e crie a sua senha nova em Minha conta.")
                st.link_button("Enviar pelo WhatsApp", pix.link_whatsapp(alvo.whatsapp, msg))
            st.caption("Ela aparece só agora. Na próxima entrada a pessoa é convidada a trocá-la.")

        obs = st.text_area("Anotações sobre esta conta", value=alvo.observacao, key=f"obs_{alvo.id_pasta}")
        if obs != alvo.observacao and st.button("Guardar anotação"):
            banco.anotar(alvo.email, obs)
            st.rerun()

        historico = banco.pagamentos(alvo.email)
        if historico:
            st.markdown("**Pagamentos desta conta**")
            st.dataframe(pd.DataFrame(historico)[["registrado_em", "valor", "dias", "plano", "forma"]],
                         hide_index=True, width="stretch")

# --- Cobrança ------------------------------------------------------------------------------
with cobranca:
    lista = ind["vencidos"] + ind["vencendo"]
    if not lista:
        st.info("Nenhuma assinatura vencida ou perto de vencer.")
    o = loja.ofertas()
    for x in lista:
        with st.container(border=True):
            dias = x.dias_restantes()
            quando = f"venceu há {-dias} dias" if dias < 0 else ("vence hoje" if dias == 0 else f"vence em {dias} dias")
            st.markdown(f"**{x.nome}**, {x.email}: {quando} ({x.validade:%d/%m/%Y})")
            if not x.whatsapp:
                st.caption("Sem WhatsApp cadastrado. Cobre por e-mail.")
                continue
            texto = (f"Olá, {x.nome.split()[0]}! Sua assinatura do Chrono Trade {quando}. "
                     "Para renovar, é só pagar pelo PIX abaixo e me mandar o comprovante.")
            if "mensal" in o and cfg.get("pix_chave"):
                codigo = pix.copia_e_cola(cfg["pix_chave"], cfg.get("pix_nome") or cfg["nome_loja"],
                                          cfg.get("pix_cidade", ""), o["mensal"]["valor"],
                                          identificador="CT" + x.email.split("@")[0][:20])
                texto += f"\n\nValor: {brl(o['mensal']['valor'])}\nPIX copia e cola:\n{codigo}"
            st.link_button("Cobrar pelo WhatsApp", pix.link_whatsapp(x.whatsapp, texto))

# --- Pagamentos -----------------------------------------------------------------------------------
with pagamentos:
    todos_pag = banco.pagamentos()
    if not todos_pag:
        st.info("Nenhum pagamento registrado ainda.")
    else:
        df = pd.DataFrame(todos_pag)
        df["data"] = pd.to_datetime(df["registrado_em"])
        mensal = df.groupby(df["data"].dt.to_period("M"))["valor"].sum().tail(12)
        fig = go.Figure(go.Bar(x=[mes_ano(p.to_timestamp()) for p in mensal.index], y=mensal.values,
                               marker_color=tema.CORES["ouro"],
                               text=[brl(v, 0) for v in mensal.values], textposition="outside", cliponaxis=False,
                               hovertemplate="%{x}: R$ %{y:,.2f}<extra></extra>"))
        fig.update_layout(height=300, yaxis_tickprefix="R$ ", title=None)
        st.subheader("Receita por mês")
        tema.mostrar(fig)
        st.dataframe(df[["registrado_em", "email", "valor", "dias", "plano", "forma", "observacao"]],
                     hide_index=True, width="stretch")
        st.download_button("Baixar pagamentos em CSV", df.drop(columns="data").to_csv(sep=";", index=False)
                           .encode("utf-8-sig"), file_name="pagamentos_chronotrade.csv", mime="text/csv")

# --- Configurações da loja -------------------------------------------------------------------------
with config:
    with st.form("loja"):
        st.markdown("**Preços do plano Completo** (deixe vazio para não oferecer)")
        c1, c2, c3 = st.columns(3)
        mensal_ = c1.text_input("Mensal (R$)", cfg["preco_mensal"])
        anual_ = c2.text_input("Anual (R$)", cfg["preco_anual"])
        limite_ = c3.text_input("Ativos no plano Gratuito", cfg["limite_gratuito"])
        st.markdown("**PIX para receber**")
        c4, c5, c6 = st.columns(3)
        chave_ = c4.text_input("Chave PIX", cfg["pix_chave"], help="CPF, CNPJ, e-mail, celular (+55...) ou chave aleatória.")
        nome_ = c5.text_input("Nome do recebedor", cfg["pix_nome"], help="Como aparece no seu banco, até 25 letras.")
        cidade_ = c6.text_input("Cidade", cfg["pix_cidade"])
        whats_ = st.text_input("Seu WhatsApp de atendimento (com DDD)", cfg["whatsapp_admin"])
        if st.form_submit_button("Salvar configurações", type="primary"):
            banco.salvar_config({"preco_mensal": mensal_.replace(",", "."), "preco_anual": anual_.replace(",", "."),
                                 "limite_gratuito": limite_, "pix_chave": chave_, "pix_nome": nome_,
                                 "pix_cidade": cidade_, "whatsapp_admin": whats_})
            st.success("Configurações salvas.")
            st.rerun()
    if cfg.get("pix_chave"):
        st.markdown("**Teste do PIX**: pague R$ 0,01 para conferir se o dinheiro cai na conta certa.")
        teste = pix.copia_e_cola(cfg["pix_chave"], cfg.get("pix_nome") or cfg["nome_loja"], cfg.get("pix_cidade", ""),
                                 0.01, identificador="TESTE")
        st.image(pix.qr_png(teste), width=180)
        st.code(teste, language=None, wrap_lines=True)
