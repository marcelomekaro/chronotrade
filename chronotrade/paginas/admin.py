"""Painel do administrador: assinantes, cobranças, receita, agente e configurações da loja."""

import os
import shutil
from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from chronotrade import avisos, contas, estado, pagamentos, pix, planos, tema
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
    tema.janela("Assinantes ativos", str(ind["ativos"]),
                ", ".join(f"{planos.NOMES[p]} {n}" for p, n in ind["por_plano"].items()), ouro=True)
with col2:
    tema.janela("Receita recorrente", brl(ind["receita_recorrente"], 0), "Por mês, pelos planos ativos")
with col3:
    tema.janela("Recebido no mês", brl(ind["receita_mes"], 0), "Pagamentos registrados")
with col4:
    tema.janela("Atenção", f"{ind['pendentes']} pendentes",
                f"{len(ind['vencendo'])} vencem em 7 dias, {len(ind['vencidos'])} vencidos")

OPCOES_DIAS = {30: "30 dias", 90: "90 dias", 180: "180 dias", 365: "1 ano", 7: "7 dias (teste)"}
FORMAS = ["PIX", "Cartão", "Dinheiro", "Cortesia"]


def _formulario_liberar(email: str, chave: str, rotulo: str, plano_atual: str = "medio") -> None:
    """Plano, dias e valor; ao confirmar, ativa ou renova a conta e registra o pagamento."""
    with st.form(f"liberar_{chave}"):
        c1, c2, c3, c4 = st.columns(4)
        plano = c1.selectbox("Plano", planos.ORDEM, index=planos.ORDEM.index(planos.normalizar(plano_atual)),
                             format_func=planos.NOMES.get)
        dias = c2.selectbox("Acesso", list(OPCOES_DIAS), format_func=OPCOES_DIAS.get)
        forma = c3.selectbox("Forma", FORMAS)
        valor = c4.number_input("Valor recebido (R$)", min_value=0.0, step=1.0, format="%.2f",
                                value=planos.preco_mensal(cfg, planos.normalizar(plano_atual)),
                                help="Use 0 para cortesia.")
        if st.form_submit_button(rotulo, type="primary"):
            novo = banco.liberar(email, plano, dias, valor=0.0 if forma == "Cortesia" else valor, forma=forma)
            estado.caixa_avisos().criar(novo.email, "assinatura", "Plano liberado",
                                        f"O seu plano {planos.NOMES[novo.plano_efetivo]} está ativo até "
                                        f"{novo.validade:%d/%m/%Y}. Bons aportes!")
            st.success(f"{novo.nome}: plano {planos.NOMES[novo.plano_efetivo]} até {novo.validade:%d/%m/%Y}.")
            st.rerun()


abas = st.tabs(["Pendentes", "Assinantes", "Cobrança", "Pagamentos", "Agente", "Loja e integrações", "Comunidade"])

# --- Pendentes ------------------------------------------------------------------------
with abas[0]:
    fila = [x for x in banco.listar() if x.status == "pendente"]
    if not fila:
        st.info("Ninguém aguardando liberação.")
    for p in fila:
        with st.container(border=True):
            contato = f", WhatsApp {p.whatsapp}" if p.whatsapp else ""
            st.markdown(f"**{p.nome}**, {p.email}{contato}  \nCadastro em {p.criado_em:%d/%m/%Y %H:%M}")
            _formulario_liberar(p.email, f"p_{p.id_pasta}", "Liberar acesso")
            if p.whatsapp:
                st.link_button("Chamar no WhatsApp", pix.link_whatsapp(
                    p.whatsapp, f"Olá, {p.nome.split()[0]}! Aqui é do Chrono Trade. Vi o seu cadastro."))
            if st.button("Recusar cadastro", key=f"recusar_{p.id_pasta}"):
                banco.mudar_status(p.email, "bloqueado")
                st.rerun()

