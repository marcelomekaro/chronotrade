"""Pontos e loja: check-in diário, conquistas e itens para o seu avatar do Pregão."""

import dataclasses
import html

import streamlit as st

from chronotrade import avatar as av, estado, jogo as jg, pix, pregao as pg, tema
from chronotrade.calculos import brl

st.title("Pontos e loja")
tema.subtitulo("Constância vira pontos, e pontos viram estilo para o seu avatar.")
estado.exigir("loja")
db_jogo = estado.jogo()
db = estado.pregao()
eu, nome = estado.identidade()
pode = estado.pode_conversar() and not estado.visitante()
perfil = db.perfil_completo(eu, nome)
boneco = av.Avatar.de_json(perfil.avatar) or av.sortear(eu)
saldo = db_jogo.saldo(eu)
seq = db_jogo.sequencia(eu)
fez = db_jogo.fez_checkin(eu)

tema.fala("Ganhe <b>Chrono Pontos</b> cuidando da carteira todo dia e troque por itens para o seu avatar: "
          "terno, cartola, coroa, maleta… <b>Buy and hold diário</b> também é constância.")

c1, c2, c3 = st.columns(3)
with c1:
    tema.janela("Seus pontos", f"{saldo:,}".replace(",", "."), "Pontos não valem dinheiro", ouro=True)
with c2:
    tema.janela("Sequência", f"{seq} {'dia' if seq == 1 else 'dias'}", "A cada 7 dias seguidos, +30 pontos")
with c3:
    if not pode:
        tema.janela("Check-in", "Crie a sua conta", "Para guardar os pontos")
    elif fez:
        tema.janela("Check-in de hoje", "Feito ✅", "Volte amanhã para manter a sequência")
    else:
        proximo = 10 + min(seq, 7) * 2
        tema.janela("Check-in de hoje", f"+{proximo} pontos", "Toque no botão abaixo")
        if st.button("✅ Fazer check-in do dia", type="primary", width="stretch"):
            r = db_jogo.checkin(eu)
            if r:
                st.toast(f"Check-in feito: +{r[0]} pontos. Sequência de {r[1]} dias!", icon="✅")
            st.rerun()

with st.expander("Como ganhar pontos"):
    st.markdown(
        "- **Check-in diário:** 10 pontos, mais 2 por dia de sequência (até +14). A cada 7 dias seguidos, +30.\n"
        f"- **Carteira valorizou na semana:** 1 ponto a cada 0,1% de alta das posições que você já tinha, até "
        f"{jg.MAX_DESEMPENHO} por semana. O cálculo usa as mesmas quantidades do início ao fim da semana, então "
        "aporte novo não conta: vale a constância, não o risco.\n"
        "- **Conquistas:** " + ", ".join(f"{n} (+{p})" for n, p, _ in jg.CONQUISTAS.values()) + ".\n"
        "- **Pacotes de pontos:** no fim desta página, pelo PIX.")
    tema.legenda("Pontos e itens são só para personalizar o seu avatar. Não valem dinheiro, não são resgatáveis e "
                 "não são recomendação de investimento.")

# --- Loja ------------------------------------------------------------------------------------
st.subheader("Loja do avatar")
meus = db_jogo.itens(eu)
equipado = {"traje": boneco.traje, "chapeu": boneco.chapeu, "extra": boneco.extra, "moldura": boneco.moldura}
VAZIO = {"traje": "casual", "chapeu": "nenhum", "extra": "nenhum", "moldura": "nenhuma"}


def _equipar(categoria: str, item: str) -> None:
    novo = dataclasses.replace(boneco, **{categoria: item})
    try:
        db.salvar_perfil(eu, perfil.apelido, novo.json())
    except pg.ErroPregao as erro:
        st.error(str(erro))
        return
    st.rerun()


