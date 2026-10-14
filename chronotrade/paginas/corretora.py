"""Corretora: carteira simulada para treinar e conexão com a corretora real (MetaTrader 5)."""

import pandas as pd
import streamlit as st

from chronotrade import estado, tema
from chronotrade.calculos import brl
from chronotrade.carteira import Posicao, pasta_dados
from chronotrade.corretoras import ErroCorretora, Ordem, abrir
from chronotrade.corretoras.mt5 import ordens_reais_permitidas
from chronotrade.mercado import normalizar_ticker, parece_fii, ticker_curto

st.title("Corretora")
estado.exigir("simulador")
c = estado.carteira()


def _boleta(chave: str, real: bool) -> Ordem | None:
    """Formulário de ordem. Devolve a ordem só depois da confirmação."""
    with st.form(f"boleta_{chave}"):
        col1, col2, col3, col4 = st.columns(4)
        ticker = col1.text_input("Ativo", placeholder="ITUB4")
        lado = col2.selectbox("Operação", ["compra", "venda"], format_func=str.capitalize)
        qtd = col3.number_input("Quantidade", min_value=1, step=1, value=100)
        tipo = col4.selectbox("Tipo", ["mercado", "limitada"], format_func=lambda t: "A mercado" if t == "mercado" else "Limitada")
        limite = st.number_input("Preço limite (só para ordem limitada)", min_value=0.0, step=0.01, format="%.2f")
        confirma = st.checkbox("Confirmo esta ordem" + (" com DINHEIRO REAL na minha corretora" if real else "")
                               + ". A decisão e o risco são meus.")
        if st.form_submit_button("Enviar ordem", type="primary"):
            if not ticker.strip():
                st.error("Informe o ativo.")
            elif not confirma:
                st.error("Marque a confirmação para enviar.")
            else:
                return Ordem(ticker, lado, int(qtd), tipo, limite or None)
    return None


simulada, real = st.tabs(["Carteira simulada", "Corretora real"])

# --- Simulada ---------------------------------------------------------------------------
with simulada:
    st.markdown("Treine compras e vendas com preços de mercado, sem dinheiro real. Ordens limitadas ficam "
                "pendentes e o agente Sentinela as executa quando o preço chega ao limite.")
    pasta = estado.pasta() or (pasta_dados() / "visitantes" / estado.email_avisos().split(":")[-1])
    sim = abrir("simulada", pasta, preco=lambda t: estado.ativo(t).preco)
    posicoes = sim.posicoes()
    valor = sum(p.quantidade * (estado.ativo(p.ticker).preco or p.preco_medio) for p in posicoes)
    col1, col2, col3 = st.columns(3)
    with col1:
        tema.janela("Saldo livre", brl(sim.saldo(), 0), "Dinheiro simulado", ouro=True)
    with col2:
        tema.janela("Em ativos", brl(valor, 0), f"{len(posicoes)} {'posição' if len(posicoes) == 1 else 'posições'}")
    with col3:
        tema.janela("Total", brl(sim.saldo() + valor, 0), "Começa com R$ 100.000")
    ordem = _boleta("sim", real=False)
    if ordem:
        try:
            r = sim.enviar(ordem)
            if r.situacao == "executada":
                texto = f"Ordem executada: {r.ordem.lado} de {r.ordem.quantidade} {ticker_curto(r.ordem.ticker)} a {brl(r.preco)}."
            elif r.situacao == "pendente":
                texto = f"Ordem limitada registrada. {r.mensagem}"
            else:
                texto = f"Ordem recusada: {r.mensagem}"
            st.session_state.resultado_ordem = (r.situacao != "recusada", texto.replace("$", "\\$"))
            st.rerun()  # atualiza saldo e posições acima
        except ErroCorretora as erro:
            st.error(str(erro))
    resultado = st.session_state.pop("resultado_ordem", None)
    if resultado:
        (st.success if resultado[0] else st.error)(resultado[1])
    if posicoes:
        st.dataframe(pd.DataFrame([{"Ativo": ticker_curto(p.ticker), "Cotas": int(p.quantidade),
                                    "Preço médio": brl(p.preco_medio),
                                    "Preço hoje": brl(estado.ativo(p.ticker).preco)} for p in posicoes]),
                     hide_index=True, width="stretch")
    ordens = sim.ordens()
    if ordens:
        st.markdown("**Ordens**")
        st.dataframe(pd.DataFrame([{"Quando": f"{o.ordem.criada_em:%d/%m %H:%M}", "Ativo": ticker_curto(o.ordem.ticker),
                                    "Operação": o.ordem.lado, "Cotas": o.ordem.quantidade,
                                    "Tipo": o.ordem.tipo, "Limite": brl(o.ordem.preco_limite) if o.ordem.preco_limite else "",
                                    "Situação": o.situacao, "Preço": brl(o.preco) if o.preco else "", "ID": o.id}
                                   for o in ordens]), hide_index=True, width="stretch")
        pendentes = [o.id for o in ordens if o.situacao == "pendente"]
        if pendentes:
            cancelar = st.selectbox("Cancelar ordem pendente", pendentes)
            if st.button("Cancelar ordem"):
                sim.cancelar(cancelar)
                st.rerun()
    with st.popover("Recomeçar a simulação"):
        if st.button("Zerar e voltar a R$ 100.000", type="primary"):
            sim.zerar()
            st.rerun()

