"""A parte comercial na tela: planos, preços e o painel de pagamento por PIX."""

from __future__ import annotations

import streamlit as st

from chronotrade import estado, pix, tema
from chronotrade.calculos import brl, pct


def _preco(chave: str) -> float:
    try:
        return float(estado.config_loja().get(chave, "0").replace(",", "."))
    except ValueError:
        return 0.0


def ofertas() -> dict[str, dict]:
    """As formas de assinar o plano Completo, com preço e dias de acesso."""
    mensal, anual = _preco("preco_mensal"), _preco("preco_anual")
    itens = {}
    if mensal:
        itens["mensal"] = {"nome": "Mensal", "valor": mensal, "dias": 30}
    if anual:
        itens["anual"] = {"nome": "Anual", "valor": anual, "dias": 365}
    return itens


def economia_anual() -> float | None:
    o = ofertas()
    if "mensal" in o and "anual" in o and o["mensal"]["valor"]:
        return 1 - o["anual"]["valor"] / (o["mensal"]["valor"] * 12)
    return None


def mostrar_planos() -> None:
    """Os dois planos lado a lado, com o que cada um inclui."""
    cfg = estado.config_loja()
    o = ofertas()
    limite = cfg.get("limite_gratuito", "5")
    col1, col2 = st.columns(2)
    with col1:
        tema.janela("Plano Gratuito", "R$ 0",
                    f"Até {limite} ativos, Portal, Tesouro, Linha do Tempo e a ficha rápida de cada ação.")
    with col2:
        if "mensal" in o:
            valor = f"{brl(o['mensal']['valor'])}/mês"
        elif "anual" in o:
            valor = f"{brl(o['anual']['valor'])}/ano"
        else:
            valor = "Consulte"
        extra = ""
        if "anual" in o and "mensal" in o:
            extra = f" Ou {brl(o['anual']['valor'])} por ano ({pct(economia_anual(), 0)} de desconto)."
        tema.janela("Plano Completo", valor,
                    "Ativos ilimitados, Próximo Aporte com preço de entrada e alvo, Oráculo de IA, "
                    f"relatórios para imprimir e compartilhar.{extra}", ouro=True)


def painel_pagamento(email: str, nome: str) -> None:
    """QR Code e copia-e-cola do PIX, mais o botão de avisar pelo WhatsApp."""
    cfg = estado.config_loja()
    o = ofertas()
    if not o:
        st.info("Os preços ainda não foram configurados. Fale com o suporte.")
        return
    escolha = st.radio("Plano Completo", list(o), horizontal=True,
                       format_func=lambda k: f"{o[k]['nome']}: {brl(o[k]['valor'])}", key=f"oferta_{email}")
    oferta = o[escolha]
    if not cfg.get("pix_chave"):
        st.info("O pagamento por PIX ainda não foi configurado. Fale com o suporte pelo WhatsApp.")
    else:
        codigo = pix.copia_e_cola(cfg["pix_chave"], cfg.get("pix_nome") or cfg.get("nome_loja", ""),
                                  cfg.get("pix_cidade", ""), oferta["valor"],
                                  identificador="CT" + email.split("@")[0][:20],
                                  descricao=f"Chrono Trade {oferta['nome']}")
        col_qr, col_txt = st.columns([1, 1.4])
        with col_qr:
            st.image(pix.qr_png(codigo), caption="Aponte a câmera do app do banco", width=230)
        with col_txt:
            st.markdown(f"**Valor:** {brl(oferta['valor'])} por {oferta['dias']} dias de acesso".replace("$", "\\$"))
            st.markdown("**PIX copia e cola**")
            st.code(codigo, language=None, wrap_lines=True)
            st.caption(f"Recebedor: {cfg.get('pix_nome') or cfg.get('nome_loja')}. Confira o nome antes de pagar.")
    whatsapp = cfg.get("whatsapp_admin")
    if whatsapp:
        mensagem = (f"Olá! Sou {nome} ({email}). Paguei o plano Completo {oferta['nome'].lower()} "
                    f"do Chrono Trade ({brl(oferta['valor'])}). Segue o comprovante.")
        st.link_button("Enviar comprovante pelo WhatsApp", pix.link_whatsapp(whatsapp, mensagem), type="primary")
    tema.legenda("A liberação é manual: assim que o pagamento for conferido, o acesso aparece na sua conta.")