# --- Assinantes -------------------------------------------------------------------------
with abas[1]:
    todos = [x for x in banco.listar() if not x.admin]
    if not todos:
        st.info("Ainda não há contas cadastradas.")
    else:
        tabela = pd.DataFrame([{
            "Nome": x.nome, "E-mail": x.email, "WhatsApp": x.whatsapp,
            "Situação": "Vencido" if x.status == "ativo" and x.vencido() else contas.STATUS[x.status],
            "Plano": planos.NOMES[x.plano_efetivo],
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
        st.markdown(f"**{contas.STATUS[alvo.status]}**, plano {planos.NOMES[alvo.plano_efetivo]}"
                    + (f", válido até {alvo.validade:%d/%m/%Y}" if alvo.validade else ""))
        st.markdown("**Renovar ou mudar o plano** (os dias são somados à validade atual)")
        _formulario_liberar(alvo.email, f"a_{alvo.id_pasta}", "Registrar e liberar", alvo.plano_efetivo)

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
            st.dataframe(pd.DataFrame(historico)[["registrado_em", "valor", "dias", "plano", "forma", "observacao"]],
                         hide_index=True, width="stretch")

# --- Cobrança ------------------------------------------------------------------------------
with abas[2]:
    lista = ind["vencidos"] + ind["vencendo"]
    if not lista:
        st.info("Nenhuma assinatura vencida ou perto de vencer.")
    for x in lista:
        with st.container(border=True):
            dias = x.dias_restantes()
            quando = f"venceu há {-dias} dias" if dias < 0 else ("vence hoje" if dias == 0 else f"vence em {dias} dias")
            st.markdown(f"**{x.nome}**, {x.email}: plano {planos.NOMES[x.plano_efetivo]}, {quando} ({x.validade:%d/%m/%Y})")
            if not x.whatsapp:
                st.caption("Sem WhatsApp cadastrado. Cobre por e-mail.")
                continue
            valor = planos.preco_mensal(cfg, x.plano_efetivo)
            texto = (f"Olá, {x.nome.split()[0]}! Sua assinatura do Chrono Trade {quando}. Para renovar, entre no app "
                     f"em Minha conta ou pague {brl(valor)} pelo PIX {cfg.get('pix_chave', '')} e me mande o comprovante.")
            if cfg.get("pix_chave"):
                codigo = pix.copia_e_cola(cfg["pix_chave"], cfg.get("pix_nome") or cfg["nome_loja"],
                                          cfg.get("pix_cidade", ""), valor)
                texto += f"\n\nPIX copia e cola:\n{codigo}"
            st.link_button("Cobrar pelo WhatsApp", pix.link_whatsapp(x.whatsapp, texto))

# --- Pagamentos -----------------------------------------------------------------------------------
with abas[3]:
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
        fig.update_layout(height=300, yaxis_tickprefix="R$ ")
        st.subheader("Receita por mês")
        tema.mostrar(fig)
        st.dataframe(df[["registrado_em", "email", "valor", "dias", "plano", "forma", "observacao"]],
                     hide_index=True, width="stretch")
        st.download_button("Baixar pagamentos em CSV", df.drop(columns="data").to_csv(sep=";", index=False)
                           .encode("utf-8-sig"), file_name="pagamentos_chronotrade.csv", mime="text/csv")
    if pagamentos.automatico():
        cob = pagamentos.Cobrancas(banco.caminho)
        historico = cob.historico()
        if historico:
            st.subheader("Cobranças PIX do Mercado Pago")
            st.dataframe(pd.DataFrame([{"Criada": f"{c.criado_em:%d/%m %H:%M}", "E-mail": c.email,
                                        "Plano": planos.NOMES.get(c.plano, c.plano), "Valor": brl(c.valor),
                                        "Situação": "Paga e liberada" if c.paga else c.status} for c in historico]),
                         hide_index=True, width="stretch")
        if st.button("Conferir pagamentos agora"):
            liberadas = cob.verificar(banco)
            st.success(f"{len(liberadas)} assinatura(s) liberada(s) automaticamente.")

# --- Agente ---------------------------------------------------------------------------------------
with abas[4]:
    st.markdown("O **agente Sentinela** roda sozinho de hora em hora: confere pagamentos, manda a dica do próximo "
                "aporte (semanal no Básico e Médio, diária no Premium), avisa datas com e executa ordens simuladas.")
    caixa = estado.caixa_avisos()
    if st.button("Rodar o Sentinela agora para todos", type="primary",
                 help="Manda a dica para todos os assinantes ativos, mesmo que não esteja na hora."):
        from chronotrade.agentes import sentinela

        with st.spinner("Analisando as carteiras…"):
            cobr = pagamentos.Cobrancas(banco.caminho) if pagamentos.automatico() else None
            resumo = sentinela.ciclo(banco, caixa, cobr, obter=estado.ativo, forcar=True)
        st.success(f"Dicas enviadas: {resumo['dicas']}. Avisos de data com: {resumo['proventos']}. "
                   f"Ordens executadas: {resumo['ordens']}. Alertas: {resumo['alertas']}. Zona de compra: {resumo['zonas']}. Assinaturas liberadas: {resumo['liberadas']}. "
                   f"Erros: {resumo['erros']}.")
    st.caption(f"Intervalo: {os.environ.get('CHRONOTRADE_AGENTE_MINUTOS', '60')} minutos "
               "(CHRONOTRADE_AGENTE_MINUTOS no .env).")

# --- Loja e integrações -------------------------------------------------------------------------
with abas[5]:
    with st.form("loja"):
        st.markdown("**Preços mensais** (o anual sai com o desconto abaixo)")
        c1, c2, c3, c4 = st.columns(4)
        basico_ = c1.text_input("Básico (R$)", cfg["preco_basico"])
        medio_ = c2.text_input("Médio (R$)", cfg["preco_medio"])
        premium_ = c3.text_input("Premium (R$)", cfg["preco_premium"])
        desconto_ = c4.text_input("Desconto anual (%)", cfg["desconto_anual"])
        st.markdown("**PIX para receber** (usado quando o Mercado Pago não está ligado)")
        c5, c6, c7 = st.columns(3)
        chave_ = c5.text_input("Chave PIX", cfg["pix_chave"], help="CPF, CNPJ, e-mail, celular (+55...) ou chave aleatória.")
        nome_ = c6.text_input("Nome do recebedor", cfg["pix_nome"], help="Como aparece no seu banco, até 25 letras.")
        cidade_ = c7.text_input("Cidade", cfg["pix_cidade"])
        whats_ = st.text_input("WhatsApp de atendimento (com DDD)", cfg["whatsapp_admin"])
        if st.form_submit_button("Salvar configurações", type="primary"):
            banco.salvar_config({"preco_basico": basico_.replace(",", "."), "preco_medio": medio_.replace(",", "."),
                                 "preco_premium": premium_.replace(",", "."), "desconto_anual": desconto_.replace(",", "."),
                                 "pix_chave": chave_, "pix_nome": nome_, "pix_cidade": cidade_, "whatsapp_admin": whats_})
            st.success("Configurações salvas.")
            st.rerun()
    if cfg.get("pix_chave"):
        st.markdown("**Teste do PIX**: pague R$ 0,01 para conferir se o dinheiro cai na conta certa.")
        teste = pix.copia_e_cola(cfg["pix_chave"], cfg.get("pix_nome") or cfg["nome_loja"], cfg.get("pix_cidade", ""), 0.01)
        st.image(pix.qr_png(teste), width=180)
        st.code(teste, language=None, wrap_lines=True)

    st.subheader("Integrações")
    from chronotrade.motor_ia import chave_configurada, configuracao_do_ambiente

    ia = configuracao_do_ambiente()
    status = [
        ("Mercado Pago (liberação automática)", pagamentos.automatico(), "MERCADOPAGO_ACCESS_TOKEN"),
        ("E-mail (SMTP)", avisos.email_configurado(), "CHRONOTRADE_SMTP_HOST, _USUARIO, _SENHA"),
        ("WhatsApp Cloud API", avisos.whatsapp_configurado(), "WHATSAPP_TOKEN, WHATSAPP_PHONE_ID"),
        ("OpenJarvis (voz)", bool(cfg.get("openjarvis_url") or os.environ.get("OPENJARVIS_URL")),
         "OPENJARVIS_URL ou o campo na aba Comunidade"),
        ("Conector do PC (API)", bool(cfg.get("url_publica") or os.environ.get("CHRONOTRADE_URL")),
         "serviço api do docker-compose + endereço público na aba Comunidade"),
        (f"IA ({ia.provedor}, {ia.modelo_rapido})", chave_configurada(ia.provedor), "chave do provedor de IA"),
    ]
    st.dataframe(pd.DataFrame([{"Integração": n, "Situação": "✅ Ligada" if ok else "⬜ Desligada",
                                "Como ligar (no .env do servidor)": como} for n, ok, como in status]),
                 hide_index=True, width="stretch")
    st.caption("O passo a passo de cada integração está no GUIA_CHRONOTRADE.md.")

# --- Comunidade: Pregão, notícias, vídeos e Jarvis ---------------------------------------------
with abas[6]:
    from chronotrade import noticias as _noticias

    pregao_db = estado.pregao()
    online = pregao_db.online()
    tema.janela("Online no Pregão agora", str(len(online)), ", ".join(p.apelido for p in online[:8]) or "ninguém")
    st.subheader("Moderação")
    denuncias = pregao_db.denunciadas()
    if not denuncias:
        st.info("Nenhuma mensagem denunciada.")
    for m in denuncias:
        with st.container(border=True):
            st.markdown(f"**{m.apelido}** ({m.email}), {m.criado_em:%d/%m %H:%M}, {m.denuncias} denúncia(s)  \n{m.texto}")
            b1, b2 = st.columns(2)
            if b1.button("Apagar mensagem", key=f"adm_apg{m.id}"):
                pregao_db.remover(m.id)
                st.rerun()
            if b2.button("Silenciar 24h", key=f"adm_sil{m.id}"):
                pregao_db.silenciar(m.email)
                st.toast(f"{m.apelido} silenciado por 24 horas.")

    fotos = pregao_db.fotos()
    if fotos:
        with st.expander(f"Fotos de perfil ({len(fotos)})"):
            colunas = st.columns(6)
            for i, f in enumerate(fotos):
                with colunas[i % 6]:
                    st.image(f.foto, width=72, caption=f.apelido)
                    if st.button("Remover", key=f"rmfoto{i}"):
                        pregao_db.remover_foto(f.email)
                        estado.avisar(f.email, "admin", "Sua foto do Pregão foi removida",
                                      "A moderação removeu a foto do seu perfil. Use uma foto sua, adequada ao ambiente.")
                        st.rerun()

    st.subheader("Conteúdo e conexões")
    fontes_atuais = cfg.get("fontes_noticias") or "\n".join(f"{n} | {u}" for n, u in _noticias.FONTES_PADRAO)
    with st.form("comunidade"):
        tv_ = st.text_input("Vídeo da TV do Pregão (link do YouTube, pode ser uma live)", cfg.get("tv_pregao", ""))
        fontes_ = st.text_area("Fontes de notícias, uma por linha: Nome | endereço do RSS (ou google:termo de busca)",
                               fontes_atuais, height=150)
        canais_ = st.text_area("Canais do YouTube sugeridos a todos, um por linha: Nome | link ou ID do canal (UC...)",
                               cfg.get("canais_youtube", ""), height=100)
        url_ = st.text_input("Endereço público do app (usado no atalho do Conector do PC)", cfg.get("url_publica", ""),
                             placeholder="https://chronotrade.seudominio.com.br")
        oj_ = st.text_input("Endereço do OpenJarvis padrão", cfg.get("openjarvis_url", ""), placeholder="http://localhost:8000")
        if st.form_submit_button("Salvar comunidade", type="primary"):
            banco.salvar_config({"tv_pregao": tv_.strip(), "fontes_noticias": fontes_.strip(),
                                 "canais_youtube": canais_.strip(), "url_publica": url_.strip(),
                                 "openjarvis_url": oj_.strip()})
            st.success("Salvo.")
            st.rerun()
    st.caption("Notícias e vídeos vêm de feeds RSS públicos e gratuitos. Respeite os direitos de cada site: o app "
               "mostra título, resumo e link para a matéria original.")