# --- Real --------------------------------------------------------------------------------
with real:
    if estado.liberado("corretora"):
        tema.fala("Conecte a sua corretora pelo <b>MetaTrader 5</b> para trazer as posições reais para o "
                  "Inventário e, se você ligar, enviar ordens. Funciona com o app instalado no seu computador "
                  "Windows, com o terminal MT5 da corretora aberto e logado.")
        with st.expander("Dados de conexão (opcional, se o terminal já estiver logado deixe em branco)"):
            caminho = st.text_input("Caminho do terminal64.exe")
            login = st.text_input("Número da conta")
            servidor = st.text_input("Servidor da corretora")
            senha = st.text_input("Senha da conta", type="password", help="Usada só nesta conexão, não é guardada.")
        if st.button("Conectar ao MetaTrader 5", type="primary"):
            try:
                st.session_state.mt5_opcoes = {"caminho_terminal": caminho or None, "login": int(login) if login else None,
                                               "senha": senha or None, "servidor": servidor or None}
                abrir("mt5", None, **st.session_state.mt5_opcoes)
                st.session_state.mt5_ok = True
            except (ErroCorretora, ValueError) as erro:
                st.session_state.mt5_ok = False
                st.error(str(erro))
        if st.session_state.get("mt5_ok"):
            try:
                corretora = abrir("mt5", None, **st.session_state.mt5_opcoes)
                posicoes_reais = corretora.posicoes()
                st.success(f"Conectado. Saldo: {brl(corretora.saldo())}".replace("$", "\\$"))
                if posicoes_reais:
                    st.dataframe(pd.DataFrame([{"Ativo": p.ticker, "Quantidade": p.quantidade,
                                                "Preço médio": brl(p.preco_medio)} for p in posicoes_reais]),
                                 hide_index=True, width="stretch")
                    if st.button("Trazer estas posições para o Inventário"):
                        atuais = {p.ticker: p for p in c.posicoes}
                        for p in posicoes_reais:
                            t = normalizar_ticker(p.ticker)
                            atuais[t] = Posicao(t, p.quantidade, p.preco_medio, "FII" if parece_fii(t) else "Ação")
                        c.posicoes = list(atuais.values())
                        estado.salvar()
                        st.success("Inventário atualizado com as posições da corretora.")
                if ordens_reais_permitidas():
                    tema.aviso("Ordens com dinheiro real estão LIGADAS neste computador.")
                    ordem_real = _boleta("real", real=True)
                    if ordem_real:
                        r = corretora.enviar(ordem_real)
                        (st.success if r.situacao == "executada" else st.error)(f"{r.situacao}: {r.mensagem}")
                else:
                    st.caption("Envio de ordens reais desligado. Para ligar no seu computador, coloque "
                               "CHRONOTRADE_PERMITIR_ORDENS_REAIS=1 no arquivo .env.")
            except ErroCorretora as erro:
                st.error(str(erro))
        st.markdown("**Outras corretoras**: o app tem uma interface pronta (pasta `chronotrade/corretoras`) para "
                    "ligar novas corretoras quando elas oferecerem API. Enquanto isso, importe a sua carteira real "
                    "por planilha no Inventário.")
tema.aviso_legal()
