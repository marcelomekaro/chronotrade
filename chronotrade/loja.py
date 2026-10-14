"""A parte comercial na tela: planos, comparativo, preços e o painel de pagamento."""

from __future__ import annotations

import base64

import pandas as pd
import streamlit as st

from chronotrade import estado, pagamentos, pix, planos, tema
from chronotrade.calculos import brl, pct

DESTAQUE = {"basico": "Organize a carteira e veja os dividendos chegando.",
            "medio": "Saiba onde e quando aportar, com fundamentos e gráfico.",
            "premium": "Agentes de IA, alertas diários e conexão com a corretora."}


def _cobrancas() -> pagamentos.Cobrancas | None:
    return pagamentos.Cobrancas(estado.banco().caminho) if pagamentos.automatico() else None


def mostrar_planos(destacar: str = "medio") -> None:
    """Os três planos lado a lado, com preço e frase de valor."""
    cfg = estado.config_loja()
    desconto = planos.desconto_anual(cfg)
    colunas = st.columns(3)
    for coluna, plano in zip(colunas, planos.ORDEM, strict=True):
        with coluna:
            mensal = planos.preco_mensal(cfg, plano)
            anual = planos.preco(cfg, plano, "anual")
            selo = " (mais escolhido)" if plano == destacar else ""
            tema.janela(f"{planos.NOMES[plano]}{selo}", f"{brl(mensal)}/mês",
                        f"{DESTAQUE[plano]}<br><span style='color:var(--suave)'>Ou {brl(anual)} por ano "
                        f"({pct(desconto, 0)} de desconto)</span>", ouro=plano == destacar)


def comparativo() -> None:
    """Tabela do que cada plano inclui: o argumento de venda em uma olhada."""
    linhas = []
    for recurso, nome in planos.NOMES_RECURSOS.items():
        linhas.append({"Recurso": nome, **{planos.NOMES[p]: "✅" if planos.libera(p, recurso) else "—"
                                           for p in planos.ORDEM}})
    extras = [
        {"Recurso": "Ativos na carteira",
         **{planos.NOMES[p]: (str(planos.LIMITES[p].ativos) if planos.LIMITES[p].ativos else "Ilimitados")
            for p in planos.ORDEM}},
        {"Recurso": "Análises de IA por mês",
         **{planos.NOMES[p]: (str(planos.LIMITES[p].analises_ia_mes) if planos.LIMITES[p].analises_ia_mes else "—")
            for p in planos.ORDEM}},
        {"Recurso": "Frequência do agente Sentinela",
         **{planos.NOMES[p]: planos.LIMITES[p].sentinela.replace("diario", "Diária").replace("semanal", "Semanal")
            for p in planos.ORDEM}},
    ]
    st.dataframe(pd.DataFrame(extras + linhas), hide_index=True, width="stretch",
                 height=36 * (len(linhas) + len(extras) + 1) + 4)


def painel_pagamento(email: str, nome: str, sugestao: str = "medio") -> None:
    """Escolha do plano e o PIX: automático (Mercado Pago) ou com a chave do administrador."""
    cfg = estado.config_loja()
    col1, col2 = st.columns(2)
    plano = col1.selectbox("Plano", planos.ORDEM, index=planos.ORDEM.index(planos.normalizar(sugestao)),
                           format_func=lambda p: f"{planos.NOMES[p]}: {brl(planos.preco_mensal(cfg, p))}/mês",
                           key=f"plano_{email}")
    periodo = col2.radio("Período", ["mensal", "anual"], horizontal=True, key=f"periodo_{email}",
                         format_func=lambda p: "Mensal" if p == "mensal" else
                         f"Anual ({pct(planos.desconto_anual(cfg), 0)} de desconto)")
    valor = planos.preco(cfg, plano, periodo)
    dias = planos.DIAS[periodo]
    st.markdown(f"**Total: {brl(valor)}** por {dias} dias do plano {planos.NOMES[plano]}.".replace("$", "\\$"))

    cobrancas = _cobrancas()
    if cobrancas is not None:
        if st.button("Gerar PIX", type="primary", key=f"gerar_{email}"):
            try:
                st.session_state[f"cobranca_{email}"] = cobrancas.criar(
                    email, plano, periodo, dias, valor, f"Chrono Trade {planos.NOMES[plano]} {periodo}").id
            except Exception as erro:
                st.error(f"Não consegui gerar o PIX agora ({erro}). Tente de novo em instantes.")
        id_cob = st.session_state.get(f"cobranca_{email}")
        cob = next((c for c in cobrancas.historico(email) if c.id == id_cob), None)
        if cob and not cob.paga:
            col_qr, col_txt = st.columns([1, 1.4])
            with col_qr:
                if cob.qr_base64:
                    st.image(base64.b64decode(cob.qr_base64), width=230, caption="Aponte a câmera do app do banco")
            with col_txt:
                st.markdown("**PIX copia e cola**")
                st.code(cob.qr_texto, language=None, wrap_lines=True)
                st.caption("A liberação é automática: assim que o banco confirmar, o plano é ativado.")
                if st.button("Já paguei, verificar agora", key=f"verificar_{email}"):
                    liberadas = cobrancas.verificar(estado.banco(), so_email=email)
                    if liberadas:
                        st.success("Pagamento confirmado! O seu plano já está ativo.")
                        st.rerun()
                    else:
                        st.info("Ainda não chegou. Pode levar alguns segundos; o app confere sozinho a cada 5 minutos.")
        return

    # PIX estático com a chave do administrador: funciona em qualquer banco, liberação manual.
    chave = cfg.get("pix_chave", "").strip()
    if not chave:
        st.info("O pagamento ainda não foi configurado. Fale com o suporte pelo WhatsApp.")
    else:
        codigo = pix.copia_e_cola(chave, cfg.get("pix_nome") or cfg.get("nome_loja", ""), cfg.get("pix_cidade", ""), valor)
        col_qr, col_txt = st.columns([1, 1.4])
        with col_qr:
            st.image(pix.qr_png(codigo), caption="Aponte a câmera do app do banco", width=230)
        with col_txt:
            st.markdown("**Ou pague pela chave PIX**")
            st.code(chave, language=None)
            st.markdown(f"Valor: **{brl(valor)}**".replace("$", "\\$"))
            st.markdown("**PIX copia e cola**")
            st.code(codigo, language=None, wrap_lines=True)
    whatsapp = cfg.get("whatsapp_admin")
    if whatsapp:
        mensagem = (f"Olá! Sou {nome} ({email}). Paguei o plano {planos.NOMES[plano]} {periodo} do Chrono Trade "
                    f"({brl(valor)}). Segue o comprovante.")
        st.link_button("Enviar comprovante pelo WhatsApp", pix.link_whatsapp(whatsapp, mensagem), type="primary")
    tema.legenda("Depois de conferido o pagamento, o plano aparece ativo na sua conta.")