abas = st.tabs([f"{jg.CATEGORIAS[c]}" for c in jg.CATEGORIAS])
for aba, categoria in zip(abas, jg.CATEGORIAS, strict=True):
    with aba:
        itens = [(k, v) for k, v in jg.CATALOGO.items() if v[1] == categoria]
        colunas = st.columns(3)
        for i, (item, (nome_item, _, preco, descricao)) in enumerate(itens):
            with colunas[i % 3], st.container(border=True):
                vitrine = dataclasses.replace(boneco, **{categoria: item})
                if categoria == "moldura":
                    imagem = av.retrato(vitrine.json(), perfil.foto or av.data_uri(vitrine, 96), eu, 96, nome_item)
                else:
                    imagem = av.img(vitrine, 110, nome_item)
                st.html(f'<div style="display:flex;justify-content:center;padding:6px 0">{imagem}</div>')
                st.markdown(f"**{html.escape(nome_item)}**  \n{html.escape(descricao)}")
                if item in meus:
                    if equipado[categoria] == item:
                        if st.button("Tirar", key=f"tirar_{item}", width="stretch", disabled=not pode):
                            _equipar(categoria, VAZIO[categoria])
                    elif st.button("Usar", key=f"usar_{item}", type="primary", width="stretch", disabled=not pode):
                        _equipar(categoria, item)
                else:
                    rotulo = f"Comprar por {preco} pontos" if saldo >= preco else f"Faltam {preco - saldo} pontos"
                    if st.button(rotulo, key=f"comprar_{item}", width="stretch", disabled=not pode or saldo < preco):
                        try:
                            db_jogo.comprar(eu, item)
                            st.toast(f"{nome_item} é seu! Toque em Usar para vestir.", icon="🛍️")
                            st.rerun()
                        except jg.ErroJogo as erro:
                            st.error(str(erro))
        if categoria == "moldura" and not perfil.foto:
            st.caption("As molduras aparecem ao redor da foto do perfil. Coloque uma foto em Meu perfil.")

# --- Conquistas e extrato -------------------------------------------------------------------
col_c, col_e = st.columns(2)
with col_c:
    st.subheader("Conquistas")
    feitas = db_jogo.conquistas(eu)
    for chave, (nome_c, pontos, descricao) in jg.CONQUISTAS.items():
        st.markdown(f"{'🏆' if chave in feitas else '🔒'} **{nome_c}** (+{pontos}): {descricao}")
with col_e:
    st.subheader("Extrato")
    extrato = db_jogo.extrato(eu, 15)
    if not extrato:
        st.caption("Ainda sem pontos. Comece pelo check-in de hoje!")
    for lanc in extrato:
        cor = "var(--jade)" if lanc.delta > 0 else "var(--brasa)"
        st.markdown(f"<span style='color:{cor};font-weight:700'>{lanc.delta:+d}</span> {html.escape(lanc.motivo)} "
                    f"<span style='color:var(--suave);font-size:.85rem'>{lanc.criado_em:%d/%m %H:%M}</span>",
                    unsafe_allow_html=True)

# --- Pacotes de pontos pelo PIX --------------------------------------------------------------
st.subheader("Mais pontos pelo PIX")
if not pode:
    st.caption("Crie a sua conta para comprar pacotes.")
else:
    cfg = estado.config_loja()
    cols = st.columns(len(jg.PACOTES))
    for col, (pacote, (pontos, valor)) in zip(cols, jg.PACOTES.items(), strict=True):
        with col, st.container(border=True):
            st.markdown(f"### {pontos:,} pontos".replace(",", "."))
            st.markdown(f"**{brl(valor)}**".replace("$", "\\$"))
            if st.button("Quero este", key=f"pac_{pacote}", width="stretch"):
                st.session_state.pedido_pontos = db_jogo.pedir_pacote(eu, pacote).id
    pedido_id = st.session_state.get("pedido_pontos")
    pedido = next((p for p in db_jogo.pedidos(None, eu) if p.id == pedido_id), None)
    if pedido and pedido.status == "aguardando":
        codigo = pix.copia_e_cola(cfg["pix_chave"], cfg.get("pix_nome") or cfg["nome_loja"], cfg.get("pix_cidade", ""),
                                  pedido.valor, identificador=f"PONTOS{pedido.id}")
        q1, q2 = st.columns([1, 2])
        q1.image(pix.qr_png(codigo), width=200)
        with q2:
            st.markdown(f"**Pedido {pedido.id}: {pedido.pontos} pontos por {brl(pedido.valor)}**".replace("$", "\\$"))
            st.code(codigo, language=None, wrap_lines=True)
            if st.button("Já paguei", type="primary"):
                from chronotrade.contas import email_admin

                estado.avisar(email_admin(), "admin", f"Pontos pagos? Pedido {pedido.id}",
                              f"{perfil.apelido} ({eu}) diz que pagou {pedido.pontos} pontos por "
                              f"{brl(pedido.valor)}. Confirme em Painel do admin → Pontos.")
                st.success("Recebido! Assim que o pagamento for confirmado, os pontos entram na sua conta.")
    elif pedido and pedido.status == "pago":
        st.success(f"Pagamento confirmado: +{pedido.pontos} pontos.")
    tema.legenda("Compra de itens virtuais de personalização, sem valor monetário. Direito de arrependimento em 7 "
                 "dias enquanto os pontos não forem usados.")
